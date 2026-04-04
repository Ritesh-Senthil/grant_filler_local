import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: "default-org")
    legal_name: Mapped[str] = mapped_column(String(512), default="")
    mission_short: Mapped[str] = mapped_column(Text, default="")
    mission_long: Mapped[str] = mapped_column(Text, default="")
    address: Mapped[str] = mapped_column(Text, default="")
    extra_sections: Mapped[list | None] = mapped_column(JSON, default=list)

    facts: Mapped[list["Fact"]] = relationship("Fact", back_populates="org", cascade="all, delete-orphan")


class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("organizations.id"), index=True)
    key: Mapped[str] = mapped_column(String(256), default="")
    value: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(512), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org: Mapped["Organization"] = relationship("Organization", back_populates="facts")


class Grant(Base):
    __tablename__ = "grants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(512), default="")
    grant_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    portal_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="pdf")  # web | pdf | docx
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft | ready | ...
    source_file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    export_file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions: Mapped[list["Question"]] = relationship(
        "Question",
        back_populates="grant",
        cascade="all, delete-orphan",
        order_by="Question.sort_order",
    )
    answers: Mapped[list["Answer"]] = relationship("Answer", back_populates="grant", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("grant_id", "question_id", name="uq_grant_question"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    grant_id: Mapped[str] = mapped_column(String(64), ForeignKey("grants.id"), index=True)
    question_id: Mapped[str] = mapped_column(String(128))
    question_text: Mapped[str] = mapped_column(Text, default="")
    q_type: Mapped[str] = mapped_column(String(32), default="textarea")
    options: Mapped[list | None] = mapped_column(JSON, default=list)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    char_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    grant: Mapped["Grant"] = relationship("Grant", back_populates="questions")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("grant_id", "question_id", name="uq_grant_answer"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    grant_id: Mapped[str] = mapped_column(String(64), ForeignKey("grants.id"), index=True)
    question_id: Mapped[str] = mapped_column(String(128))
    answer_value: Mapped[object | None] = mapped_column(JSON, nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_manual_input: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_fact_ids: Mapped[list | None] = mapped_column(JSON, default=list)

    grant: Mapped["Grant"] = relationship("Grant", back_populates="answers")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    grant_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("grants.id"), nullable=True, index=True)
    job_kind: Mapped[str] = mapped_column(String(32))  # parse | generate | learn_org
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | running | completed | failed
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
