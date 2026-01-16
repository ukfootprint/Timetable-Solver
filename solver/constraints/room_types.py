"""Room type requirement constraints."""

from __future__ import annotations
from typing import Optional
from ortools.sat.python import cp_model


def add_room_type_requirements(
    model: cp_model.CpModel,
    variables: dict[tuple, cp_model.IntVar],
    data: dict
) -> None:
    """
    Lessons can only be assigned to rooms of the required type.

    If a subject requires a specific room type (e.g., Science needs a lab),
    the lesson can only be assigned to rooms of that type.
    """
    lessons = data["lessons"]
    rooms = data["rooms"]
    subjects = {s["id"]: s for s in data.get("subjects", [])}
    num_days = data.get("num_days", 5)
    num_periods = data.get("num_periods", 6)

    # Build room type map
    room_types: dict[str, Optional[str]] = {r["id"]: r.get("type") for r in rooms}

    for lesson in lessons:
        lesson_id = lesson["id"]
        subject_id = lesson["subject_id"]
        subject = subjects.get(subject_id, {})
        required_type = subject.get("required_room_type")

        if not required_type:
            continue  # No room type requirement

        # Forbid assignment to rooms of wrong type
        for day in range(num_days):
            for period in range(1, num_periods + 1):
                for room in rooms:
                    room_id = room["id"]
                    room_type = room_types.get(room_id)

                    if room_type != required_type:
                        var = variables.get((lesson_id, day, period, room_id))
                        if var is not None:
                            model.Add(var == 0)
