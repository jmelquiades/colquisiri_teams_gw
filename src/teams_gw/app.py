from __future__ import annotations
import os, logging
from fastapi import FastAPI, Request
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    BotFrameworkAdapter,
    ConversationState,
    MemoryStorage,
    TurnContext,
)
from botbuilder.schema import Activity
from .settings import settings
from .bot import TeamsGatewayBot
from .health import router as health_router

# Exporta los nombres que la SDK también busca
os.environ.setdefault("MicrosoftAppId", settings.MICROSOFT_APP_ID)
os.environ.setdefault("MicrosoftAppPassword", os.getenv("MICROSOFT_APP_PASSWORD", ""))
if settings.MICROSOFT_APP_TENANT_ID:
    os.environ.setdefault("MicrosoftAppTenantId", settings.MICROSOFT_APP_TENANT_ID)

app = FastAPI(title="teams_gw")
app.include_router(health_router)

adapter = BotFrameworkAdapter(
    BotFrameworkAdapterSettings(settings.MICROSOFT_APP_ID, os.getenv("MICROSOFT_APP_PASSWORD", ""))
)

conversation_state = ConversationState(MemoryStorage())
bot = TeamsGatewayBot()

@app.post("/api/messages")
async def messages(request: Request):
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    await adapter.process_activity(activity, auth_header, aux_logic)
    return {"ok": True}

@app.get("/")
async def root():
    return {"service": app.title, "ready": True}
