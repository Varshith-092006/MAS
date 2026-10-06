"""FastAPI REST routes for MAS runs, events, results, change requests, and evaluations."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from mas.core.change_request import ChangeRequestManager
from mas.core.llm import FakeLLMProvider, OpenAIProvider, token_logger
from mas.core.workflow import MASWorkflow
from mas.db.models import AgentEvent, Evaluation, Metric, Run
from mas.db.session import get_session

router = APIRouter()


class CreateRunRequest(BaseModel):
    requirement: str
    task_id: str = "custom"
    model: str = "fake"  # 'fake', 'gpt-4o', 'gpt-4o-mini'
    workspace_base: str = "./workspace"


class ChangeRequestPayload(BaseModel):
    new_requirement: str


@router.post("/runs")
async def create_run(req: CreateRunRequest, background_tasks: BackgroundTasks):
    """Creates and starts an execution run."""
    llm = FakeLLMProvider() if req.model == "fake" else OpenAIProvider()
    workflow = MASWorkflow(llm=llm)

    # Execute workflow in background or immediate task
    # For responsiveness, run execution in threadpool/async
    loop = asyncio.get_event_loop()

    state = await loop.run_in_executor(
        None,
        lambda: workflow.run(
            requirement=req.requirement,
            task_id=req.task_id,
            model_name=req.model,
            workspace_base=req.workspace_base,
        ),
    )

    return {
        "run_id": state.get("run_id"),
        "status": state.get("status"),
        "complexity": state.get("complexity"),
        "iterations": state.get("iteration"),
        "tokens": state.get("total_tokens"),
        "cost": state.get("estimated_cost"),
    }


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    """Returns run metadata and current status."""
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        totals = token_logger.get_run_totals(run_id)
        return {
            "run_id": run.run_id,
            "task_id": run.task_id,
            "system": run.system,
            "model": run.model,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "total_tokens": totals["total_tokens"],
            "estimated_cost": totals["estimated_cost"],
        }


@router.get("/runs/{run_id}/results")
def get_run_results(run_id: str):
    """Returns neutral and internal metrics for a completed run."""
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        metrics = session.query(Metric).filter(Metric.run_id == run_id).all()
        results = {"run_id": run_id, "status": run.status, "neutral": {}, "internal": {}}
        for m in metrics:
            results[m.scope][m.metric_name] = m.metric_value
        return results


@router.get("/runs/{run_id}/events")
def get_run_events(run_id: str):
    """Returns ordered append-only agent events for a run."""
    with get_session() as session:
        events = (
            session.query(AgentEvent)
            .filter(AgentEvent.run_id == run_id)
            .order_by(AgentEvent.seq)
            .all()
        )
        return [
            {
                "seq": e.seq,
                "agent": e.agent,
                "event": e.event,
                "status": e.status,
                "summary": e.redacted_summary,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]


@router.post("/runs/{run_id}/change")
def submit_change_request(run_id: str, payload: ChangeRequestPayload):
    """Submits a requirement change request for an existing run."""
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

    workspace_path = f"./workspace/{run_id}"
    cm = ChangeRequestManager(llm=FakeLLMProvider())
    result = cm.apply_change_request(
        run_id=run_id,
        new_requirement=payload.new_requirement,
        workspace_path=workspace_path,
    )
    return result


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    """Cancels an active run."""
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        run.status = "CANCELLED"
        run.finished_at = datetime.utcnow()
        session.commit()
        return {"run_id": run_id, "status": "CANCELLED"}


@router.get("/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str):
    """Returns evaluation batch details."""
    with get_session() as session:
        ev = session.query(Evaluation).filter(Evaluation.evaluation_id == evaluation_id).first()
        if not ev:
            raise HTTPException(status_code=404, detail="Evaluation batch not found")
        runs = session.query(Run).filter(Run.evaluation_id == evaluation_id).all()
        return {
            "evaluation_id": ev.evaluation_id,
            "benchmark": ev.benchmark,
            "repeat_no": ev.repeat_no,
            "ablation": ev.ablation,
            "runs_count": len(runs),
            "runs": [r.run_id for r in runs],
        }
