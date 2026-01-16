"""
Solution extractor for converting CP-SAT solutions to output format.

This module extracts variable values from a solved CP-SAT model and
converts them to the structured TimetableOutput format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from .schema import (
    OutputStatus,
    LessonOutput,
    QualityMetrics,
    DaySchedule,
    EntitySchedule,
    TimetableViews,
    Timetable,
    TimetableOutput,
)

if TYPE_CHECKING:
    from solver.model_builder import (
        TimetableModelBuilder,
        LessonInstanceVars,
        PenaltyVar,
    )
    from solver.data.models import TimetableInput


# =============================================================================
# Constants
# =============================================================================

MINUTES_PER_DAY = 1440
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# =============================================================================
# Helper Functions
# =============================================================================

def minutes_to_time_string(minutes: int) -> str:
    """
    Convert minutes from midnight to 'HH:MM' string.

    Args:
        minutes: Minutes from midnight (0-1439)

    Returns:
        Time string in 'HH:MM' format

    Examples:
        >>> minutes_to_time_string(540)
        '09:00'
        >>> minutes_to_time_string(825)
        '13:45'
    """
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def week_minutes_to_day_time(week_minutes: int) -> tuple[int, int]:
    """
    Convert week minutes to (day, day_minutes).

    Args:
        week_minutes: Minutes from start of week

    Returns:
        Tuple of (day_index, minutes_from_midnight)

    Examples:
        >>> week_minutes_to_day_time(540)  # Monday 9:00
        (0, 540)
        >>> week_minutes_to_day_time(1980)  # Tuesday 9:00
        (1, 540)
    """
    day = week_minutes // MINUTES_PER_DAY
    day_minutes = week_minutes % MINUTES_PER_DAY
    return day, day_minutes


def group_by_teacher(lessons: list[LessonOutput]) -> dict[str, list[LessonOutput]]:
    """Group lessons by teacher ID."""
    result: dict[str, list[LessonOutput]] = {}
    for lesson in lessons:
        if lesson.teacher_id not in result:
            result[lesson.teacher_id] = []
        result[lesson.teacher_id].append(lesson)
    return result


def group_by_class(lessons: list[LessonOutput]) -> dict[str, list[LessonOutput]]:
    """Group lessons by class ID."""
    result: dict[str, list[LessonOutput]] = {}
    for lesson in lessons:
        if lesson.class_id not in result:
            result[lesson.class_id] = []
        result[lesson.class_id].append(lesson)
    return result


def group_by_room(lessons: list[LessonOutput]) -> dict[str, list[LessonOutput]]:
    """Group lessons by room ID."""
    result: dict[str, list[LessonOutput]] = {}
    for lesson in lessons:
        if lesson.room_id not in result:
            result[lesson.room_id] = []
        result[lesson.room_id].append(lesson)
    return result


def group_by_day(lessons: list[LessonOutput]) -> dict[int, list[LessonOutput]]:
    """Group lessons by day index."""
    result: dict[int, list[LessonOutput]] = {}
    for lesson in lessons:
        if lesson.day not in result:
            result[lesson.day] = []
        result[lesson.day].append(lesson)
    return result


def sort_lessons(lessons: list[LessonOutput]) -> list[LessonOutput]:
    """Sort lessons by day then start time."""
    return sorted(lessons, key=lambda l: (l.day, l.start_time))


# =============================================================================
# Solution Extractor
# =============================================================================

class SolutionExtractor:
    """
    Extracts and converts CP-SAT solver solutions to output format.

    This class handles the conversion from raw solver variable values
    to structured TimetableOutput with all views populated.

    Usage:
        extractor = SolutionExtractor()

        # After solving:
        status = solver.Solve(model)
        output = extractor.extract(solver, builder, status)
    """

    def __init__(self):
        """Initialize the solution extractor."""
        pass

    def extract(
        self,
        solver: cp_model.CpSolver,
        builder: TimetableModelBuilder,
        solver_status: int | None = None,
    ) -> TimetableOutput:
        """
        Extract solution from solver and build output.

        Args:
            solver: The CP-SAT solver after solving
            builder: The model builder with variables and input data
            solver_status: The status code returned from solver.Solve()
                          If None, assumes OPTIMAL/FEASIBLE based on objective

        Returns:
            TimetableOutput with complete solution data
        """
        # 1. Check solver status
        status = self._get_status(solver, solver_status)

        # 2. Get solve time
        solve_time_seconds = solver.WallTime()

        # If not feasible, return empty output
        if status not in (OutputStatus.OPTIMAL, OutputStatus.FEASIBLE):
            return self._create_empty_output(status, solve_time_seconds)

        # 3. Extract lesson assignments
        lessons = self._extract_lessons(solver, builder)

        # 4. Calculate quality metrics
        quality = self._extract_quality(solver, builder)

        # 5. Create views
        views = self._create_views(lessons, builder.input)

        # 6. Build and return output
        return TimetableOutput(
            status=status,
            solveTimeSeconds=solve_time_seconds,
            quality=quality,
            timetable=Timetable(lessons=lessons),
            views=views,
        )

    def extract_from_builder(
        self,
        builder: TimetableModelBuilder,
        solver_status: int,
        solver: cp_model.CpSolver,
    ) -> TimetableOutput:
        """
        Extract solution using builder's stored data.

        Alternative method that uses the builder's solve results.

        Args:
            builder: The model builder after solving
            solver_status: The raw solver status code
            solver: The CP-SAT solver

        Returns:
            TimetableOutput with complete solution data
        """
        return self.extract(solver, builder, solver_status)

    def _get_status(
        self,
        solver: cp_model.CpSolver,
        solver_status: int | None,
    ) -> OutputStatus:
        """Map CP-SAT status to output status."""
        if solver_status is None:
            # Try to infer from solver state
            try:
                # If we can get an objective value, it's likely feasible
                solver.ObjectiveValue()
                return OutputStatus.OPTIMAL
            except Exception:
                return OutputStatus.UNKNOWN

        status_name = solver.StatusName(solver_status)

        status_map = {
            "OPTIMAL": OutputStatus.OPTIMAL,
            "FEASIBLE": OutputStatus.FEASIBLE,
            "INFEASIBLE": OutputStatus.INFEASIBLE,
            "MODEL_INVALID": OutputStatus.UNKNOWN,
            "UNKNOWN": OutputStatus.TIMEOUT,
        }

        return status_map.get(status_name, OutputStatus.UNKNOWN)

    def _create_empty_output(
        self,
        status: OutputStatus,
        solve_time_seconds: float,
    ) -> TimetableOutput:
        """Create output for non-feasible solutions."""
        return TimetableOutput(
            status=status,
            solveTimeSeconds=solve_time_seconds,
            quality=QualityMetrics(
                totalPenalty=0,
                hardConstraintsSatisfied=False,
                softConstraintScores={},
            ),
            timetable=Timetable(lessons=[]),
            views=TimetableViews(
                byTeacher={},
                byClass={},
                byRoom={},
                byDay={},
            ),
        )

    def _extract_lessons(
        self,
        solver: cp_model.CpSolver,
        builder: TimetableModelBuilder,
    ) -> list[LessonOutput]:
        """Extract lesson assignments from solver."""
        lessons: list[LessonOutput] = []

        for lesson_id, instances in builder.lesson_vars.items():
            # Get lesson metadata
            lesson_data = builder.input.get_lesson(lesson_id)
            if not lesson_data:
                continue

            teacher = builder.input.get_teacher(lesson_data.teacher_id)
            cls = builder.input.get_class(lesson_data.class_id)
            subject = builder.input.get_subject(lesson_data.subject_id)

            for inst in instances:
                lesson_output = self._extract_single_lesson(
                    solver=solver,
                    inst=inst,
                    builder=builder,
                    teacher_name=teacher.name if teacher else None,
                    class_name=cls.name if cls else None,
                    subject_name=subject.name if subject else None,
                    teacher_id=lesson_data.teacher_id,
                    class_id=lesson_data.class_id,
                    subject_id=lesson_data.subject_id,
                )
                lessons.append(lesson_output)

        # Sort by day then time
        return sort_lessons(lessons)

    def _extract_single_lesson(
        self,
        solver: cp_model.CpSolver,
        inst: LessonInstanceVars,
        builder: TimetableModelBuilder,
        teacher_name: str | None,
        class_name: str | None,
        subject_name: str | None,
        teacher_id: str,
        class_id: str,
        subject_id: str,
    ) -> LessonOutput:
        """Extract a single lesson assignment."""
        # Get variable values
        week_start = solver.Value(inst.start_var)
        week_end = solver.Value(inst.end_var)
        room_idx = solver.Value(inst.room_var)
        day = solver.Value(inst.day_var)

        # Convert to day minutes
        _, start_minutes = week_minutes_to_day_time(week_start)
        _, end_minutes = week_minutes_to_day_time(week_end)

        # Get room info
        room = builder.input.rooms[room_idx]

        # Find matching period
        period_id, period_name = self._find_period(
            builder.input, day, start_minutes
        )

        return LessonOutput(
            lessonId=inst.lesson_id,
            instance=inst.instance,
            day=day,
            startTime=minutes_to_time_string(start_minutes),
            endTime=minutes_to_time_string(end_minutes),
            roomId=room.id,
            roomName=room.name,
            teacherId=teacher_id,
            teacherName=teacher_name,
            classId=class_id,
            className=class_name,
            subjectId=subject_id,
            subjectName=subject_name,
            periodId=period_id,
            periodName=period_name,
        )

    def _find_period(
        self,
        input_data: TimetableInput,
        day: int,
        start_minutes: int,
    ) -> tuple[str | None, str | None]:
        """Find the period matching day and start time."""
        for period in input_data.periods:
            if period.day == day and period.start_minutes == start_minutes:
                return period.id, period.name
        return None, None

    def _extract_quality(
        self,
        solver: cp_model.CpSolver,
        builder: TimetableModelBuilder,
    ) -> QualityMetrics:
        """Extract quality metrics from solver."""
        # Get objective value
        try:
            total_penalty = int(solver.ObjectiveValue())
        except Exception:
            total_penalty = 0

        # Extract individual penalty values
        soft_scores: dict[str, int] = {}
        for penalty_var in builder.penalty_vars:
            value = solver.Value(penalty_var.var)
            if value > 0:
                weighted_value = value * penalty_var.weight
                soft_scores[penalty_var.name] = weighted_value

        return QualityMetrics(
            totalPenalty=total_penalty,
            hardConstraintsSatisfied=True,
            softConstraintScores=soft_scores,
        )

    def _create_views(
        self,
        lessons: list[LessonOutput],
        input_data: TimetableInput,
    ) -> TimetableViews:
        """Create pre-computed views from lessons."""
        # Group lessons
        by_teacher = group_by_teacher(lessons)
        by_class = group_by_class(lessons)
        by_room = group_by_room(lessons)
        by_day = group_by_day(lessons)

        # Build name mappings
        teacher_names = {t.id: t.name for t in input_data.teachers}
        class_names = {c.id: c.name for c in input_data.classes}
        room_names = {r.id: r.name for r in input_data.rooms}

        # Create teacher schedules
        teacher_schedules = {}
        for teacher_id, teacher_lessons in by_teacher.items():
            sorted_lessons = sort_lessons(teacher_lessons)
            teacher_schedules[teacher_id] = EntitySchedule(
                id=teacher_id,
                name=teacher_names.get(teacher_id, teacher_id),
                lessons=sorted_lessons,
                byDay=self._group_entity_by_day(sorted_lessons),
            )

        # Create class schedules
        class_schedules = {}
        for class_id, class_lessons in by_class.items():
            sorted_lessons = sort_lessons(class_lessons)
            class_schedules[class_id] = EntitySchedule(
                id=class_id,
                name=class_names.get(class_id, class_id),
                lessons=sorted_lessons,
                byDay=self._group_entity_by_day(sorted_lessons),
            )

        # Create room schedules
        room_schedules = {}
        for room_id, room_lessons in by_room.items():
            sorted_lessons = sort_lessons(room_lessons)
            room_schedules[room_id] = EntitySchedule(
                id=room_id,
                name=room_names.get(room_id, room_id),
                lessons=sorted_lessons,
                byDay=self._group_entity_by_day(sorted_lessons),
            )

        # Create day schedules
        day_schedules = {}
        for day, day_lessons in by_day.items():
            sorted_lessons = sort_lessons(day_lessons)
            day_name = DAY_NAMES[day] if day < len(DAY_NAMES) else f"Day {day}"
            day_schedules[day] = DaySchedule(
                day=day,
                dayName=day_name,
                lessons=sorted_lessons,
            )

        return TimetableViews(
            byTeacher=teacher_schedules,
            byClass=class_schedules,
            byRoom=room_schedules,
            byDay=day_schedules,
        )

    def _group_entity_by_day(
        self,
        lessons: list[LessonOutput],
    ) -> dict[int, list[LessonOutput]]:
        """Group an entity's lessons by day."""
        result: dict[int, list[LessonOutput]] = {}
        for lesson in lessons:
            if lesson.day not in result:
                result[lesson.day] = []
            result[lesson.day].append(lesson)
        return result


# =============================================================================
# Convenience Functions
# =============================================================================

def extract_solution(
    solver: cp_model.CpSolver,
    builder: TimetableModelBuilder,
    solver_status: int | None = None,
) -> TimetableOutput:
    """
    Extract solution from solver - convenience function.

    Args:
        solver: The CP-SAT solver after solving
        builder: The model builder with variables
        solver_status: The status code returned from solver.Solve()

    Returns:
        TimetableOutput with complete solution
    """
    extractor = SolutionExtractor()
    return extractor.extract(solver, builder, solver_status)


def extract_to_json(
    solver: cp_model.CpSolver,
    builder: TimetableModelBuilder,
    solver_status: int | None = None,
    indent: int = 2,
) -> str:
    """
    Extract solution and convert to JSON string.

    Args:
        solver: The CP-SAT solver after solving
        builder: The model builder with variables
        solver_status: The status code returned from solver.Solve()
        indent: JSON indentation

    Returns:
        JSON string representation
    """
    output = extract_solution(solver, builder, solver_status)
    return output.to_json(indent=indent)


def extract_to_dict(
    solver: cp_model.CpSolver,
    builder: TimetableModelBuilder,
    solver_status: int | None = None,
) -> dict[str, Any]:
    """
    Extract solution and convert to dictionary.

    Args:
        solver: The CP-SAT solver after solving
        builder: The model builder with variables
        solver_status: The status code returned from solver.Solve()

    Returns:
        Dictionary representation
    """
    output = extract_solution(solver, builder, solver_status)
    return output.to_dict()
