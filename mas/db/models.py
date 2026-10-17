"""SQLAlchemy models for MAS database schema (LLD Sec 4.2)."""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(String(50), primary_key=True)
    category = Column(String(30), nullable=True)  # Education, Work, Life, Games, Creation
    name = Column(String(100), nullable=True)
    description = Column(Text, nullable=False)

    runs = relationship("Run", back_populates="task", cascade="all, delete-orphan")


class Evaluation(Base):
    __tablename__ = "evaluations"

    evaluation_id = Column(String(50), primary_key=True)
    benchmark = Column(String(50), nullable=False)  # e.g. srdd20
    repeat_no = Column(Integer, nullable=False, default=1)
    ablation = Column(String(30), nullable=False, default="A0")

    runs = relationship("Run", back_populates="evaluation", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "runs"

    run_id = Column(String(40), primary_key=True)
    task_id = Column(String(50), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=True)
    evaluation_id = Column(String(50), ForeignKey("evaluations.evaluation_id", ondelete="CASCADE"), nullable=True)
    system = Column(String(20), nullable=False, default="mas")  # mas or chatdev
    model = Column(String(40), nullable=False, default="gpt-4o")
    execution_mode = Column(String(20), nullable=False, default="LIVE_API")  # LIVE_API, SIMULATED, FAILED, INCOMPLETE
    actual_model = Column(String(80), nullable=True)
    provider_request_id = Column(String(80), nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    token_provenance = Column(String(30), nullable=False, default="UNAVAILABLE")  # PROVIDER_REPORTED, SIMULATED, UNAVAILABLE
    estimated_cost = Column(Float, nullable=False, default=0.0)
    failure_reason = Column(Text, nullable=True)
    skip_reason = Column(Text, nullable=True)
    workspace_path = Column(String(255), nullable=True)
    artifacts_manifest = Column(JSON, nullable=True)
    sandbox_status = Column(String(30), nullable=True)  # PASSED, FAILED, UNAVAILABLE
    seed = Column(Integer, nullable=False, default=42)
    status = Column(String(60), nullable=False, default="CREATED")  # CREATED, RUNNING, COMPLETED, COMPLETED_QUALITY_GATE, STOPPED_MAX_ITERATIONS_WITH_OPEN_FINDINGS, FAILED, CANCELLED
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="runs")
    evaluation = relationship("Evaluation", back_populates="runs")
    events = relationship("AgentEvent", back_populates="run", cascade="all, delete-orphan", order_by="AgentEvent.seq")
    artifacts = relationship("Artifact", back_populates="run", cascade="all, delete-orphan")
    checkpoints = relationship("Checkpoint", back_populates="run", cascade="all, delete-orphan")
    model_calls = relationship("ModelCall", back_populates="run", cascade="all, delete-orphan")
    metrics = relationship("Metric", back_populates="run", cascade="all, delete-orphan")
    config_snapshot = relationship("ConfigSnapshot", back_populates="run", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_runs_system_model_eval", "system", "model", "evaluation_id"),
    )


class AgentEvent(Base):
    """Append-only audit events table."""
    __tablename__ = "agent_events"

    seq = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    run_id = Column(String(40), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    agent = Column(String(30), nullable=False)
    event = Column(String(40), nullable=False)  # run_started, agent_started, agent_completed, artifact_rejected, rollback, code_executed, etc.
    status = Column(String(20), nullable=False, default="success")  # success, failure
    redacted_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("Run", back_populates="events")

    __table_args__ = (
        Index("ix_agent_events_run_seq", "run_id", "seq"),
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    artifact_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(40), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(30), nullable=False)  # TaskPlan, UserStory, Architecture, CodePatch, ReviewReport, TestReport, ReflectionDecision
    version = Column(Integer, nullable=False, default=1)
    schema_valid = Column(Boolean, nullable=False, default=True)
    json_data = Column(JSON, nullable=False)

    run = relationship("Run", back_populates="artifacts")


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    checkpoint_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(40), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    iteration = Column(Integer, nullable=False, default=1)
    git_ref = Column(String(64), nullable=False)

    run = relationship("Run", back_populates="checkpoints")


class ModelCall(Base):
    __tablename__ = "model_calls"

    call_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(40), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    agent = Column(String(30), nullable=False)
    model = Column(String(40), nullable=False)
    requested_model = Column(String(80), nullable=True)
    actual_model = Column(String(80), nullable=True)
    request_id = Column(String(80), nullable=True)
    raw_metadata = Column(JSON, nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=False, default=0)
    cost = Column(Float, nullable=True, default=0.0)

    run = relationship("Run", back_populates="model_calls")


class Metric(Base):
    __tablename__ = "metrics"

    metric_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(40), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(50), nullable=False)
    metric_value = Column(Float, nullable=False)
    scope = Column(String(20), nullable=False)  # 'neutral' or 'internal'

    run = relationship("Run", back_populates="metrics")

    __table_args__ = (
        Index("ix_metrics_run_name", "run_id", "metric_name"),
    )


class ConfigSnapshot(Base):
    __tablename__ = "config_snapshots"

    run_id = Column(String(40), ForeignKey("runs.run_id", ondelete="CASCADE"), primary_key=True)
    config_json = Column(JSON, nullable=False)
    library_versions = Column(JSON, nullable=False)
    docker_image_tag = Column(String(80), nullable=False)
    checks_file_hash = Column(String(64), nullable=False)

    run = relationship("Run", back_populates="config_snapshot")
