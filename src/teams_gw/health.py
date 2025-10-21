from __future__ import annotations
from fastapi import APIRouter

router = APIRouter()

@router.get("/__ready")
async def ready():
    return {"status": "ok"}

@router.get("/health")
async def health():
    return {"status": "ok"}
