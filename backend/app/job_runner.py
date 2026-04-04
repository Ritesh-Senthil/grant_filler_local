import logging
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.deps import ensure_default_org
from app.models import Answer, Fact, Grant, Job, Question
from app.services.answers import AnswerItem, generate_answers_batch, normalize_answer_flags
from app.services.learn_org_facts import extract_new_facts_from_grant, norm_fact_key
from app.services import web_fetch
from app.services.ingest import extract_docx_bytes, extract_pdf_bytes, segments_to_chunks
from app.services.ollama import OllamaClient
from app.services.questions_extract import extract_questions_from_chunks
from app.storage import StorageService

logger = logging.getLogger(__name__)


async def run_parse_job(
    session_factory: async_sessionmaker,
    settings: Settings,
    storage: StorageService,
    ollama: OllamaClient,
    job_id: str,
    grant_id: str,
    file_key: str | None,
    *,
    parse_from_web: bool = False,
    web_url_override: str | None = None,
) -> None:
    async with session_factory() as session:
        try:
            await _do_parse(
                session,
                settings,
                storage,
                ollama,
                job_id,
                grant_id,
                file_key,
                parse_from_web=parse_from_web,
                web_url_override=web_url_override,
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.exception("parse job failed job_id=%s grant_id=%s", job_id, grant_id)
            async with session_factory() as session2:
                job = await session2.get(Job, job_id)
                if job:
                    job.status = "failed"
                    job.error = str(e)
                    job.progress = 1.0
                    await session2.commit()


async def _do_parse(
    session: AsyncSession,
    settings: Settings,
    storage: StorageService,
    ollama: OllamaClient,
    job_id: str,
    grant_id: str,
    file_key: str | None,
    *,
    parse_from_web: bool = False,
    web_url_override: str | None = None,
) -> None:
    job = await session.get(Job, job_id)
    if not job:
        raise ValueError(
            f"Parse job row not found (job_id={job_id}). "
            "If this persists, check that the API commits the Job before starting the background worker."
        )
    logger.info("parse_job_start grant_id=%s job_id=%s", grant_id, job_id)
    job.status = "running"
    job.progress = 0.05
    await session.flush()

    grant = await session.get(Grant, grant_id)
    if not grant:
        raise ValueError("Grant not found")

    web_meta: dict | None = None
    if parse_from_web:
        url = (web_url_override or "").strip() or (grant.grant_url or "").strip()
        if not url:
            raise ValueError(
                "No application URL: set grant_url on the grant or pass url when parsing from the web"
            )
        try:
            segments, web_meta = await web_fetch.fetch_web_segments(settings, url)
        except web_fetch.WebFetchError as e:
            raise ValueError(str(e)) from e
        grant.grant_url = url
        grant.source_type = "web"
    else:
        key = file_key or grant.source_file_key
        if not key or not storage.exists(key):
            raise ValueError("No source file uploaded for this grant")

        data = storage.read_bytes(key)
        st = (grant.source_type or "pdf").lower()
        if st == "docx":
            segments = extract_docx_bytes(data)
        else:
            segments = extract_pdf_bytes(data)
        if not segments:
            raise ValueError("No text extracted from document")

    chunks = segments_to_chunks(segments, settings)
    job.progress = 0.2
    await session.flush()

    logger.info(
        "parse grant=%s chunks=%d concurrency=%d chunk_max=%d",
        grant_id,
        len(chunks),
        settings.parse_chunk_concurrency,
        settings.chunk_max_chars,
    )
    questions = await extract_questions_from_chunks(
        ollama,
        chunks,
        max_concurrency=settings.parse_chunk_concurrency,
    )
    if not questions:
        raise ValueError("No valid questions extracted; try a clearer PDF/DOCX or edit questions manually later")

    await session.execute(delete(Question).where(Question.grant_id == grant_id))
    await session.execute(delete(Answer).where(Answer.grant_id == grant_id))

    for i, eq in enumerate(questions):
        session.add(
            Question(
                grant_id=grant_id,
                question_id=eq.question_id,
                question_text=eq.question_text,
                q_type=eq.type,
                options=eq.options or [],
                required=eq.required,
                char_limit=eq.char_limit,
                sort_order=i,
            )
        )

    grant.status = "ready"
    grant.updated_at = datetime.utcnow()
    job.status = "completed"
    job.progress = 1.0
    job.result_json = {"question_count": len(questions)}
    if web_meta:
        job.result_json["web_fetch"] = web_meta
    job.error = None
    logger.info(
        "parse_job_done grant_id=%s job_id=%s questions=%d",
        grant_id,
        job_id,
        len(questions),
    )


async def run_generate_job(
    session_factory: async_sessionmaker,
    settings: Settings,
    ollama: OllamaClient,
    job_id: str,
    grant_id: str,
    question_ids: list[str] | None,
) -> None:
    async with session_factory() as session:
        try:
            await _do_generate(session, ollama, job_id, grant_id, question_ids)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.exception("generate job failed job_id=%s grant_id=%s", job_id, grant_id)
            async with session_factory() as session2:
                job = await session2.get(Job, job_id)
                if job:
                    job.status = "failed"
                    job.error = str(e)
                    job.progress = 1.0
                    await session2.commit()


async def _do_generate(
    session: AsyncSession,
    ollama: OllamaClient,
    job_id: str,
    grant_id: str,
    question_ids: list[str] | None,
) -> None:
    job = await session.get(Job, job_id)
    if not job:
        raise ValueError(f"Generate job row not found (job_id={job_id})")
    logger.info("generate_job_start grant_id=%s job_id=%s", grant_id, job_id)
    job.status = "running"
    job.progress = 0.1
    await session.flush()

    org = await ensure_default_org(session)
    r = await session.execute(select(Fact).where(Fact.org_id == org.id))
    facts = list(r.scalars().all())

    rq = await session.execute(
        select(Question).where(Question.grant_id == grant_id).order_by(Question.sort_order)
    )
    qs = list(rq.scalars().all())
    if question_ids:
        wanted = set(question_ids)
        qs = [q for q in qs if q.question_id in wanted]

    job.progress = 0.3
    await session.flush()

    items: list[AnswerItem] = await generate_answers_batch(ollama, org, facts, qs)

    for q, item in zip(qs, items, strict=True):
        existing = await session.execute(
            select(Answer).where(
                Answer.grant_id == grant_id,
                Answer.question_id == item.question_id,
            )
        )
        ans = existing.scalar_one_or_none()
        val = item.answer_value
        if val == "INSUFFICIENT_INFO":
            val = ""
            nmi = True
        else:
            nmi = item.needs_manual_input
        val, nmi = normalize_answer_flags(q, val, nmi)
        if ans is None:
            session.add(
                Answer(
                    grant_id=grant_id,
                    question_id=item.question_id,
                    answer_value=val,
                    needs_manual_input=nmi,
                    evidence_fact_ids=item.evidence_fact_ids or [],
                )
            )
        else:
            ans.answer_value = val
            ans.needs_manual_input = nmi
            ans.evidence_fact_ids = item.evidence_fact_ids or []

    g = await session.get(Grant, grant_id)
    if g:
        g.status = "ready"
        g.updated_at = datetime.utcnow()

    job.status = "completed"
    job.progress = 1.0
    job.result_json = {"answer_count": len(items)}
    job.error = None
    logger.info(
        "generate_job_done grant_id=%s job_id=%s answers=%d",
        grant_id,
        job_id,
        len(items),
    )


async def run_learn_org_job(
    session_factory: async_sessionmaker,
    ollama: OllamaClient,
    job_id: str,
    grant_id: str,
) -> None:
    async with session_factory() as session:
        try:
            await _do_learn_org(session, ollama, job_id, grant_id)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.exception("learn_org job failed job_id=%s grant_id=%s", job_id, grant_id)
            async with session_factory() as session2:
                job = await session2.get(Job, job_id)
                if job:
                    job.status = "failed"
                    job.error = str(e)
                    job.progress = 1.0
                    await session2.commit()


async def _do_learn_org(
    session: AsyncSession,
    ollama: OllamaClient,
    job_id: str,
    grant_id: str,
) -> None:
    job = await session.get(Job, job_id)
    if not job:
        raise ValueError(f"Learn-org job row not found (job_id={job_id})")
    logger.info("learn_org_job_start grant_id=%s job_id=%s", grant_id, job_id)
    job.status = "running"
    job.progress = 0.1
    await session.flush()

    org = await ensure_default_org(session)
    r = await session.execute(select(Fact).where(Fact.org_id == org.id))
    all_facts: list[Fact] = list(r.scalars().all())

    g = await session.get(Grant, grant_id)
    if not g:
        raise ValueError("Grant not found")

    rq = await session.execute(
        select(Question).where(Question.grant_id == grant_id).order_by(Question.sort_order)
    )
    questions = list(rq.scalars().all())
    ra = await session.execute(select(Answer).where(Answer.grant_id == grant_id))
    answers = list(ra.scalars().all())
    amap = {a.question_id: a for a in answers}
    pairs: list[tuple[Question, Answer]] = []
    for q in questions:
        a = amap.get(q.question_id)
        if a is None:
            continue
        pairs.append((q, a))

    job.progress = 0.35
    await session.flush()

    extracted = await extract_new_facts_from_grant(ollama, org, all_facts, pairs)

    job.progress = 0.7
    await session.flush()

    source = f"Learned from grant: {g.name}"[:512]
    added = 0
    updated = 0
    for ex in extracted:
        k = (ex.key or "").strip()
        v = (ex.value or "").strip()
        if not k or not v:
            continue
        nk = norm_fact_key(k)
        match: Fact | None = None
        for f in all_facts:
            if norm_fact_key(f.key or "") == nk:
                match = f
                break
        if match is not None:
            if match.value != v:
                match.value = v
                if not (match.source or "").strip():
                    match.source = source
                updated += 1
        else:
            nf = Fact(org_id=org.id, key=k[:256], value=v, source=source)
            session.add(nf)
            all_facts.append(nf)
            added += 1

    job.status = "completed"
    job.progress = 1.0
    job.result_json = {"facts_added": added, "facts_updated": updated}
    job.error = None
    logger.info(
        "learn_org_job_done grant_id=%s job_id=%s added=%s updated=%s",
        grant_id,
        job_id,
        added,
        updated,
    )
