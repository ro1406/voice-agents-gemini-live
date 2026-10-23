"""Turn plain Python functions into Live API tools.

Decorate a function with @tool in any module listed in TOOL_MODULES. Its type hints
become the parameter schema and its docstring becomes the description.
"""

import importlib
import inspect
import logging
import re
import time
import types as pytypes
from collections.abc import Callable
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

from google.genai import types

log = logging.getLogger(__name__)

JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


class ToolError(Exception):
    """A problem the agent should explain to the guest, e.g. 'check-out is before check-in'."""


def tool(fn: Callable | None = None, *, blocking: bool = True) -> Callable:
    """Mark a function as a tool. Use @tool(blocking=False) to let the agent keep talking while it runs."""

    def mark(f: Callable) -> Callable:
        f.tool_blocking = blocking
        return f

    return mark(fn) if fn else mark


def json_schema(hint: Any) -> dict:
    """JSON schema for a type hint: str/int/float/bool, Literal[...] and X | None."""
    if get_origin(hint) is Literal:
        return {"type": JSON_TYPES[type(get_args(hint)[0])], "enum": list(get_args(hint))}
    if get_origin(hint) in (Union, pytypes.UnionType):
        return json_schema(next(a for a in get_args(hint) if a is not type(None)))
    return {"type": JSON_TYPES[hint]}


def parse_docstring(fn: Callable) -> tuple[str, dict[str, str]]:
    """Split a Google-style docstring into (summary, {arg: description})."""
    summary, _, args = inspect.getdoc(fn).partition("Args:")
    return summary.strip(), dict(re.findall(r"^\s*(\w+):\s*(.+)$", args, re.MULTILINE))


def declaration(fn: Callable) -> types.FunctionDeclaration:
    """Build a FunctionDeclaration from a function's signature and docstring."""
    summary, arg_docs = parse_docstring(fn)
    hints = get_type_hints(fn)
    params = inspect.signature(fn).parameters
    properties = {n: {**json_schema(hints[n]), "description": arg_docs.get(n, "")} for n in params}
    required = [n for n, p in params.items() if p.default is inspect.Parameter.empty]
    return types.FunctionDeclaration(
        name=fn.__name__,
        description=summary,
        parameters_json_schema={"type": "object", "properties": properties, "required": required},
        behavior=types.Behavior.BLOCKING if fn.tool_blocking else types.Behavior.NON_BLOCKING,
    )


class ToolRegistry:
    """Collects @tool functions from modules and runs the model's tool calls."""

    def __init__(self, modules: tuple[str, ...], on_event: Callable | None = None) -> None:
        self.tools = {
            name: fn
            for module in modules
            for name, fn in vars(importlib.import_module(module.strip())).items()
            if hasattr(fn, "tool_blocking")
        }
        self.declarations = [declaration(fn) for fn in self.tools.values()]
        self.on_event = on_event

    async def run(self, tool_call: types.LiveServerToolCall) -> list[types.FunctionResponse]:
        """Run every call in a tool_call and return responses ready for send_tool_response."""
        return [await self.call(fc) for fc in tool_call.function_calls]

    async def call(self, fc: types.FunctionCall) -> types.FunctionResponse:
        """Run one function call. Errors become {"error": ...} so the model can apologise."""
        await self.emit({"phase": "start", "id": fc.id, "name": fc.name, "args": fc.args})
        started = time.perf_counter()
        fn = self.tools.get(fc.name)
        try:
            if fn is None:
                raise ToolError(f"Unknown tool {fc.name}.")
            result = fn(**(fc.args or {}))
            result = await result if inspect.isawaitable(result) else result
            result = result if isinstance(result, dict) else {"result": result}
        except ToolError as e:
            result = {"error": str(e)}
        except Exception:
            log.exception("Tool %s crashed", fc.name)
            result = {"error": "Sorry, something went wrong on our side. Please try again."}
        ms = round((time.perf_counter() - started) * 1000)
        await self.emit({"phase": "end", "id": fc.id, "name": fc.name, "result": result, "ms": ms})
        return types.FunctionResponse(
            id=fc.id,
            name=fc.name,
            response=result,
            # Non-blocking results are announced once the agent finishes its current sentence.
            # (The docs also show "scheduling" inside `response`; the SDK has this typed field.)
            scheduling=None if fn is None or fn.tool_blocking else types.FunctionResponseScheduling.WHEN_IDLE,
        )

    async def emit(self, event: dict) -> None:
        if self.on_event:
            await self.on_event(event)
