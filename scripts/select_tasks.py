"""Select 20 benchmark tasks (4 per major category) from data_attribute_format.csv

following the iCoder research methodology (40-80 words description, seed 42, no duplicates).
Generates eval/category_map.json and eval/tasks_v2.json, and records SHA-256 in benchmark_manifest.json.
"""

import csv
import hashlib
import json
import os
import random
import sys

# Mapping 40 SRDD subcategories to iCoder paper's 5 major categories:
# Education, Work, Life, Games, Creation
CATEGORY_MAP = {
    # Education
    "Culture": "Education",
    "Language": "Education",
    "News": "Education",
    "Reference_Books": "Education",
    "Science": "Education",
    # Work
    "Budgeting": "Work",
    "Business": "Work",
    "Data": "Work",
    "Development": "Work",
    "Finance": "Work",
    "Office": "Work",
    "Schedule": "Work",
    "Security": "Work",
    "Tools_Utilities": "Work",
    # Life
    "Family_Kids": "Life",
    "Health_Fitness": "Life",
    "Medical": "Life",
    "Notebook": "Life",
    "Personalisation": "Life",
    "Restaurants_Delivery": "Life",
    "Shopping": "Life",
    "SocialNetwork": "Life",
    "Sports": "Life",
    "Transportation": "Life",
    "Travel": "Life",
    # Games
    "Action_Game": "Games",
    "Board_Game": "Games",
    "Management_Game": "Games",
    "Puzzle_Game": "Games",
    "Racing_Game": "Games",
    "Role_Playing_Game": "Games",
    "Shooter_Game": "Games",
    "Simulation_Game": "Games",
    "Sport_Game": "Games",
    "Strategy_Game": "Games",
    # Creation
    "Entertainment": "Creation",
    "Graphics": "Creation",
    "Music": "Creation",
    "Photo": "Creation",
    "Video": "Creation",
}


def select_tasks(
    csv_path: str = "data_attribute_format.csv",
    output_tasks_path: str = "eval/tasks_v2.json",
    category_map_path: str = "eval/category_map.json",
    manifest_path: str = "eval/benchmark_manifest.json",
    seed: int = 42,
):
    # 1. Save category mapping
    os.makedirs(os.path.dirname(category_map_path) or ".", exist_ok=True)
    with open(category_map_path, "w", encoding="utf-8") as f:
        json.dump(CATEGORY_MAP, f, indent=2, sort_keys=True)
    print(f"Saved category map (40 subcategories -> 5 major categories) to {category_map_path}")

    # 2. Read and filter tasks
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Source dataset not found at {csv_path}")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    by_major = {cat: [] for cat in ["Education", "Work", "Life", "Games", "Creation"]}
    seen_names = set()

    for r in rows:
        sub = r.get("Category", "").strip()
        major = CATEGORY_MAP.get(sub)
        if not major:
            continue
        desc = r.get("Description", "").strip()
        words = desc.split()
        wc = len(words)
        name = r.get("Name", "").strip()

        # Filter to paper's typical word range 40-80
        if 40 <= wc <= 80:
            clean_name = name.replace("_", " ")
            if clean_name.lower() not in seen_names:
                seen_names.add(clean_name.lower())
                by_major[major].append({
                    "name": clean_name,
                    "description": desc,
                    "category": major,
                    "subcategory": sub,
                    "word_count": wc,
                })

    # 3. Deterministically sample 4 tasks per major category with seed 42
    random.seed(seed)
    selected_tasks = []
    prefix_map = {
        "Education": "educ",
        "Work": "work",
        "Life": "life",
        "Games": "game",
        "Creation": "crea",
    }

    for cat in ["Education", "Work", "Life", "Games", "Creation"]:
        candidates = sorted(by_major[cat], key=lambda x: x["name"])
        if len(candidates) < 4:
            raise ValueError(f"Insufficient candidates ({len(candidates)}) in category {cat}")
        sampled = random.sample(candidates, 4)
        sampled.sort(key=lambda x: x["name"])
        prefix = prefix_map[cat]
        for idx, t in enumerate(sampled):
            t_obj = {
                "task_id": f"srdd_{prefix}_{idx+1:02d}",
                "name": t["name"],
                "description": t["description"],
                "category": t["category"],
                "subcategory": t["subcategory"],
                "word_count": t["word_count"],
            }
            selected_tasks.append(t_obj)

    # 4. Write tasks_v2.json
    os.makedirs(os.path.dirname(output_tasks_path) or ".", exist_ok=True)
    with open(output_tasks_path, "w", encoding="utf-8") as f:
        json.dump(selected_tasks, f, indent=2)

    # 5. Calculate SHA-256
    with open(output_tasks_path, "rb") as f:
        tasks_sha = hashlib.sha256(f.read()).hexdigest()

    print(f"\nSaved {len(selected_tasks)} tasks to {output_tasks_path}")
    print(f"SHA-256 of tasks_v2.json: {tasks_sha}")

    # 6. Store SHA-256 in manifest if present
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest["tasks_v2_sha256"] = tasks_sha
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            print(f"Updated {manifest_path} with tasks_v2_sha256")
        except Exception as e:
            print(f"[WARN] Could not update manifest with SHA-256: {e}")

    # Display table
    print("\nSelected Benchmark Tasks (SRDD-20 v2):")
    print("-" * 80)
    for t in selected_tasks:
        print(f"[{t['task_id']}] ({t['category']}/{t['subcategory']}, {t['word_count']} words) {t['name']}")
    print("-" * 80)

    return selected_tasks, tasks_sha


if __name__ == "__main__":
    select_tasks()

