"""Format solver solutions for output."""

from __future__ import annotations
from datetime import datetime


def format_solution(solution, school_data: dict) -> dict:
    """
    Format a solver solution into a structured output.

    Args:
        solution: SolverSolution from the model
        school_data: Original school data for reference

    Returns:
        Formatted solution dictionary
    """
    # Build lookup maps
    teachers = {t["id"]: t for t in school_data["teachers"]}
    groups = {g["id"]: g for g in school_data["groups"]}
    subjects = {s["id"]: s for s in school_data["subjects"]}

    # Enrich assignments with names
    enriched_assignments = []
    for assignment in solution.assignments:
        teacher = teachers.get(assignment["teacher_id"], {})
        group = groups.get(assignment["group_id"], {})
        subject = subjects.get(assignment["subject_id"], {})

        enriched_assignments.append({
            **assignment,
            "teacher_name": teacher.get("name", "Unknown"),
            "group_name": group.get("name", "Unknown"),
            "subject_name": subject.get("name", "Unknown"),
        })

    return {
        "status": solution.status,
        "solve_time_ms": solution.solve_time_ms,
        "objective_value": solution.objective_value,
        "assignments": enriched_assignments,
        "summary": {
            "total_lessons": len(school_data["lessons"]),
            "assigned_lessons": len(solution.assignments),
            "teachers": len(school_data["teachers"]),
            "rooms": len(school_data["rooms"]),
            "groups": len(school_data["groups"]),
        },
        "generated_at": datetime.now().isoformat(),
    }


def format_timetable_grid(
    assignments: list[dict],
    view_type: str,
    view_id: str,
    num_days: int = 5,
    num_periods: int = 6
) -> dict:
    """
    Format assignments into a grid structure for a specific view.

    Args:
        assignments: List of assignment dictionaries
        view_type: One of 'teacher', 'room', 'group'
        view_id: ID of the entity to filter by
        num_days: Number of days (default 5)
        num_periods: Number of periods (default 6)

    Returns:
        Grid structure with days and periods
    """
    # Filter assignments for this view
    filter_key = f"{view_type}_id"
    filtered = [a for a in assignments if a.get(filter_key) == view_id]

    # Build grid
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"][:num_days]
    grid = {}

    for day_idx, day_name in enumerate(days):
        grid[day_name] = {}
        for period in range(1, num_periods + 1):
            # Find assignment for this slot
            slot_assignment = None
            for a in filtered:
                if a["day"] == day_idx and a["period"] == period:
                    slot_assignment = a
                    break
            grid[day_name][period] = slot_assignment

    return {
        "view_type": view_type,
        "view_id": view_id,
        "grid": grid,
    }
