"""Reflection Agent and Adaptive Stopper using internal MAS signals only."""

from typing import Any, Dict, List, Optional, Tuple
import uuid
import yaml

from mas.agents.base import BaseAgent
from mas.core.schemas import ReflectionDecision
from mas.core.state import MASState
from mas.core.events import event_logger
from mas.db.models import Metric
from mas.db.session import get_session


class AdaptiveStopper:
    """Calculates internal adaptive score and decides termination.

    NEUTRAL EVALUATOR IS NEVER IMPORTED OR INVOKED HERE.
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        stop_epsilon: float = 0.02,
        patience: int = 2,
        max_iterations: int = 3,
    ):
        self.weights = weights or {
            "internal_test": 0.30,
            "ruff": 0.10,
            "bandit": 0.15,
            "radon": 0.10,
            "reviewer": 0.15,
            "ce": 0.20,
        }
        self.stop_epsilon = stop_epsilon
        self.patience = patience
        self.max_iterations = max_iterations
        self.consecutive_low_gain = 0

    def compute_score(self, signals: Dict[str, Any]) -> float:
        """Normalizes signals and computes weighted score S_t in [0, 1]."""
        # InternalTest: pass fraction (0 to 1)
        internal_test = float(signals.get("internal_test", 1.0))

        # Ruff: 1 - min(violations / 10, 1)
        ruff_violations = signals.get("ruff_violations", 0)
        ruff_score = 1.0 - min(ruff_violations / 10.0, 1.0)

        # Bandit: 1 - min((3*High + 2*Medium + Low) / 10, 1)
        b_high = signals.get("bandit_high", 0)
        b_med = signals.get("bandit_medium", 0)
        b_low = signals.get("bandit_low", 0)
        bandit_score = 1.0 - min((3.0 * b_high + 2.0 * b_med + 1.0 * b_low) / 10.0, 1.0)

        # Radon: clip(maintainability_index / 100, 0, 1)
        mi = signals.get("radon_mi", 100.0)
        radon_score = max(0.0, min(mi / 100.0, 1.0))

        # Reviewer: 1 - min((3*critical + major) / 6, 1)
        rev_crit = signals.get("reviewer_critical", 0)
        rev_maj = signals.get("reviewer_major", 0)
        reviewer_score = 1.0 - min((3.0 * rev_crit + 1.0 * rev_maj) / 6.0, 1.0)

        # CE: 0.5 * (Completeness + Executability)
        comp = float(signals.get("completeness", 1.0))
        execu = float(signals.get("executability", 1.0))
        ce_score = 0.5 * (comp + execu)

        score = (
            self.weights["internal_test"] * internal_test
            + self.weights["ruff"] * ruff_score
            + self.weights["bandit"] * bandit_score
            + self.weights["radon"] * radon_score
            + self.weights["reviewer"] * reviewer_score
            + self.weights["ce"] * ce_score
        )
        return round(max(0.0, min(score, 1.0)), 4)

    def evaluate_stop(
        self,
        iteration: int,
        current_score: float,
        previous_score: float,
        has_critical_defects: bool,
        tests_pass: bool,
    ) -> Tuple[str, str, float]:
        """Returns (decision ['STOP' or 'CONTINUE'], reason, marginal_gain)."""
        delta = round(current_score - previous_score, 4)

        # Condition 1: Clean result
        if not has_critical_defects and tests_pass:
            return "STOP", "clean_result: no critical defects and internal tests pass", delta

        # Update low marginal gain counter
        if delta < self.stop_epsilon:
            self.consecutive_low_gain += 1
        else:
            self.consecutive_low_gain = 0

        # Condition 2: Marginal gain below epsilon for consecutive iterations
        if self.consecutive_low_gain >= self.patience:
            return "STOP", f"marginal_gain_plateau: delta ({delta}) < {self.stop_epsilon} for {self.consecutive_low_gain} iterations (open_findings={has_critical_defects})", delta

        # Condition 3: Max iterations reached
        if iteration >= self.max_iterations:
            return "STOP", f"max_iterations: reached limit of {self.max_iterations} (open_findings={has_critical_defects})", delta

        return "CONTINUE", f"continuing to iteration {iteration + 1} (delta={delta})", delta


class ReflectionAgent(BaseAgent):
    """Calculates adaptive iteration score and stops or continues the loop."""

    def __init__(self, llm=None, config_path: str = "config.yaml", **kwargs):
        super().__init__(name="reflection", llm=llm, **kwargs)
        self.stopper = self._load_stopper_config(config_path)

    def _load_stopper_config(self, config_path: str) -> AdaptiveStopper:
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                ad = cfg.get("adaptive", {})
                return AdaptiveStopper(
                    weights=ad.get("weights"),
                    stop_epsilon=ad.get("stop_epsilon", 0.02),
                    patience=ad.get("patience", 2),
                    max_iterations=ad.get("max_iterations", 3),
                )
        except Exception:
            return AdaptiveStopper()

    def run(self, state: MASState) -> MASState:
        run_id = state.get("run_id", str(uuid.uuid4()))
        iteration = state.get("iteration", 1)

        event_logger.emit(
            run_id=run_id,
            agent="reflection",
            event="agent_started",
            summary=f"Reflection calculating adaptive score for iteration {iteration}",
        )

        # Gather internal signals from actual execution, AST, and quality tools
        test_rep = state.get("mas_pytest_report", {})
        rev_rep = state.get("review_report", {})
        q_rep = state.get("quality_report", {})
        sandbox_exec = state.get("sandbox_execution", {})
        ast_rep = state.get("ast_report", {})

        ruff_viol = q_rep.get("ruff", {}).get("violations", 0) if isinstance(q_rep.get("ruff"), dict) else 0
        bandit_h = q_rep.get("bandit", {}).get("high", 0) if isinstance(q_rep.get("bandit"), dict) else 0
        bandit_m = q_rep.get("bandit", {}).get("medium", 0) if isinstance(q_rep.get("bandit"), dict) else 0
        bandit_l = q_rep.get("bandit", {}).get("low", 0) if isinstance(q_rep.get("bandit"), dict) else 0
        radon_mi = q_rep.get("radon", {}).get("mean_mi", 100.0) if isinstance(q_rep.get("radon"), dict) else 100.0
        ast_cycles = len(ast_rep.get("cycles", [])) if isinstance(ast_rep.get("cycles"), list) else 0
        exec_ok = 1.0 if sandbox_exec.get("is_success", False) else (0.0 if "is_success" in sandbox_exec else 1.0)

        signals = {
            "internal_test": float(test_rep.get("pass_rate", 1.0 if exec_ok == 1.0 else 0.0)),
            "ruff_violations": ruff_viol,
            "bandit_high": bandit_h,
            "bandit_medium": bandit_m,
            "bandit_low": bandit_l,
            "radon_mi": radon_mi,
            "reviewer_critical": rev_rep.get("critical_issues", 0),
            "reviewer_major": rev_rep.get("major_issues", 0),
            "completeness": 1.0,
            "executability": exec_ok,
        }

        current_score = self.stopper.compute_score(signals)
        prev_score = state.get("previous_adaptive_score", 0.0)

        has_critical = (
            signals["reviewer_critical"] > 0
            or ast_cycles > 0
            or exec_ok == 0.0
            or rev_rep.get("status") == "FAILED"
        )
        tests_pass = (signals["internal_test"] >= 1.0 and exec_ok >= 1.0)

        decision, reason, delta = self.stopper.evaluate_stop(
            iteration=iteration,
            current_score=current_score,
            previous_score=prev_score,
            has_critical_defects=has_critical,
            tests_pass=tests_pass,
        )

        ref_decision = ReflectionDecision(
            decision=decision,
            reason=reason,
            adaptive_score=current_score,
            marginal_gain=delta,
            iteration=iteration,
        )

        state["previous_adaptive_score"] = current_score
        state["marginal_gain"] = delta
        state["stop_reason"] = reason if decision == "STOP" else None
        state["artifacts"]["ReflectionDecision"] = ref_decision.model_dump()

        # Record internal adaptive_score metric
        try:
            with get_session() as session:
                metric = Metric(
                    run_id=run_id,
                    metric_name="adaptive_score",
                    metric_value=current_score,
                    scope="internal",
                )
                session.add(metric)
                session.commit()
        except Exception:
            pass

        event_logger.emit(
            run_id=run_id,
            agent="reflection",
            event="agent_completed",
            summary=f"Reflection decided: {decision} (S_t={current_score:.4f}, delta={delta:.4f}, reason='{reason}')",
        )

        return state
