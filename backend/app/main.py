"""FastAPI app: /api, /media (outputs/) and the built frontend."""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.routes import router
from .config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

settings = get_settings()  # also forces the offline env flags (H2)
settings.outputs_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="CodeStorm24", version=__version__)
app.include_router(router)
app.mount("/media", StaticFiles(directory=settings.outputs_dir), name="media")

_dist = settings.frontend_dist
if (_dist / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str) -> FileResponse:
    """Serve the built frontend (SPA fallback). In dev, Vite serves it on :5173."""
    if full_path.startswith(("api/", "media/")):
        raise HTTPException(404)
    index = _dist / "index.html"
    if not index.is_file():
        raise HTTPException(404, "frontend not built; run `npm --prefix frontend run build` or use :5173")
    candidate = (_dist / full_path).resolve()
    if full_path and candidate.is_file() and _dist.resolve() in candidate.parents:
        return FileResponse(candidate)
    return FileResponse(index)
