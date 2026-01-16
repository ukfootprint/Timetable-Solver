"""
Output schema for solved timetables.

This module defines the JSON-serializable output format for timetable solutions,
including pre-computed views for convenient access by different dimensions.
"""

from __future__ import annotations

from datetime import time
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field

from solver.model_builder import SolverSolution, SolverStatus, LessonAssignment


# =============================================================================
# Enums
# =============================================================================

class OutputStatus(str, Enum):
    """Solution status for output."""
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


# =============================================================================
# Lesson Output
# =============================================================================

class LessonOutput(BaseModel):
    """A single lesson assignment in the output."""
    lesson_id: str = Field(alias="lessonId")
    instance: int
    day: int
    start_time: str = Field(alias="startTime")  # 'HH:MM'
    end_time: str = Field(alias="endTime")  # 'HH:MM'
    room_id: str = Field(alias="roomId")
    teacher_id: str = Field(alias="teacherId")
    class_id: str = Field(alias="classId")
    subject_id: str = Field(alias="subjectId")

    # Optional enriched data
    room_name: Optional[str] = Field(default=None, alias="roomName")
    teacher_name: Optional[str] = Field(default=None, alias="teacherName")
    class_name: Optional[str] = Field(default=None, alias="className")
    subject_name: Optional[str] = Field(default=None, alias="subjectName")
    period_id: Optional[str] = Field(default=None, alias="periodId")
    period_name: Optional[str] = Field(default=None, alias="periodName")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_assignment(cls, assignment: LessonAssignment) -> LessonOutput:
        """Create from a LessonAssignment."""
        return cls(
            lessonId=assignment.lesson_id,
            instance=assignment.instance,
            day=assignment.day,
            startTime=_minutes_to_time_str(assignment.start_minutes),
            endTime=_minutes_to_time_str(assignment.end_minutes),
            roomId=assignment.room_id,
            teacherId=assignment.teacher_id,
            classId=assignment.class_id,
            subjectId=assignment.subject_id,
            roomName=assignment.room_name,
            teacherName=assignment.teacher_name,
            className=assignment.class_name,
            subjectName=assignment.subject_name,
            periodId=assignment.period_id,
            periodName=assignment.period_name,
        )


# =============================================================================
# Quality Metrics
# =============================================================================

class QualityMetrics(BaseModel):
    """Quality metrics for the solution."""
    total_penalty: int = Field(alias="totalPenalty")
    hard_constraints_satisfied: bool = Field(alias="hardConstraintsSatisfied")
    soft_constraint_scores: dict[str, int] = Field(
        default_factory=dict,
        alias="softConstraintScores"
    )

    model_config = {"populate_by_name": True}


# =============================================================================
# Views
# =============================================================================

class DaySchedule(BaseModel):
    """Schedule for a single day."""
    day: int
    day_name: str = Field(alias="dayName")
    lessons: list[LessonOutput]

    model_config = {"populate_by_name": True}


class EntitySchedule(BaseModel):
    """Schedule for an entity (teacher, class, or room)."""
    id: str
    name: str
    lessons: list[LessonOutput]
    by_day: dict[int, list[LessonOutput]] = Field(
        default_factory=dict,
        alias="byDay"
    )

    model_config = {"populate_by_name": True}


class TimetableViews(BaseModel):
    """Pre-computed views of the timetable for convenience."""
    by_teacher: dict[str, EntitySchedule] = Field(
        default_factory=dict,
        alias="byTeacher"
    )
    by_class: dict[str, EntitySchedule] = Field(
        default_factory=dict,
        alias="byClass"
    )
    by_room: dict[str, EntitySchedule] = Field(
        default_factory=dict,
        alias="byRoom"
    )
    by_day: dict[int, DaySchedule] = Field(
        default_factory=dict,
        alias="byDay"
    )

    model_config = {"populate_by_name": True}


# =============================================================================
# Timetable
# =============================================================================

class Timetable(BaseModel):
    """The core timetable data."""
    lessons: list[LessonOutput]

    model_config = {"populate_by_name": True}


# =============================================================================
# Complete Output
# =============================================================================

class TimetableOutput(BaseModel):
    """Complete output for a solved timetable."""
    status: OutputStatus
    solve_time_seconds: float = Field(alias="solveTimeSeconds")
    quality: QualityMetrics
    timetable: Timetable
    views: TimetableViews

    model_config = {"populate_by_name": True}

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(by_alias=True, indent=indent)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return self.model_dump(by_alias=True)


# =============================================================================
# Conversion Functions
# =============================================================================

def _minutes_to_time_str(minutes: int) -> str:
    """Convert minutes from midnight to 'HH:MM' string."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def _status_to_output(status: SolverStatus) -> OutputStatus:
    """Convert SolverStatus to OutputStatus."""
    mapping = {
        SolverStatus.OPTIMAL: OutputStatus.OPTIMAL,
        SolverStatus.FEASIBLE: OutputStatus.FEASIBLE,
        SolverStatus.INFEASIBLE: OutputStatus.INFEASIBLE,
        SolverStatus.UNKNOWN: OutputStatus.TIMEOUT,
        SolverStatus.MODEL_INVALID: OutputStatus.UNKNOWN,
    }
    return mapping.get(status, OutputStatus.UNKNOWN)


DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def create_timetable_output(
    solution: SolverSolution,
    teacher_names: dict[str, str] | None = None,
    class_names: dict[str, str] | None = None,
    room_names: dict[str, str] | None = None,
) -> TimetableOutput:
    """
    Create a TimetableOutput from a SolverSolution.

    Args:
        solution: The solver solution
        teacher_names: Optional mapping of teacher_id to name
        class_names: Optional mapping of class_id to name
        room_names: Optional mapping of room_id to name

    Returns:
        TimetableOutput with all views populated
    """
    teacher_names = teacher_names or {}
    class_names = class_names or {}
    room_names = room_names or {}

    # Convert assignments to output format
    lessons = [
        LessonOutput.from_assignment(a)
        for a in solution.assignments
    ]

    # Create quality metrics
    quality = QualityMetrics(
        totalPenalty=solution.objective_value or 0,
        hardConstraintsSatisfied=solution.is_feasible,
        softConstraintScores=solution.penalties,
    )

    # Create views
    views = _create_views(lessons, teacher_names, class_names, room_names)

    return TimetableOutput(
        status=_status_to_output(solution.status),
        solveTimeSeconds=solution.solve_time_ms / 1000.0,
        quality=quality,
        timetable=Timetable(lessons=lessons),
        views=views,
    )


def _create_views(
    lessons: list[LessonOutput],
    teacher_names: dict[str, str],
    class_names: dict[str, str],
    room_names: dict[str, str],
) -> TimetableViews:
    """Create pre-computed views from lessons."""
    # Group lessons by different dimensions
    by_teacher: dict[str, list[LessonOutput]] = {}
    by_class: dict[str, list[LessonOutput]] = {}
    by_room: dict[str, list[LessonOutput]] = {}
    by_day: dict[int, list[LessonOutput]] = {}

    for lesson in lessons:
        # By teacher
        if lesson.teacher_id not in by_teacher:
            by_teacher[lesson.teacher_id] = []
        by_teacher[lesson.teacher_id].append(lesson)

        # By class
        if lesson.class_id not in by_class:
            by_class[lesson.class_id] = []
        by_class[lesson.class_id].append(lesson)

        # By room
        if lesson.room_id not in by_room:
            by_room[lesson.room_id] = []
        by_room[lesson.room_id].append(lesson)

        # By day
        if lesson.day not in by_day:
            by_day[lesson.day] = []
        by_day[lesson.day].append(lesson)

    # Sort lessons within each group by day then start time
    def sort_lessons(lesson_list: list[LessonOutput]) -> list[LessonOutput]:
        return sorted(lesson_list, key=lambda l: (l.day, l.start_time))

    # Create EntitySchedule for teachers
    teacher_schedules = {}
    for teacher_id, teacher_lessons in by_teacher.items():
        sorted_lessons = sort_lessons(teacher_lessons)
        teacher_by_day = _group_by_day(sorted_lessons)
        teacher_schedules[teacher_id] = EntitySchedule(
            id=teacher_id,
            name=teacher_names.get(teacher_id) or teacher_lessons[0].teacher_name or teacher_id,
            lessons=sorted_lessons,
            byDay=teacher_by_day,
        )

    # Create EntitySchedule for classes
    class_schedules = {}
    for class_id, class_lessons in by_class.items():
        sorted_lessons = sort_lessons(class_lessons)
        class_by_day = _group_by_day(sorted_lessons)
        class_schedules[class_id] = EntitySchedule(
            id=class_id,
            name=class_names.get(class_id) or class_lessons[0].class_name or class_id,
            lessons=sorted_lessons,
            byDay=class_by_day,
        )

    # Create EntitySchedule for rooms
    room_schedules = {}
    for room_id, room_lessons in by_room.items():
        sorted_lessons = sort_lessons(room_lessons)
        room_by_day = _group_by_day(sorted_lessons)
        room_schedules[room_id] = EntitySchedule(
            id=room_id,
            name=room_names.get(room_id) or room_lessons[0].room_name or room_id,
            lessons=sorted_lessons,
            byDay=room_by_day,
        )

    # Create DaySchedule for each day
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


def _group_by_day(lessons: list[LessonOutput]) -> dict[int, list[LessonOutput]]:
    """Group lessons by day."""
    by_day: dict[int, list[LessonOutput]] = {}
    for lesson in lessons:
        if lesson.day not in by_day:
            by_day[lesson.day] = []
        by_day[lesson.day].append(lesson)
    return by_day


# =============================================================================
# Convenience Functions
# =============================================================================

def solution_to_json(
    solution: SolverSolution,
    teacher_names: dict[str, str] | None = None,
    class_names: dict[str, str] | None = None,
    room_names: dict[str, str] | None = None,
    indent: int = 2,
) -> str:
    """
    Convert a SolverSolution directly to JSON string.

    Args:
        solution: The solver solution
        teacher_names: Optional mapping of teacher_id to name
        class_names: Optional mapping of class_id to name
        room_names: Optional mapping of room_id to name
        indent: JSON indentation

    Returns:
        JSON string representation
    """
    output = create_timetable_output(
        solution,
        teacher_names=teacher_names,
        class_names=class_names,
        room_names=room_names,
    )
    return output.to_json(indent=indent)


def solution_to_dict(
    solution: SolverSolution,
    teacher_names: dict[str, str] | None = None,
    class_names: dict[str, str] | None = None,
    room_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Convert a SolverSolution directly to dictionary.

    Args:
        solution: The solver solution
        teacher_names: Optional mapping of teacher_id to name
        class_names: Optional mapping of class_id to name
        room_names: Optional mapping of room_id to name

    Returns:
        Dictionary representation
    """
    output = create_timetable_output(
        solution,
        teacher_names=teacher_names,
        class_names=class_names,
        room_names=room_names,
    )
    return output.to_dict()
