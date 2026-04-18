"""Migrate legacy Organization profile columns into Fact rows, then clear those columns.

Older versions stored legal name, mission, etc. on Organization. All of that information
now lives in organization facts only (single editable surface)."""

from sqlalchemy import select

from app.models import Fact, Organization
from app.services.learn_org_facts import norm_fact_key


async def migrate_legacy_org_profile_to_facts(session, org: Organization) -> None:
    legal = (org.legal_name or "").strip()
    ms = (org.mission_short or "").strip()
    ml = (org.mission_long or "").strip()
    addr = (org.address or "").strip()
    extras = org.extra_sections or []
    has_section_body = False
    if isinstance(extras, list):
        for s in extras:
            if isinstance(s, dict) and (str(s.get("content") or "").strip()):
                has_section_body = True
                break
    if not any([legal, ms, ml, addr, has_section_body]):
        return

    r = await session.execute(select(Fact).where(Fact.org_id == org.id))
    existing = list(r.scalars().all())
    taken = {norm_fact_key(f.key or "") for f in existing}

    def add_fact(key: str, value: str, source: str) -> None:
        nonlocal taken
        nk = norm_fact_key(key)
        if nk in taken:
            return
        session.add(Fact(org_id=org.id, key=key, value=value, source=source))
        taken.add(nk)

    if legal:
        add_fact("Legal name", legal, "migrated from organization profile")
    if ms:
        add_fact("Mission (short)", ms, "migrated from organization profile")
    if ml:
        add_fact("Mission (long)", ml, "migrated from organization profile")
    if addr:
        add_fact("Address", addr, "migrated from organization profile")

    if isinstance(extras, list):
        for s in extras:
            if not isinstance(s, dict):
                continue
            title = (str(s.get("title") or "").strip() or "Additional section")[:200]
            content = str(s.get("content") or "").strip()
            if not content:
                continue
            sid = str(s.get("id") or "").strip()[:24]
            base = f"{title} [{sid}]" if sid else title
            key = base
            n = 0
            while norm_fact_key(key) in taken:
                n += 1
                key = f"{base} ({n})"
            add_fact(key, content, "migrated from organization profile")

    org.legal_name = ""
    org.mission_short = ""
    org.mission_long = ""
    org.address = ""
    org.extra_sections = []
    await session.flush()
