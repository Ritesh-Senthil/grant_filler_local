import logging
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import delete, select

from app.config import Settings
from app.database import create_tables, init_engine
from app.database import get_session_factory
from app.deps import OllamaDep, SessionDep, SettingsDep, StorageDep, ensure_default_org
from app.job_runner import run_generate_job, run_learn_org_job, run_parse_job
from app.models import Answer, Fact, Grant, Job, Organization, Question
from app.schemas import (
    AnswerPatch,
    AnswerRead,
    ConfigRead,
    ExtraSection,
    ExportRequest,
    FactCreate,
    FactRead,
    FactUpdate,
    GenerateRequest,
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
)
from app.services.answer_coerce import coerce_answer_value
from app.services.export import build_qa_docx, build_qa_markdown, build_qa_pdf
from app.services.learn_org_facts import has_any_nonempty_answer
from app.services.web_fetch import WebFetchError, preview_web_fetch
from app.services.ollama import OllamaClient
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
    app.state.ollama = OllamaClient(settings)
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


def _grant_read(g: Grant) -> GrantRead:
    qs = [QuestionRead.from_model(q) for q in (g.questions or [])]
    ans = [AnswerRead.from_model(a) for a in (g.answers or [])]
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
        created_at=g.created_at,
        updated_at=g.updated_at,
        questions=qs,
        answers=ans,
    )


@app.get("/api/v1/health")
async def health():
    return {"ok": True}


@app.get("/api/v1/config", response_model=ConfigRead)
async def config(settings: SettingsDep):
    ok = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            ok = r.status_code == 200
    except Exception:
        ok = False
    return ConfigRead(
        ollama_configured=ok,
        default_model=settings.ollama_model,
        data_dir=str(settings.data_dir.resolve()),
    )


@app.get("/api/v1/org", response_model=OrganizationRead)
async def get_org(session: SessionDep):
    org = await ensure_default_org(session)
    extra = org.extra_sections or []
    sections: list[ExtraSection] = []
    for s in extra:
        if isinstance(s, dict):
            sections.append(
                ExtraSection(
                    id=str(s.get("id", "")),
                    title=str(s.get("title", "")),
                    content=str(s.get("content", "")),
                )
            )
    return OrganizationRead(
        id=org.id,
        legal_name=org.legal_name,
        mission_short=org.mission_short,
        mission_long=org.mission_long,
        address=org.address,
        extra_sections=sections,
    )


@app.put("/api/v1/org", response_model=OrganizationRead)
async def put_org(body: OrganizationUpdate, session: SessionDep):
    org = await ensure_default_org(session)
    if body.legal_name is not None:
        org.legal_name = body.legal_name
    if body.mission_short is not None:
        org.mission_short = body.mission_short
    if body.mission_long is not None:
        org.mission_long = body.mission_long
    if body.address is not None:
        org.address = body.address
    if body.extra_sections is not None:
        org.extra_sections = [s.model_dump() for s in body.extra_sections]
    await session.flush()
    return await get_org(session)


@app.get("/api/v1/org/facts", response_model=list[FactRead])
async def list_facts(session: SessionDep):
    org = await ensure_default_org(session)
    r = await session.execute(select(Fact).where(Fact.org_id == org.id).order_by(Fact.updated_at.desc()))
    rows = r.scalars().all()
    return [
        FactRead(
            id=f.id,
            org_id=f.org_id,
            key=f.key,
            value=f.value,
            source=f.source,
            updated_at=f.updated_at,
        )
        for f in rows
    ]


@app.post("/api/v1/org/facts", response_model=FactRead)
async def create_fact(body: FactCreate, session: SessionDep):
    org = await ensure_default_org(session)
    f = Fact(org_id=org.id, key=body.key, value=body.value, source=body.source)
    session.add(f)
    await session.flush()
    return FactRead(
        id=f.id,
        org_id=f.org_id,
        key=f.key,
        value=f.value,
        source=f.source,
        updated_at=f.updated_at,
    )


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
    return FactRead(
        id=f.id,
        org_id=f.org_id,
        key=f.key,
        value=f.value,
        source=f.source,
        updated_at=f.updated_at,
    )


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
    ollama: OllamaDep,
):
    g = await session.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Grant not found")
    file_key: str | None
    parse_from_web = body.use_url
    override = (body.url or "").strip() or None
    if parse_from_web:
        target = override or (g.grant_url or "").strip()
        if not target:
            raise HTTPException(
                400,
                "Set an application URL on the grant or pass url in the request to parse from the web",
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
        ollama,
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
    url = (body.url or "").strip() or (g.grant_url or "").strip()
    if not url:
        raise HTTPException(400, "Set url or grant application URL first")
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
    ollama: OllamaDep,
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
        ollama,
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
    ollama: OllamaDep,
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
            "Fill in at least one answer first — then we can save reusable facts to your organization profile.",
        )
    job = Job(grant_id=grant_id, job_kind="learn_org", status="pending")
    session.add(job)
    await session.flush()
    await session.commit()
    sf = get_session_factory()
    background_tasks.add_task(
        run_learn_org_job,
        sf,
        ollama,
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
    return {"file_key": key, "download_path": f"/api/v1/files/{key}"}


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
        ans.reviewed = body.reviewed
    await session.flush()
    return AnswerRead.from_model(ans)


@app.get("/api/v1/jobs/{job_id}", response_model=JobRead)
async def get_job(job_id: str, session: SessionDep):
    j = await session.get(Job, job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return _job_read(j)


@app.get("/api/v1/files/{file_path:path}")
async def get_file(file_path: str, storage: StorageDep):
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
    elif low.endswith(".docx"):
        ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(content=data, media_type=ct)
