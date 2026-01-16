"""
Daily limit constraints for timetabling.

This module provides soft constraints for:
- Maximum lessons per day per teacher
- Maximum lessons per day per class
- Balanced workload distribution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from solver.model_builder import TimetableModelBuilder, LessonInstanceVars


# =============================================================================
# Statistics
# =============================================================================

@dataclass
class DailyLimitStats:
    """Statistics about daily limit constraints added."""
    teachers_with_limits: int = 0
    teacher_day_constraints: int = 0
    teacher_overflow_penalties: int = 0
    classes_with_limits: int = 0
    class_day_constraints: int = 0
    class_overflow_penalties: int = 0
    indicator_variables_created: int = 0


# =============================================================================
# Teacher Daily Limits
# =============================================================================

def add_teacher_max_periods_per_day(
    builder: TimetableModelBuilder,
    default_max: int | None = None,
    weight: int = 20
) -> int:
    """
    Add soft constraints for teacher maximum periods per day.

    For each teacher with a maxPeriodsPerDay limit:
    1. For each day, count lessons using indicator variables
    2. If count exceeds limit, add penalty proportional to overflow

    Implementation:
    - Create is_on_day[lesson_instance][day] boolean variables
    - Link to day_var: is_on_day == (day_var == day)
    - Sum indicators per teacher per day
    - Create overflow = max(0, sum - limit)
    - Add overflow * weight to penalties

    Args:
        builder: The timetable model builder with created variables
        default_max: Default max periods if teacher doesn't specify one
        weight: Penalty weight per overflow period

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0
    num_days = builder.input.config.num_days

    for teacher in builder.input.teachers:
        # Get max periods limit
        max_periods = teacher.max_periods_per_day or default_max
        if max_periods is None:
            continue

        # Get all lesson instances for this teacher
        teacher_instances = _get_teacher_instances(builder, teacher.id)
        if not teacher_instances:
            continue

        for day in range(num_days):
            # Create indicator for each instance being on this day
            day_indicators = []

            for inst in teacher_instances:
                is_on_day = builder.model.NewBoolVar(
                    f"T{teacher.id}_L{inst.lesson_id}_I{inst.instance}_day{day}"
                )

                # Link indicator to day_var
                builder.model.Add(inst.day_var == day).OnlyEnforceIf(is_on_day)
                builder.model.Add(inst.day_var != day).OnlyEnforceIf(is_on_day.Not())

                day_indicators.append(is_on_day)

            if not day_indicators:
                continue

            # Create sum variable for lessons on this day
            day_count = builder.model.NewIntVar(
                0, len(day_indicators),
                f"T{teacher.id}_day{day}_count"
            )
            builder.model.Add(day_count == sum(day_indicators))

            # Create overflow variable: max(0, count - limit)
            overflow = builder.model.NewIntVar(
                0, max(0, len(day_indicators) - max_periods),
                f"T{teacher.id}_day{day}_overflow"
            )

            # overflow = max(0, day_count - max_periods)
            # Using: overflow >= 0 AND overflow >= day_count - max_periods
            # AND (overflow == 0 OR overflow == day_count - max_periods)
            builder.model.AddMaxEquality(overflow, [0, day_count - max_periods])

            # Add penalty if overflow domain allows > 0
            if len(day_indicators) > max_periods:
                builder.penalty_vars.append(PenaltyVar(
                    name=f"teacher_overload_{teacher.id}_day{day}",
                    var=overflow,
                    weight=weight,
                    description=f"Teacher {teacher.name} exceeds {max_periods} periods on day {day}"
                ))
                penalties_added += 1

    return penalties_added


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
# Class Daily Limits
# =============================================================================

def add_class_max_periods_per_day(
    builder: TimetableModelBuilder,
    default_max: int | None = None,
    weight: int = 15
) -> int:
    """
    Add soft constraints for class maximum periods per day.

    Similar to teacher limits but for student classes.

    Args:
        builder: The timetable model builder with created variables
        default_max: Default max periods if class doesn't specify one
        weight: Penalty weight per overflow period

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0
    num_days = builder.input.config.num_days

    for cls in builder.input.classes:
        # Classes don't have max_periods_per_day in the current model,
        # so we use the default if provided
        max_periods = default_max
        if max_periods is None:
            continue

        # Get all lesson instances for this class
        class_instances = _get_class_instances(builder, cls.id)
        if not class_instances:
            continue

        for day in range(num_days):
            # Create indicator for each instance being on this day
            day_indicators = []

            for inst in class_instances:
                is_on_day = builder.model.NewBoolVar(
                    f"C{cls.id}_L{inst.lesson_id}_I{inst.instance}_day{day}"
                )

                builder.model.Add(inst.day_var == day).OnlyEnforceIf(is_on_day)
                builder.model.Add(inst.day_var != day).OnlyEnforceIf(is_on_day.Not())

                day_indicators.append(is_on_day)

            if not day_indicators:
                continue

            # Create sum variable
            day_count = builder.model.NewIntVar(
                0, len(day_indicators),
                f"C{cls.id}_day{day}_count"
            )
            builder.model.Add(day_count == sum(day_indicators))

            # Create overflow variable
            overflow = builder.model.NewIntVar(
                0, max(0, len(day_indicators) - max_periods),
                f"C{cls.id}_day{day}_overflow"
            )
            builder.model.AddMaxEquality(overflow, [0, day_count - max_periods])

            # Add penalty
            if len(day_indicators) > max_periods:
                builder.penalty_vars.append(PenaltyVar(
                    name=f"class_overload_{cls.id}_day{day}",
                    var=overflow,
                    weight=weight,
                    description=f"Class {cls.name} exceeds {max_periods} periods on day {day}"
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
# Teacher Weekly Limits
# =============================================================================

def add_teacher_max_periods_per_week(
    builder: TimetableModelBuilder,
    weight: int = 50
) -> int:
    """
    Add soft constraints for teacher maximum periods per week.

    This is typically a hard constraint in practice, but implemented
    as a soft constraint with high weight for flexibility.

    Args:
        builder: The timetable model builder with created variables
        weight: Penalty weight per overflow period

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0

    for teacher in builder.input.teachers:
        max_periods = teacher.max_periods_per_week
        if max_periods is None:
            continue

        # Count total lessons for this teacher
        teacher_instances = _get_teacher_instances(builder, teacher.id)
        total_instances = len(teacher_instances)

        if total_instances <= max_periods:
            # Can't exceed limit, no constraint needed
            continue

        # All instances are scheduled, so the count is fixed
        # This is really a hard constraint check
        overflow_amount = total_instances - max_periods

        if overflow_amount > 0:
            # Create a constant penalty variable
            overflow = builder.model.NewConstant(overflow_amount)

            builder.penalty_vars.append(PenaltyVar(
                name=f"teacher_weekly_overload_{teacher.id}",
                var=overflow,
                weight=weight,
                description=f"Teacher {teacher.name} has {total_instances} periods, max is {max_periods}"
            ))
            penalties_added += 1

    return penalties_added


# =============================================================================
# Balanced Daily Workload
# =============================================================================

def add_balanced_daily_workload(
    builder: TimetableModelBuilder,
    weight: int = 5
) -> int:
    """
    Add soft constraints to balance teacher workload across days.

    Penalizes having lessons clustered on some days while others are empty.
    Uses variance-like calculation: penalize deviation from average.

    Args:
        builder: The timetable model builder with created variables
        weight: Penalty weight per deviation unit

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0
    num_days = builder.input.config.num_days

    for teacher in builder.input.teachers:
        teacher_instances = _get_teacher_instances(builder, teacher.id)
        if len(teacher_instances) <= 1:
            continue

        # Calculate target average (ideal is equal distribution)
        total_lessons = len(teacher_instances)
        target_per_day = total_lessons // num_days

        # Skip if very few lessons or target is 0
        if target_per_day == 0:
            continue

        # Create day count variables
        day_counts = []
        for day in range(num_days):
            day_indicators = []
            for inst in teacher_instances:
                is_on_day = builder.model.NewBoolVar(
                    f"T{teacher.id}_L{inst.lesson_id}_I{inst.instance}_day{day}_bal"
                )
                builder.model.Add(inst.day_var == day).OnlyEnforceIf(is_on_day)
                builder.model.Add(inst.day_var != day).OnlyEnforceIf(is_on_day.Not())
                day_indicators.append(is_on_day)

            day_count = builder.model.NewIntVar(
                0, len(teacher_instances),
                f"T{teacher.id}_day{day}_count_bal"
            )
            builder.model.Add(day_count == sum(day_indicators))
            day_counts.append(day_count)

        # Penalize deviation from target on each day
        for day, day_count in enumerate(day_counts):
            # Create deviation = |day_count - target|
            # Using: above_target = max(0, day_count - target)
            #        below_target = max(0, target - day_count)
            #        deviation = above_target + below_target

            above_target = builder.model.NewIntVar(
                0, len(teacher_instances),
                f"T{teacher.id}_day{day}_above"
            )
            builder.model.AddMaxEquality(above_target, [0, day_count - target_per_day])

            below_target = builder.model.NewIntVar(
                0, target_per_day,
                f"T{teacher.id}_day{day}_below"
            )
            builder.model.AddMaxEquality(below_target, [0, target_per_day - day_count])

            deviation = builder.model.NewIntVar(
                0, len(teacher_instances),
                f"T{teacher.id}_day{day}_deviation"
            )
            builder.model.Add(deviation == above_target + below_target)

            builder.penalty_vars.append(PenaltyVar(
                name=f"workload_imbalance_{teacher.id}_day{day}",
                var=deviation,
                weight=weight,
                description=f"Teacher {teacher.name} workload deviation on day {day}"
            ))
            penalties_added += 1

    return penalties_added


# =============================================================================
# Minimum Lessons Per Day (Avoid Fragmentation)
# =============================================================================

def add_minimum_lessons_per_day(
    builder: TimetableModelBuilder,
    min_lessons: int = 2,
    weight: int = 10
) -> int:
    """
    Add soft constraint to avoid having just 1 lesson on a day.

    Teachers generally prefer either no lessons on a day or multiple
    lessons, rather than coming in for just one period.

    Args:
        builder: The timetable model builder
        min_lessons: Minimum lessons if any are scheduled
        weight: Penalty weight for fragmentation

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0
    num_days = builder.input.config.num_days

    for teacher in builder.input.teachers:
        teacher_instances = _get_teacher_instances(builder, teacher.id)
        if len(teacher_instances) < min_lessons:
            continue

        for day in range(num_days):
            day_indicators = []
            for inst in teacher_instances:
                is_on_day = builder.model.NewBoolVar(
                    f"T{teacher.id}_L{inst.lesson_id}_I{inst.instance}_day{day}_min"
                )
                builder.model.Add(inst.day_var == day).OnlyEnforceIf(is_on_day)
                builder.model.Add(inst.day_var != day).OnlyEnforceIf(is_on_day.Not())
                day_indicators.append(is_on_day)

            if not day_indicators:
                continue

            # Count lessons on this day
            day_count = builder.model.NewIntVar(
                0, len(day_indicators),
                f"T{teacher.id}_day{day}_count_min"
            )
            builder.model.Add(day_count == sum(day_indicators))

            # has_lessons = (day_count >= 1)
            has_lessons = builder.model.NewBoolVar(
                f"T{teacher.id}_day{day}_has_lessons"
            )
            builder.model.Add(day_count >= 1).OnlyEnforceIf(has_lessons)
            builder.model.Add(day_count == 0).OnlyEnforceIf(has_lessons.Not())

            # Create penalty for having lessons but below minimum
            # fragmented = has_lessons AND (day_count < min_lessons)
            # Simplified: shortfall = max(0, min_lessons - day_count) if has_lessons else 0

            shortfall = builder.model.NewIntVar(
                0, min_lessons - 1,
                f"T{teacher.id}_day{day}_shortfall"
            )

            # When has_lessons: shortfall = max(0, min_lessons - day_count)
            # When not has_lessons: shortfall = 0
            temp_shortfall = builder.model.NewIntVar(
                0, min_lessons,
                f"T{teacher.id}_day{day}_temp_shortfall"
            )
            builder.model.AddMaxEquality(temp_shortfall, [0, min_lessons - day_count])

            builder.model.Add(shortfall == temp_shortfall).OnlyEnforceIf(has_lessons)
            builder.model.Add(shortfall == 0).OnlyEnforceIf(has_lessons.Not())

            if len(day_indicators) > 0:
                builder.penalty_vars.append(PenaltyVar(
                    name=f"fragmentation_{teacher.id}_day{day}",
                    var=shortfall,
                    weight=weight,
                    description=f"Teacher {teacher.name} has few lessons on day {day}"
                ))
                penalties_added += 1

    return penalties_added


# =============================================================================
# Combined Function
# =============================================================================

def add_all_daily_limit_constraints(
    builder: TimetableModelBuilder,
    teacher_max_weight: int = 20,
    class_max_default: int | None = None,
    class_max_weight: int = 15,
    balance_weight: int = 5,
    fragmentation_weight: int = 10
) -> DailyLimitStats:
    """
    Add all daily limit constraints.

    Args:
        builder: The timetable model builder with created variables
        teacher_max_weight: Penalty weight for teacher daily overflow
        class_max_default: Default max periods per day for classes
        class_max_weight: Penalty weight for class daily overflow
        balance_weight: Penalty weight for workload imbalance
        fragmentation_weight: Penalty weight for fragmented days

    Returns:
        DailyLimitStats with counts
    """
    stats = DailyLimitStats()

    # Count teachers with limits
    stats.teachers_with_limits = sum(
        1 for t in builder.input.teachers
        if t.max_periods_per_day is not None
    )

    # Add constraints
    stats.teacher_overflow_penalties = add_teacher_max_periods_per_day(
        builder, weight=teacher_max_weight
    )

    if class_max_default is not None:
        stats.classes_with_limits = len(builder.input.classes)
        stats.class_overflow_penalties = add_class_max_periods_per_day(
            builder, default_max=class_max_default, weight=class_max_weight
        )

    # Weekly limits (high weight, almost hard constraint)
    add_teacher_max_periods_per_week(builder, weight=50)

    # Balance and fragmentation (lower weights)
    add_balanced_daily_workload(builder, weight=balance_weight)
    add_minimum_lessons_per_day(builder, weight=fragmentation_weight)

    return stats
