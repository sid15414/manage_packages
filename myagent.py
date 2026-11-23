import uuid
from pydantic import BaseModel, Field
from typing import TypedDict, Literal, Optional

from trustcall import create_extractor

from datetime import datetime, date
from zoneinfo import ZoneInfo

# Absolute imports: Streamlit runs streamlit_app.py as a script (not as a package),
# so the old relative imports (from .models import ...) no longer work.
from models import model
from tools import getLiveLocation
from prompts import GET_DETAILS_SYSTEM_PROMPT, GET_ENTRY_INSTRUCTION, GET_QUERY_SYSTEM_PROMPT

from langgraph.prebuilt import ToolNode
from langgraph.graph import MessagesState, StateGraph, START, END

from langgraph.store.base import BaseStore
from langgraph.store.postgres import PostgresStore
from langgraph.checkpoint.postgres import PostgresSaver

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, RemoveMessage, ToolMessage




class UpdateOrders(TypedDict):
    """ Decision on what memory type to update """
    order_procecss: Literal['new', 'query', 'instructions']

class UserProfile(BaseModel):
    """Information about a user"""
    name: str | None = Field(description="name of the user", default=None)

class ShopingDetials(BaseModel):
    """Information about a user's shopping order."""
    user: str | None = Field(description="Name of the user", default=None)
    name: Optional[str] = Field(description="Item name")
    order_id: str|None = Field(description="Order Id of the order, unique for every order", default=None)
    source: str | None = Field(description="Item purchased from. website/shoping portal name", default=None)
    purchased_date: Optional[date] = Field(description="Item purchased on this date", default=None)
    expected_delivery_date: Optional[date] = Field(description="Item expected to arrive on this date")
    delivery_partner: Optional[str] =Field(description="company who is responisble for delivery")
    url: str | None = Field(description="a url which can be used to track the live location of order", default="dummay_url")


class ExtractedOrder(TypedDict):
    key: str
    order: ShopingDetials

class OverallState(MessagesState):
    order_details: list[ExtractedOrder]
    approval_status: bool = False

    


ShopingDetials_extractor = create_extractor(
    model,
    tools=[ShopingDetials],
    tool_choice="ShopingDetials",
    enable_inserts=True
)

def getShopingDetials(state: OverallState, config: RunnableConfig, store: BaseStore):
    print("==Node: getShopingDetials==")
    messages = state["messages"]
    user_name = config["configurable"]["user_name"]
    namespace = (user_name, "orders")
    memory = store.search(namespace)
    existing_memories = ([  (mem.key,"ShopingDetials",mem.value) 
        for mem in memory] 
        if memory 
        else None
     )
    current_time = datetime.now(
        ZoneInfo("Asia/Kolkata")
        ).strftime("%A, %d %B %Y, %H:%M")
    orderDetails = ShopingDetials_extractor.invoke({"messages": [SystemMessage(content=GET_DETAILS_SYSTEM_PROMPT.format(userDetails=user_name, time=current_time))]+messages[:-1],
                                                    "existing": existing_memories
                                                    })

    extracted_orders = []

    for r, rmeta in zip(
        orderDetails["responses"],
        orderDetails["response_metadata"]
    ):
        extracted_orders.append({
            "key": rmeta.get("json_doc_id", str(uuid.uuid4())),
            "order": r
        })
    print("====>",orderDetails["responses"])
    details = '\n'.join(
    f"""Product: {r.name}
Store: {r.source or "Not available"}
Order ID: {r.order_id or "Not available"}
Purchase Date: {r.purchased_date.strftime("%d %b %Y") if r.purchased_date else "Not available"}
Expected Delivery: {r.expected_delivery_date.strftime("%d %b %Y") if r.expected_delivery_date else "Not available"}
Delivery Partner: {r.delivery_partner or "Not available"}
Tracking URL: {r.url or "Not available"}"""
    for r in orderDetails["responses"]
)
    tool_calls = messages[-1].tool_calls
    return {"order_details": extracted_orders,
            "messages": [{
                            "role":"tool", 
                            "content": f"Details Extracted\n {details}",
                            "tool_call_id": tool_calls[0]["id"]
                        }]}

def store_memory(
    state: OverallState,
    config: RunnableConfig,
    store: BaseStore
):
    print("==Node: store_memory==")

    user_name = config["configurable"]["user_name"]
    namespace = (user_name, "orders")

    for item in state["order_details"]:

        store.put(
            namespace,
            item["key"],
            item["order"].model_dump(mode="json")
        )

    return {}



def queryOnOrders (state: OverallState, config: RunnableConfig, store: BaseStore):
        print("==Node: queryOnOrders==")

        messages = state["messages"]
        user_name = config["configurable"]["user_name"]
        namespace = (user_name, "orders")
        memory = store.search(namespace)
        today = date.today()
        order_lines = []
        for mem in memory:
            value = dict(mem.value)
            order_lines.append(f"- {value}")
        existing_memories = '\n'.join(order_lines)

        print("==queryOnOrders:TODAY (server):", today)
        # print("ORDERS SENT TO MODEL:\n", existing_memories)
        # entryNode's routing call (UpdateOrders) must be answered with a ToolMessage,
        # otherwise OpenAI rejects the request (400: tool_calls without tool responses).
        # Only do this on the first pass; when we come back here after the live-location
        # "tools" node, the last message is a different tool call/result.
        ack_messages = []
        last = messages[-1]
        if isinstance(last, AIMessage) and last.tool_calls and last.tool_calls[0]["name"] == "UpdateOrders":
            ack_messages = [
                ToolMessage(content="Routed to order query.", tool_call_id=tc["id"])
                for tc in last.tool_calls
            ]
        current_time = datetime.now(
                ZoneInfo("Asia/Kolkata")
            ).strftime("%A, %d %B %Y, %H:%M")
        all_messages = ([SystemMessage(content=GET_QUERY_SYSTEM_PROMPT.format(order_details=existing_memories,
                                                                            time=current_time))]
                                                                            +
                                                                        messages
                                                                            +
                                                                        ack_messages)

        response = model.bind_tools([getLiveLocation]).invoke(all_messages)
        print(response)
        return {"messages": ack_messages + [response]}

def entryNode(state: OverallState, config: RunnableConfig, store: BaseStore):

    messages = state["messages"]
    sys_message = SystemMessage(content=GET_ENTRY_INSTRUCTION)
    return {"messages": model.bind_tools([UpdateOrders]).invoke([sys_message]+messages)}

def human_feedback(state: OverallState, config: RunnableConfig, store: BaseStore):
    pass

def reject_order(state: OverallState):

    print("==Node: reject_order==")

    messages = state["messages"]

    # Remove all existing messages
    remove_messages = [
        RemoveMessage(id=message.id)
        for message in messages
        if message.id
    ]

    return {
        "messages": remove_messages,
        "pending_orders": [],
        "approval_status": None
    }


#Router
def whichNode(state:OverallState):
    message = state["messages"][-1]
    if len(message.tool_calls) ==0:
        print("====whichNode:ENDING CONVERTATION===")
        return END
    else:
        tool_call = message.tool_calls[0]
        print(f"====whichNode:tool_call['args']['order_procecss']: {tool_call['args']['order_procecss']} ===")
        if tool_call['args']['order_procecss'] == "new":
            return "getShopingDetials"
        elif tool_call['args']['order_procecss'] == "query":
            return "queryOnOrders"
        else:
            raise ValueError

def should_continue(state):
    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tools"

    return END

def approve_discard(state: OverallState):
    approval_status = state["approval_status"]
    if approval_status == True:
        return "store_memory"
    else:
        return "reject_order"



builder = StateGraph(OverallState)
builder.add_node(entryNode)
builder.add_node(getShopingDetials)
builder.add_node(queryOnOrders)
builder.add_node(human_feedback)
builder.add_node(store_memory)
builder.add_node(reject_order)
builder.add_node("tools", ToolNode([getLiveLocation]))

builder.add_edge(START, "entryNode")
builder.add_conditional_edges("entryNode", whichNode, [END, "getShopingDetials", "queryOnOrders"])
builder.add_conditional_edges("queryOnOrders", should_continue, [END, "tools"])
builder.add_edge("getShopingDetials", "human_feedback")
builder.add_conditional_edges("human_feedback", approve_discard, ["store_memory", "reject_order"])
builder.add_edge("store_memory", "entryNode")
builder.add_edge("reject_order", END)
builder.add_edge("tools", "queryOnOrders")


def build_graph(db_url: str):
    """
    Compile the graph against Postgres (Supabase).

    - PostgresStore  -> long-term memory (the saved orders, per user)
    - PostgresSaver  -> per-thread checkpoints (needed for the approval interrupt)

    Call this ONCE per process (streamlit_app.py wraps it in st.cache_resource),
    because it opens a connection pool.
    """
    pool = ConnectionPool(
        conninfo=db_url,
        min_size=1,
        max_size=5,
        open=True,
        # Reconnect transparently if Supabase dropped an idle connection
        check=ConnectionPool.check_connection,
        # Required by LangGraph's Postgres store/checkpointer
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )

    store = PostgresStore(pool)
    checkpointer = PostgresSaver(pool)

    # Creates the tables on first run; safe to call every time
    store.setup()
    checkpointer.setup()

    return builder.compile(
        checkpointer=checkpointer,
        store=store,
        interrupt_before=["human_feedback"],
    )