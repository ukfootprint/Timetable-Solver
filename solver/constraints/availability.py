"""
Availability constraints for timetabling.

This module provides constraints for:
- Teacher unavailability (teachers can't teach during specified times)
- School day boundaries (lessons within school hours)
- Break time avoidance (lessons can't overlap with breaks)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from solver.model_builder import TimetableModelBuilder, LessonInstanceVars
    from solver.data.models import Availability, Period


# =============================================================================
# Constants
# =============================================================================

MINUTES_PER_DAY = 1440


# =============================================================================
# Statistics
# =============================================================================

@dataclass
class AvailabilityStats:
    """Statistics about availability constraints added."""
    teacher_unavailability_constraints: int = 0
    teachers_with_unavailability: int = 0
    class_unavailability_constraints: int = 0
    room_unavailability_constraints: int = 0
    school_day_constraints: int = 0
    break_avoidance_constraints: int = 0


# =============================================================================
# Helper Functions
# =============================================================================

def day_minutes_to_week_minutes(day: int, minutes: int) -> int:
    """
    Convert day and minutes-from-midnight to week minutes.

    Args:
        day: Day of week (0=Monday, 4=Friday)
        minutes: Minutes from midnight on that day

    Returns:
        Minutes from start of week (Monday 00:00)

    Example:
        >>> day_minutes_to_week_minutes(0, 540)  # Monday 9:00
        540
        >>> day_minutes_to_week_minutes(1, 540)  # Tuesday 9:00
        1980
    """
    return day * MINUTES_PER_DAY + minutes


# =============================================================================
# Teacher Unavailability Constraints
# =============================================================================

def add_teacher_unavailability(builder: TimetableModelBuilder) -> int:
    """
    Add constraints preventing teachers from teaching during unavailable times.

    For each teacher's unavailability window:
    1. Convert to week minute range
    2. For each lesson taught by that teacher:
       - Add constraint: lesson_end <= unavail_start OR lesson_start >= unavail_end

    Uses reified constraints with AddBoolOr for the OR logic.

    Args:
        builder: The timetable model builder with created variables

    Returns:
        Number of constraints added
    """
    constraints_added = 0

    for teacher in builder.input.teachers:
        if not teacher.availability:
            continue

        # Build list of unavailable week-minute ranges
        unavailable_ranges = _get_unavailable_ranges(teacher.availability)

        if not unavailable_ranges:
            continue

        # Get all lessons for this teacher
        teacher_lessons = builder.input.get_teacher_lessons(teacher.id)

        for lesson in teacher_lessons:
            instances = builder.lesson_vars.get(lesson.id, [])

            for inst in instances:
                for unavail_start, unavail_end in unavailable_ranges:
                    _add_no_overlap_with_range(
                        builder.model,
                        inst,
                        unavail_start,
                        unavail_end,
                        f"T{teacher.id}_unavail_{unavail_start}"
                    )
                    constraints_added += 1

    return constraints_added


def _get_unavailable_ranges(
    availability: list[Availability]
) -> list[tuple[int, int]]:
    """
    Extract unavailable time ranges from availability list.

    Args:
        availability: List of Availability objects

    Returns:
        List of (week_start_minutes, week_end_minutes) for unavailable periods
    """
    ranges = []

    for avail in availability:
        if not avail.available:
            week_start = day_minutes_to_week_minutes(avail.day, avail.start_minutes)
            week_end = day_minutes_to_week_minutes(avail.day, avail.end_minutes)
            ranges.append((week_start, week_end))

    return ranges


def _add_no_overlap_with_range(
    model: cp_model.CpModel,
    inst: LessonInstanceVars,
    range_start: int,
    range_end: int,
    name_prefix: str
) -> None:
    """
    Add constraint that a lesson instance doesn't overlap with a time range.

    The constraint is: lesson_end <= range_start OR lesson_start >= range_end

    This is implemented using reified constraints:
    - ends_before = (lesson_end <= range_start)
    - starts_after = (lesson_start >= range_end)
    - AddBoolOr([ends_before, starts_after])

    Args:
        model: The CP-SAT model
        inst: Lesson instance variables
        range_start: Start of forbidden range (week minutes)
        range_end: End of forbidden range (week minutes)
        name_prefix: Prefix for variable names
    """
    # Create boolean for "lesson ends before range starts"
    ends_before = model.NewBoolVar(
        f"{name_prefix}_L{inst.lesson_id}_I{inst.instance}_ends_before"
    )

    # Create boolean for "lesson starts after range ends"
    starts_after = model.NewBoolVar(
        f"{name_prefix}_L{inst.lesson_id}_I{inst.instance}_starts_after"
    )

    # Reify: ends_before <=> (end_var <= range_start)
    model.Add(inst.end_var <= range_start).OnlyEnforceIf(ends_before)
    model.Add(inst.end_var > range_start).OnlyEnforceIf(ends_before.Not())

    # Reify: starts_after <=> (start_var >= range_end)
    model.Add(inst.start_var >= range_end).OnlyEnforceIf(starts_after)
    model.Add(inst.start_var < range_end).OnlyEnforceIf(starts_after.Not())

    # At least one must be true (no overlap)
    model.AddBoolOr([ends_before, starts_after])


# =============================================================================
# School Day Constraints
# =============================================================================

def add_school_day_constraints(builder: TimetableModelBuilder) -> int:
    """
    Add constraints ensuring lessons occur within school day boundaries.

    For each day:
    1. Find the earliest start and latest end from schedulable periods
    2. For lessons on that day, ensure they fit within boundaries

    Args:
        builder: The timetable model builder with created variables

    Returns:
        Number of constraints added
    """
    constraints_added = 0

    # Get school day boundaries for each day
    day_boundaries = _get_day_boundaries(builder.input.get_schedulable_periods())

    if not day_boundaries:
        return 0

    # For each lesson instance, constrain to school hours based on its day
    for lesson_id, instances in builder.lesson_vars.items():
        for inst in instances:
            constraints_added += _add_day_boundary_constraints(
                builder.model,
                inst,
                day_boundaries,
                builder.input.config.num_days
            )

    return constraints_added


def _get_day_boundaries(
    periods: list[Period]
) -> dict[int, tuple[int, int]]:
    """
    Get school day start/end times for each day.

    Args:
        periods: List of schedulable periods

    Returns:
        Dict mapping day -> (earliest_start_minutes, latest_end_minutes)
    """
    boundaries: dict[int, tuple[int, int]] = {}

    for period in periods:
        day = period.day
        start = period.start_minutes
        end = period.end_minutes

        if day not in boundaries:
            boundaries[day] = (start, end)
        else:
            current_start, current_end = boundaries[day]
            boundaries[day] = (min(start, current_start), max(end, current_end))

    return boundaries


def _add_day_boundary_constraints(
    model: cp_model.CpModel,
    inst: LessonInstanceVars,
    day_boundaries: dict[int, tuple[int, int]],
    num_days: int
) -> int:
    """
    Add constraints that lesson respects school day boundaries.

    For each possible day, if the lesson is on that day, it must fit
    within that day's school hours.

    Args:
        model: The CP-SAT model
        inst: Lesson instance variables
        day_boundaries: Dict of day -> (start, end) boundaries
        num_days: Number of school days

    Returns:
        Number of constraints added
    """
    constraints_added = 0

    for day in range(num_days):
        if day not in day_boundaries:
            continue

        day_start, day_end = day_boundaries[day]

        # Convert to week minutes
        week_day_start = day_minutes_to_week_minutes(day, day_start)
        week_day_end = day_minutes_to_week_minutes(day, day_end)

        # Create boolean for "lesson is on this day"
        is_on_day = model.NewBoolVar(
            f"L{inst.lesson_id}_I{inst.instance}_on_day{day}_boundary"
        )

        model.Add(inst.day_var == day).OnlyEnforceIf(is_on_day)
        model.Add(inst.day_var != day).OnlyEnforceIf(is_on_day.Not())

        # If on this day, must be within boundaries
        # start >= day_start AND end <= day_end
        model.Add(inst.start_var >= week_day_start).OnlyEnforceIf(is_on_day)
        model.Add(inst.end_var <= week_day_end).OnlyEnforceIf(is_on_day)

        constraints_added += 1

    return constraints_added


# =============================================================================
# Break Time Constraints
# =============================================================================

def add_break_avoidance(builder: TimetableModelBuilder) -> int:
    """
    Add constraints preventing lessons from overlapping with break times.

    For each break period, ensure no lesson overlaps with it.

    Args:
        builder: The timetable model builder with created variables

    Returns:
        Number of constraints added
    """
    constraints_added = 0

    # Get all break periods
    break_periods = [p for p in builder.input.periods if p.is_break or p.is_lunch]

    if not break_periods:
        return 0

    for period in break_periods:
        break_start = day_minutes_to_week_minutes(period.day, period.start_minutes)
        break_end = day_minutes_to_week_minutes(period.day, period.end_minutes)

        for lesson_id, instances in builder.lesson_vars.items():
            for inst in instances:
                # Add constraint: don't overlap with this break
                _add_no_overlap_with_range(
                    builder.model,
                    inst,
                    break_start,
                    break_end,
                    f"break_{period.id}"
                )
                constraints_added += 1

    return constraints_added


# =============================================================================
# Class Unavailability Constraints
# =============================================================================

def add_class_unavailability(builder: TimetableModelBuilder) -> int:
    """
    Add constraints preventing classes from having lessons during unavailable times.

    Similar to teacher unavailability but for student classes.

    Args:
        builder: The timetable model builder with created variables

    Returns:
        Number of constraints added
    """
    constraints_added = 0

    for cls in builder.input.classes:
        if not cls.availability:
            continue

        # Build list of unavailable week-minute ranges
        unavailable_ranges = _get_unavailable_ranges(cls.availability)

        if not unavailable_ranges:
            continue

        # Get all lessons for this class
        class_lessons = builder.input.get_class_lessons(cls.id)

        for lesson in class_lessons:
            instances = builder.lesson_vars.get(lesson.id, [])

            for inst in instances:
                for unavail_start, unavail_end in unavailable_ranges:
                    _add_no_overlap_with_range(
                        builder.model,
                        inst,
                        unavail_start,
                        unavail_end,
                        f"C{cls.id}_unavail_{unavail_start}"
                    )
                    constraints_added += 1

    return constraints_added


# =============================================================================
# Room Unavailability Constraints
# =============================================================================

def add_room_unavailability(builder: TimetableModelBuilder) -> int:
    """
    Add constraints preventing lessons in rooms during unavailable times.

    For each room with unavailability, if a lesson is assigned to that room,
    it must not overlap with the room's unavailable times.

    Args:
        builder: The timetable model builder with created variables

    Returns:
        Number of constraints added
    """
    constraints_added = 0

    for room_idx, room in enumerate(builder.input.rooms):
        if not room.availability:
            continue

        # Build list of unavailable week-minute ranges
        unavailable_ranges = _get_unavailable_ranges(room.availability)

        if not unavailable_ranges:
            continue

        # For each lesson instance that could use this room
        for lesson_id, instances in builder.lesson_vars.items():
            lesson = builder.input.get_lesson(lesson_id)
            if not lesson:
                continue

            for inst in instances:
                for unavail_start, unavail_end in unavailable_ranges:
                    # Create boolean for "lesson is in this room"
                    is_in_room = builder.model.NewBoolVar(
                        f"L{lesson_id}_I{inst.instance}_in_R{room.id}_unavail_{unavail_start}"
                    )

                    builder.model.Add(inst.room_var == room_idx).OnlyEnforceIf(is_in_room)
                    builder.model.Add(inst.room_var != room_idx).OnlyEnforceIf(is_in_room.Not())

                    # If in this room, must not overlap with unavailability
                    _add_conditional_no_overlap(
                        builder.model,
                        inst,
                        unavail_start,
                        unavail_end,
                        is_in_room,
                        f"R{room.id}_unavail_{unavail_start}"
                    )
                    constraints_added += 1

    return constraints_added


def _add_conditional_no_overlap(
    model: cp_model.CpModel,
    inst: LessonInstanceVars,
    range_start: int,
    range_end: int,
    condition: cp_model.IntVar,
    name_prefix: str
) -> None:
    """
    Add constraint that lesson doesn't overlap range, only if condition is true.

    The constraint is: IF condition THEN (lesson_end <= range_start OR lesson_start >= range_end)

    Args:
        model: The CP-SAT model
        inst: Lesson instance variables
        range_start: Start of forbidden range (week minutes)
        range_end: End of forbidden range (week minutes)
        condition: Boolean that must be true for constraint to apply
        name_prefix: Prefix for variable names
    """
    # Create boolean for "lesson ends before range starts"
    ends_before = model.NewBoolVar(
        f"{name_prefix}_L{inst.lesson_id}_I{inst.instance}_ends_before"
    )

    # Create boolean for "lesson starts after range ends"
    starts_after = model.NewBoolVar(
        f"{name_prefix}_L{inst.lesson_id}_I{inst.instance}_starts_after"
    )

    # Reify: ends_before <=> (end_var <= range_start)
    model.Add(inst.end_var <= range_start).OnlyEnforceIf(ends_before)
    model.Add(inst.end_var > range_start).OnlyEnforceIf(ends_before.Not())

    # Reify: starts_after <=> (start_var >= range_end)
    model.Add(inst.start_var >= range_end).OnlyEnforceIf(starts_after)
    model.Add(inst.start_var < range_end).OnlyEnforceIf(starts_after.Not())

    # If condition is true, at least one must be true (no overlap)
    # This is: condition => (ends_before OR starts_after)
    # Which is: NOT(condition) OR ends_before OR starts_after
    model.AddBoolOr([condition.Not(), ends_before, starts_after])


# =============================================================================
# Combined Function
# =============================================================================

def add_all_availability_constraints(
    builder: TimetableModelBuilder
) -> AvailabilityStats:
    """
    Add all availability-related constraints.

    This is a convenience function that adds:
    - Teacher unavailability
    - Class unavailability
    - Room unavailability
    - School day boundaries
    - Break avoidance

    Args:
        builder: The timetable model builder with created variables

    Returns:
        AvailabilityStats with counts of constraints added
    """
    stats = AvailabilityStats()

    # Count teachers with unavailability
    stats.teachers_with_unavailability = sum(
        1 for t in builder.input.teachers
        if t.availability and any(not a.available for a in t.availability)
    )

    # Add constraints
    stats.teacher_unavailability_constraints = add_teacher_unavailability(builder)
    stats.class_unavailability_constraints = add_class_unavailability(builder)
    stats.room_unavailability_constraints = add_room_unavailability(builder)
    stats.school_day_constraints = add_school_day_constraints(builder)
    stats.break_avoidance_constraints = add_break_avoidance(builder)

    return stats
