import json

manifest_path = "eval/benchmark_manifest.json"
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

# Phase B: Freeze configuration metadata
manifest["frozen_benchmark_versions"] = {
    "freeze_status": "FROZEN",
    "frozen_utc": "2026-11-06T19:29:15Z",
    "mas": {
        "version": "v1.1.0-frozen",
        "commit": "fdb7294a753093b7d287387e300f424f7477d58f",
        "description": "MAS with expanded agent token headroom (2500-4000), strict=False JSON decode, direct schema prompt, sanitized retry feedback, unclosed fence AST parsing"
    },
    "chatdev": {
        "version": "v1.3.0-frozen",
        "submodule_commit": "c1c31e2",
        "description": "ChatDev with Windows UTF-8 decoding, 900s timeout, bounded reflection cycles, test model propagation, assistant null content handling"
    },
    "evaluator": {
        "version": "v1.3",
        "shared_test_formula": "Q = C * E * S"
    },
    "environment": {
        "model": "cohere/north-mini-code:free",
        "authorized_spend_usd": 0.0,
        "token_ceiling_per_run": 60000,
        "daily_transmissions_cap": 45
    }
}

# Phase A: Tag exact version metadata on completed runs
version_map = {
    "mas_srdd_educ_01_r1_attempt4": {
        "implementation_version": "mas-v1.0.0-legacy",
        "git_commit": "cac29d54aef001ad2b6f223f6f8c8ab39b25efaa",
        "version_status": "SUPERSEDED_BY_FREEZE"
    },
    "cd_srdd_educ_01_r1_attempt7": {
        "implementation_version": "chatdev-v1.3.0-frozen",
        "git_commit": "df7b3b790c855f368cdd0c64756e405d2e9e6ab9",
        "chatdev_submodule_commit": "c1c31e2",
        "version_status": "MATCHES_FROZEN_VERSION"
    },
    "cd_srdd_educ_01_r2_attempt2": {
        "implementation_version": "chatdev-v1.3.0-frozen",
        "git_commit": "473fea2db6d14c9f162c3a546e7b6aaa3c27719c",
        "chatdev_submodule_commit": "c1c31e2",
        "version_status": "MATCHES_FROZEN_VERSION"
    },
    "mas_srdd_educ_01_r2_attempt7": {
        "implementation_version": "mas-v1.1.0-frozen",
        "git_commit": "fdb7294a753093b7d287387e300f424f7477d58f",
        "version_status": "MATCHES_FROZEN_VERSION"
    }
}

for run in manifest.get("runs", []):
    rid = run.get("run_id")
    if rid in version_map:
        run.update(version_map[rid])

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print("Manifest successfully enriched with Phase A & B version metadata.")

