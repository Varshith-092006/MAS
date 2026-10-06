"""SRDD (Software Requirements Dataset) Loader.

Loads the standard 5-category benchmark tasks (Education, Work, Life, Games, Creation),
selects 4 tasks per category with fixed seed 42 (total 20 tasks),
saves them to eval/tasks.json, and persists them into the database tasks table.
"""

import json
import os
import random
from typing import Any, Dict, List

from mas.db.models import Task
from mas.db.session import get_session, init_db

# Canonical SRDD task catalog across the 5 categories
SRDD_CANDIDATE_TASKS = {
    "Education": [
        {
            "task_id": "srdd_edu_01",
            "name": "Flashcard Quiz System",
            "description": "Develop a command-line flashcard study app where users can create decks of questions and answers, review cards with spaced repetition scores, and view study performance summaries.",
        },
        {
            "task_id": "srdd_edu_02",
            "name": "Typing Speed Tester",
            "description": "Create a typing speed test application that presents sample text paragraphs, measures words-per-minute (WPM) and accuracy percentage, and displays summary statistics.",
        },
        {
            "task_id": "srdd_edu_03",
            "name": "Language Vocabulary Builder",
            "description": "Build an interactive vocabulary training tool that quizzes users on foreign language word translations, tracks incorrect answers, and generates review lists.",
        },
        {
            "task_id": "srdd_edu_04",
            "name": "Math Quiz Generator",
            "description": "Implement a mathematical quiz utility that automatically generates arithmetic problems of configurable difficulty levels and calculates scores with time tracking.",
        },
        {
            "task_id": "srdd_edu_05",
            "name": "Interactive Periodic Table Guide",
            "description": "Develop an educational chemistry reference tool that displays element properties, atomic weights, electron configurations, and allows search by symbol or atomic number.",
        },
    ],
    "Work": [
        {
            "task_id": "srdd_work_01",
            "name": "Markdown Todo Organizer",
            "description": "Create a task tracking manager that parses and updates markdown todo lists, supports task priority tagging, due dates, and prints pending task summaries.",
        },
        {
            "task_id": "srdd_work_02",
            "name": "Timesheet & Billing Calculator",
            "description": "Implement a work hours logging utility that records client project sessions, hourly rates, calculates billable totals, and outputs formatted text invoices.",
        },
        {
            "task_id": "srdd_work_03",
            "name": "Meeting Agenda Planner",
            "description": "Build a CLI meeting agenda assistant that organizes agenda topics with estimated time limits, tracks speaker discussion allocations, and exports meeting minutes.",
        },
        {
            "task_id": "srdd_work_04",
            "name": "CSV Data Validator & Normalizer",
            "description": "Develop a tabular data cleanup script that validates CSV columns against schema rules, strips whitespace, formats dates, and reports validation errors.",
        },
        {
            "task_id": "srdd_work_05",
            "name": "Employee Shift Scheduler",
            "description": "Create a workplace scheduling utility that assigns staff members to weekly work shifts according to availability constraints and outputs a weekly roster.",
        },
    ],
    "Life": [
        {
            "task_id": "srdd_life_01",
            "name": "Personal Expense Tracker",
            "description": "Build a personal budgeting application that logs daily financial expenses across custom categories, calculates monthly balances, and prints spending breakdown reports.",
        },
        {
            "task_id": "srdd_life_02",
            "name": "Daily Habit Streak Tracker",
            "description": "Develop a daily habit tracking tool that records habit completions, maintains streak counters, and computes completion rates over a 30-day window.",
        },
        {
            "task_id": "srdd_life_03",
            "name": "Recipe & Meal Planner",
            "description": "Create a meal preparation assistant that stores food recipes with ingredient quantities, plans weekly dinners, and automatically compiles combined grocery shopping lists.",
        },
        {
            "task_id": "srdd_life_04",
            "name": "Water Intake & Hydration Reminder",
            "description": "Implement a wellness utility that tracks daily water consumption volume against a target goal, logs timestamps of glasses consumed, and calculates remaining intake.",
        },
        {
            "task_id": "srdd_life_05",
            "name": "Workout Exercise Log",
            "description": "Build a fitness tracking app that records workout sessions with sets, reps, and weights lifted, providing progressive overload progress comparisons.",
        },
    ],
    "Games": [
        {
            "task_id": "srdd_game_01",
            "name": "Terminal Blackjack Game",
            "description": "Develop a full console Blackjack card game with card deck shuffling, player hit/stand actions, dealer rules (soft 17), and chip betting balances.",
        },
        {
            "task_id": "srdd_game_02",
            "name": "Tic-Tac-Toe with Minimax AI",
            "description": "Create a 3x3 Tic-Tac-Toe game supporting two-player local mode and single-player mode against an optimal minimax algorithm computer opponent.",
        },
        {
            "task_id": "srdd_game_03",
            "name": "Text Adventure Dungeon Crawler",
            "description": "Build a room-based text adventure game featuring room navigation commands, inventory management, monster encounters with turn-based combat, and treasure collection.",
        },
        {
            "task_id": "srdd_game_04",
            "name": "Hangman Word Guessing Game",
            "description": "Implement the classic Hangman word game with ASCII gallows art rendering, hidden word letter reveals, guess tracking, and remaining life counts.",
        },
        {
            "task_id": "srdd_game_05",
            "name": "Connect Four Console Game",
            "description": "Develop a two-player Connect Four grid game in console with column piece dropping, boundary checks, and four-in-a-row victory condition detection.",
        },
    ],
    "Creation": [
        {
            "task_id": "srdd_create_01",
            "name": "ASCII Art Banner Generator",
            "description": "Create a command-line utility that renders text strings as large block ASCII art characters with customizable borders and font styles.",
        },
        {
            "task_id": "srdd_create_02",
            "name": "Static Site HTML Builder",
            "description": "Build a lightweight static website compiler that takes markdown content files and Jinja-like text templates, producing styled standalone HTML pages.",
        },
        {
            "task_id": "srdd_create_03",
            "name": "Color Palette Generator",
            "description": "Develop a color scheme tool that calculates complementary, triadic, and analogous color palettes from a base hex color, outputting RGB and CSS hex codes.",
        },
        {
            "task_id": "srdd_create_04",
            "name": "Procedural Dungeon Map Generator",
            "description": "Implement a procedural 2D tile dungeon map generator using cellular automata or random walk algorithms, outputting ASCII dungeon layouts.",
        },
        {
            "task_id": "srdd_create_05",
            "name": "Story Narrative Prompt Generator",
            "description": "Create a creative writing assistant that randomly combines genre tropes, protagonist archetypes, setting descriptors, and plot conflicts into creative story prompts.",
        },
    ],
}


def load_srdd_benchmark_tasks(seed: int = 42, tasks_per_category: int = 4) -> List[Dict[str, Any]]:
    """Selects tasks_per_category from each of the 5 categories using fixed seed."""
    rng = random.Random(seed)
    selected_tasks: List[Dict[str, Any]] = []

    for category in ["Education", "Work", "Life", "Games", "Creation"]:
        candidates = SRDD_CANDIDATE_TASKS[category]
        # Fixed deterministic sample
        chosen = rng.sample(candidates, tasks_per_category)
        for t in chosen:
            task_copy = dict(t)
            task_copy["category"] = category
            selected_tasks.append(task_copy)

    return selected_tasks


def save_and_persist_tasks(
    output_path: str = "eval/tasks.json",
    seed: int = 42,
    tasks_per_category: int = 4,
) -> List[Dict[str, Any]]:
    """Generates the 20 benchmark tasks, writes to tasks.json, and persists to DB."""
    tasks = load_srdd_benchmark_tasks(seed=seed, tasks_per_category=tasks_per_category)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)

    # Persist in DB
    init_db()
    with get_session() as session:
        for t in tasks:
            existing = session.query(Task).filter(Task.task_id == t["task_id"]).first()
            if not existing:
                session.add(
                    Task(
                        task_id=t["task_id"],
                        category=t["category"],
                        name=t["name"],
                        description=t["description"],
                    )
                )
        session.commit()

    return tasks


if __name__ == "__main__":
    tasks = save_and_persist_tasks()
    print(f"Successfully selected and persisted {len(tasks)} SRDD benchmark tasks to eval/tasks.json and DB.")
