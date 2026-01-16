"""
No-overlap constraints for timetabling.

This module provides constraints that prevent double-booking of:
- Teachers (cannot teach two lessons at the same time)
- Classes (cannot have two lessons at the same time)
- Rooms (cannot host two lessons at the same time)

All constraints use CP-SAT's AddNoOverlap which efficiently handles
interval variables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from solver.model_builder import TimetableModelBuilder, LessonInstanceVars
    from solver.data.models import Room, Lesson


@dataclass
class NoOverlapStats:
    """Statistics about no-overlap constraints added."""
    teacher_constraints: int = 0
    teacher_intervals: int = 0
    class_constraints: int = 0
    class_intervals: int = 0
    room_constraints: int = 0
    room_optional_intervals: int = 0


def add_teacher_no_overlap(builder: TimetableModelBuilder) -> int:
    """
    Add no-overlap constraints for teachers.

    Groups all lesson intervals by teacher and adds a NoOverlap constraint
    for each teacher, ensuring they cannot teach two lessons simultaneously.

    Args:
        builder: The timetable model builder with created variables

    Returns:
        Number of NoOverlap constraints added
    """
    constraints_added = 0

    for teacher in builder.input.teachers:
        intervals = _get_teacher_intervals(builder, teacher.id)

        if len(intervals) > 1:
            builder.model.AddNoOverlap(intervals)
            constraints_added += 1

    return constraints_added


def add_class_no_overlap(builder: TimetableModelBuilder) -> int:
    """
    Add no-overlap constraints for classes.

    Groups all lesson intervals by class and adds a NoOverlap constraint
    for each class, ensuring they cannot have two lessons simultaneously.

    Args:
        builder: The timetable model builder with created variables

    Returns:
        Number of NoOverlap constraints added
    """
    constraints_added = 0

    for cls in builder.input.classes:
        intervals = _get_class_intervals(builder, cls.id)

        if len(intervals) > 1:
            builder.model.AddNoOverlap(intervals)
            constraints_added += 1

    return constraints_added


def add_room_no_overlap(builder: TimetableModelBuilder) -> int:
    """
    Add no-overlap constraints for rooms.

    This is more complex than teacher/class constraints because room assignment
    is a variable (room_var). We use optional intervals that are only active
    when a lesson is assigned to that specific room.

    For each room:
    1. Create optional intervals for each lesson that could use that room
    2. Link the optional interval's presence to (room_var == room_index)
    3. Add NoOverlap on all optional intervals for that room

    Args:
        builder: The timetable model builder with created variables

    Returns:
        Number of NoOverlap constraints added
    """
    constraints_added = 0

    for room_idx, room in enumerate(builder.input.rooms):
        optional_intervals = _create_room_optional_intervals(
            builder, room, room_idx
        )

        if len(optional_intervals) > 1:
            builder.model.AddNoOverlap(optional_intervals)
            constraints_added += 1

    return constraints_added


def add_all_no_overlap_constraints(
    builder: TimetableModelBuilder
) -> NoOverlapStats:
    """
    Add all no-overlap constraints (teachers, classes, and rooms).

    This is a convenience function that adds all three types of
    no-overlap constraints and returns statistics.

    Args:
        builder: The timetable model builder with created variables

    Returns:
        NoOverlapStats with counts of constraints added
    """
    stats = NoOverlapStats()

    # Teacher no-overlap
    stats.teacher_constraints = add_teacher_no_overlap(builder)
    stats.teacher_intervals = sum(
        len(_get_teacher_intervals(builder, t.id))
        for t in builder.input.teachers
    )

    # Class no-overlap
    stats.class_constraints = add_class_no_overlap(builder)
    stats.class_intervals = sum(
        len(_get_class_intervals(builder, c.id))
        for c in builder.input.classes
    )

    # Room no-overlap
    stats.room_constraints = add_room_no_overlap(builder)
    stats.room_optional_intervals = _count_room_optional_intervals(builder)

    return stats


# =============================================================================
# Helper Functions
# =============================================================================

def _get_teacher_intervals(
    builder: TimetableModelBuilder,
    teacher_id: str
) -> list[cp_model.IntervalVar]:
    """
    Get all interval variables for lessons taught by a specific teacher.

    Args:
        builder: The model builder
        teacher_id: ID of the teacher

    Returns:
        List of IntervalVar for all lesson instances of this teacher
    """
    intervals = []

    for lesson in builder.input.lessons:
        if lesson.teacher_id == teacher_id:
            for inst in builder.lesson_vars.get(lesson.id, []):
                intervals.append(inst.interval_var)

    return intervals


def _get_class_intervals(
    builder: TimetableModelBuilder,
    class_id: str
) -> list[cp_model.IntervalVar]:
    """
    Get all interval variables for lessons of a specific class.

    Args:
        builder: The model builder
        class_id: ID of the class

    Returns:
        List of IntervalVar for all lesson instances of this class
    """
    intervals = []

    for lesson in builder.input.lessons:
        if lesson.class_id == class_id:
            for inst in builder.lesson_vars.get(lesson.id, []):
                intervals.append(inst.interval_var)

    return intervals


def _is_room_valid_for_lesson(
    builder: TimetableModelBuilder,
    room: Room,
    lesson: Lesson
) -> bool:
    """
    Check if a room is valid for a lesson based on type requirements.

    Args:
        builder: The model builder (for access to subjects)
        room: The room to check
        lesson: The lesson to check

    Returns:
        True if the room can host this lesson
    """
    # Check excluded rooms from lesson requirement
    if lesson.room_requirement and room.id in lesson.room_requirement.excluded_rooms:
        return False

    # Determine required room type
    required_type = None

    # First check lesson's explicit room requirement
    if lesson.room_requirement and lesson.room_requirement.room_type:
        required_type = lesson.room_requirement.room_type
    else:
        # Then check subject's room requirement
        subject = builder.input.get_subject(lesson.subject_id)
        if subject and subject.requires_specialist_room:
            required_type = subject.required_room_type

    # If there's a required type, room must match
    if required_type and room.type != required_type:
        return False

    return True


def _create_room_optional_intervals(
    builder: TimetableModelBuilder,
    room: Room,
    room_idx: int
) -> list[cp_model.IntervalVar]:
    """
    Create optional intervals for a room.

    For each lesson that could potentially use this room, creates an optional
    interval that is active only when room_var equals this room's index.

    Args:
        builder: The model builder
        room: The room
        room_idx: Index of the room in the rooms list

    Returns:
        List of optional IntervalVar for this room
    """
    optional_intervals = []

    for lesson_id, instances in builder.lesson_vars.items():
        lesson = builder.input.get_lesson(lesson_id)
        if not lesson:
            continue

        # Skip if this room can't host this lesson
        if not _is_room_valid_for_lesson(builder, room, lesson):
            continue

        for inst in instances:
            # Create boolean: is this lesson instance assigned to this room?
            is_in_room = builder.model.NewBoolVar(
                f"L{lesson_id}_I{inst.instance}_in_R{room.id}"
            )

            # Link boolean to room_var:
            # is_in_room == True  <=> room_var == room_idx
            # is_in_room == False <=> room_var != room_idx
            builder.model.Add(
                inst.room_var == room_idx
            ).OnlyEnforceIf(is_in_room)

            builder.model.Add(
                inst.room_var != room_idx
            ).OnlyEnforceIf(is_in_room.Not())

            # Create optional interval that exists only when lesson is in this room
            optional_interval = builder.model.NewOptionalIntervalVar(
                inst.start_var,
                inst.duration,
                inst.end_var,
                is_in_room,
                f"L{lesson_id}_I{inst.instance}_R{room.id}_opt_interval"
            )

            optional_intervals.append(optional_interval)

    return optional_intervals


def _count_room_optional_intervals(builder: TimetableModelBuilder) -> int:
    """Count total optional intervals that would be created for rooms."""
    count = 0

    for room_idx, room in enumerate(builder.input.rooms):
        for lesson_id, instances in builder.lesson_vars.items():
            lesson = builder.input.get_lesson(lesson_id)
            if not lesson:
                continue

            if _is_room_valid_for_lesson(builder, room, lesson):
                count += len(instances)

    return count
