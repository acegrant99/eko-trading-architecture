"""FastAPI server — drives Eko's Evosystem autonomous loop."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import uvicorn

from eko_controller import EkoController

eko = EkoController()
_background_task = None


async def _background_auto():
    """Server-side Evosystem loop when autonomous is on."""
    sweeps = 0
    while True:
        try:
            if eko.autonomous:
                if sweeps % 3 == 0:
                    await eko.ecosystem_cycle()
                else:
                    syms = eko.evosystem
                    sym = syms[sweeps % len(syms)]
                    await eko.think_and_act(sym)
                sweeps += 1
                await asyncio.sleep(eko.auto_interval_sec)
            else:
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(8)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _background_task
    _background_task = asyncio.create_task(_background_auto())
    yield
    if _background_task:
        _background_task.cancel()
    await eko.close()


app = FastAPI(title="Eko Evosystem", lifespan=lifespan)


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
    return await eko.think_and_act(symbol)


@app.get("/api/ecosystem")
async def ecosystem():
    return await eko.ecosystem_cycle()


@app.get("/api/portfolio")
async def portfolio():
    if eko.mode == "paper":
        return eko.paper.status()
    return eko.live.status()


@app.get("/api/risk")
async def risk():
    return eko.risk.status()


@app.get("/api/conscience")
async def conscience():
    return eko.conscience.status()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await eko.think_and_act("BTC-USD")
            await ws.send_json(data)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    except Exception:
        await ws.close()


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
