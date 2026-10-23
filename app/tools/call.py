"""Call-control tools any agent can reuse. The browser hangs up when end_call finishes."""

from app.tools.registry import tool


@tool
def end_call() -> dict:
    """Hang up. Only call this after the guest says goodbye or needs nothing else, and after you have said goodbye."""
    return {"status": "Call ended."}
