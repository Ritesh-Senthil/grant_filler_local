from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import get_session
from app.models import Organization
from app.services.org_profile_migrate import migrate_legacy_org_profile_to_facts
from app.services.llm_types import Embedder, LlmClient
from app.storage import StorageService


def get_settings(request: Request) -> Settings:
    """Effective settings: env base + user preference override for llm_provider (see preferences.py)."""
    base: Settings = request.app.state.settings
    p = request.app.state.effective_llm_provider
    return base.model_copy(update={"llm_provider": p})


def get_storage(request: Request) -> StorageService:
    return request.app.state.storage


def get_llm(request: Request) -> LlmClient:
    return request.app.state.llm


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder


SettingsDep = Annotated[Settings, Depends(get_settings)]
StorageDep = Annotated[StorageService, Depends(get_storage)]
LlmDep = Annotated[LlmClient, Depends(get_llm)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def ensure_default_org(session: AsyncSession) -> Organization:
    r = await session.execute(select(Organization).where(Organization.id == "default-org"))
    org = r.scalar_one_or_none()
    if org is None:
        org = Organization(id="default-org")
        session.add(org)
        await session.flush()
    await migrate_legacy_org_profile_to_facts(session, org)
    return org
