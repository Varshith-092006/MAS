"""DEC-046: MAS retries temporary provider errors like ChatDev does; honest batch summary."""

import pytest

import eval.runner as runner_mod
from mas.core.llm import OpenRouterAPIError, OpenRouterProvider


class FlakyProvider(OpenRouterProvider):
    """_generate_once fails with the given errors first, then succeeds. Never touches the network."""

    def __init__(self, errors):
        super().__init__(api_key="test-key-not-real", base_url="http://127.0.0.1:1/v1", default_model="m")
        self.errors = list(errors)
        self.calls = 0
        self.waits = []

    def _sleep(self, seconds):
        self.waits.append(seconds)

    def _generate_once(self, *a, **k):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "OK"


def _err(code, limit_source=None):
    data = {"error": {"message": "x", "metadata": {"limit_source": limit_source} if limit_source else {}}}
    return OpenRouterAPIError(code, f"error {code}", error_data=data)


def test_retries_503_then_succeeds_with_backoff():
    p = FlakyProvider([_err(503), _err(500)])
    assert p.generate([{"role": "user", "content": "hi"}]) == "OK"
    assert p.calls == 3
    assert p.waits == [5.0, 5.0]  # wait_exponential(min=5) for the first attempts


def test_gives_up_after_five_attempts_like_chatdev():
    p = FlakyProvider([_err(503)] * 10)
    with pytest.raises(OpenRouterAPIError):
        p.generate([{"role": "user", "content": "hi"}])
    assert p.calls == OpenRouterProvider.RETRY_MAX_ATTEMPTS == 5
    assert all(5.0 <= w <= 60.0 for w in p.waits)


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_never_retries_request_errors(code):
    p = FlakyProvider([_err(code)])
    with pytest.raises(OpenRouterAPIError):
        p.generate([{"role": "user", "content": "hi"}])
    assert p.calls == 1


def test_per_minute_429_is_retried_but_daily_quota_is_not():
    p = FlakyProvider([_err(429)])
    assert p.generate([{"role": "user", "content": "hi"}]) == "OK"
    daily = FlakyProvider([_err(429, limit_source="free_tier_daily")])
    with pytest.raises(OpenRouterAPIError):
        daily.generate([{"role": "user", "content": "hi"}])
    assert daily.calls == 1


def test_non_transient_python_errors_are_not_retried():
    p = FlakyProvider([ValueError("bad output")])
    with pytest.raises(ValueError):
        p.generate([{"role": "user", "content": "hi"}])
    assert p.calls == 1


def test_summary_prints_na_not_zero_for_unscored_system(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner_mod, "MANIFEST_FILE", str(tmp_path / "m.json"))
    monkeypatch.setattr(runner_mod, "generate_stats_markdown_report", lambda *a, **k: "")

    def boom(*a, **k):
        raise RuntimeError("Connection refused")

    monkeypatch.setattr(runner_mod, "MASWorkflow", boom)
    tasks = tmp_path / "tasks.json"
    tasks.write_text('[{"task_id": "t1", "name": "T", "description": "d", "category": "Work"}]')
    runner_mod.EvaluationRunner(results_path=str(tmp_path / "r.csv")).run_benchmark(
        task_count=1, model="fake", use_fake=True, systems=["mas", "single"], tasks_file=str(tasks))
    out = capsys.readouterr().out
    assert "MAS Quality:         n/a (0 of 1 runs scored" in out
    assert "-100.0%" not in out
