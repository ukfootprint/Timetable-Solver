"""Core constraints that every timetable must satisfy."""

from __future__ import annotations
from ortools.sat.python import cp_model


def add_one_slot_per_lesson(
    model: cp_model.CpModel,
    variables: dict[tuple, cp_model.IntVar],
    data: dict
) -> None:
    """
    Each lesson must be assigned to exactly one slot and one room.

    This ensures every lesson appears in the timetable exactly once.
    """
    lessons = data["lessons"]
    rooms = data["rooms"]
    num_days = data.get("num_days", 5)
    num_periods = data.get("num_periods", 6)

    for lesson in lessons:
        lesson_id = lesson["id"]
        lesson_vars = []

        for day in range(num_days):
            for period in range(1, num_periods + 1):
                for room in rooms:
                    room_id = room["id"]
                    var = variables.get((lesson_id, day, period, room_id))
                    if var is not None:
                        lesson_vars.append(var)

        # Exactly one assignment per lesson
        model.AddExactlyOne(lesson_vars)


def add_teacher_no_overlap(
    model: cp_model.CpModel,
    variables: dict[tuple, cp_model.IntVar],
    data: dict
) -> None:
    """
    A teacher cannot teach two lessons at the same time.

    For each teacher and each time slot, at most one of their lessons
    can be assigned to that slot.
    """
    lessons = data["lessons"]
    rooms = data["rooms"]
    num_days = data.get("num_days", 5)
    num_periods = data.get("num_periods", 6)

    # Group lessons by teacher
    teacher_lessons: dict[str, list[str]] = {}
    for lesson in lessons:
        teacher_id = lesson["teacher_id"]
        if teacher_id not in teacher_lessons:
            teacher_lessons[teacher_id] = []
        teacher_lessons[teacher_id].append(lesson["id"])

    # For each teacher and time slot, at most one lesson
    for teacher_id, lesson_ids in teacher_lessons.items():
        if len(lesson_ids) <= 1:
            continue

        for day in range(num_days):
            for period in range(1, num_periods + 1):
                slot_vars = []
                for lesson_id in lesson_ids:
                    for room in rooms:
                        room_id = room["id"]
                        var = variables.get((lesson_id, day, period, room_id))
                        if var is not None:
                            slot_vars.append(var)

                if len(slot_vars) > 1:
                    model.AddAtMostOne(slot_vars)


def add_room_no_overlap(
    model: cp_model.CpModel,
    variables: dict[tuple, cp_model.IntVar],
    data: dict
) -> None:
    """
    A room cannot host two lessons at the same time.

    For each room and each time slot, at most one lesson can be assigned.
    """
    lessons = data["lessons"]
    rooms = data["rooms"]
    num_days = data.get("num_days", 5)
    num_periods = data.get("num_periods", 6)

    for room in rooms:
        room_id = room["id"]
        for day in range(num_days):
            for period in range(1, num_periods + 1):
                slot_vars = []
                for lesson in lessons:
                    lesson_id = lesson["id"]
                    var = variables.get((lesson_id, day, period, room_id))
                    if var is not None:
                        slot_vars.append(var)

                if len(slot_vars) > 1:
                    model.AddAtMostOne(slot_vars)


def add_group_no_overlap(
    model: cp_model.CpModel,
    variables: dict[tuple, cp_model.IntVar],
    data: dict
) -> None:
    """
    A student group cannot have two lessons at the same time.

    For each group and each time slot, at most one lesson can be assigned.
    """
    lessons = data["lessons"]
    rooms = data["rooms"]
    num_days = data.get("num_days", 5)
    num_periods = data.get("num_periods", 6)

    # Group lessons by student group
    group_lessons: dict[str, list[str]] = {}
    for lesson in lessons:
        group_id = lesson["group_id"]
        if group_id not in group_lessons:
            group_lessons[group_id] = []
        group_lessons[group_id].append(lesson["id"])

    # For each group and time slot, at most one lesson
    for group_id, lesson_ids in group_lessons.items():
        if len(lesson_ids) <= 1:
            continue

        for day in range(num_days):
            for period in range(1, num_periods + 1):
                slot_vars = []
                for lesson_id in lesson_ids:
                    for room in rooms:
                        room_id = room["id"]
                        var = variables.get((lesson_id, day, period, room_id))
                        if var is not None:
                            slot_vars.append(var)

                if len(slot_vars) > 1:
                    model.AddAtMostOne(slot_vars)
