from typing import Literal

from google.genai import types

from app.tools.registry import ToolError, ToolRegistry, declaration, tool


@tool
def book_table(name: str, people: int, area: Literal["indoor", "terrace"], note: str | None = None) -> dict:
    """Book a restaurant table.

    Args:
        name: Guest name.
        people: Party size.
        area: Where to sit.
        note: Anything special.
    """
    if people > 8:
        raise ToolError("We seat at most 8 people.")
    return {"ok": True, "name": name}


@tool(blocking=False)
async def slow_lookup(query: str) -> str:
    """Look something up slowly.

    Args:
        query: What to look up.
    """
    return f"found {query}"


@tool
def broken() -> dict:
    """Always crashes."""
    raise RuntimeError("database exploded")


def registry(events: list | None = None) -> ToolRegistry:
    async def record(event: dict) -> None:
        events.append(event)

    return ToolRegistry(("tests.test_registry",), on_event=record if events is not None else None)


def call(tool_name: str, /, **args) -> types.LiveServerToolCall:
    return types.LiveServerToolCall(function_calls=[types.FunctionCall(id="c1", name=tool_name, args=args)])


def test_schema_from_hints_and_docstring():
    d = declaration(book_table)
    assert d.name == "book_table"
    assert d.description == "Book a restaurant table."
    assert d.behavior == types.Behavior.BLOCKING
    assert d.parameters_json_schema == {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Guest name."},
            "people": {"type": "integer", "description": "Party size."},
            "area": {"type": "string", "enum": ["indoor", "terrace"], "description": "Where to sit."},
            "note": {"type": "string", "description": "Anything special."},
        },
        "required": ["name", "people", "area"],
    }


def test_non_blocking_tool():
    assert declaration(slow_lookup).behavior == types.Behavior.NON_BLOCKING


def test_collects_only_decorated_functions():
    assert set(registry().tools) == {"book_table", "slow_lookup", "broken"}


async def test_run_returns_response_and_events():
    events = []
    [response] = await registry(events).run(call("book_table", name="Sara", people=2, area="terrace"))
    assert (response.id, response.name, response.response) == ("c1", "book_table", {"ok": True, "name": "Sara"})
    assert response.scheduling is None
    assert [e["phase"] for e in events] == ["start", "end"]
    assert events[1]["ms"] >= 0


async def test_async_non_blocking_result_is_wrapped_and_scheduled():
    [response] = await registry().run(call("slow_lookup", query="pool"))
    assert response.response == {"result": "found pool"}
    assert response.scheduling == types.FunctionResponseScheduling.WHEN_IDLE


async def test_tool_error_becomes_spoken_error():
    [response] = await registry().run(call("book_table", name="Sara", people=12, area="indoor"))
    assert response.response == {"error": "We seat at most 8 people."}


async def test_crash_and_unknown_tool_become_generic_errors():
    [crash] = await registry().run(call("broken"))
    assert "something went wrong" in crash.response["error"]
    [unknown] = await registry().run(call("nope"))
    assert unknown.response == {"error": "Unknown tool nope."}
