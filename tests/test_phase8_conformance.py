"""Phase 8 (DEC-041): deterministic design-vs-code conformance (reverse architecture check)."""

from mas.analysis.conformance import check_conformance, planned_classes, reverse_model


ARCH = {
    "file_structure": ["main.py", "store.py", "report.py"],
    "uml_class_diagram": "classDiagram\nclass Store { +save() }\nclass Report { +render() }",
    "module_dependencies": {"main": ["store", "report"], "report": ["store"]},
}


def test_planned_classes_parses_mermaid_and_plantuml():
    assert planned_classes(ARCH["uml_class_diagram"]) == {"Store", "Report"}
    assert planned_classes("@startuml\nclass Ledger\n@enduml") == {"Ledger"}


def test_full_conformance(tmp_path):
    (tmp_path / "store.py").write_text("class Store:\n    def save(self):\n        return 1\n")
    (tmp_path / "report.py").write_text("from store import Store\nclass Report:\n    def render(self):\n        return Store().save()\n")
    (tmp_path / "main.py").write_text("import store\nimport report\n")
    c = check_conformance(ARCH, str(tmp_path))
    assert c["applicable"] and c["conformance_score"] == 1.0 and c["findings"] == []


def test_deviations_are_reported(tmp_path):
    (tmp_path / "main.py").write_text("class Store:\n    def save(self):\n        return 1\n")
    (tmp_path / "store.py").write_text("x = 1\n")
    c = check_conformance(ARCH, str(tmp_path))
    assert c["missing_files"] == ["report.py"]
    assert c["missing_classes"] == ["Report"]
    assert c["conformance_score"] == round(1 - 2 / 5, 4)
    assert any("report.py" in f for f in c["findings"])


def test_reverse_model_only_keeps_local_imports(tmp_path):
    (tmp_path / "a.py").write_text("import os\nimport b\n")
    (tmp_path / "b.py").write_text("")
    assert reverse_model(str(tmp_path))["imports"]["a"] == ["b"]


def test_not_applicable_without_architecture(tmp_path):
    assert check_conformance({}, str(tmp_path)) == {"applicable": False}


def test_structured_workflow_records_conformance(tmp_path):
    from mas.core.llm import FakeLLMProvider
    from mas.core.workflow import MASWorkflow

    st = MASWorkflow(llm=FakeLLMProvider(), ablation="A1").run(
        requirement="Simple math helper module",
        task_id="p8_conf",
        run_id="p8_conf",
        workspace_base=str(tmp_path),
    )
    assert "conformance_report" in st
    assert st["conformance_report"]["applicable"] is True
