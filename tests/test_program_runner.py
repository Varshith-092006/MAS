"""DEC-053: run a generated project from the UI (quick test + open on this computer).

No network calls and no real windows: the launcher is replaced by a fake in these tests.
"""

import asyncio
import os

import httpx
import pytest

from mas.api import program_runner as pr


def _project(tmp_path, code, name="main.py"):
    ws = tmp_path / "run_x"
    ws.mkdir()
    (ws / name).write_text(code, encoding="utf-8")
    return ws


def test_entry_point_matches_evaluator_order(tmp_path):
    ws = tmp_path / "w"
    ws.mkdir()
    (ws / "test_a.py").write_text("", encoding="utf-8")
    (ws / "b.py").write_text("", encoding="utf-8")
    assert pr.find_entry_point(str(ws)) == "b.py"
    (ws / "app.py").write_text("", encoding="utf-8")
    assert pr.find_entry_point(str(ws)) == "app.py"
    (ws / "main.py").write_text("", encoding="utf-8")
    assert pr.find_entry_point(str(ws)) == "main.py"


def test_quick_test_reports_output_and_leaves_original_unchanged(tmp_path):
    ws = _project(
        tmp_path,
        "def main():\n    open('data.db', 'w').write('x')\n    print('hello from the program')\n",
    )
    res = pr.quick_test(str(ws))
    assert res["success"] is True and res["entry_point"] == "main.py"
    assert "hello from the program" in res["stdout"]
    # The program wrote a file, but only in the temporary copy.
    assert not (ws / "data.db").exists()


def test_quick_test_reports_a_crash(tmp_path):
    ws = _project(tmp_path, "def main():\n    raise ValueError('boom')\n")
    res = pr.quick_test(str(ws))
    assert res["success"] is False
    assert "boom" in res["stderr"]


def test_clean_env_never_contains_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("PROVIDER_API_KEY", "secret-value")
    monkeypatch.setenv("MY_TOKEN", "secret-value")
    env = pr.clean_env(str(tmp_path))
    assert "secret-value" not in env.values()
    assert env["PYTHONPATH"] == str(tmp_path)


def test_open_program_runs_a_copy_with_args_and_no_keys(monkeypatch, tmp_path):
    monkeypatch.setenv("PROVIDER_API_KEY", "secret-value")
    ws = _project(tmp_path, "print('hi')\n")
    calls = []
    info = pr.open_program(str(ws), "--size 3", popen=lambda cmd, **kw: calls.append((cmd, kw)))
    cmd, kw = calls[0]
    assert "main.py" in cmd and cmd[-2:] == ["--size", "3"]
    assert os.path.abspath(kw["cwd"]) != os.path.abspath(str(ws))
    assert os.path.isfile(os.path.join(kw["cwd"], "main.py"))
    assert "secret-value" not in kw["env"].values()
    assert info["entry_point"] == "main.py"


# ---------------------------------------------------------------- API
def _call(method, url, client=("127.0.0.1", 5000), **kw):
    from mas.api.main import app

    async def _go():
        transport = httpx.ASGITransport(app=app, client=client)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
            return await c.request(method, url, **kw)

    return asyncio.run(_go())


@pytest.fixture
def run_root(tmp_path, monkeypatch):
    import mas.api.routes as routes

    monkeypatch.setattr(routes, "_PROGRAM_ROOTS", (str(tmp_path),))
    ws = tmp_path / "demo_run"
    ws.mkdir()
    (ws / "main.py").write_text("def main():\n    print('api ok')\n", encoding="utf-8")
    return tmp_path


def test_quick_test_endpoint(run_root):
    resp = _call("POST", "/runs/demo_run/quick-test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True and "api ok" in body["stdout"]


def test_open_endpoint_is_local_only(run_root, monkeypatch):
    launched = []
    monkeypatch.setattr(pr.subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))
    remote = _call("POST", "/runs/demo_run/open", client=("203.0.113.9", 5000), json={"args": ""})
    assert remote.status_code == 403 and not launched
    local = _call("POST", "/runs/demo_run/open", json={"args": ""})
    assert local.status_code == 200 and local.json()["opened"] is True and len(launched) == 1


def test_unknown_or_escaping_run_ids_are_refused(run_root):
    assert _call("POST", "/runs/no_such_run/quick-test").status_code == 404
    assert _call("POST", "/runs/..%2F..%2Fwindows/quick-test").status_code == 404
