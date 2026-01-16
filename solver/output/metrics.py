"""
Quality metrics calculator for evaluating timetable solutions.

This module provides comprehensive metrics for evaluating the quality
of generated timetables, including gap analysis, distribution scoring,
and workload balance calculations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from solver.data.models import TimetableInput, Teacher, Lesson
    from .schema import TimetableOutput, LessonOutput


# =============================================================================
# Constants
# =============================================================================

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Target thresholds for quality assessment
DEFAULT_TARGETS = {
    "gap_score": 30.0,           # Max average gap in minutes
    "distribution_score": 80.0,   # Min % well-distributed
    "daily_balance": 1.5,         # Max std dev for balance
    "utilization": 70.0,          # Min utilization percentage
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class GapMetrics:
    """Metrics for teacher gaps (idle time between lessons)."""
    average_gap_minutes: float
    max_gap_minutes: float
    total_gap_minutes: float
    teacher_days_analyzed: int
    gaps_by_teacher: dict[str, float] = field(default_factory=dict)

    @property
    def score(self) -> float:
        """Lower is better. Returns 100 - normalized gap."""
        # Normalize: 0 gap = 100, 60+ min gap = 0
        normalized = max(0, 100 - (self.average_gap_minutes / 60) * 100)
        return round(normalized, 2)


@dataclass
class DistributionMetrics:
    """Metrics for lesson distribution across days."""
    well_distributed_count: int
    total_multi_lesson_subjects: int
    percentage_well_distributed: float
    poorly_distributed: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Higher is better. Returns percentage."""
        return round(self.percentage_well_distributed, 2)


@dataclass
class BalanceMetrics:
    """Metrics for daily workload balance."""
    average_std_dev: float
    max_std_dev: float
    teacher_balance: dict[str, float] = field(default_factory=dict)
    unbalanced_teachers: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Lower std dev is better. Returns 100 - normalized deviation."""
        # Normalize: 0 std dev = 100, 3+ std dev = 0
        normalized = max(0, 100 - (self.average_std_dev / 3) * 100)
        return round(normalized, 2)


@dataclass
class UtilizationMetrics:
    """Metrics for resource utilization."""
    room_utilization: float
    teacher_utilization: float
    slot_utilization: float
    total_lessons_scheduled: int
    total_slots_available: int


@dataclass
class MetricsReport:
    """Complete metrics report for a timetable solution."""
    # Individual metric components
    gap_metrics: GapMetrics
    distribution_metrics: DistributionMetrics
    balance_metrics: BalanceMetrics
    utilization_metrics: UtilizationMetrics

    # Overall scores
    overall_score: float
    grade: str

    # Constraint satisfaction
    hard_constraints_satisfied: bool
    soft_constraint_penalty: int

    # Summary statistics
    total_lessons: int
    total_teachers: int
    total_days: int

    # Improvement suggestions
    improvement_areas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "overallScore": self.overall_score,
            "grade": self.grade,
            "hardConstraintsSatisfied": self.hard_constraints_satisfied,
            "softConstraintPenalty": self.soft_constraint_penalty,
            "totalLessons": self.total_lessons,
            "totalTeachers": self.total_teachers,
            "totalDays": self.total_days,
            "gaps": {
                "score": self.gap_metrics.score,
                "averageGapMinutes": self.gap_metrics.average_gap_minutes,
                "maxGapMinutes": self.gap_metrics.max_gap_minutes,
            },
            "distribution": {
                "score": self.distribution_metrics.score,
                "wellDistributedPercent": self.distribution_metrics.percentage_well_distributed,
                "poorlyDistributed": self.distribution_metrics.poorly_distributed,
            },
            "balance": {
                "score": self.balance_metrics.score,
                "averageStdDev": self.balance_metrics.average_std_dev,
                "unbalancedTeachers": self.balance_metrics.unbalanced_teachers,
            },
            "utilization": {
                "roomUtilization": self.utilization_metrics.room_utilization,
                "teacherUtilization": self.utilization_metrics.teacher_utilization,
                "slotUtilization": self.utilization_metrics.slot_utilization,
            },
            "improvementAreas": self.improvement_areas,
        }


# =============================================================================
# Quality Metrics Calculator
# =============================================================================

class QualityMetricsCalculator:
    """
    Calculator for timetable quality metrics.

    Evaluates timetable solutions across multiple dimensions:
    - Gap score: Idle time between lessons for teachers
    - Distribution score: How well lessons are spread across days
    - Daily balance: Evenness of daily workload
    - Utilization: Resource usage efficiency

    Usage:
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(output, input_data)
        print(calculator.generate_report(report))
    """

    def __init__(self, targets: dict[str, float] | None = None):
        """
        Initialize the calculator.

        Args:
            targets: Custom target thresholds (optional)
        """
        self.targets = {**DEFAULT_TARGETS, **(targets or {})}

    def calculate_all(
        self,
        output: TimetableOutput,
        input_data: TimetableInput,
    ) -> MetricsReport:
        """
        Calculate all quality metrics for a timetable solution.

        Args:
            output: The timetable solution output
            input_data: The original input data

        Returns:
            MetricsReport with all metrics calculated
        """
        # Calculate individual metrics
        gap_metrics = self.calculate_gap_metrics(output, input_data.teachers)
        distribution_metrics = self.calculate_distribution_metrics(output, input_data.lessons)
        balance_metrics = self.calculate_daily_balance_metrics(output, input_data.teachers)
        utilization_metrics = self.calculate_utilization_metrics(output, input_data)

        # Calculate overall score (weighted average)
        overall_score = self._calculate_overall_score(
            gap_metrics, distribution_metrics, balance_metrics, utilization_metrics
        )

        # Determine grade
        grade = self._score_to_grade(overall_score)

        # Identify improvement areas
        improvement_areas = self._identify_improvements(
            gap_metrics, distribution_metrics, balance_metrics, utilization_metrics
        )

        # Get unique days in schedule
        days_in_schedule = set()
        for lesson in output.timetable.lessons:
            days_in_schedule.add(lesson.day)

        return MetricsReport(
            gap_metrics=gap_metrics,
            distribution_metrics=distribution_metrics,
            balance_metrics=balance_metrics,
            utilization_metrics=utilization_metrics,
            overall_score=overall_score,
            grade=grade,
            hard_constraints_satisfied=output.quality.hard_constraints_satisfied,
            soft_constraint_penalty=output.quality.total_penalty,
            total_lessons=len(output.timetable.lessons),
            total_teachers=len(output.views.by_teacher),
            total_days=len(days_in_schedule),
            improvement_areas=improvement_areas,
        )

    def calculate_gap_score(
        self,
        output: TimetableOutput,
        teachers: list[Teacher],
    ) -> float:
        """
        Calculate the gap score for teachers.

        For each teacher, for each day:
        - Find first and last lesson
        - Gap = (last_end - first_start) - total_teaching_time
        - Return average gap across all teacher-days

        Args:
            output: The timetable solution
            teachers: List of teachers

        Returns:
            Average gap in minutes (lower is better)
        """
        metrics = self.calculate_gap_metrics(output, teachers)
        return metrics.average_gap_minutes

    def calculate_gap_metrics(
        self,
        output: TimetableOutput,
        teachers: list[Teacher],
    ) -> GapMetrics:
        """
        Calculate detailed gap metrics.

        Args:
            output: The timetable solution
            teachers: List of teachers

        Returns:
            GapMetrics with detailed breakdown
        """
        total_gap = 0.0
        max_gap = 0.0
        teacher_days = 0
        gaps_by_teacher: dict[str, float] = {}

        for teacher in teachers:
            teacher_schedule = output.views.by_teacher.get(teacher.id)
            if not teacher_schedule:
                continue

            teacher_total_gap = 0.0
            teacher_day_count = 0

            for day, day_lessons in teacher_schedule.by_day.items():
                if len(day_lessons) < 2:
                    continue

                # Sort by start time
                sorted_lessons = sorted(day_lessons, key=lambda l: l.start_time)

                # Get first and last lesson times
                first_start = self._time_to_minutes(sorted_lessons[0].start_time)
                last_end = self._time_to_minutes(sorted_lessons[-1].end_time)

                # Calculate total teaching time
                total_teaching = sum(
                    self._time_to_minutes(l.end_time) - self._time_to_minutes(l.start_time)
                    for l in sorted_lessons
                )

                # Gap = span - teaching time
                day_gap = (last_end - first_start) - total_teaching
                day_gap = max(0, day_gap)  # Ensure non-negative

                total_gap += day_gap
                max_gap = max(max_gap, day_gap)
                teacher_total_gap += day_gap
                teacher_day_count += 1
                teacher_days += 1

            if teacher_day_count > 0:
                gaps_by_teacher[teacher.id] = teacher_total_gap / teacher_day_count

        avg_gap = total_gap / teacher_days if teacher_days > 0 else 0.0

        return GapMetrics(
            average_gap_minutes=round(avg_gap, 2),
            max_gap_minutes=max_gap,
            total_gap_minutes=total_gap,
            teacher_days_analyzed=teacher_days,
            gaps_by_teacher=gaps_by_teacher,
        )

    def calculate_distribution_score(
        self,
        output: TimetableOutput,
        lessons: list[Lesson],
    ) -> float:
        """
        Calculate the distribution score for lessons.

        For each multi-lesson subject:
        - Check if lessons are scheduled on different days
        - Return percentage that are well-distributed

        Args:
            output: The timetable solution
            lessons: List of lesson definitions

        Returns:
            Percentage of well-distributed multi-lesson subjects (0-100)
        """
        metrics = self.calculate_distribution_metrics(output, lessons)
        return metrics.percentage_well_distributed

    def calculate_distribution_metrics(
        self,
        output: TimetableOutput,
        lessons: list[Lesson],
    ) -> DistributionMetrics:
        """
        Calculate detailed distribution metrics.

        Args:
            output: The timetable solution
            lessons: List of lesson definitions

        Returns:
            DistributionMetrics with detailed breakdown
        """
        # Group output lessons by lesson_id to find multi-instance lessons
        lessons_by_id: dict[str, list[LessonOutput]] = {}
        for lesson_output in output.timetable.lessons:
            lid = lesson_output.lesson_id
            if lid not in lessons_by_id:
                lessons_by_id[lid] = []
            lessons_by_id[lid].append(lesson_output)

        # Identify multi-lesson subjects (lessons with 2+ instances)
        multi_lesson_ids = [lid for lid, instances in lessons_by_id.items() if len(instances) >= 2]

        well_distributed = 0
        poorly_distributed: list[str] = []

        for lid in multi_lesson_ids:
            instances = lessons_by_id[lid]
            days_used = set(l.day for l in instances)

            # Well-distributed if each instance is on a different day
            if len(days_used) == len(instances):
                well_distributed += 1
            else:
                # Find the lesson definition for reporting
                lesson_def = next((l for l in lessons if l.id == lid), None)
                if lesson_def:
                    poorly_distributed.append(
                        f"{lesson_def.subject_id} ({lid}): {len(instances)} lessons on {len(days_used)} days"
                    )

        total_multi = len(multi_lesson_ids)
        percentage = (well_distributed / total_multi * 100) if total_multi > 0 else 100.0

        return DistributionMetrics(
            well_distributed_count=well_distributed,
            total_multi_lesson_subjects=total_multi,
            percentage_well_distributed=round(percentage, 2),
            poorly_distributed=poorly_distributed,
        )

    def calculate_daily_balance(
        self,
        output: TimetableOutput,
        teachers: list[Teacher],
    ) -> float:
        """
        Calculate daily workload balance for teachers.

        For each teacher, count lessons per day and calculate
        standard deviation. Return average std dev across teachers.

        Args:
            output: The timetable solution
            teachers: List of teachers

        Returns:
            Average standard deviation of daily lesson counts
        """
        metrics = self.calculate_daily_balance_metrics(output, teachers)
        return metrics.average_std_dev

    def calculate_daily_balance_metrics(
        self,
        output: TimetableOutput,
        teachers: list[Teacher],
    ) -> BalanceMetrics:
        """
        Calculate detailed balance metrics.

        Args:
            output: The timetable solution
            teachers: List of teachers

        Returns:
            BalanceMetrics with detailed breakdown
        """
        teacher_std_devs: dict[str, float] = {}
        unbalanced: list[str] = []

        for teacher in teachers:
            teacher_schedule = output.views.by_teacher.get(teacher.id)
            if not teacher_schedule:
                continue

            # Count lessons per day
            lessons_per_day: list[int] = []

            # Include all days (even those with 0 lessons)
            for day in range(5):  # Mon-Fri
                day_lessons = teacher_schedule.by_day.get(day, [])
                lessons_per_day.append(len(day_lessons))

            if not lessons_per_day or sum(lessons_per_day) == 0:
                continue

            # Calculate standard deviation
            std_dev = self._calculate_std_dev(lessons_per_day)
            teacher_std_devs[teacher.id] = std_dev

            # Flag if significantly unbalanced (std dev > 1.5)
            if std_dev > self.targets["daily_balance"]:
                unbalanced.append(f"{teacher.name}: std_dev={std_dev:.2f}")

        if not teacher_std_devs:
            return BalanceMetrics(
                average_std_dev=0.0,
                max_std_dev=0.0,
                teacher_balance={},
                unbalanced_teachers=[],
            )

        avg_std_dev = sum(teacher_std_devs.values()) / len(teacher_std_devs)
        max_std_dev = max(teacher_std_devs.values())

        return BalanceMetrics(
            average_std_dev=round(avg_std_dev, 2),
            max_std_dev=round(max_std_dev, 2),
            teacher_balance=teacher_std_devs,
            unbalanced_teachers=unbalanced,
        )

    def calculate_utilization_metrics(
        self,
        output: TimetableOutput,
        input_data: TimetableInput,
    ) -> UtilizationMetrics:
        """
        Calculate resource utilization metrics.

        Args:
            output: The timetable solution
            input_data: The original input data

        Returns:
            UtilizationMetrics with utilization percentages
        """
        total_lessons = len(output.timetable.lessons)

        # Room utilization: lessons / (rooms * periods)
        schedulable_periods = len(input_data.get_schedulable_periods())
        total_room_slots = len(input_data.rooms) * schedulable_periods
        room_util = (total_lessons / total_room_slots * 100) if total_room_slots > 0 else 0

        # Teacher utilization: lessons / (teachers * periods)
        total_teacher_slots = len(input_data.teachers) * schedulable_periods
        teacher_util = (total_lessons / total_teacher_slots * 100) if total_teacher_slots > 0 else 0

        # Slot utilization: unique (day, time) combinations used
        used_slots = set()
        for lesson in output.timetable.lessons:
            used_slots.add((lesson.day, lesson.start_time))
        slot_util = (len(used_slots) / schedulable_periods * 100) if schedulable_periods > 0 else 0

        return UtilizationMetrics(
            room_utilization=round(room_util, 2),
            teacher_utilization=round(teacher_util, 2),
            slot_utilization=round(slot_util, 2),
            total_lessons_scheduled=total_lessons,
            total_slots_available=total_room_slots,
        )

    def generate_report(self, metrics: MetricsReport) -> str:
        """
        Generate a human-readable report with all metrics.

        Args:
            metrics: The calculated MetricsReport

        Returns:
            Formatted string report
        """
        lines = []

        # Header
        lines.append("=" * 70)
        lines.append("TIMETABLE QUALITY REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Overall Score
        lines.append(f"Overall Score: {metrics.overall_score:.1f}/100 (Grade: {metrics.grade})")
        lines.append(f"Hard Constraints: {'SATISFIED' if metrics.hard_constraints_satisfied else 'VIOLATED'}")
        lines.append(f"Soft Constraint Penalty: {metrics.soft_constraint_penalty}")
        lines.append("")

        # Summary
        lines.append("-" * 40)
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Lessons Scheduled: {metrics.total_lessons}")
        lines.append(f"Teachers with Schedules: {metrics.total_teachers}")
        lines.append(f"Days Used: {metrics.total_days}")
        lines.append("")

        # Gap Analysis
        lines.append("-" * 40)
        lines.append("GAP ANALYSIS (Teacher idle time)")
        lines.append("-" * 40)
        gap = metrics.gap_metrics
        lines.append(f"Score: {gap.score}/100")
        lines.append(f"Average Gap: {gap.average_gap_minutes:.1f} minutes")
        lines.append(f"Maximum Gap: {gap.max_gap_minutes:.0f} minutes")
        lines.append(f"Teacher-Days Analyzed: {gap.teacher_days_analyzed}")
        target = self.targets["gap_score"]
        status = "GOOD" if gap.average_gap_minutes <= target else "NEEDS IMPROVEMENT"
        lines.append(f"Target: <={target:.0f} min | Status: {status}")
        lines.append("")

        # Distribution
        lines.append("-" * 40)
        lines.append("DISTRIBUTION (Lessons spread across days)")
        lines.append("-" * 40)
        dist = metrics.distribution_metrics
        lines.append(f"Score: {dist.score}/100")
        lines.append(f"Well-Distributed: {dist.well_distributed_count}/{dist.total_multi_lesson_subjects}")
        lines.append(f"Percentage: {dist.percentage_well_distributed:.1f}%")
        target = self.targets["distribution_score"]
        status = "GOOD" if dist.percentage_well_distributed >= target else "NEEDS IMPROVEMENT"
        lines.append(f"Target: >={target:.0f}% | Status: {status}")
        if dist.poorly_distributed:
            lines.append("Poorly distributed lessons:")
            for item in dist.poorly_distributed[:5]:  # Show top 5
                lines.append(f"  - {item}")
        lines.append("")

        # Balance
        lines.append("-" * 40)
        lines.append("DAILY BALANCE (Workload evenness)")
        lines.append("-" * 40)
        balance = metrics.balance_metrics
        lines.append(f"Score: {balance.score}/100")
        lines.append(f"Average Std Dev: {balance.average_std_dev:.2f}")
        lines.append(f"Maximum Std Dev: {balance.max_std_dev:.2f}")
        target = self.targets["daily_balance"]
        status = "GOOD" if balance.average_std_dev <= target else "NEEDS IMPROVEMENT"
        lines.append(f"Target: <={target:.1f} | Status: {status}")
        if balance.unbalanced_teachers:
            lines.append("Unbalanced teachers:")
            for item in balance.unbalanced_teachers[:5]:
                lines.append(f"  - {item}")
        lines.append("")

        # Utilization
        lines.append("-" * 40)
        lines.append("UTILIZATION")
        lines.append("-" * 40)
        util = metrics.utilization_metrics
        lines.append(f"Room Utilization: {util.room_utilization:.1f}%")
        lines.append(f"Teacher Utilization: {util.teacher_utilization:.1f}%")
        lines.append(f"Time Slot Utilization: {util.slot_utilization:.1f}%")
        lines.append(f"Lessons/Slots: {util.total_lessons_scheduled}/{util.total_slots_available}")
        lines.append("")

        # Improvement Areas
        if metrics.improvement_areas:
            lines.append("-" * 40)
            lines.append("AREAS FOR IMPROVEMENT")
            lines.append("-" * 40)
            for area in metrics.improvement_areas:
                lines.append(f"  * {area}")
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _time_to_minutes(self, time_str: str) -> int:
        """Convert HH:MM to minutes from midnight."""
        parts = time_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])

    def _calculate_std_dev(self, values: list[int | float]) -> float:
        """Calculate standard deviation of a list of values."""
        if not values:
            return 0.0
        n = len(values)
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / n
        return math.sqrt(variance)

    def _calculate_overall_score(
        self,
        gap: GapMetrics,
        dist: DistributionMetrics,
        balance: BalanceMetrics,
        util: UtilizationMetrics,
    ) -> float:
        """Calculate weighted overall score."""
        # Weights for each component
        weights = {
            "gap": 0.25,
            "distribution": 0.30,
            "balance": 0.25,
            "utilization": 0.20,
        }

        # Normalize utilization to 0-100 score
        util_score = min(100, util.slot_utilization)

        score = (
            weights["gap"] * gap.score +
            weights["distribution"] * dist.score +
            weights["balance"] * balance.score +
            weights["utilization"] * util_score
        )

        return round(score, 1)

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def _identify_improvements(
        self,
        gap: GapMetrics,
        dist: DistributionMetrics,
        balance: BalanceMetrics,
        util: UtilizationMetrics,
    ) -> list[str]:
        """Identify areas that need improvement."""
        improvements = []

        if gap.average_gap_minutes > self.targets["gap_score"]:
            improvements.append(
                f"Reduce teacher gaps: Average gap ({gap.average_gap_minutes:.0f} min) "
                f"exceeds target ({self.targets['gap_score']:.0f} min)"
            )

        if dist.percentage_well_distributed < self.targets["distribution_score"]:
            improvements.append(
                f"Improve lesson distribution: {dist.percentage_well_distributed:.0f}% well-distributed "
                f"is below target ({self.targets['distribution_score']:.0f}%)"
            )

        if balance.average_std_dev > self.targets["daily_balance"]:
            improvements.append(
                f"Balance daily workloads: Std dev ({balance.average_std_dev:.2f}) "
                f"exceeds target ({self.targets['daily_balance']:.1f})"
            )

        if util.slot_utilization < self.targets["utilization"]:
            improvements.append(
                f"Improve slot utilization: {util.slot_utilization:.0f}% "
                f"is below target ({self.targets['utilization']:.0f}%)"
            )

        return improvements


# =============================================================================
# Convenience Functions
# =============================================================================

def calculate_all_metrics(
    output: TimetableOutput,
    input_data: TimetableInput,
    targets: dict[str, float] | None = None,
) -> MetricsReport:
    """
    Calculate all quality metrics for a timetable solution.

    Args:
        output: The timetable solution output
        input_data: The original input data
        targets: Custom target thresholds (optional)

    Returns:
        MetricsReport with all metrics
    """
    calculator = QualityMetricsCalculator(targets)
    return calculator.calculate_all(output, input_data)


def calculate_gap_score(
    output: TimetableOutput,
    teachers: list[Teacher],
) -> float:
    """
    Calculate average teacher gap score.

    Args:
        output: The timetable solution
        teachers: List of teachers

    Returns:
        Average gap in minutes
    """
    calculator = QualityMetricsCalculator()
    return calculator.calculate_gap_score(output, teachers)


def calculate_distribution_score(
    output: TimetableOutput,
    lessons: list[Lesson],
) -> float:
    """
    Calculate distribution score for lessons.

    Args:
        output: The timetable solution
        lessons: List of lesson definitions

    Returns:
        Percentage of well-distributed lessons (0-100)
    """
    calculator = QualityMetricsCalculator()
    return calculator.calculate_distribution_score(output, lessons)


def calculate_daily_balance(
    output: TimetableOutput,
    teachers: list[Teacher],
) -> float:
    """
    Calculate daily workload balance.

    Args:
        output: The timetable solution
        teachers: List of teachers

    Returns:
        Average standard deviation of daily lesson counts
    """
    calculator = QualityMetricsCalculator()
    return calculator.calculate_daily_balance(output, teachers)


def generate_report(
    output: TimetableOutput,
    input_data: TimetableInput,
    targets: dict[str, float] | None = None,
) -> str:
    """
    Generate a human-readable quality report.

    Args:
        output: The timetable solution output
        input_data: The original input data
        targets: Custom target thresholds (optional)

    Returns:
        Formatted report string
    """
    calculator = QualityMetricsCalculator(targets)
    metrics = calculator.calculate_all(output, input_data)
    return calculator.generate_report(metrics)
