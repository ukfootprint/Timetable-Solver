"""
Constraint modules for the timetabling solver.

This package contains modular constraint implementations that can be
added to the CP-SAT model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from solver.model_builder import TimetableModelBuilder

from .no_overlap import (
    add_teacher_no_overlap,
    add_class_no_overlap,
    add_room_no_overlap,
    add_all_no_overlap_constraints,
    NoOverlapStats,
)

from .availability import (
    add_teacher_unavailability,
    add_class_unavailability,
    add_room_unavailability,
    add_school_day_constraints,
    add_break_avoidance,
    add_all_availability_constraints,
    AvailabilityStats,
)

from .rooms import (
    get_valid_rooms_for_lesson,
    add_room_assignment_constraints,
    add_room_no_overlap_with_optional_intervals,
    add_preferred_room_soft_constraint,
    add_room_consistency_soft_constraint,
    add_all_room_constraints,
    analyze_room_assignments,
    get_lessons_without_valid_rooms,
    RoomConstraintStats,
    RoomSuitability,
)

from .daily_limits import (
    add_teacher_max_periods_per_day,
    add_class_max_periods_per_day,
    add_teacher_max_periods_per_week,
    add_balanced_daily_workload,
    add_minimum_lessons_per_day,
    add_all_daily_limit_constraints,
    DailyLimitStats,
)

from .gaps import (
    add_teacher_gap_minimization,
    add_class_gap_minimization,
    add_early_finish_preference,
    add_consecutive_lesson_preference,
    add_all_gap_constraints,
    GapStats,
)

from .distribution import (
    add_subject_distribution,
    add_minimum_day_gap,
    add_even_distribution,
    add_no_consecutive_days,
    add_all_distribution_constraints,
    DistributionStats,
)


# =============================================================================
# Constraint Manager Configuration
# =============================================================================

@dataclass
class ConstraintWeights:
    """Configurable penalty weights for soft constraints."""
    # Daily limit penalties
    teacher_daily_overflow: int = 100  # Per lesson over daily limit
    class_daily_overflow: int = 100
    teacher_weekly_overflow: int = 150

    # Consecutive lesson penalties
    consecutive_exceeded: int = 50  # Per lesson over consecutive limit

    # Gap penalties
    teacher_gap: int = 1  # Per minute of gap
    class_gap: int = 1
    late_finish: int = 1  # Per minute after threshold

    # Distribution penalties
    same_day_subject: int = 20  # Per occurrence of same-day lessons
    day_gap_shortfall: int = 10  # Per day below minimum gap
    uneven_distribution: int = 5  # Per day deviation from ideal
    consecutive_days: int = 20  # For subjects that shouldn't be consecutive

    # Workload balance penalties
    workload_imbalance: int = 5  # Per deviation from balanced load
    fragmentation: int = 10  # For days with too few lessons

    # Room preference penalties
    non_preferred_room: int = 10  # Per occurrence
    room_inconsistency: int = 5  # Per different room for same lesson


@dataclass
class ConstraintManagerStats:
    """Statistics about all constraints applied."""
    # Hard constraint stats
    no_overlap: NoOverlapStats = field(default_factory=NoOverlapStats)
    availability: AvailabilityStats = field(default_factory=AvailabilityStats)
    room: RoomConstraintStats = field(default_factory=RoomConstraintStats)

    # Soft constraint stats
    daily_limits: DailyLimitStats = field(default_factory=DailyLimitStats)
    gaps: GapStats = field(default_factory=GapStats)
    distribution: DistributionStats = field(default_factory=DistributionStats)

    # Summary counts
    total_hard_constraints: int = 0
    total_soft_penalties: int = 0


# =============================================================================
# Constraint Manager
# =============================================================================

class ConstraintManager:
    """
    Centralized manager for applying all timetabling constraints.

    This class orchestrates the application of both hard constraints
    (must be satisfied) and soft constraints (optimized via penalties).

    Usage:
        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        manager = ConstraintManager(weights=ConstraintWeights())
        stats = manager.apply_all_constraints(builder)

        builder.set_objective()
        solution = builder.solve()
    """

    def __init__(self, weights: ConstraintWeights | None = None):
        """
        Initialize the constraint manager.

        Args:
            weights: Configurable penalty weights (uses defaults if None)
        """
        self.weights = weights or ConstraintWeights()

    def apply_all_constraints(
        self,
        builder: TimetableModelBuilder,
        skip_hard: bool = False,
        skip_soft: bool = False
    ) -> ConstraintManagerStats:
        """
        Apply all constraints to the model.

        Args:
            builder: The timetable model builder with created variables
            skip_hard: Skip hard constraints (for testing)
            skip_soft: Skip soft constraints (for feasibility check only)

        Returns:
            ConstraintManagerStats with counts of applied constraints
        """
        stats = ConstraintManagerStats()

        # Apply hard constraints (must be satisfied)
        if not skip_hard:
            self._apply_hard_constraints(builder, stats)

        # Apply soft constraints (add penalties for optimization)
        if not skip_soft:
            self._apply_soft_constraints(builder, stats)

        # Mark constraints as added on the builder
        builder._constraints_added = True

        return stats

    def _apply_hard_constraints(
        self,
        builder: TimetableModelBuilder,
        stats: ConstraintManagerStats
    ) -> None:
        """Apply all hard constraints that must be satisfied."""
        # 1. Valid time slots (lessons must be in schedulable periods)
        builder._add_valid_time_slots_constraint()

        # 2. No overlap constraints (teacher, class, room cannot double-book)
        stats.no_overlap = add_all_no_overlap_constraints(builder)
        stats.total_hard_constraints += (
            stats.no_overlap.teacher_constraints +
            stats.no_overlap.class_constraints +
            stats.no_overlap.room_constraints
        )

        # 3. Availability constraints (unavailability, school day bounds, breaks)
        stats.availability = add_all_availability_constraints(builder)
        stats.total_hard_constraints += (
            stats.availability.teacher_unavailability_constraints +
            stats.availability.school_day_constraints +
            stats.availability.break_avoidance_constraints
        )

        # 4. Room suitability (type, capacity, equipment requirements)
        # Note: Room soft constraint weights use defaults from add_all_room_constraints
        # Custom weights can be applied by calling individual functions separately
        stats.room = add_all_room_constraints(builder, include_soft_constraints=True)
        stats.total_hard_constraints += stats.room.room_assignment_constraints

    def _apply_soft_constraints(
        self,
        builder: TimetableModelBuilder,
        stats: ConstraintManagerStats
    ) -> None:
        """Apply all soft constraints as penalties for optimization."""
        w = self.weights

        # 1. Daily limit constraints (max lessons per day/week)
        stats.daily_limits = add_all_daily_limit_constraints(
            builder,
            teacher_max_weight=w.teacher_daily_overflow,
            class_max_weight=w.class_daily_overflow,
            balance_weight=w.workload_imbalance,
            fragmentation_weight=w.fragmentation
        )
        stats.total_soft_penalties += (
            stats.daily_limits.teacher_overflow_penalties +
            stats.daily_limits.class_overflow_penalties
        )

        # Also add weekly limits
        add_teacher_max_periods_per_week(builder, weight=w.teacher_weekly_overflow)

        # 2. Gap minimization constraints (compact schedules)
        stats.gaps = add_all_gap_constraints(
            builder,
            teacher_gap_weight=w.teacher_gap,
            class_gap_weight=w.class_gap
        )
        stats.total_soft_penalties += (
            stats.gaps.teacher_gap_penalties +
            stats.gaps.class_gap_penalties
        )

        # Also add early finish preference
        add_early_finish_preference(builder, weight=w.late_finish)

        # 3. Subject distribution constraints (spread across days)
        stats.distribution = add_all_distribution_constraints(
            builder,
            same_day_weight=w.same_day_subject,
            min_gap_weight=w.day_gap_shortfall,
            even_dist_weight=w.uneven_distribution
        )
        stats.total_soft_penalties += (
            stats.distribution.same_day_penalties +
            stats.distribution.min_gap_penalties
        )

    def apply_hard_constraints_only(
        self,
        builder: TimetableModelBuilder
    ) -> ConstraintManagerStats:
        """
        Apply only hard constraints (for feasibility checking).

        Args:
            builder: The timetable model builder

        Returns:
            ConstraintManagerStats with hard constraint counts
        """
        return self.apply_all_constraints(builder, skip_soft=True)

    def apply_soft_constraints_only(
        self,
        builder: TimetableModelBuilder
    ) -> ConstraintManagerStats:
        """
        Apply only soft constraints (when hard constraints added elsewhere).

        Args:
            builder: The timetable model builder

        Returns:
            ConstraintManagerStats with soft constraint counts
        """
        return self.apply_all_constraints(builder, skip_hard=True)


__all__ = [
    # No-overlap constraints
    "add_teacher_no_overlap",
    "add_class_no_overlap",
    "add_room_no_overlap",
    "add_all_no_overlap_constraints",
    "NoOverlapStats",
    # Availability constraints
    "add_teacher_unavailability",
    "add_class_unavailability",
    "add_room_unavailability",
    "add_school_day_constraints",
    "add_break_avoidance",
    "add_all_availability_constraints",
    "AvailabilityStats",
    # Room constraints
    "get_valid_rooms_for_lesson",
    "add_room_assignment_constraints",
    "add_room_no_overlap_with_optional_intervals",
    "add_preferred_room_soft_constraint",
    "add_room_consistency_soft_constraint",
    "add_all_room_constraints",
    "analyze_room_assignments",
    "get_lessons_without_valid_rooms",
    "RoomConstraintStats",
    "RoomSuitability",
    # Daily limit constraints
    "add_teacher_max_periods_per_day",
    "add_class_max_periods_per_day",
    "add_teacher_max_periods_per_week",
    "add_balanced_daily_workload",
    "add_minimum_lessons_per_day",
    "add_all_daily_limit_constraints",
    "DailyLimitStats",
    # Gap constraints
    "add_teacher_gap_minimization",
    "add_class_gap_minimization",
    "add_early_finish_preference",
    "add_consecutive_lesson_preference",
    "add_all_gap_constraints",
    "GapStats",
    # Distribution constraints
    "add_subject_distribution",
    "add_minimum_day_gap",
    "add_even_distribution",
    "add_no_consecutive_days",
    "add_all_distribution_constraints",
    "DistributionStats",
    # Constraint manager
    "ConstraintManager",
    "ConstraintWeights",
    "ConstraintManagerStats",
]
