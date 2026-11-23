import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool


@tool
def getLiveLocation(url: str) -> dict:
    """
    Get the latest order tracking status and location from a tracking URL.

    Use this tool when the user asks for the current delivery status,
    current package location, latest tracking information, or whether
    an order is currently out for delivery/delivered.
    """

    try:
        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/140.0 Safari/537.36"
                )
            },
        )

        response.raise_for_status()

        # -------------------------
        # JSON response
        # -------------------------
        content_type = response.headers.get("content-type", "").lower()

        if "application/json" in content_type:
            data = response.json()

            return {
                "success": True,
                "source_url": url,
                "status": data.get("status"),
                "location": data.get("location"),
                "estimated_delivery": data.get("estimated_delivery"),
                "last_updated": data.get("updated_at"),
                "tracking_events": data.get("events", []),
            }

        # -------------------------
        # HTML response
        # -------------------------
        soup = BeautifulSoup(response.text, "html.parser")

        # These selectors will need to be customized for each
        # tracking website.
        status_element = (
            soup.select_one(".tracking-status")
            or soup.select_one(".status")
            or soup.select_one("[data-status]")
        )

        location_element = (
            soup.select_one(".tracking-location")
            or soup.select_one(".location")
            or soup.select_one("[data-location]")
        )

        status = (
            status_element.get_text(" ", strip=True)
            if status_element
            else None
        )

        location = (
            location_element.get_text(" ", strip=True)
            if location_element
            else None
        )

        return {
            "success": True,
            "source_url": url,
            "status": status,
            "location": location,
            "estimated_delivery": None,
            "last_updated": None,
            "tracking_events": [],
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "source_url": url,
            "error": "Tracking website timed out.",
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "source_url": url,
            "error": f"Could not access tracking website: {str(e)}",
        }

    except Exception as e:
        return {
            "success": False,
            "source_url": url,
            "error": f"Failed to read tracking information: {str(e)}",
        }