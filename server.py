"""FastAPI server that serves the UI and exposes Eko + architecture APIs."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # load .env if present

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import uvicorn
import asyncio

from eko_controller import EkoController

eko = EkoController()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await eko.close()


app = FastAPI(title="Eko Trading Architecture", lifespan=lifespan)


@app.get("/")
def root():
    return FileResponse("ui/3d-architecture.html")


@app.get("/api/status")
async def status():
    return await eko._status()


@app.get("/api/eko/status")
async def eko_status():
    return await eko._status()


@app.post("/api/eko/command")
async def eko_command(payload: dict):
    text = payload.get("text") or payload.get("command") or ""
    return await eko.handle_command(text)


@app.get("/api/tick")
async def tick(symbol: str = "BTC-USD"):
    return await eko.tick(symbol)


@app.get("/api/portfolio")
async def portfolio():
    if eko.mode == "paper":
        return eko.paper.status()
    return eko.live.status()


@app.get("/api/risk")
async def risk():
    return eko.risk.status()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await eko.tick("BTC-USD")
            await ws.send_json(data)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    except Exception:
        await ws.close()


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
