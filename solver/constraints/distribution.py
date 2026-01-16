"""
Subject distribution constraints for timetabling.

This module provides soft constraints to distribute lessons of the
same subject across different days of the week, avoiding clustering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from solver.model_builder import TimetableModelBuilder, LessonInstanceVars


# =============================================================================
# Statistics
# =============================================================================

@dataclass
class DistributionStats:
    """Statistics about distribution constraints added."""
    lessons_with_distribution: int = 0
    same_day_penalties: int = 0
    min_gap_penalties: int = 0


# =============================================================================
# Subject Distribution Across Days
# =============================================================================

def add_subject_distribution(
    builder: TimetableModelBuilder,
    weight: int = 15,
    min_lessons: int = 2
) -> int:
    """
    Add soft constraints to distribute subject lessons across different days.

    For each lesson with multiple instances per week, penalizes scheduling
    two instances on the same day. This encourages spreading lessons like
    Maths across Mon/Wed/Fri instead of Mon/Mon/Tue.

    Implementation:
    - For each pair of lesson instances (same subject/class/teacher):
      - Create same_day indicator: day1 == day2
      - Add penalty if same_day is true
    - Scale penalty inversely with lessons_per_week (more lessons = less penalty)

    Args:
        builder: The timetable model builder with created variables
        weight: Base penalty weight for same-day scheduling
        min_lessons: Minimum lessons per week to apply constraint

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0

    for lesson in builder.input.lessons:
        if lesson.lessons_per_week < min_lessons:
            continue

        instances = builder.lesson_vars.get(lesson.id, [])
        if len(instances) < 2:
            continue

        # Scale penalty: fewer lessons = higher penalty for same-day
        # 2 lessons: weight * 1.0, 3 lessons: weight * 0.67, 5 lessons: weight * 0.4
        scaled_weight = max(1, weight * 2 // lesson.lessons_per_week)

        # For each pair of instances
        for i, inst1 in enumerate(instances):
            for j, inst2 in enumerate(instances[i + 1:], start=i + 1):
                same_day = builder.model.NewBoolVar(
                    f"same_day_L{lesson.id}_I{i}_I{j}"
                )

                # same_day = (day1 == day2)
                builder.model.Add(inst1.day_var == inst2.day_var).OnlyEnforceIf(same_day)
                builder.model.Add(inst1.day_var != inst2.day_var).OnlyEnforceIf(same_day.Not())

                # Add penalty for same-day scheduling
                builder.penalty_vars.append(PenaltyVar(
                    name=f"same_day_{lesson.id}_{i}_{j}",
                    var=same_day,
                    weight=scaled_weight,
                    description=f"Lesson {lesson.id} instances {i} and {j} on same day"
                ))
                penalties_added += 1

    return penalties_added


# =============================================================================
# Minimum Day Gap Between Lessons
# =============================================================================

def add_minimum_day_gap(
    builder: TimetableModelBuilder,
    min_gap_days: int = 1,
    weight: int = 10
) -> int:
    """
    Add soft constraints for minimum day gap between lesson instances.

    Encourages having at least min_gap_days between instances of the same
    lesson. For example, with min_gap_days=1, Mon and Wed is preferred
    over Mon and Tue.

    Implementation:
    - For each pair of instances:
      - Calculate |day1 - day2|
      - Penalize if gap < min_gap_days

    Args:
        builder: The timetable model builder with created variables
        min_gap_days: Minimum preferred days between instances
        weight: Penalty weight per day of shortfall

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0
    num_days = builder.input.config.num_days

    for lesson in builder.input.lessons:
        if lesson.lessons_per_week < 2:
            continue

        instances = builder.lesson_vars.get(lesson.id, [])
        if len(instances) < 2:
            continue

        for i, inst1 in enumerate(instances):
            for j, inst2 in enumerate(instances[i + 1:], start=i + 1):
                # Calculate absolute difference: |day1 - day2|
                # Using: diff = max(day1 - day2, day2 - day1)
                diff1 = builder.model.NewIntVar(
                    -num_days, num_days,
                    f"diff1_L{lesson.id}_I{i}_I{j}"
                )
                builder.model.Add(diff1 == inst1.day_var - inst2.day_var)

                diff2 = builder.model.NewIntVar(
                    -num_days, num_days,
                    f"diff2_L{lesson.id}_I{i}_I{j}"
                )
                builder.model.Add(diff2 == inst2.day_var - inst1.day_var)

                abs_diff = builder.model.NewIntVar(
                    0, num_days,
                    f"abs_diff_L{lesson.id}_I{i}_I{j}"
                )
                builder.model.AddMaxEquality(abs_diff, [diff1, diff2])

                # Shortfall = max(0, min_gap_days - abs_diff)
                shortfall = builder.model.NewIntVar(
                    0, min_gap_days,
                    f"gap_shortfall_L{lesson.id}_I{i}_I{j}"
                )
                builder.model.AddMaxEquality(shortfall, [0, min_gap_days - abs_diff])

                if min_gap_days > 0:
                    builder.penalty_vars.append(PenaltyVar(
                        name=f"day_gap_{lesson.id}_{i}_{j}",
                        var=shortfall,
                        weight=weight,
                        description=f"Lesson {lesson.id} instances {i},{j} too close"
                    ))
                    penalties_added += 1

    return penalties_added


# =============================================================================
# Even Distribution Across Week
# =============================================================================

def add_even_distribution(
    builder: TimetableModelBuilder,
    weight: int = 5
) -> int:
    """
    Add soft constraints for even distribution of lessons across the week.

    For lessons with 2+ instances, encourages spreading them evenly.
    For 2 lessons in 5 days: ideal gap is 2-3 days.
    For 3 lessons in 5 days: ideal gap is 1-2 days.

    Implementation:
    - Calculate ideal gap based on lessons_per_week and num_days
    - Penalize deviation from ideal spacing

    Args:
        builder: The timetable model builder with created variables
        weight: Penalty weight for uneven distribution

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0
    num_days = builder.input.config.num_days

    for lesson in builder.input.lessons:
        if lesson.lessons_per_week < 2:
            continue

        instances = builder.lesson_vars.get(lesson.id, [])
        if len(instances) < 2:
            continue

        # Calculate ideal gap between lessons
        # For n lessons in d days, ideal gap = d / n
        ideal_gap = num_days // lesson.lessons_per_week

        if ideal_gap < 1:
            continue

        for i, inst1 in enumerate(instances):
            for j, inst2 in enumerate(instances[i + 1:], start=i + 1):
                # Calculate absolute difference
                diff1 = builder.model.NewIntVar(-num_days, num_days, f"ed_diff1_L{lesson.id}_{i}_{j}")
                builder.model.Add(diff1 == inst1.day_var - inst2.day_var)

                diff2 = builder.model.NewIntVar(-num_days, num_days, f"ed_diff2_L{lesson.id}_{i}_{j}")
                builder.model.Add(diff2 == inst2.day_var - inst1.day_var)

                abs_diff = builder.model.NewIntVar(0, num_days, f"ed_abs_L{lesson.id}_{i}_{j}")
                builder.model.AddMaxEquality(abs_diff, [diff1, diff2])

                # Deviation from ideal = |abs_diff - ideal_gap|
                dev1 = builder.model.NewIntVar(-num_days, num_days, f"ed_dev1_L{lesson.id}_{i}_{j}")
                builder.model.Add(dev1 == abs_diff - ideal_gap)

                dev2 = builder.model.NewIntVar(-num_days, num_days, f"ed_dev2_L{lesson.id}_{i}_{j}")
                builder.model.Add(dev2 == ideal_gap - abs_diff)

                deviation = builder.model.NewIntVar(0, num_days, f"ed_deviation_L{lesson.id}_{i}_{j}")
                builder.model.AddMaxEquality(deviation, [dev1, dev2])

                builder.penalty_vars.append(PenaltyVar(
                    name=f"even_dist_{lesson.id}_{i}_{j}",
                    var=deviation,
                    weight=weight,
                    description=f"Lesson {lesson.id} instances {i},{j} unevenly spaced"
                ))
                penalties_added += 1

    return penalties_added


# =============================================================================
# No Consecutive Days (for specific subjects)
# =============================================================================

def add_no_consecutive_days(
    builder: TimetableModelBuilder,
    subject_ids: list[str] | None = None,
    weight: int = 20
) -> int:
    """
    Add soft constraint to avoid consecutive days for specific subjects.

    Some subjects (like PE or heavy academic subjects) benefit from
    rest days between sessions.

    Args:
        builder: The timetable model builder with created variables
        subject_ids: List of subject IDs to apply constraint to (None = all)
        weight: Penalty weight for consecutive day scheduling

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0

    for lesson in builder.input.lessons:
        # Filter by subject if specified
        if subject_ids is not None and lesson.subject_id not in subject_ids:
            continue

        if lesson.lessons_per_week < 2:
            continue

        instances = builder.lesson_vars.get(lesson.id, [])
        if len(instances) < 2:
            continue

        for i, inst1 in enumerate(instances):
            for j, inst2 in enumerate(instances[i + 1:], start=i + 1):
                # Check if consecutive: |day1 - day2| == 1
                is_consecutive = builder.model.NewBoolVar(
                    f"consecutive_L{lesson.id}_I{i}_I{j}"
                )

                # day2 == day1 + 1 OR day1 == day2 + 1
                day1_plus_1 = builder.model.NewBoolVar(f"d1p1_L{lesson.id}_{i}_{j}")
                day2_plus_1 = builder.model.NewBoolVar(f"d2p1_L{lesson.id}_{i}_{j}")

                builder.model.Add(inst2.day_var == inst1.day_var + 1).OnlyEnforceIf(day1_plus_1)
                builder.model.Add(inst2.day_var != inst1.day_var + 1).OnlyEnforceIf(day1_plus_1.Not())

                builder.model.Add(inst1.day_var == inst2.day_var + 1).OnlyEnforceIf(day2_plus_1)
                builder.model.Add(inst1.day_var != inst2.day_var + 1).OnlyEnforceIf(day2_plus_1.Not())

                # is_consecutive = day1_plus_1 OR day2_plus_1
                builder.model.AddBoolOr([day1_plus_1, day2_plus_1]).OnlyEnforceIf(is_consecutive)
                builder.model.AddBoolAnd([day1_plus_1.Not(), day2_plus_1.Not()]).OnlyEnforceIf(is_consecutive.Not())

                builder.penalty_vars.append(PenaltyVar(
                    name=f"consecutive_{lesson.id}_{i}_{j}",
                    var=is_consecutive,
                    weight=weight,
                    description=f"Lesson {lesson.id} instances {i},{j} on consecutive days"
                ))
                penalties_added += 1

    return penalties_added


# =============================================================================
# Combined Function
# =============================================================================

def add_all_distribution_constraints(
    builder: TimetableModelBuilder,
    same_day_weight: int = 15,
    min_gap_weight: int = 10,
    even_dist_weight: int = 5,
    min_gap_days: int = 1
) -> DistributionStats:
    """
    Add all distribution-related constraints.

    Args:
        builder: The timetable model builder with created variables
        same_day_weight: Penalty for same-day scheduling
        min_gap_weight: Penalty for insufficient day gap
        even_dist_weight: Penalty for uneven distribution
        min_gap_days: Minimum days between lesson instances

    Returns:
        DistributionStats with counts
    """
    stats = DistributionStats()

    # Count lessons that will have distribution constraints
    for lesson in builder.input.lessons:
        if lesson.lessons_per_week >= 2:
            stats.lessons_with_distribution += 1

    # Add constraints
    stats.same_day_penalties = add_subject_distribution(
        builder,
        weight=same_day_weight
    )

    stats.min_gap_penalties = add_minimum_day_gap(
        builder,
        min_gap_days=min_gap_days,
        weight=min_gap_weight
    )

    # Even distribution is lighter weight, optional enhancement
    add_even_distribution(builder, weight=even_dist_weight)

    return stats
