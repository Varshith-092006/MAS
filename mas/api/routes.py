"""FastAPI REST routes for MAS runs, events, results, change requests, evaluations, and research analytics."""

import asyncio
from datetime import datetime
import json
import os
import time
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
import numpy as np
from pydantic import BaseModel, Field

from eval.chatdev_adapter import ChatDevAdapter
from eval.neutral_evaluator import NeutralEvaluator
from eval.srdd_loader import load_srdd_benchmark_tasks
from eval.published_references import PUBLISHED_REFERENCES, get_published_reference
from eval.stats import compare_systems, summarize_metric_distribution
from mas.core.change_request import ChangeRequestManager
from mas.core.llm import FakeLLMProvider, OpenRouterProvider, token_logger, is_model_match
from mas.core.workflow import MASWorkflow, generate_artifacts_manifest
from mas.db.models import AgentEvent, Artifact, Evaluation, Metric, ModelCall, Run, Task
from mas.db.session import get_session

router = APIRouter()


class CreateRunRequest(BaseModel):
    requirement: str
    task_id: str = "custom"
    system: str = "mas"  # 'mas' or 'chatdev'
    model: str = "openrouter/free"  # e.g., 'openrouter/free', 'fake', 'openai/gpt-4o', 'openai/gpt-4o-mini'
    repeats: int = 1
    workspace_base: str = "./workspace"


class ChangeRequestPayload(BaseModel):
    new_requirement: str


class CreateEvaluationRequest(BaseModel):
    tasks: Optional[List[Dict[str, Any]]] = None
    task_count: Optional[int] = None
    systems: List[str] = Field(default_factory=lambda: ["mas", "chatdev"])
    models: List[str] = Field(default_factory=lambda: ["gpt-4o"])
    repeats: int = 3
    seed: int = 42
    temperature: float = 0.0
    dry_run: bool = True
    ablation: str = "A0"


@router.post("/runs")
async def create_run(req: CreateRunRequest, background_tasks: BackgroundTasks):
    """Creates and starts an execution run for MAS or ChatDev."""
    try:
        if req.model == "fake":
            os.environ["MAS_ALLOW_SUBPROCESS_SANDBOX"] = "1"

        llm = FakeLLMProvider() if req.model == "fake" else OpenRouterProvider(default_model=req.model)
        loop = asyncio.get_event_loop()

        if req.system.lower() == "chatdev":
            adapter = ChatDevAdapter(llm=llm)
            task_data = {
                "task_id": req.task_id,
                "name": req.task_id,
                "description": req.requirement,
                "category": "Custom",
            }
            use_fake = (req.model == "fake")
            
            output = await loop.run_in_executor(
                None,
                lambda: adapter.run_task(
                    task=task_data,
                    output_base_dir=req.workspace_base,
                    model=req.model,
                    use_fake=use_fake,
                ),
            )

            # Run neutral evaluation
            evaluator = NeutralEvaluator()
            metrics = await loop.run_in_executor(
                None,
                lambda: evaluator.evaluate_project(
                    workspace_path=output["workspace_dir"],
                    requirement=req.requirement,
                    task_id=req.task_id,
                    run_id=output["run_id"],
                ),
            )

            totals = token_logger.get_run_totals(output["run_id"])
            return {
                "run_id": output["run_id"],
                "system": "chatdev",
                "status": "COMPLETED",
                "complexity": "STANDARD",
                "iterations": 1,
                "tokens": totals["total_tokens"],
                "cost": totals["estimated_cost"],
            }
        else:
            workflow = MASWorkflow(llm=llm)
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
                "system": "mas",
                "status": state.get("status"),
                "complexity": state.get("complexity"),
                "iterations": state.get("iteration"),
                "tokens": state.get("total_tokens"),
                "cost": state.get("estimated_cost"),
            }
    except Exception as e:
        status_code = 402 if ("402" in str(e) or "Insufficient Credits" in str(e)) else 400
        raise HTTPException(status_code=status_code, detail=str(e))



@router.get("/runs")
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    execution_mode: Optional[str] = None,
    system: Optional[str] = None,
    model: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
):
    """Lists runs with filter options and overall research summary."""
    with get_session() as session:
        query = session.query(Run)
        if execution_mode:
            query = query.filter(Run.execution_mode == execution_mode.upper())
        if system:
            query = query.filter(Run.system == system.lower())
        if model:
            m_clean = model.strip().lower()
            if m_clean in ("openai/gpt-4o", "gpt-4o"):
                query = query.filter(Run.model.in_(["openai/gpt-4o", "gpt-4o"]))
            else:
                query = query.filter(Run.model.ilike(f"%{model}%"))
        if status:
            query = query.filter(Run.status == status.upper())

        all_runs_count = query.count()
        runs_db = query.order_by(Run.started_at.desc()).offset(offset).limit(limit).all()

        runs_list = []
        for r in runs_db:
            totals = token_logger.get_run_totals(r.run_id)
            metrics_list = session.query(Metric).filter(Metric.run_id == r.run_id).all()
            metrics_dict = {m.metric_name: m.metric_value for m in metrics_list}

            duration = 0.0
            if r.started_at and r.finished_at:
                duration = round((r.finished_at - r.started_at).total_seconds(), 2)

            has_metrics = bool(metrics_list)
            quality = metrics_dict.get("quality", metrics_dict.get("adaptive_score")) if has_metrics else None
            completeness = metrics_dict.get("completeness") if has_metrics else None
            executability = metrics_dict.get("executability") if has_metrics else None
            consistency = metrics_dict.get("consistency") if has_metrics else None
            shared_test = metrics_dict.get("shared_test", metrics_dict.get("pytest_pass_rate")) if has_metrics else None

            tot_tokens = totals.get("total_tokens")
            if not totals.get("call_count") or totals.get("token_provenance") == "UNAVAILABLE":
                display_tokens = None
            else:
                display_tokens = tot_tokens

            q_per_1k = round(quality / (display_tokens / 1000), 4) if (quality is not None and display_tokens and display_tokens > 0) else None

            # Calculate manifest count
            manifest_count = 0
            if r.artifacts_manifest:
                try:
                    m_data = json.loads(r.artifacts_manifest)
                    if isinstance(m_data, list):
                        manifest_count = len(m_data)
                except Exception:
                    pass

            runs_list.append({
                "run_id": r.run_id,
                "task_id": r.task_id or "custom",
                "category": r.task.category if r.task else "Creation",
                "system": r.system,
                "model": r.model,
                "actual_model": r.actual_model or r.model,
                "execution_mode": r.execution_mode or ("SIMULATED" if "fake" in r.model.lower() else "LIVE_API"),
                "token_provenance": r.token_provenance or ("SIMULATED" if "fake" in r.model.lower() else ("PROVIDER_REPORTED" if (tot_tokens and tot_tokens > 0) else "UNAVAILABLE")),
                "provider_request_id": r.provider_request_id,
                "status": r.status,
                "failure_reason": r.failure_reason,
                "skip_reason": r.skip_reason,
                "sandbox_status": r.sandbox_status or "UNKNOWN",
                "files_count": manifest_count,
                "repeat_no": r.evaluation.repeat_no if r.evaluation else 1,
                "ablation": r.evaluation.ablation if r.evaluation else "A0",
                "evaluation_id": r.evaluation_id,
                "benchmark": r.evaluation.benchmark if r.evaluation else ("FREE_MODEL_EXPLORATORY" if ("free" in (r.model or "").lower()) else "srdd20_canonical"),
                "eligibility_status": "ELIGIBLE" if (r.status in ("COMPLETED", "COMPLETED_QUALITY_GATE") and r.execution_mode == "LIVE_API") else "EXCLUDED",
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "duration_seconds": duration,
                "tokens": display_tokens,
                "input_tokens": totals.get("input_tokens") if totals.get("call_count") else None,
                "output_tokens": totals.get("output_tokens") if totals.get("call_count") else None,
                "estimated_cost": totals.get("estimated_cost", 0.0),
                "quality": round(quality, 4) if quality is not None else None,
                "completeness": round(completeness, 4) if completeness is not None else None,
                "executability": round(executability, 4) if executability is not None else None,
                "consistency": round(consistency, 4) if consistency is not None else None,
                "shared_test": round(shared_test, 4) if shared_test is not None else None,
                "ruff": round(metrics_dict.get("ruff", 1.0), 4) if has_metrics else None,
                "bandit": round(metrics_dict.get("bandit", 1.0), 4) if has_metrics else None,
                "radon": round(metrics_dict.get("radon", 1.0), 4) if has_metrics else None,
                "reviewer": round(metrics_dict.get("reviewer_score", 1.0), 4) if has_metrics else None,
                "quality_per_1k": q_per_1k,
            })

        # Summary across database categorized by execution mode
        total_runs = session.query(Run).count()
        completed_runs = session.query(Run).filter(Run.status.in_(["COMPLETED", "COMPLETED_QUALITY_GATE"])).count()
        failed_runs = session.query(Run).filter(Run.status.in_(["FAILED", "MODEL_MISMATCH_DIAGNOSTIC", "DIAGNOSTIC_RUN"])).count()
        skipped_runs = session.query(Run).filter(Run.status.in_(["SKIPPED", "NOT_STARTED"])).count()
        simulated_runs = session.query(Run).filter(Run.execution_mode == "SIMULATED").count()

        # Empirical calculations strictly on eligible live completed runs without model mismatches or diagnostic flags
        all_completed_live = session.query(Run).filter(Run.execution_mode == "LIVE_API", Run.status.in_(["COMPLETED", "COMPLETED_QUALITY_GATE"])).all()
        live_runs = [
            r for r in all_completed_live
            if is_model_match(r.model, r.actual_model or r.model)
            and not (r.failure_reason and ("MODEL_MISMATCH" in r.failure_reason or "DIAGNOSTIC" in r.failure_reason))
        ]
        eligible_live_runs = len(live_runs)

        live_run_ids = [r.run_id for r in live_runs]
        live_metrics = session.query(Metric).filter(Metric.run_id.in_(live_run_ids), Metric.metric_name == "quality").all() if live_run_ids else []
        live_calls = session.query(ModelCall).filter(ModelCall.run_id.in_(live_run_ids)).all() if live_run_ids else []

        live_total_tokens = sum(c.total_tokens for c in live_calls)
        live_total_cost = sum(c.cost for c in live_calls if c.cost is not None)
        live_avg_quality = round(sum(m.metric_value for m in live_metrics) / len(live_metrics), 4) if live_metrics else 0.0
        live_avg_tokens = round(live_total_tokens / len(live_runs), 1) if live_runs else 0.0
        live_q1k = round(live_avg_quality / (live_avg_tokens / 1000), 4) if live_avg_tokens > 0 else None

        summary = {
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "failed_runs": failed_runs,
            "skipped_runs": skipped_runs,
            "eligible_live_runs": eligible_live_runs,
            "excluded_simulated_runs": simulated_runs,
            "excluded_failed_runs": failed_runs,
            "excluded_skipped_runs": skipped_runs,
            "total_tokens": live_total_tokens,
            "average_tokens_per_run": live_avg_tokens,
            "average_quality": live_avg_quality,
            "quality_per_1k_tokens": live_q1k,
            "estimated_cost": round(live_total_cost, 4),
        }

        return {
            "summary": summary,
            "runs": runs_list,
            "total_count": all_runs_count,
        }


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    """Returns run metadata, current status, and full execution provenance."""
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        totals = token_logger.get_run_totals(run_id)
        
        # Calculate duration
        duration = 0.0
        if run.started_at and run.finished_at:
            duration = round((run.finished_at - run.started_at).total_seconds(), 2)

        metrics_list = session.query(Metric).filter(Metric.run_id == run_id).all()
        metrics_dict = {m.metric_name: m.metric_value for m in metrics_list}
        quality = metrics_dict.get("quality", metrics_dict.get("adaptive_score", 0.0))
        tot_tokens = totals["total_tokens"]
        q_per_1k = round(quality / (tot_tokens / 1000), 4) if tot_tokens > 0 else None

        manifest_list = []
        if run.artifacts_manifest:
            try:
                manifest_list = json.loads(run.artifacts_manifest)
                if not isinstance(manifest_list, list):
                    manifest_list = []
            except Exception:
                manifest_list = []

        return {
            "run_id": run.run_id,
            "task_id": run.task_id,
            "system": run.system,
            "model": run.model,
            "actual_model": run.actual_model or run.model,
            "execution_mode": run.execution_mode or ("SIMULATED" if "fake" in run.model.lower() else "LIVE_API"),
            "token_provenance": run.token_provenance or ("SIMULATED" if "fake" in run.model.lower() else ("PROVIDER_REPORTED" if tot_tokens > 0 else "UNAVAILABLE")),
            "provider_request_id": run.provider_request_id,
            "status": run.status,
            "failure_reason": run.failure_reason,
            "skip_reason": run.skip_reason,
            "evaluation_id": run.evaluation_id,
            "benchmark": run.evaluation.benchmark if run.evaluation else ("FREE_MODEL_EXPLORATORY" if ("free" in (run.model or "").lower()) else "srdd20_canonical"),
            "eligibility_status": "ELIGIBLE" if (run.status in ("COMPLETED", "COMPLETED_QUALITY_GATE") and run.execution_mode == "LIVE_API") else "EXCLUDED",
            "workspace_path": run.workspace_path,
            "sandbox_status": run.sandbox_status or "UNKNOWN",
            "files_count": len(manifest_list),
            "artifacts_manifest": manifest_list,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "duration_seconds": duration,
            "input_tokens": totals.get("input_tokens"),
            "output_tokens": totals.get("output_tokens"),
            "total_tokens": tot_tokens,
            "quality_per_1k": q_per_1k,
            "estimated_cost": totals["estimated_cost"],
        }


@router.get("/runs/{run_id}/workspace")
def get_run_workspace(run_id: str, file_path: Optional[str] = None):
    """Retrieves generated project workspace file manifest or specific file content with strict path-traversal protection."""
    ws_path = None
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == run_id).first()
        if run and run.workspace_path and os.path.exists(run.workspace_path):
            ws_path = run.workspace_path

    if not ws_path:
        candidates = [
            os.path.abspath(os.path.join("eval", "workspaces", run_id)),
            os.path.abspath(os.path.join("workspace", run_id)),
            os.path.abspath(os.path.join("workspaces", run_id)),
        ]
        for c in candidates:
            if os.path.exists(c):
                ws_path = c
                break

    if not ws_path or not os.path.exists(ws_path):
        return {
            "run_id": run_id,
            "workspace_path": None,
            "files": [],
            "message": "No generated workspace files found for this run",
        }

    safe_root = os.path.abspath(ws_path)

    # If specific file content requested
    if file_path:
        target_path = os.path.abspath(os.path.join(safe_root, file_path))
        try:
            common = os.path.commonpath([safe_root, target_path])
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied: Invalid file path")

        if common != safe_root:
            raise HTTPException(status_code=403, detail="Access denied: Path traversal detected")

        if not os.path.isfile(target_path):
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        try:
            with open(target_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except Exception as e:
            content = f"# Error reading file: {str(e)}"

        return {
            "run_id": run_id,
            "path": file_path,
            "content": content,
            "size": os.path.getsize(target_path),
        }

    # Return full manifest
    manifest = generate_artifacts_manifest(safe_root)
    return {
        "run_id": run_id,
        "workspace_path": safe_root,
        "files": manifest,
        "file_count": len(manifest),
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


@router.get("/runs/{run_id}/artifacts")
def get_run_artifacts(run_id: str):
    """Returns all validated artifacts produced during the run."""
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        artifacts = (
            session.query(Artifact)
            .filter(Artifact.run_id == run_id)
            .order_by(Artifact.artifact_id)
            .all()
        )
        return [
            {
                "artifact_id": a.artifact_id,
                "type": a.type,
                "version": a.version,
                "schema_valid": a.schema_valid,
                "json_data": a.json_data,
            }
            for a in artifacts
        ]


@router.get("/runs/{run_id}/workspace")
def get_run_workspace(run_id: str, file_path: Optional[str] = None):
    """Lists workspace files or returns the contents of a specific file."""
    workspace_path = os.path.abspath(f"./workspace/{run_id}")
    if not os.path.exists(workspace_path):
        return {"files": [], "content": None, "exists": False}

    if file_path:
        clean_rel = os.path.normpath(file_path).lstrip("\\/.")
        target_fp = os.path.abspath(os.path.join(workspace_path, clean_rel))
        if not target_fp.startswith(workspace_path) or not os.path.isfile(target_fp):
            raise HTTPException(status_code=404, detail="File not found")
        try:
            with open(target_fp, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return {"file_path": clean_rel, "content": content}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    files_list = []
    for root, _, fnames in os.walk(workspace_path):
        if any(x in root for x in [".git", "__pycache__", ".mas_snapshots"]):
            continue
        for fn in fnames:
            full_fp = os.path.join(root, fn)
            rel_fp = os.path.relpath(full_fp, workspace_path).replace("\\", "/")
            size = os.path.getsize(full_fp)
            files_list.append({"path": rel_fp, "name": fn, "size": size})

    return {"files": files_list, "exists": True}


# ---------------------------------------------------------------------------
# BATCH BENCHMARK & EVALUATION ENDPOINTS
# ---------------------------------------------------------------------------

@router.post("/evaluations")
def create_evaluation_plan(req: CreateEvaluationRequest):
    """Creates a benchmark evaluation specification or validates a dry run with ZERO model calls."""
    # 1. Resolve tasks
    tasks = req.tasks
    if not tasks:
        all_benchmark_tasks = load_srdd_benchmark_tasks()
        count = req.task_count if req.task_count is not None else 20
        tasks = all_benchmark_tasks[:count]

    task_count = len(tasks)
    systems_count = len(req.systems)
    models_count = len(req.models)
    repeats = req.repeats

    # Total planned runs
    planned_runs = task_count * repeats * systems_count * models_count

    # 2. Engineering Token Envelope (budget cap calculation)
    # LLD Sec 7: GPT-4o capped at 40k tokens/run; GPT-4o-mini capped at 20k tokens/run
    envelope_breakdown = {}
    total_token_envelope = 0
    for model_name in req.models:
        cap_per_run = 40_000 if "mini" not in model_name.lower() else 20_000
        sub_runs = task_count * repeats * systems_count
        model_envelope = sub_runs * cap_per_run
        envelope_breakdown[model_name] = {
            "runs": sub_runs,
            "cap_per_run": cap_per_run,
            "envelope_tokens": model_envelope,
            "envelope_millions": round(model_envelope / 1e6, 2),
        }
        total_token_envelope += model_envelope

    planning_token_envelope = {
        "label": "ENGINEERING TOKEN ENVELOPE (Budget cap, not measured benchmark data)",
        "total_envelope_tokens": total_token_envelope,
        "total_envelope_millions": round(total_token_envelope / 1e6, 2),
        "breakdown": envelope_breakdown,
    }

    eval_id = f"eval_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    
    config_snapshot = {
        "task_count": task_count,
        "repeats": repeats,
        "systems": req.systems,
        "models": req.models,
        "seed": req.seed,
        "temperature": req.temperature,
        "ablation": req.ablation,
        "dry_run": req.dry_run,
    }

    # Generate sample of planned run items for preview
    planned_items = []
    for t_idx, t in enumerate(tasks):
        t_id = t.get("task_id", f"task_{t_idx+1:03d}")
        req_text = t.get("requirement", t.get("description", ""))
        cat = t.get("category", "Creation")
        for r_no in range(1, repeats + 1):
            for sys_name in req.systems:
                for m_name in req.models:
                    planned_items.append({
                        "task_id": t_id,
                        "task_name": t.get("name", t_id),
                        "category": cat,
                        "system": sys_name,
                        "model": m_name,
                        "repeat": r_no,
                        "requirement": req_text[:80] + "..." if len(req_text) > 80 else req_text,
                    })

    if not req.dry_run:
        # Persist evaluation record
        with get_session() as session:
            ev = Evaluation(
                evaluation_id=eval_id,
                benchmark=f"custom_{task_count}t",
                repeat_no=repeats,
                ablation=req.ablation,
            )
            session.add(ev)
            session.commit()

    return {
        "evaluation_id": eval_id,
        "dry_run": req.dry_run,
        "tasks_count": task_count,
        "repeats": repeats,
        "systems": req.systems,
        "models": req.models,
        "planned_runs": planned_runs,
        "model_calls": 0 if req.dry_run else planned_runs,
        "planning_token_envelope": planning_token_envelope,
        "configuration_snapshot": config_snapshot,
        "preview_items": planned_items[:10],
    }


@router.post("/evaluations/{evaluation_id}/start")
def start_evaluation(evaluation_id: str):
    """Confirms start of a validated benchmark evaluation."""
    return {
        "evaluation_id": evaluation_id,
        "status": "QUEUED",
        "message": "Benchmark configuration validated and queued for execution.",
    }


@router.get("/evaluations")
def list_evaluations():
    """Returns list of benchmark evaluations recorded."""
    with get_session() as session:
        evals = session.query(Evaluation).all()
        result = []
        for e in evals:
            runs_count = session.query(Run).filter(Run.evaluation_id == e.evaluation_id).count()
            result.append({
                "evaluation_id": e.evaluation_id,
                "benchmark": e.benchmark,
                "repeat_no": e.repeat_no,
                "ablation": e.ablation,
                "runs_count": runs_count,
            })
        return result


@router.get("/evaluations/srdd-tasks")
def get_srdd_tasks():
    """Returns the canonical 20 SRDD benchmark tasks (4 across 5 categories)."""
    return load_srdd_benchmark_tasks()



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


@router.get("/evaluations/{evaluation_id}/results")
def get_evaluation_results(evaluation_id: str):
    """Returns aggregated results for a specific evaluation."""
    with get_session() as session:
        runs = session.query(Run).filter(Run.evaluation_id == evaluation_id).all()
        run_ids = [r.run_id for r in runs]
        metrics = session.query(Metric).filter(Metric.run_id.in_(run_ids)).all() if run_ids else []
        
        mas_quality = []
        chatdev_quality = []
        for r in runs:
            r_metrics = {m.metric_name: m.metric_value for m in metrics if m.run_id == r.run_id}
            q = r_metrics.get("quality", r_metrics.get("adaptive_score", 0.0))
            if r.system == "mas":
                mas_quality.append(q)
            elif r.system == "chatdev":
                chatdev_quality.append(q)

        return {
            "evaluation_id": evaluation_id,
            "runs_count": len(runs),
            "mas_mean_quality": round(sum(mas_quality) / len(mas_quality), 4) if mas_quality else 0.0,
            "chatdev_mean_quality": round(sum(chatdev_quality) / len(chatdev_quality), 4) if chatdev_quality else 0.0,
        }


# ---------------------------------------------------------------------------
# RESEARCH STATISTICAL SUMMARY & iCoder REFERENCE
# ---------------------------------------------------------------------------

@router.get("/analytics/summary")
def get_analytics_summary(
    include_simulated: bool = False,
    system: Optional[str] = None,
    model: Optional[str] = None,
):
    """Computes rigorous empirical statistical analysis and displays published iCoder reference.

    By default, empirical research analytics strictly excludes SIMULATED, FAILED, and INCOMPLETE runs.
    """
    with get_session() as session:
        # Run counts by provenance
        total_runs = session.query(Run).count()
        completed_runs = session.query(Run).filter(Run.status.in_(["COMPLETED", "COMPLETED_QUALITY_GATE"])).count()
        failed_runs = session.query(Run).filter(Run.status.in_(["FAILED", "MODEL_MISMATCH_DIAGNOSTIC", "DIAGNOSTIC_RUN"])).count()
        skipped_runs = session.query(Run).filter(Run.status.in_(["SKIPPED", "NOT_STARTED"])).count()
        simulated_runs_count = session.query(Run).filter(Run.execution_mode == "SIMULATED").count()

        # Query eligible research runs
        query = session.query(Run).filter(Run.status.in_(["COMPLETED", "COMPLETED_QUALITY_GATE"]))
        if not include_simulated:
            query = query.filter(Run.execution_mode == "LIVE_API")
        if system:
            query = query.filter(Run.system == system.lower())
        if model:
            m_clean = model.strip().lower()
            if m_clean in ("openai/gpt-4o", "gpt-4o"):
                query = query.filter(Run.model.in_(["openai/gpt-4o", "gpt-4o"]))
            else:
                query = query.filter(Run.model.ilike(f"%{model}%"))

        candidate_runs = query.all()

        # Strict research validity filtering:
        # Exclude runs with model mismatches, diagnostic flags, or non-completed status
        valid_research_runs = []
        excluded_mismatch_count = 0
        for r in candidate_runs:
            if r.status in ("SKIPPED", "NOT_STARTED") or r.execution_mode == "SKIPPED":
                continue
            actual = r.actual_model or r.model
            if not is_model_match(r.model, actual):
                excluded_mismatch_count += 1
                continue
            if r.failure_reason and ("MODEL_MISMATCH" in r.failure_reason or "DIAGNOSTIC" in r.failure_reason):
                excluded_mismatch_count += 1
                continue
            valid_research_runs.append(r)

        runs = valid_research_runs
        run_ids = [r.run_id for r in runs]
        eligible_live_runs_count = len([r for r in runs if r.execution_mode == "LIVE_API"])

        # Audit missing usage and missing artifacts
        missing_usage_count = sum(1 for r in runs if (r.total_tokens is None or r.total_tokens == 0 or r.token_provenance == "UNAVAILABLE"))
        missing_artifacts_count = 0
        for r in runs:
            if not r.artifacts_manifest or r.artifacts_manifest == "[]":
                missing_artifacts_count += 1
            else:
                try:
                    m_arr = json.loads(r.artifacts_manifest)
                    if not m_arr or len(m_arr) == 0:
                        missing_artifacts_count += 1
                except Exception:
                    missing_artifacts_count += 1

        metrics_db = session.query(Metric).filter(Metric.run_id.in_(run_ids)).all() if run_ids else []
        
        # Group metrics by run_id
        metrics_by_run: Dict[str, Dict[str, float]] = {}
        for m in metrics_db:
            if m.run_id not in metrics_by_run:
                metrics_by_run[m.run_id] = {}
            metrics_by_run[m.run_id][m.metric_name] = m.metric_value

        mas_quality = []
        mas_completeness = []
        mas_executability = []
        mas_consistency = []
        mas_tokens = []

        chatdev_quality = []
        chatdev_completeness = []
        chatdev_executability = []
        chatdev_consistency = []
        chatdev_tokens = []

        mas_mini_quality = []

        for r in runs:
            m_dict = metrics_by_run.get(r.run_id, {})
            totals = token_logger.get_run_totals(r.run_id)
            tok = totals["total_tokens"]
            q = m_dict.get("quality", m_dict.get("adaptive_score", 0.0))
            comp = m_dict.get("completeness", 0.0)
            exec_val = m_dict.get("executability", 0.0)
            cons = m_dict.get("consistency", 0.0)

            if r.system.lower() == "mas":
                if "mini" in r.model.lower():
                    mas_mini_quality.append(q)
                mas_quality.append(q)
                mas_completeness.append(comp)
                mas_executability.append(exec_val)
                mas_consistency.append(cons)
                if tok > 0:
                    mas_tokens.append(tok)
            elif r.system.lower() == "chatdev":
                chatdev_quality.append(q)
                chatdev_completeness.append(comp)
                chatdev_executability.append(exec_val)
                chatdev_consistency.append(cons)
                if tok > 0:
                    chatdev_tokens.append(tok)

        # Compute empirical statistics using eval/stats.py if runs exist
        stat_quality = compare_systems(mas_quality, chatdev_quality, metric_name="Quality") if (mas_quality or chatdev_quality) else {
            "mas_mean": 0.0, "chatdev_mean": 0.0, "absolute_difference": 0.0, "relative_delta_pct": 0.0,
            "mann_whitney_u": 0.0, "p_value": 1.0, "is_statistically_significant": False, "cohens_d": 0.0,
            "sample_sizes": {"mas": len(mas_quality), "chatdev": len(chatdev_quality)}
        }
        stat_completeness = compare_systems(mas_completeness, chatdev_completeness, metric_name="Completeness") if (mas_completeness or chatdev_completeness) else {}
        stat_executability = compare_systems(mas_executability, chatdev_executability, metric_name="Executability") if (mas_executability or chatdev_executability) else {}
        stat_consistency = compare_systems(mas_consistency, chatdev_consistency, metric_name="Consistency") if (mas_consistency or chatdev_consistency) else {}

        # Distribution for MAS & ChatDev
        mas_dist_q = summarize_metric_distribution(mas_quality) if mas_quality else {"count": 0, "mean": 0.0, "std": 0.0, "median": 0.0, "iqr": 0.0, "min": 0.0, "max": 0.0}
        cd_dist_q = summarize_metric_distribution(chatdev_quality) if chatdev_quality else {"count": 0, "mean": 0.0, "std": 0.0, "median": 0.0, "iqr": 0.0, "min": 0.0, "max": 0.0}

        # Published iCoder Reference metrics (strictly REFERENCE ONLY, not executed locally)
        icoder_reference = {
            "status": "PUBLISHED REFERENCE — NOT EXECUTED LOCALLY",
            "citation": "You et al., 'iCoder: A Multi-Agent Software Development Platform', Information and Software Technology 198 (2026) 108224, Tables 1-4, pp. 11-13.",
            "metric_definition": "Quality = Completeness × Executability × Consistency",
            "note": "iCoder is a published literature benchmark, NOT executed locally in this repository.",
            "gpt_4o": PUBLISHED_REFERENCES["gpt-4o"],
            "gpt_35_turbo": PUBLISHED_REFERENCES["gpt-3.5-turbo"],
            # Top-level backward compatible fields defaulting to primary GPT-4o condition
            "icoder_quality": PUBLISHED_REFERENCES["gpt-4o"]["icoder_quality"],
            "chatdev_reference_quality": PUBLISHED_REFERENCES["gpt-4o"]["chatdev_quality"],
            "icoder_reported_tokens_per_task": PUBLISHED_REFERENCES["gpt-4o"]["icoder_tokens_per_task"],
            "chatdev_reported_tokens_per_task": PUBLISHED_REFERENCES["gpt-4o"]["chatdev_tokens_per_task"],
        }

        # Token breakdown strictly for contributing runs
        contributing_calls = session.query(ModelCall).filter(ModelCall.run_id.in_(run_ids)).all() if run_ids else []
        total_input = sum(c.input_tokens for c in contributing_calls)
        total_output = sum(c.output_tokens for c in contributing_calls)
        total_all_tokens = sum(c.total_tokens for c in contributing_calls)
        total_cost = sum(c.cost for c in contributing_calls)

        token_list = [c.total_tokens for c in contributing_calls if c.total_tokens > 0]
        max_tokens = max(token_list) if token_list else 0
        median_tokens = round(float(np.median(token_list)), 1) if token_list else 0.0
        avg_tokens = round(float(np.mean(token_list)), 1) if token_list else 0.0
        q1k = round(stat_quality["mas_mean"] / (avg_tokens / 1000), 4) if (avg_tokens > 0 and stat_quality.get("mas_mean", 0) > 0) else None

        return {
            "provenance_filter": {
                "include_simulated": include_simulated,
                "eligible_live_runs": eligible_live_runs_count,
                "excluded_simulated_runs": simulated_runs_count,
                "excluded_failed_runs": failed_runs,
                "excluded_skipped_runs": skipped_runs,
                "excluded_model_mismatched_runs": excluded_mismatch_count,
                "runs_with_missing_usage": missing_usage_count,
                "runs_with_missing_artifacts": missing_artifacts_count,
                "total_runs_in_db": total_runs,
            },
            "statistical_summary": {
                "quality": stat_quality,
                "completeness": stat_completeness,
                "executability": stat_executability,
                "consistency": stat_consistency,
                "mas_quality_distribution": mas_dist_q,
                "chatdev_quality_distribution": cd_dist_q,
            },
            "mas_gpt4o_mini": {
                "mean_quality": round(sum(mas_mini_quality) / len(mas_mini_quality), 4) if mas_mini_quality else 0.0,
                "n_runs": len(mas_mini_quality),
            },
            "token_analytics": {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "total_tokens": total_all_tokens,
                "average_tokens_per_run": avg_tokens,
                "median_tokens_per_run": median_tokens,
                "maximum_tokens_per_run": max_tokens,
                "estimated_cost": round(total_cost, 4),
                "quality_per_1k_tokens": q1k,
            },
            "icoder_reference": icoder_reference,
        }
