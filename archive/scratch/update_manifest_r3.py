import json

manifest_path = "eval/benchmark_manifest.json"
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

# Update Repeat 3 run entries with exact implementation versions
version_map = {
    "mas_srdd_educ_01_r3_attempt4": {
        "implementation_version": "mas-v1.1.0-frozen",
        "git_commit": "5cffff09a066bcfa488423ef210db9f5a0445d47",
        "version_status": "MATCHES_FROZEN_VERSION",
        "series": "PRIMARY_FROZEN_SERIES"
    },
    "cd_srdd_educ_01_r3_attempt2": {
        "implementation_version": "chatdev-v1.3.0-frozen",
        "git_commit": "5cffff09a066bcfa488423ef210db9f5a0445d47",
        "chatdev_submodule_commit": "c1c31e2",
        "version_status": "MATCHES_FROZEN_VERSION",
        "series": "PRIMARY_FROZEN_SERIES"
    },
    "mas_srdd_educ_01_r2_attempt7": {
        "series": "PRIMARY_FROZEN_SERIES"
    },
    "cd_srdd_educ_01_r2_attempt2": {
        "series": "PRIMARY_FROZEN_SERIES"
    },
    "mas_srdd_educ_01_r1_attempt4": {
        "series": "LEGACY_EXPLORATORY_BASELINE"
    },
    "cd_srdd_educ_01_r1_attempt7": {
        "series": "LEGACY_EXPLORATORY_BASELINE"
    }
}

for run in manifest.get("runs", []):
    rid = run.get("run_id")
    if rid in version_map:
        run.update(version_map[rid])

# Update summary to distinguish total pairs from frozen-version comparable pairs
manifest["summary"]["total_completed_paired_repeats"] = 3
manifest["summary"]["frozen_version_comparable_paired_repeats"] = 2
manifest["summary"]["legacy_exploratory_paired_repeats"] = 1
manifest["summary"]["statistical_series_notes"] = (
    "Repeat 1 is classified as LEGACY_EXPLORATORY_BASELINE (MAS v1.0.0-legacy vs ChatDev v1.3.0-frozen). "
    "Repeats 2 and 3 constitute the PRIMARY_FROZEN_SERIES under identical frozen implementations (MAS v1.1.0-frozen vs ChatDev v1.3.0-frozen)."
)

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print("Manifest successfully updated with statistical classification and version metadata.")

