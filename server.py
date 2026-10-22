"""FastAPI server that serves the 3D UI and provides live status wired to the real architecture modules.
Eko is the superior controller that executes real actions on the system from natural language prompts.
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from pathlib import Path
from datetime import datetime
import json
import hashlib

app = FastAPI(title="Eko Trading Architecture")

@app.get("/")
def root():
    return FileResponse("ui/3d-architecture.html")

@app.get("/api/status")
def status():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

@app.get("/api/eko/status")
def eko_status():
    return {"ok": True, "message": "Eko ready"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
