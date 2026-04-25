"""STUB — Person E owns. FastAPI app + WebSocket bus.

Routes:
  GET  /api/engines           list all engines
  GET  /api/generations       list all generations
  GET  /api/games?gen=N       games in a generation
  POST /api/generations/run   trigger a new generation
  WS   /ws                    live event stream
"""

from fastapi import FastAPI

app = FastAPI(title="Cubist")


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True}
