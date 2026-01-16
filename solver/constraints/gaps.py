"""
Gap minimization constraints for timetabling.

This module provides soft constraints to minimize gaps in schedules:
- Teacher schedule compactness (lessons grouped together)
- Class schedule compactness
- Minimizing idle time between lessons
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from solver.model_builder import TimetableModelBuilder, LessonInstanceVars


# =============================================================================
# Constants
# =============================================================================

MINUTES_PER_DAY = 1440


# =============================================================================
# Statistics
# =============================================================================

@dataclass
class GapStats:
    """Statistics about gap constraints added."""
    teachers_with_gap_constraints: int = 0
    teacher_gap_penalties: int = 0
    classes_with_gap_constraints: int = 0
    class_gap_penalties: int = 0


# =============================================================================
# Teacher Gap Minimization
# =============================================================================

def add_teacher_gap_minimization(
    builder: TimetableModelBuilder,
    weight: int = 2,
    min_lessons_for_gap: int = 2
) -> int:
    """
    Add soft constraints to minimize gaps in teacher schedules.

    For each teacher and each day:
    1. Identify which lessons are on that day using indicators
    2. Calculate: gap = (latest_end - earliest_start) - total_teaching_time
    3. Add gap as penalty (encourages compact schedules)

    Implementation:
    - For each lesson on day: create is_on_day indicator
    - Use conditional min/max for earliest start and latest end
    - Gap only counted if teacher has >= min_lessons_for_gap lessons on day

    Args:
        builder: The timetable model builder with created variables
        weight: Penalty weight per minute of gap
        min_lessons_for_gap: Minimum lessons on a day to count gaps

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0
    num_days = builder.input.config.num_days

    for teacher in builder.input.teachers:
        # Get all lesson instances for this teacher
        teacher_instances = _get_teacher_instances(builder, teacher.id)

        if len(teacher_instances) < min_lessons_for_gap:
            # Not enough lessons to have gaps
            continue

        for day in range(num_days):
            penalty_var = _create_day_gap_constraint(
                builder,
                teacher_instances,
                day,
                f"T{teacher.id}",
                min_lessons_for_gap
            )

            if penalty_var is not None:
                builder.penalty_vars.append(PenaltyVar(
                    name=f"teacher_gap_{teacher.id}_day{day}",
                    var=penalty_var,
                    weight=weight,
                    description=f"Gap in {teacher.name}'s schedule on day {day}"
                ))
                penalties_added += 1

    return penalties_added


def _create_day_gap_constraint(
    builder: TimetableModelBuilder,
    instances: list[LessonInstanceVars],
    day: int,
    prefix: str,
    min_lessons: int
) -> cp_model.IntVar | None:
    """
    Create gap constraint for a set of lesson instances on a specific day.

    Returns:
        Gap variable if constraint was created, None otherwise
    """
    if len(instances) < min_lessons:
        return None

    model = builder.model
    day_offset = day * MINUTES_PER_DAY

    # Create indicator variables for each instance being on this day
    day_indicators = []
    instance_data = []  # (indicator, start_var, end_var, duration)

    for inst in instances:
        is_on_day = model.NewBoolVar(f"{prefix}_L{inst.lesson_id}_I{inst.instance}_day{day}_gap")

        model.Add(inst.day_var == day).OnlyEnforceIf(is_on_day)
        model.Add(inst.day_var != day).OnlyEnforceIf(is_on_day.Not())

        day_indicators.append(is_on_day)
        instance_data.append((is_on_day, inst.start_var, inst.end_var, inst.duration))

    # Count lessons on this day
    num_on_day = model.NewIntVar(0, len(instances), f"{prefix}_day{day}_count_gap")
    model.Add(num_on_day == sum(day_indicators))

    # Check if we have enough lessons to calculate a gap
    has_enough = model.NewBoolVar(f"{prefix}_day{day}_has_enough")
    model.Add(num_on_day >= min_lessons).OnlyEnforceIf(has_enough)
    model.Add(num_on_day < min_lessons).OnlyEnforceIf(has_enough.Not())

    # For min/max calculations, we use sentinel values for lessons not on this day
    # Min: use MINUTES_PER_DAY for lessons not on day (won't be minimum)
    # Max: use 0 for lessons not on day (won't be maximum)
    conditional_starts = []
    conditional_ends = []

    for idx, (is_on_day, start_var, end_var, duration) in enumerate(instance_data):
        # Conditional start: if on day, use (start - day_offset); else use MINUTES_PER_DAY
        cond_start = model.NewIntVar(0, MINUTES_PER_DAY, f"{prefix}_cond_start_{idx}")

        # We need to handle the case where start_var might not be on this day
        # Use element constraint approach: cond_start = is_on_day ? (start - offset) : MINUTES_PER_DAY
        model.Add(cond_start == start_var - day_offset).OnlyEnforceIf(is_on_day)
        model.Add(cond_start == MINUTES_PER_DAY).OnlyEnforceIf(is_on_day.Not())
        conditional_starts.append(cond_start)

        # Conditional end: if on day, use (end - day_offset); else use 0
        cond_end = model.NewIntVar(0, MINUTES_PER_DAY, f"{prefix}_cond_end_{idx}")
        model.Add(cond_end == end_var - day_offset).OnlyEnforceIf(is_on_day)
        model.Add(cond_end == 0).OnlyEnforceIf(is_on_day.Not())
        conditional_ends.append(cond_end)

    # Calculate min start (smallest among lessons actually on this day)
    min_start = model.NewIntVar(0, MINUTES_PER_DAY, f"{prefix}_day{day}_min_start")
    model.AddMinEquality(min_start, conditional_starts)

    # Calculate max end (largest among lessons actually on this day)
    max_end = model.NewIntVar(0, MINUTES_PER_DAY, f"{prefix}_day{day}_max_end")
    model.AddMaxEquality(max_end, conditional_ends)

    # Calculate total teaching time on this day
    teaching_contributions = []
    for idx, (is_on_day, start_var, end_var, duration) in enumerate(instance_data):
        contrib = model.NewIntVar(0, duration, f"{prefix}_contrib_{idx}")
        model.Add(contrib == duration).OnlyEnforceIf(is_on_day)
        model.Add(contrib == 0).OnlyEnforceIf(is_on_day.Not())
        teaching_contributions.append(contrib)

    total_teaching = model.NewIntVar(0, MINUTES_PER_DAY, f"{prefix}_day{day}_teaching")
    model.Add(total_teaching == sum(teaching_contributions))

    # Calculate span = max_end - min_start (could be negative if no lessons)
    span = model.NewIntVar(-MINUTES_PER_DAY, MINUTES_PER_DAY, f"{prefix}_day{day}_span")
    model.Add(span == max_end - min_start)

    # Calculate gap = max(0, span - total_teaching)
    raw_gap = model.NewIntVar(-MINUTES_PER_DAY, MINUTES_PER_DAY, f"{prefix}_day{day}_raw_gap")
    model.Add(raw_gap == span - total_teaching)

    gap = model.NewIntVar(0, MINUTES_PER_DAY, f"{prefix}_day{day}_gap")
    model.AddMaxEquality(gap, [0, raw_gap])

    # Only count gap if we have enough lessons on this day
    final_gap = model.NewIntVar(0, MINUTES_PER_DAY, f"{prefix}_day{day}_final_gap")
    model.Add(final_gap == gap).OnlyEnforceIf(has_enough)
    model.Add(final_gap == 0).OnlyEnforceIf(has_enough.Not())

    return final_gap


def _get_teacher_instances(
    builder: TimetableModelBuilder,
    teacher_id: str
) -> list[LessonInstanceVars]:
    """Get all lesson instances for a teacher."""
    instances = []
    for lesson in builder.input.lessons:
        if lesson.teacher_id == teacher_id:
            instances.extend(builder.lesson_vars.get(lesson.id, []))
    return instances


# =============================================================================
# Class Gap Minimization
# =============================================================================

def add_class_gap_minimization(
    builder: TimetableModelBuilder,
    weight: int = 2,
    min_lessons_for_gap: int = 2
) -> int:
    """
    Add soft constraints to minimize gaps in class schedules.

    Similar to teacher gap minimization but for student classes.

    Args:
        builder: The timetable model builder with created variables
        weight: Penalty weight per minute of gap
        min_lessons_for_gap: Minimum lessons on a day to count gaps

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0
    num_days = builder.input.config.num_days

    for cls in builder.input.classes:
        # Get all lesson instances for this class
        class_instances = _get_class_instances(builder, cls.id)

        if len(class_instances) < min_lessons_for_gap:
            continue

        for day in range(num_days):
            penalty_var = _create_day_gap_constraint(
                builder,
                class_instances,
                day,
                f"C{cls.id}",
                min_lessons_for_gap
            )

            if penalty_var is not None:
                builder.penalty_vars.append(PenaltyVar(
                    name=f"class_gap_{cls.id}_day{day}",
                    var=penalty_var,
                    weight=weight,
                    description=f"Gap in {cls.name}'s schedule on day {day}"
                ))
                penalties_added += 1

    return penalties_added


def _get_class_instances(
    builder: TimetableModelBuilder,
    class_id: str
) -> list[LessonInstanceVars]:
    """Get all lesson instances for a class."""
    instances = []
    for lesson in builder.input.lessons:
        if lesson.class_id == class_id:
            instances.extend(builder.lesson_vars.get(lesson.id, []))
    return instances


# =============================================================================
# Early/Late Preference Constraints
# =============================================================================

def add_early_finish_preference(
    builder: TimetableModelBuilder,
    weight: int = 1
) -> int:
    """
    Add soft constraint preferring earlier finish times.

    Penalizes lessons scheduled late in the day.

    Args:
        builder: The timetable model builder
        weight: Penalty weight per hour of late scheduling

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0
    num_days = builder.input.config.num_days

    for teacher in builder.input.teachers:
        teacher_instances = _get_teacher_instances(builder, teacher.id)

        if not teacher_instances:
            continue

        for day in range(num_days):
            # Find latest end time on this day
            day_offset = day * MINUTES_PER_DAY

            conditional_ends = []
            day_indicators = []

            for inst in teacher_instances:
                is_on_day = builder.model.NewBoolVar(
                    f"T{teacher.id}_L{inst.lesson_id}_I{inst.instance}_day{day}_late"
                )
                builder.model.Add(inst.day_var == day).OnlyEnforceIf(is_on_day)
                builder.model.Add(inst.day_var != day).OnlyEnforceIf(is_on_day.Not())

                day_indicators.append(is_on_day)

                # End time relative to day
                cond_end = builder.model.NewIntVar(
                    0, MINUTES_PER_DAY,
                    f"T{teacher.id}_cond_end_day{day}_{len(conditional_ends)}"
                )

                day_rel_end = builder.model.NewIntVar(0, MINUTES_PER_DAY, f"rel_end_{len(conditional_ends)}")
                builder.model.Add(day_rel_end == inst.end_var - day_offset).OnlyEnforceIf(is_on_day)
                builder.model.Add(day_rel_end == 0).OnlyEnforceIf(is_on_day.Not())

                builder.model.Add(cond_end == day_rel_end).OnlyEnforceIf(is_on_day)
                builder.model.Add(cond_end == 0).OnlyEnforceIf(is_on_day.Not())

                conditional_ends.append(cond_end)

            if not conditional_ends:
                continue

            # Check if any lessons on this day
            has_lessons = builder.model.NewBoolVar(f"T{teacher.id}_day{day}_has_late")
            builder.model.AddBoolOr(day_indicators).OnlyEnforceIf(has_lessons)
            builder.model.AddBoolAnd([i.Not() for i in day_indicators]).OnlyEnforceIf(has_lessons.Not())

            # Latest end time
            latest_end = builder.model.NewIntVar(0, MINUTES_PER_DAY, f"T{teacher.id}_day{day}_latest")
            builder.model.AddMaxEquality(latest_end, conditional_ends)

            # Calculate "lateness" penalty (end time beyond a threshold, e.g., 15:00 = 900 minutes)
            # Penalty increases for each hour after 15:00
            threshold = 900  # 15:00
            late_minutes = builder.model.NewIntVar(
                0, MINUTES_PER_DAY - threshold,
                f"T{teacher.id}_day{day}_late_mins"
            )
            builder.model.AddMaxEquality(late_minutes, [0, latest_end - threshold])

            # Only penalize if teacher has lessons on this day
            final_penalty = builder.model.NewIntVar(
                0, MINUTES_PER_DAY - threshold,
                f"T{teacher.id}_day{day}_late_penalty"
            )
            builder.model.Add(final_penalty == late_minutes).OnlyEnforceIf(has_lessons)
            builder.model.Add(final_penalty == 0).OnlyEnforceIf(has_lessons.Not())

            # Convert to hours for reasonable penalty scaling
            # (divide by 60, but we'll just use lower weight)
            builder.penalty_vars.append(PenaltyVar(
                name=f"late_finish_{teacher.id}_day{day}",
                var=final_penalty,
                weight=weight,
                description=f"Teacher {teacher.name} finishes late on day {day}"
            ))
            penalties_added += 1

    return penalties_added


# =============================================================================
# Consecutive Lessons Preference
# =============================================================================

def add_consecutive_lesson_preference(
    builder: TimetableModelBuilder,
    weight: int = 5
) -> int:
    """
    Add soft constraint preferring consecutive lessons (no gaps between).

    For each pair of lessons for the same teacher on the same day,
    penalizes gaps between them.

    Args:
        builder: The timetable model builder
        weight: Penalty weight for gaps between consecutive lessons

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0
    num_days = builder.input.config.num_days

    for teacher in builder.input.teachers:
        teacher_instances = _get_teacher_instances(builder, teacher.id)

        if len(teacher_instances) < 2:
            continue

        for day in range(num_days):
            day_offset = day * MINUTES_PER_DAY

            # For each pair of instances
            for i, inst1 in enumerate(teacher_instances):
                for inst2 in teacher_instances[i + 1:]:
                    # Both on same day
                    both_on_day = builder.model.NewBoolVar(
                        f"T{teacher.id}_L{inst1.lesson_id}{inst1.instance}_L{inst2.lesson_id}{inst2.instance}_day{day}"
                    )

                    inst1_on_day = builder.model.NewBoolVar(f"temp1_{i}_{day}")
                    inst2_on_day = builder.model.NewBoolVar(f"temp2_{i}_{day}")

                    builder.model.Add(inst1.day_var == day).OnlyEnforceIf(inst1_on_day)
                    builder.model.Add(inst1.day_var != day).OnlyEnforceIf(inst1_on_day.Not())

                    builder.model.Add(inst2.day_var == day).OnlyEnforceIf(inst2_on_day)
                    builder.model.Add(inst2.day_var != day).OnlyEnforceIf(inst2_on_day.Not())

                    builder.model.AddBoolAnd([inst1_on_day, inst2_on_day]).OnlyEnforceIf(both_on_day)
                    builder.model.AddBoolOr([inst1_on_day.Not(), inst2_on_day.Not()]).OnlyEnforceIf(both_on_day.Not())

                    # Calculate gap between them (absolute difference minus durations)
                    # Gap = |start1 - start2| - min(duration1, duration2) if adjacent
                    # Simpler: gap = max(start1, start2) - min(end1, end2) if positive

                    # min_end = min(end1, end2)
                    min_end = builder.model.NewIntVar(0, builder.week_minutes, f"min_end_{i}_{day}")
                    builder.model.AddMinEquality(min_end, [inst1.end_var, inst2.end_var])

                    # max_start = max(start1, start2)
                    max_start = builder.model.NewIntVar(0, builder.week_minutes, f"max_start_{i}_{day}")
                    builder.model.AddMaxEquality(max_start, [inst1.start_var, inst2.start_var])

                    # gap_between = max(0, max_start - min_end)
                    raw_gap = builder.model.NewIntVar(-builder.week_minutes, builder.week_minutes, f"raw_gap_{i}_{day}")
                    builder.model.Add(raw_gap == max_start - min_end)

                    gap_between = builder.model.NewIntVar(0, builder.week_minutes, f"gap_between_{i}_{day}")
                    builder.model.AddMaxEquality(gap_between, [0, raw_gap])

                    # Only count if both on same day
                    final_gap = builder.model.NewIntVar(0, builder.week_minutes, f"pair_gap_{i}_{day}")
                    builder.model.Add(final_gap == gap_between).OnlyEnforceIf(both_on_day)
                    builder.model.Add(final_gap == 0).OnlyEnforceIf(both_on_day.Not())

                    builder.penalty_vars.append(PenaltyVar(
                        name=f"gap_between_{teacher.id}_{inst1.lesson_id}{inst1.instance}_{inst2.lesson_id}{inst2.instance}_day{day}",
                        var=final_gap,
                        weight=weight,
                        description=f"Gap between {teacher.name}'s lessons on day {day}"
                    ))
                    penalties_added += 1

    return penalties_added


# =============================================================================
# Combined Function
# =============================================================================

def add_all_gap_constraints(
    builder: TimetableModelBuilder,
    teacher_gap_weight: int = 2,
    class_gap_weight: int = 2,
    min_lessons_for_gap: int = 2
) -> GapStats:
    """
    Add all gap-related constraints.

    Args:
        builder: The timetable model builder with created variables
        teacher_gap_weight: Penalty weight for teacher gaps
        class_gap_weight: Penalty weight for class gaps
        min_lessons_for_gap: Minimum lessons to consider gaps

    Returns:
        GapStats with counts
    """
    stats = GapStats()

    # Count potential gap situations
    for teacher in builder.input.teachers:
        instances = _get_teacher_instances(builder, teacher.id)
        if len(instances) >= min_lessons_for_gap:
            stats.teachers_with_gap_constraints += 1

    for cls in builder.input.classes:
        instances = _get_class_instances(builder, cls.id)
        if len(instances) >= min_lessons_for_gap:
            stats.classes_with_gap_constraints += 1

    # Add constraints
    stats.teacher_gap_penalties = add_teacher_gap_minimization(
        builder,
        weight=teacher_gap_weight,
        min_lessons_for_gap=min_lessons_for_gap
    )

    stats.class_gap_penalties = add_class_gap_minimization(
        builder,
        weight=class_gap_weight,
        min_lessons_for_gap=min_lessons_for_gap
    )

    return stats
