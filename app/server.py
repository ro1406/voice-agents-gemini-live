"""FastAPI app: serves the page and runs one agent per browser WebSocket."""

import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from app.agent import run_agent
from app.bridge import BrowserBridge
from app.config import ROOT
from app.store import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Saffron Palm receptionist")


@app.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    await ws.accept()
    bridge = BrowserBridge(ws)
    await bridge.send({"type": "bookings", "bookings": store.all("bookings")})
    try:
        await run_agent(bridge)
    except* WebSocketDisconnect:
        log.info("Browser disconnected")
    except* Exception as group:
        log.exception("Session ended with an error", exc_info=group)
        error = group.exceptions[0]
        try:
            await bridge.send({"type": "error", "message": f"{type(error).__name__}: {error}"})
            await ws.close()
        except Exception:
            pass  # The browser is already gone.


app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
