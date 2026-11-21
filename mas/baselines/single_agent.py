"""Single-agent, single-call baseline (system id: "single").

One LLM call turns the requirement into project files. No planning, no architecture, no
review, no repair loop. It answers the question "what do the extra agents buy?" at the
lowest possible request cost (1 request per task), which matters on the free tier.

Fairness: it receives the exact same augmented requirement text as MAS and ChatDev, goes
through the same provider, model, temperature, seed and token logger, and is scored by the
same frozen NeutralEvaluator. The prompt is generic (no task-specific words).
"""

import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from mas.agents.developer import GENERATION_RULES, max_output_tokens, parse_delimiter_blocks
from mas.core.llm import LLMProvider, FakeLLMProvider, token_logger

SYSTEM_ID = "single"
AGENT_NAME = "single_agent"

SYSTEM_PROMPT = (
    "You are a senior Python developer. Write a complete, working Python project for the "
    "user's requirement in one answer. The entry point must be main.py.\n"
    "Format every file exactly like this:\n"
    "=== FILE: <filename> ===\n"
    "<raw code>\n"
    "=== END FILE ===\n"
    "Do not use placeholders, pass-only stubs or TODO comments. Output only the file blocks.\n"
    + GENERATION_RULES
)


def _safe_rel_path(name: str) -> Optional[str]:
    name = (name or "").strip().replace("\\", "/").lstrip("/")
    if not name or ".." in name.split("/") or ":" in name:
        return None
    return name


class SingleAgentBaseline:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def run(
        self,
        requirement: str,
        run_id: Optional[str] = None,
        model: Optional[str] = None,
        workspace_base: str = "./eval/workspaces",
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        run_id = run_id or f"single_{uuid.uuid4().hex[:8]}"
        workspace = os.path.abspath(os.path.join(workspace_base, run_id))
        os.makedirs(workspace, exist_ok=True)
        started = datetime.utcnow()
        is_fake = isinstance(self.llm, FakeLLMProvider) or model == "fake"
        self._upsert_run(run_id, model or "fake", workspace, "RUNNING", is_fake, started=started)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": requirement},
        ]
        status, error, files = "COMPLETED", None, []
        try:
            res = self.llm.generate(
                messages=messages,
                model=model or getattr(self.llm, "default_model", None),
                run_id=run_id,
                agent_name=AGENT_NAME,
                max_tokens=max_tokens or max_output_tokens(),
            )
            blocks = parse_delimiter_blocks(res.text or "")
            if not blocks and isinstance(res.parsed_json, dict) and "file_contents" in res.parsed_json:
                blocks = res.parsed_json
            contents = (blocks or {}).get("file_contents", {}) or {}
            for name, code in contents.items():
                rel = _safe_rel_path(name)
                if not rel or not isinstance(code, str):
                    continue
                path = os.path.join(workspace, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(code)
                files.append(rel)
            if not files:
                # A parse failure is a quality failure of the baseline, not an infra error:
                # it is scored (Quality 0) and never re-sent (AGENTS.md: no quality retries).
                status, error = "COMPLETED", "no files could be parsed from the model output"
        except Exception as exc:  # provider / budget errors propagate as FAILED for the runner
            status, error = "FAILED", f"{type(exc).__name__}: {exc}"

        self._upsert_run(run_id, model or "fake", workspace, "SIMULATION_ONLY" if is_fake and status == "COMPLETED" else status,
                         is_fake, finished=datetime.utcnow(), failure=error)
        return {
            "run_id": run_id,
            "workspace_path": workspace,
            "status": status,
            "error": error,
            "files": files,
            "totals": token_logger.get_run_totals(run_id),
        }

    @staticmethod
    def _upsert_run(run_id, model, workspace, status, is_fake, started=None, finished=None, failure=None):
        try:
            from mas.db.models import Run
            from mas.db.session import get_session, init_db
            init_db()
            with get_session() as s:
                row = s.query(Run).filter(Run.run_id == run_id).first()
                if not row:
                    row = Run(
                        run_id=run_id, system=SYSTEM_ID, model=model, actual_model=model,
                        execution_mode="SIMULATED" if is_fake else "LIVE_API",
                        token_provenance="SIMULATED" if is_fake else "PROVIDER_REPORTED",
                        workspace_path=workspace, status=status, started_at=started or datetime.utcnow(),
                    )
                    s.add(row)
                else:
                    row.status = status
                if finished:
                    row.finished_at = finished
                if failure:
                    row.failure_reason = failure
                s.commit()
        except Exception:
            pass
