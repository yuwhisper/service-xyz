import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from server.config import PORT
from server.routers import auth, dashboard, apis, schedules, ozon, dingtalk, jst

app = FastAPI(title="Service XYZ", docs_url=None, redoc_url=None)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes (must be registered BEFORE static/fallback)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(apis.router)
app.include_router(schedules.router)
app.include_router(ozon.router)
app.include_router(dingtalk.router)
app.include_router(jst.router)

# Static files — serve entire client directory
CLIENT = Path(__file__).resolve().parent.parent / "client"
if CLIENT.exists():
    app.mount("/js", StaticFiles(directory=CLIENT / "js"), name="js")
    app.mount("/css", StaticFiles(directory=CLIENT / "css"), name="css")

    # Serve root-level static files (index.html, test.html, favicon, etc.)
    @app.get("/{filename:path}")
    async def serve_static(filename: str):
        file_path = CLIENT / filename
        headers = {"Cache-Control": "no-cache, no-store, must-revalidate"}
        # If the requested file exists, serve it
        if file_path.is_file():
            return FileResponse(file_path, headers=headers)
        # SPA fallback: serve index.html for any non-file route
        idx = CLIENT / "index.html"
        if idx.exists():
            return FileResponse(idx, headers=headers)
        return FileResponse(CLIENT / "index.html", headers=headers)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=PORT, reload=True)
