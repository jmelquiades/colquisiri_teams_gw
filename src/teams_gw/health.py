from __future__ import annotations
from fastapi import APIRouter
from .settings import settings
import msal, os

router = APIRouter()

@router.get("/__ready")
async def ready():
    return {"status": "ok"}

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/__env")
async def env_echo():
    # NO exponemos secretos; solo flags y valores no sensibles
    return {
        "MICROSOFT_APP_ID_set": bool(settings.MICROSOFT_APP_ID),
        "MICROSOFT_APP_PASSWORD_set": bool(bool(os.getenv("MICROSOFT_APP_PASSWORD"))),
        "MICROSOFT_APP_TENANT_ID_set": bool(settings.MICROSOFT_APP_TENANT_ID),
        "MICROSOFT_APP_OAUTH_SCOPE": settings.MICROSOFT_APP_OAUTH_SCOPE,
        "N2SQL_URL": settings.N2SQL_URL,
        "N2SQL_QUERY_PATH": settings.N2SQL_QUERY_PATH,
        "N2SQL_DATASET": getattr(settings, "N2SQL_DATASET", None),
        "APP_TZ": settings.APP_TZ,
    }

@router.get("/__auth-probe")
async def auth_probe():
    """
    Intenta obtener un token de app para https://api.botframework.com/.default
    Útil para confirmar AppId/Secret (y tenant si aplica).
    """
    tenant = settings.MICROSOFT_APP_TENANT_ID or "organizations"
    authority = f"https://login.microsoftonline.com/{tenant}"
    app = msal.ConfidentialClientApplication(
        client_id=settings.MICROSOFT_APP_ID,
        client_credential=os.getenv("MICROSOFT_APP_PASSWORD"),
        authority=authority,
    )
    result = app.acquire_token_for_client(scopes=["https://api.botframework.com/.default"])
    if "access_token" in result:
        return {"ok": True, "expires_in": result.get("expires_in")}
    return {"ok": False, "error": result.get("error"), "desc": result.get("error_description")}
