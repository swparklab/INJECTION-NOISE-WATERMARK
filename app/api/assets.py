"""Asset download endpoint — serve watermarked / processed outputs to the UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config.settings import get_settings

router = APIRouter(tags=["assets"])


@router.get("/assets/{name}")
async def download_asset(name: str) -> FileResponse:
    """Download a generated asset (watermarked or processed output) by file name.

    Only plain file names within the assets directory are allowed (no path
    traversal).
    """
    safe = Path(name).name  # strip any directory components
    if safe != name:
        raise HTTPException(status_code=400, detail="invalid asset name")

    path = Path(get_settings().data_dir) / "assets" / safe
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="asset not found")

    return FileResponse(str(path), filename=safe)
