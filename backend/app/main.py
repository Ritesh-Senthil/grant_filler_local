import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Literal

import httpx
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import and_, delete, or_, select, update

from app.download_filename import (
    build_export_download_filename,
    content_disposition_attachment,
    default_export_stem_from_key,
    sanitize_content_disposition_filename,
)
from app.config import Settings
from app.database import create_tables, init_engine
from app.database import get_session_factory
from app.deps import EmbedderDep, LlmDep, SessionDep, SettingsDep, StorageDep, ensure_default_org, get_settings
from app.job_runner import run_generate_job, run_learn_org_job, run_parse_job
from app.models import Answer, Fact, Grant, Job, Organization, Question
from app.schemas import (
    AnswerPatch,
    AnswerRead,
    ConfigRead,
    LlmPreferenceUpdate,
    DeveloperCreditsRead,
    EnhancementSubmit,
    ExportRequest,
    FactCreate,
    FactRead,
    FactUpdate,
    GenerateRequest,
    DuplicateGrantRequest,
    GrantCreate,
    GrantRead,
    GrantSummary,
    GrantUpdate,
    JobRead,
    OrganizationRead,
    OrganizationUpdate,
    ParseRequest,
    PreviewUrlRequest,
    QuestionRead,
    QuestionReorderRequest,
    UserPreferencesPatch,
    UserPreferencesRead,
)
from app.services.answer_coerce import coerce_answer_value
from app.services.evidence_ids import normalize_evidence_fact_ids
from app.services.answers import answer_value_is_effectively_empty
from app.services.export import build_qa_docx, build_qa_markdown, build_qa_pdf
from app.services.learn_org_facts import has_any_nonempty_answer
from app.services.web_fetch import WebFetchError, preview_web_fetch
from app.preferences import (
    clear_llm_provider_override,
    load_llm_provider_override,
    load_locale_override,
    save_llm_provider_override,
    save_locale_override,
    user_llm_override_exists,
)
from app.services.inference_factory import build_llm_and_embedder
from app.storage import StorageService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    init_engine(settings)
    await create_tables()
    sf = get_session_factory()
    async with sf() as session:
        await ensure_default_org(session)
        await session.commit()
    app.state.settings = settings
    app.state.storage = StorageService(settings)
    override = load_llm_provider_override(settings.data_dir)
    if override is not None:
        app.state.effective_llm_provider = override
    else:
        app.state.effective_llm_provider = settings.llm_provider
    eff = settings.model_copy(update={"llm_provider": app.state.effective_llm_provider})
    try:
        llm, embedder = build_llm_and_embedder(eff)
    except ValueError as e:
        logger.warning("LLM init failed (%s); retrying with env default provider.", e)
        app.state.effective_llm_provider = settings.llm_provider
        eff = settings
        llm, embedder = build_llm_and_embedder(eff)
    app.state.llm = llm
    app.state.embedder = embedder
    app.state.session_factory = sf
    yield


app = FastAPI(title="GrantFiller API", version="0.1.0", lifespan=lifespan)


def _cors_origins(settings: Settings) -> list[str]:
    return [o.strip() for o in settings.cors_origins.split(",") if o.strip()]


def setup_cors(settings: Settings):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


setup_cors(Settings())


def _job_read(j: Job) -> JobRead:
    return JobRead(
        id=j.id,
        grant_id=j.grant_id,
        job_kind=j.job_kind,
        status=j.status,
        progress=j.progress,
        error=j.error,
        result_json=j.result_json,
        created_at=j.created_at,
    )


def _grant_web_url(g: Grant) -> str:
    """Application page URL: primary field, then optional portal link."""
    return (g.grant_url or "").strip() or (g.portal_url or "").strip()


def _truncate_question_preview(text: str, max_len: int = 160) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


async def fact_reads_with_provenance(session, facts: list[Fact]) -> list[FactRead]:
    """Build FactRead rows with grant name and question preview for list/detail APIs."""
    grant_ids = {f.learned_from_grant_id for f in facts if f.learned_from_grant_id}
    grants_by_id: dict[str, Grant] = {}
    if grant_ids:
        rg = await session.execute(select(Grant).where(Grant.id.in_(grant_ids)))
        grants_by_id = {g.id: g for g in rg.scalars().all()}

    pair_keys: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for f in facts:
        gid = f.learned_from_grant_id
        qid = (f.learned_from_question_id or "").strip()
        if gid and qid:
            key = (gid, qid)
            if key not in seen_pairs:
                seen_pairs.add(key)
                pair_keys.append(key)

    preview_by_pair: dict[tuple[str, str], str] = {}
    if pair_keys:
        conds = [and_(Question.grant_id == gid, Question.question_id == qid) for gid, qid in pair_keys]
        rq = await session.execute(select(Question).where(or_(*conds)))
        for q in rq.scalars().all():
            preview_by_pair[(q.grant_id, q.question_id)] = _truncate_question_preview(q.question_text or "")

    out: list[FactRead] = []
    for f in facts:
        gn: str | None = None
        qp: str | None = None
        if f.learned_from_grant_id and f.learned_from_grant_id in grants_by_id:
            gn = (grants_by_id[f.learned_from_grant_id].name or "").strip() or None
        qid = (f.learned_from_question_id or "").strip()
        if f.learned_from_grant_id and qid:
            qp = preview_by_pair.get((f.learned_from_grant_id, qid)) or None
        out.append(
            FactRead(
                id=f.id,
                org_id=f.org_id,
                key=f.key,
                value=f.value,
                source=f.source,
                learned_from_grant_id=f.learned_from_grant_id,
                learned_from_question_id=f.learned_from_question_id or None,
                learned_from_grant_name=gn,
                learned_from_question_preview=qp,
                updated_at=f.updated_at,
            )
        )
    return out


def _grant_read(g: Grant) -> GrantRead:
    qs = [QuestionRead.from_model(q) for q in (g.questions or [])]
    ans = [AnswerRead.from_model(a) for a in (g.answers or [])]
    raw_chunks = g.source_chunks_json
    nchunks = len(raw_chunks) if isinstance(raw_chunks, list) else 0
    return GrantRead(
        id=g.id,
        name=g.name,
        grant_url=g.grant_url,
        portal_url=g.portal_url,
        source_type=g.source_type,
        status=g.status,
        source_file_key=g.source_file_key,
        file_name=g.file_name,
        export_file_key=g.export_file_key,
        source_chunk_count=nchunks,
        created_at=g.created_at,
        updated_at=g.updated_at,
        questions=qs,
        answers=ans,
    )


@app.get("/api/v1/health")
async def health():
    return {"ok": True}


async def _config_read(settings: Settings) -> ConfigRead:
    ok = False
    if settings.llm_provider == "gemini":
        ok = bool(settings.google_api_key and settings.google_api_key.strip())
    else:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
                ok = r.status_code == 200
        except Exception:
            ok = False
    chat_model = settings.gemini_chat_model if settings.llm_provider == "gemini" else settings.ollama_model
    embed_model = settings.gemini_embed_model if settings.llm_provider == "gemini" else settings.ollama_embed_model
    src: Literal["env", "user"] = "user" if user_llm_override_exists(settings.data_dir) else "env"
    return ConfigRead(
        llm_provider=settings.llm_provider,
        llm_provider_source=src,
        llm_configured=ok,
        chat_model=chat_model,
        embed_model=embed_model,
        data_dir=str(settings.data_dir.resolve()),
    )


@app.get("/api/v1/config", response_model=ConfigRead)
async def config(settings: SettingsDep):
    return await _config_read(settings)


@app.patch("/api/v1/llm", response_model=ConfigRead)
async def patch_llm_preference(body: LlmPreferenceUpdate, request: Request):
    """Switch between Ollama (local) and Gemini (API key). Persists under DATA_DIR/app_preferences.json."""
    base: Settings = request.app.state.settings
    save_llm_provider_override(base.data_dir, body.llm_provider)
    request.app.state.effective_llm_provider = body.llm_provider
    eff = base.model_copy(update={"llm_provider": body.llm_provider})
    try:
        request.app.state.llm, request.app.state.embedder = build_llm_and_embedder(eff)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return await _config_read(get_settings(request))


@app.delete("/api/v1/llm", response_model=ConfigRead)
async def delete_llm_preference(request: Request):
    """Clear saved provider; use LLM_PROVIDER from .env again."""
    base: Settings = request.app.state.settings
    clear_llm_provider_override(base.data_dir)
    request.app.state.effective_llm_provider = base.llm_provider
    eff = base
    try:
        request.app.state.llm, request.app.state.embedder = build_llm_and_embedder(eff)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return await _config_read(get_settings(request))


def _banner_ext_from_upload(content_type: str | None, filename: str | None) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    by_mime = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    if ct in by_mime:
        return by_mime[ct]
    n = (filename or "").lower()
    for suf in (".jpg", ".jpeg"):
        if n.endswith(suf):
            return "jpg"
    for suf, ext in ((".png", "png"), (".webp", "webp"), (".gif", "gif")):
        if n.endswith(suf):
            return ext
    raise HTTPException(415, "Upload a JPEG, PNG, WebP, or GIF image")


def _org_model_to_read(org: Organization) -> OrganizationRead:
    bk = org.banner_file_key
    if isinstance(bk, str) and not bk.strip():
        bk = None
    return OrganizationRead(
        id=org.id,
        header_display_name=(org.header_display_name or "").strip(),
        banner_file_key=bk,
    )


@app.get("/api/v1/org", response_model=OrganizationRead)
async def get_org(session: SessionDep):
    org = await ensure_default_org(session)
    return _org_model_to_read(org)


@app.put("/api/v1/org", response_model=OrganizationRead)
async def put_org(body: OrganizationUpdate, session: SessionDep, storage: StorageDep):
    org = await ensure_default_org(session)
    if body.header_display_name is not None:
        org.header_display_name = body.header_display_name
    if body.clear_banner is True:
        if org.banner_file_key:
            storage.delete(org.banner_file_key)
        org.banner_file_key = None
    await session.flush()
    org = await ensure_default_org(session)
    return _org_model_to_read(org)


@app.post("/api/v1/org/banner", response_model=OrganizationRead)
async def upload_org_banner(
    session: SessionDep,
    storage: StorageDep,
    settings: SettingsDep,
    file: UploadFile = File(...),
):
    org = await ensure_default_org(session)
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty image")
    max_b = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_b:
        raise HTTPException(413, f"Image too large (max {settings.max_upload_mb} MB)")
    ext = _banner_ext_from_upload(file.content_type, file.filename)
    try:
        key = StorageService.org_banner_key(org.id, ext)
    except ValueError as e:
        raise HTTPException(415, str(e)) from e
    old = org.banner_file_key
    storage.write_bytes(key, data)
    org.banner_file_key = key
    if old and old != key:
        storage.delete(old)
    await session.flush()
    return _org_model_to_read(org)


@app.delete("/api/v1/org/banner", response_model=OrganizationRead)
async def delete_org_banner(session: SessionDep, storage: StorageDep):
    org = await ensure_default_org(session)
    if org.banner_file_key:
        storage.delete(org.banner_file_key)
    org.banner_file_key = None
    await session.flush()
    return _org_model_to_read(org)


@app.get("/api/v1/app/developer-credits", response_model=DeveloperCreditsRead)
async def developer_credits(request: Request):
    s: Settings = request.app.state.settings
    return DeveloperCreditsRead(
        display_name=s.grantfiller_dev_display_name or "",
        github_url=s.grantfiller_dev_github_url or "",
        linkedin_url=s.grantfiller_dev_linkedin_url or "",
        sponsor_text=s.grantfiller_dev_sponsor_text or "",
        sponsor_url=s.grantfiller_dev_sponsor_url or "",
    )


@app.get("/api/v1/preferences", response_model=UserPreferencesRead)
async def get_user_preferences(settings: SettingsDep):
    loc = load_locale_override(settings.data_dir)
    return UserPreferencesRead(locale=loc if loc is not None else "iso")


@app.patch("/api/v1/preferences", response_model=UserPreferencesRead)
async def patch_user_preferences(body: UserPreferencesPatch, settings: SettingsDep):
    if body.locale is not None:
        try:
            save_locale_override(settings.data_dir, body.locale)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    return await get_user_preferences(settings)


@app.post("/api/v1/enhancements")
async def submit_enhancement(body: EnhancementSubmit, settings: SettingsDep):
    """Stub until outbound email exists (roadmap M): append one JSON line to a file under DATA_DIR."""
    path = settings.data_dir / "enhancement_requests.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    line = json.dumps({"ts": ts, "message": body.message}, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
    return {"ok": True}


@app.get("/api/v1/org/facts", response_model=list[FactRead])
async def list_facts(session: SessionDep):
    org = await ensure_default_org(session)
    r = await session.execute(select(Fact).where(Fact.org_id == org.id).order_by(Fact.updated_at.desc()))
    rows = list(r.scalars().all())
    return await fact_reads_with_provenance(session, rows)


@app.post("/api/v1/org/facts", response_model=FactRead)
async def create_fact(body: FactCreate, session: SessionDep):
    org = await ensure_default_org(session)
    f = Fact(org_id=org.id, key=body.key, value=body.value, source=body.source)
    session.add(f)
    await session.flush()
    reads = await fact_reads_with_provenance(session, [f])
    return reads[0]


@app.put("/api/v1/org/facts/{fact_id}", response_model=FactRead)
async def update_fact(fact_id: str, body: FactUpdate, session: SessionDep):
    f = await session.get(Fact, fact_id)
    if not f:
        raise HTTPException(404, "Fact not found")
    if body.key is not None:
        f.key = body.key
    if body.value is not None:
        f.value = body.value
    if body.source is not None:
        f.source = body.source
    await session.flush()
    reads = await fact_reads_with_provenance(session, [f])
    return reads[0]


@app.delete("/api/v1/org/facts/{fact_id}")
async def delete_fact(fact_id: str, session: SessionDep):
    f = await session.get(Fact, fact_id)
    if not f:
        raise HTTPException(404, "Fact not found")
    await session.delete(f)
    return {"ok": True}


@app.get("/api/v1/grants", response_model=list[GrantSummary])
async def list_grants(session: SessionDep):
    r = await session.execute(select(Grant).order_by(Grant.created_at.desc()))
    rows = r.scalars().all()
    return [
        GrantSummary(
            id=g.id,
            name=g.name,
            status=g.status,
            source_type=g.source_type,
            created_at=g.created_at,
            updated_at=g.updated_at,
        )
        for g in rows
    ]


@app.post("/api/v1/grants", response_model=GrantRead)
async def create_grant(body: GrantCreate, session: SessionDep):
    g = Grant(
        name=body.name,
        grant_url=body.grant_url,
        portal_url=body.portal_url,
        source_type=body.source_type,
        status="draft",
    )
    session.add(g)
    await session.flush()
    await session.refresh(g, ["questions", "answers"])
    return _grant_read(g)


@app.post("/api/v1/grants/{grant_id}/duplicate", response_model=GrantRead)
async def duplicate_grant(
    grant_id: str,
    body: DuplicateGrantRequest,
    session: SessionDep,
    storage: StorageDep,
):
    """Fork a grant: copies file and indexed source text; optionally copies questions and answers."""
    src = await session.get(Grant, grant_id)
    if not src:
        raise HTTPException(404, "Grant not found")
    name = (body.name or "").strip() or f"{src.name} (copy)"
    g = Grant(
        name=name,
        grant_url=src.grant_url,
        portal_url=src.portal_url,
        source_type=src.source_type,
        status=src.status if body.include_qa else "draft",
        source_file_key=None,
        file_name=src.file_name,
        export_file_key=None,
        source_chunks_json=list(src.source_chunks_json) if src.source_chunks_json else None,
    )
    session.add(g)
    await session.flush()

    if src.source_file_key and storage.exists(src.source_file_key):
        data = storage.read_bytes(src.source_file_key)
        fname = src.file_name or "source.pdf"
        nk = StorageService.grant_source_key(g.id, fname)
        storage.write_bytes(nk, data)
        g.source_file_key = nk

    if body.include_qa:
        rq = await session.execute(
            select(Question).where(Question.grant_id == grant_id).order_by(Question.sort_order)
        )
        for q in rq.scalars().all():
            session.add(
                Question(
                    grant_id=g.id,
                    question_id=q.question_id,
                    question_text=q.question_text,
                    q_type=q.q_type,
                    options=list(q.options or []),
                    required=q.required,
                    char_limit=q.char_limit,
                    sort_order=q.sort_order,
                )
            )
        ra = await session.execute(select(Answer).where(Answer.grant_id == grant_id))
        for a in ra.scalars().all():
            session.add(
                Answer(
                    grant_id=g.id,
                    question_id=a.question_id,
                    answer_value=a.answer_value,
                    reviewed=a.reviewed,
                    needs_manual_input=a.needs_manual_input,
                    evidence_fact_ids=normalize_evidence_fact_ids(a.evidence_fact_ids),
                )
            )

    await session.flush()
    await session.refresh(g, ["questions", "answers"])
    return _grant_read(g)


@app.get("/api/v1/grants/{grant_id}", response_model=GrantRead)
async def get_grant(grant_id: str, session: SessionDep):
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    await session.refresh(g, ["questions", "answers"])
    return _grant_read(g)


@app.put("/api/v1/grants/{grant_id}", response_model=GrantRead)
async def update_grant(grant_id: str, body: GrantUpdate, session: SessionDep):
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    if body.name is not None:
        g.name = body.name
    if body.grant_url is not None:
        g.grant_url = body.grant_url
    if body.portal_url is not None:
        g.portal_url = body.portal_url
    if body.status is not None:
        g.status = body.status
    g.updated_at = datetime.utcnow()
    await session.flush()
    await session.refresh(g, ["questions", "answers"])
    return _grant_read(g)


@app.delete("/api/v1/grants/{grant_id}")
async def delete_grant(grant_id: str, session: SessionDep, storage: StorageDep):
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    await session.execute(
        update(Fact).where(Fact.learned_from_grant_id == grant_id).values(learned_from_grant_id=None)
    )
    if g.source_file_key:
        storage.delete(g.source_file_key)
    if g.export_file_key:
        storage.delete(g.export_file_key)
    await session.execute(delete(Job).where(Job.grant_id == grant_id))
    await session.delete(g)
    return {"ok": True}


@app.post("/api/v1/grants/{grant_id}/files")
async def upload_file(
    grant_id: str,
    session: SessionDep,
    storage: StorageDep,
    settings: SettingsDep,
    file: UploadFile = File(...),
):
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    data = await file.read()
    max_b = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_b:
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB)")
    name = file.filename or "upload.bin"
    key = StorageService.grant_source_key(grant_id, name)
    storage.write_bytes(key, data)
    g.source_file_key = key
    g.file_name = name
    g.source_chunks_json = None
    low = name.lower()
    if low.endswith(".docx"):
        g.source_type = "docx"
    elif low.endswith(".pdf"):
        g.source_type = "pdf"
    g.updated_at = datetime.utcnow()
    await session.flush()
    return {"file_key": key, "file_name": name, "mime_type": file.content_type or "application/octet-stream"}


@app.post("/api/v1/grants/{grant_id}/parse", status_code=202)
async def parse_grant(
    grant_id: str,
    body: ParseRequest,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    storage: StorageDep,
    settings: SettingsDep,
    llm: LlmDep,
):
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    file_key: str | None
    parse_from_web = body.use_url
    override = (body.url or "").strip() or None
    if parse_from_web:
        target = override or _grant_web_url(g)
        if not target:
            raise HTTPException(
                400,
                "Set an application URL (or portal URL) on the grant, or pass url in the request to parse from the web",
            )
        file_key = None
    else:
        file_key = body.file_key or g.source_file_key
        if not file_key:
            raise HTTPException(400, "Upload a PDF or DOCX first, or use use_url with an https URL")
    job = Job(grant_id=grant_id, job_kind="parse", status="pending")
    session.add(job)
    await session.flush()
    # Commit before the background task runs so another DB session can see this Job row.
    # Otherwise the worker may load before the request transaction commits and skip work silently.
    await session.commit()
    sf = get_session_factory()
    background_tasks.add_task(
        run_parse_job,
        sf,
        settings,
        storage,
        llm,
        job.id,
        grant_id,
        file_key,
        parse_from_web=parse_from_web,
        web_url_override=override,
    )
    return {"job_id": job.id, "status": "pending"}


@app.post("/api/v1/grants/{grant_id}/preview-url")
async def preview_grant_url(
    grant_id: str,
    body: PreviewUrlRequest,
    session: SessionDep,
    settings: SettingsDep,
):
    """Fetch and extract text without running the full parse job (for UX sanity-check)."""
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    url = (body.url or "").strip() or _grant_web_url(g)
    if not url:
        raise HTTPException(400, "Set url or grant / portal application link first")
    try:
        return await preview_web_fetch(settings, url)
    except WebFetchError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/v1/grants/{grant_id}/generate", status_code=202)
async def generate_grant(
    grant_id: str,
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
    llm: LlmDep,
    embedder: EmbedderDep,
):
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    r = await session.execute(select(Question).where(Question.grant_id == grant_id))
    if not r.scalars().first():
        raise HTTPException(400, "No questions — run parse first")
    job = Job(grant_id=grant_id, job_kind="generate", status="pending")
    session.add(job)
    await session.flush()
    await session.commit()
    sf = get_session_factory()
    background_tasks.add_task(
        run_generate_job,
        sf,
        settings,
        llm,
        embedder,
        job.id,
        grant_id,
        body.question_ids,
    )
    return {"job_id": job.id, "status": "pending"}


@app.post("/api/v1/grants/{grant_id}/learn-org", status_code=202)
async def learn_org_from_grant(
    grant_id: str,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
    llm: LlmDep,
    embedder: EmbedderDep,
):
    """Background job: LLM extracts reusable facts from this grant's answers into org Facts."""
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    r = await session.execute(select(Question).where(Question.grant_id == grant_id))
    if not r.scalars().first():
        raise HTTPException(400, "No questions yet — find questions from a file or web page first.")
    ra = await session.execute(select(Answer).where(Answer.grant_id == grant_id))
    answers = list(ra.scalars().all())
    if not has_any_nonempty_answer(answers):
        raise HTTPException(
            400,
            "Fill in at least one answer first — then we can save reusable organization facts.",
        )
    job = Job(grant_id=grant_id, job_kind="learn_org", status="pending")
    session.add(job)
    await session.flush()
    await session.commit()
    sf = get_session_factory()
    background_tasks.add_task(
        run_learn_org_job,
        sf,
        settings,
        llm,
        embedder,
        job.id,
        grant_id,
    )
    return {"job_id": job.id, "status": "pending"}


@app.post("/api/v1/grants/{grant_id}/export")
async def export_grant(
    grant_id: str,
    body: ExportRequest,
    session: SessionDep,
    storage: StorageDep,
):
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    await session.refresh(g, ["questions", "answers"])
    qs = list(g.questions or [])
    ans = list(g.answers or [])
    if body.format == "markdown":
        text = build_qa_markdown(g, qs, ans)
        key = StorageService.export_key(grant_id, "md")
        storage.write_bytes(key, text.encode("utf-8"))
    elif body.format == "docx":
        docx_bytes = build_qa_docx(g, qs, ans)
        key = StorageService.export_key(grant_id, "docx")
        storage.write_bytes(key, docx_bytes)
    else:
        pdf_bytes = build_qa_pdf(g, qs, ans)
        key = StorageService.export_key(grant_id, "pdf")
        storage.write_bytes(key, pdf_bytes)
    g.export_file_key = key
    g.updated_at = datetime.utcnow()
    await session.flush()
    download_name = build_export_download_filename(g.name, body.format)
    return {
        "file_key": key,
        "download_path": f"/api/v1/files/{key}",
        "filename": download_name,
    }


@app.patch("/api/v1/grants/{grant_id}/questions/{question_id}")
async def patch_answer(
    grant_id: str,
    question_id: str,
    body: AnswerPatch,
    session: SessionDep,
):
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    rq = await session.execute(
        select(Question).where(Question.grant_id == grant_id, Question.question_id == question_id)
    )
    qrow = rq.scalar_one_or_none()
    if not qrow:
        raise HTTPException(404, "Question not found")
    r = await session.execute(
        select(Answer).where(Answer.grant_id == grant_id, Answer.question_id == question_id)
    )
    ans = r.scalar_one_or_none()
    if ans is None:
        ans = Answer(grant_id=grant_id, question_id=question_id)
        session.add(ans)
    if body.answer_value is not None:
        try:
            ans.answer_value = coerce_answer_value(qrow, body.answer_value)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    if body.reviewed is not None:
        if body.reviewed:
            if answer_value_is_effectively_empty(ans.answer_value, qrow.q_type):
                raise HTTPException(
                    422,
                    "Add an answer before marking as reviewed.",
                )
            ans.reviewed = True
            ans.needs_manual_input = False
        else:
            ans.reviewed = False
    await session.flush()
    return AnswerRead.from_model(ans)


@app.put("/api/v1/grants/{grant_id}/questions/reorder", response_model=GrantRead)
async def reorder_questions(grant_id: str, body: QuestionReorderRequest, session: SessionDep):
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    r = await session.execute(select(Question).where(Question.grant_id == grant_id))
    rows = list(r.scalars().all())
    if not rows:
        raise HTTPException(400, "No questions to reorder")
    expected = {q.question_id for q in rows}
    got = list(body.question_ids)
    if len(got) != len(set(got)):
        raise HTTPException(422, "Duplicate question_id in reorder list")
    if set(got) != expected:
        raise HTTPException(
            422,
            "question_ids must list each question for this grant exactly once",
        )
    by_id = {q.question_id: q for q in rows}
    for i, qid in enumerate(got):
        by_id[qid].sort_order = i
    g.updated_at = datetime.utcnow()
    await session.flush()
    await session.refresh(g, ["questions", "answers"])
    return _grant_read(g)


@app.get("/api/v1/jobs/{job_id}", response_model=JobRead)
async def get_job(job_id: str, session: SessionDep):
    j = await session.get(Job, job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return _job_read(j)


@app.get("/api/v1/files/{file_path:path}")
async def get_file(
    file_path: str,
    storage: StorageDep,
    filename: str | None = Query(
        None,
        description="Optional basename for Content-Disposition; ignored except under exports/.",
    ),
):
    try:
        data = storage.read_bytes(file_path)
    except (ValueError, FileNotFoundError, OSError):
        raise HTTPException(404, "File not found")
    ct = "application/octet-stream"
    low = file_path.lower()
    if low.endswith(".pdf"):
        ct = "application/pdf"
    elif low.endswith(".docx"):
        ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif low.endswith(".md"):
        ct = "text/markdown; charset=utf-8"

    headers: dict[str, str] = {}
    if file_path.startswith("exports/"):
        if low.endswith(".pdf"):
            ext = ".pdf"
        elif low.endswith(".docx"):
            ext = ".docx"
        elif low.endswith(".md"):
            ext = ".md"
        else:
            ext = PurePosixPath(file_path).suffix or ".bin"
        default_stem = default_export_stem_from_key(file_path)
        final_name = sanitize_content_disposition_filename(
            filename,
            default_stem=default_stem,
            required_ext=ext,
        )
        headers["Content-Disposition"] = content_disposition_attachment(final_name)

    return Response(content=data, media_type=ct, headers=headers)
