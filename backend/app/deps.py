from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import get_session
from app.models import Organization
from app.services.ollama import OllamaClient
from app.storage import StorageService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> StorageService:
    return request.app.state.storage


def get_ollama(request: Request) -> OllamaClient:
    return request.app.state.ollama


SettingsDep = Annotated[Settings, Depends(get_settings)]
StorageDep = Annotated[StorageService, Depends(get_storage)]
OllamaDep = Annotated[OllamaClient, Depends(get_ollama)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def ensure_default_org(session: AsyncSession) -> Organization:
    r = await session.execute(select(Organization).where(Organization.id == "default-org"))
    org = r.scalar_one_or_none()
    if org is None:
        org = Organization(id="default-org")
        session.add(org)
        await session.flush()
    return org
