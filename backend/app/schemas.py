from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models import Answer, Question
from app.services.evidence_ids import normalize_evidence_fact_ids
from app.services.json_safe import sanitize_answer_value_for_api


class OrganizationRead(BaseModel):
    id: str
    header_display_name: str = ""
    banner_file_key: str | None = None


class OrganizationUpdate(BaseModel):
    header_display_name: str | None = None
    clear_banner: bool | None = None


class DeveloperCreditsRead(BaseModel):
    display_name: str = ""
    github_url: str = ""
    linkedin_url: str = ""
    sponsor_text: str = ""
    sponsor_url: str = ""


class UserPreferencesRead(BaseModel):
    """Stub locale until Settings date formats wire through (roadmap E)."""
    locale: str = "iso"


class UserPreferencesPatch(BaseModel):
    locale: str | None = None


class EnhancementSubmit(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class FactRead(BaseModel):
    id: str
    org_id: str
    key: str
    value: str
    source: str = ""
    learned_from_grant_id: str | None = None
    learned_from_question_id: str | None = None
    # Enriched for display (learned facts); omitted on write payloads
    learned_from_grant_name: str | None = None
    learned_from_question_preview: str | None = None
    updated_at: datetime | None = None


class FactCreate(BaseModel):
    key: str = ""
    value: str = ""
    source: str = ""


class FactUpdate(BaseModel):
    key: str | None = None
    value: str | None = None
    source: str | None = None


class GrantCreate(BaseModel):
    name: str
    grant_url: str | None = None
    portal_url: str | None = None
    source_type: str = "pdf"


class GrantUpdate(BaseModel):
    name: str | None = None
    grant_url: str | None = None
    portal_url: str | None = None
    status: str | None = None


class QuestionRead(BaseModel):
    question_id: str
    question_text: str
    type: str
    options: list[str] = Field(default_factory=list)
    required: bool = False
    char_limit: int | None = None
    sort_order: int = 0

    @classmethod
    def from_model(cls, q: Question) -> QuestionRead:
        return cls(
            question_id=q.question_id,
            question_text=q.question_text,
            type=q.q_type,
            options=list(q.options or []),
            required=bool(q.required) if q.required is not None else False,
            char_limit=q.char_limit,
            sort_order=q.sort_order,
        )


class AnswerRead(BaseModel):
    question_id: str
    answer_value: Any = None
    reviewed: bool = False
    needs_manual_input: bool = False
    evidence_fact_ids: list[str] = Field(default_factory=list)

    @classmethod
    def from_model(cls, a: Answer) -> AnswerRead:
        return cls(
            question_id=a.question_id,
            answer_value=sanitize_answer_value_for_api(a.answer_value),
            reviewed=a.reviewed,
            needs_manual_input=a.needs_manual_input,
            evidence_fact_ids=normalize_evidence_fact_ids(a.evidence_fact_ids),
        )


class GrantRead(BaseModel):
    id: str
    name: str
    grant_url: str | None = None
    portal_url: str | None = None
    source_type: str
    status: str
    source_file_key: str | None = None
    file_name: str | None = None
    export_file_key: str | None = None
    source_chunk_count: int = 0
    created_at: datetime
    updated_at: datetime
    questions: list[QuestionRead] = Field(default_factory=list)
    answers: list[AnswerRead] = Field(default_factory=list)


class GrantSummary(BaseModel):
    id: str
    name: str
    status: str
    source_type: str
    created_at: datetime
    updated_at: datetime


class ParseRequest(BaseModel):
    file_key: str | None = None
    use_url: bool = False  # fetch grant_url or url over HTTPS
    url: str | None = None  # optional override for parse-from-web


class PreviewUrlRequest(BaseModel):
    url: str | None = None  # optional; else Grant.grant_url


class GenerateRequest(BaseModel):
    question_ids: list[str] | None = None


class DuplicateGrantRequest(BaseModel):
    name: str | None = None
    include_qa: bool = False


class ExportRequest(BaseModel):
    format: Literal["qa_pdf", "markdown", "docx"] = "qa_pdf"


class JobRead(BaseModel):
    id: str
    grant_id: str | None
    job_kind: str
    status: str
    progress: float
    error: str | None = None
    result_json: dict[str, Any] | None = None
    created_at: datetime


class AnswerPatch(BaseModel):
    answer_value: Any | None = None
    reviewed: bool | None = None


class QuestionReorderRequest(BaseModel):
    """Full ordered list of question_id values for this grant; replaces sort_order 0..n-1."""

    question_ids: list[str] = Field(min_length=1)


class ConfigRead(BaseModel):
    llm_provider: str = "ollama"
    """Whether the active provider comes from env or from a saved choice in DATA_DIR/app_preferences.json."""
    llm_provider_source: Literal["env", "user"] = "env"
    llm_configured: bool = False
    chat_model: str = ""
    embed_model: str = ""
    data_dir: str = ""


class LlmPreferenceUpdate(BaseModel):
    """Persist active provider under DATA_DIR/app_preferences.json (overrides LLM_PROVIDER from .env)."""

    llm_provider: Literal["ollama", "gemini"]

