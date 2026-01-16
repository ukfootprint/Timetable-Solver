"""Tests for output schema."""

from __future__ import annotations

import json
import pytest

from solver.model_builder import SolverSolution, SolverStatus, LessonAssignment
from solver.output.schema import (
    OutputStatus,
    LessonOutput,
    QualityMetrics,
    DaySchedule,
    EntitySchedule,
    TimetableViews,
    Timetable,
    TimetableOutput,
    create_timetable_output,
    solution_to_json,
    solution_to_dict,
)


@pytest.fixture
def sample_assignments() -> list[LessonAssignment]:
    """Create sample lesson assignments."""
    return [
        LessonAssignment(
            lesson_id="l1",
            instance=0,
            day=0,
            start_minutes=540,  # 09:00
            end_minutes=600,    # 10:00
            room_id="r1",
            room_name="Room 101",
            teacher_id="t1",
            teacher_name="Mr Smith",
            class_id="c1",
            class_name="Year 10A",
            subject_id="mat",
            subject_name="Maths",
            period_id="mon1",
            period_name="Monday Period 1",
        ),
        LessonAssignment(
            lesson_id="l1",
            instance=1,
            day=2,
            start_minutes=600,  # 10:00
            end_minutes=660,    # 11:00
            room_id="r1",
            room_name="Room 101",
            teacher_id="t1",
            teacher_name="Mr Smith",
            class_id="c1",
            class_name="Year 10A",
            subject_id="mat",
            subject_name="Maths",
            period_id="wed2",
            period_name="Wednesday Period 2",
        ),
        LessonAssignment(
            lesson_id="l2",
            instance=0,
            day=0,
            start_minutes=600,  # 10:00
            end_minutes=660,    # 11:00
            room_id="r2",
            room_name="Room 102",
            teacher_id="t2",
            teacher_name="Ms Jones",
            class_id="c1",
            class_name="Year 10A",
            subject_id="eng",
            subject_name="English",
            period_id="mon2",
            period_name="Monday Period 2",
        ),
    ]


@pytest.fixture
def sample_solution(sample_assignments) -> SolverSolution:
    """Create a sample solver solution."""
    return SolverSolution(
        status=SolverStatus.OPTIMAL,
        assignments=sample_assignments,
        solve_time_ms=1500,
        objective_value=25,
        penalties={"same_day_l1_0_1": 10, "teacher_gap_t1_day0": 15},
    )


class TestLessonOutput:
    """Tests for LessonOutput model."""

    def test_from_assignment(self, sample_assignments):
        """Creates LessonOutput from LessonAssignment."""
        assignment = sample_assignments[0]
        output = LessonOutput.from_assignment(assignment)

        assert output.lesson_id == "l1"
        assert output.instance == 0
        assert output.day == 0
        assert output.start_time == "09:00"
        assert output.end_time == "10:00"
        assert output.room_id == "r1"
        assert output.teacher_id == "t1"
        assert output.class_id == "c1"
        assert output.subject_id == "mat"

    def test_serializes_with_camel_case(self, sample_assignments):
        """Serializes to camelCase JSON."""
        assignment = sample_assignments[0]
        output = LessonOutput.from_assignment(assignment)
        data = output.model_dump(by_alias=True)

        assert "lessonId" in data
        assert "startTime" in data
        assert "endTime" in data
        assert "roomId" in data
        assert "teacherId" in data
        assert "classId" in data
        assert "subjectId" in data

    def test_time_formatting(self):
        """Time is formatted as HH:MM."""
        assignment = LessonAssignment(
            lesson_id="l1",
            instance=0,
            day=0,
            start_minutes=65,   # 01:05
            end_minutes=125,    # 02:05
            room_id="r1",
            room_name="Room 1",
            teacher_id="t1",
            teacher_name="Teacher 1",
            class_id="c1",
            class_name="Class 1",
            subject_id="s1",
            subject_name="Subject 1",
        )
        output = LessonOutput.from_assignment(assignment)

        assert output.start_time == "01:05"
        assert output.end_time == "02:05"


class TestQualityMetrics:
    """Tests for QualityMetrics model."""

    def test_creates_from_values(self):
        """Creates QualityMetrics with correct values."""
        metrics = QualityMetrics(
            totalPenalty=100,
            hardConstraintsSatisfied=True,
            softConstraintScores={"gap": 50, "distribution": 50},
        )

        assert metrics.total_penalty == 100
        assert metrics.hard_constraints_satisfied is True
        assert metrics.soft_constraint_scores["gap"] == 50

    def test_serializes_with_camel_case(self):
        """Serializes to camelCase JSON."""
        metrics = QualityMetrics(
            totalPenalty=100,
            hardConstraintsSatisfied=True,
            softConstraintScores={},
        )
        data = metrics.model_dump(by_alias=True)

        assert "totalPenalty" in data
        assert "hardConstraintsSatisfied" in data
        assert "softConstraintScores" in data


class TestCreateTimetableOutput:
    """Tests for create_timetable_output function."""

    def test_creates_output_from_solution(self, sample_solution):
        """Creates complete TimetableOutput from SolverSolution."""
        output = create_timetable_output(sample_solution)

        assert output.status == OutputStatus.OPTIMAL
        assert output.solve_time_seconds == 1.5
        assert output.quality.total_penalty == 25
        assert output.quality.hard_constraints_satisfied is True
        assert len(output.timetable.lessons) == 3

    def test_status_mapping(self):
        """Maps solver status correctly."""
        statuses = [
            (SolverStatus.OPTIMAL, OutputStatus.OPTIMAL),
            (SolverStatus.FEASIBLE, OutputStatus.FEASIBLE),
            (SolverStatus.INFEASIBLE, OutputStatus.INFEASIBLE),
            (SolverStatus.UNKNOWN, OutputStatus.TIMEOUT),
        ]

        for solver_status, expected in statuses:
            solution = SolverSolution(
                status=solver_status,
                assignments=[],
                solve_time_ms=0,
            )
            output = create_timetable_output(solution)
            assert output.status == expected

    def test_views_by_teacher(self, sample_solution):
        """Creates views grouped by teacher."""
        output = create_timetable_output(sample_solution)

        assert "t1" in output.views.by_teacher
        assert "t2" in output.views.by_teacher

        t1_schedule = output.views.by_teacher["t1"]
        assert t1_schedule.id == "t1"
        assert t1_schedule.name == "Mr Smith"
        assert len(t1_schedule.lessons) == 2  # l1 instance 0 and 1

    def test_views_by_class(self, sample_solution):
        """Creates views grouped by class."""
        output = create_timetable_output(sample_solution)

        assert "c1" in output.views.by_class

        c1_schedule = output.views.by_class["c1"]
        assert c1_schedule.id == "c1"
        assert c1_schedule.name == "Year 10A"
        assert len(c1_schedule.lessons) == 3  # All lessons for c1

    def test_views_by_room(self, sample_solution):
        """Creates views grouped by room."""
        output = create_timetable_output(sample_solution)

        assert "r1" in output.views.by_room
        assert "r2" in output.views.by_room

        r1_schedule = output.views.by_room["r1"]
        assert r1_schedule.id == "r1"
        assert r1_schedule.name == "Room 101"
        assert len(r1_schedule.lessons) == 2

    def test_views_by_day(self, sample_solution):
        """Creates views grouped by day."""
        output = create_timetable_output(sample_solution)

        assert 0 in output.views.by_day  # Monday
        assert 2 in output.views.by_day  # Wednesday

        monday = output.views.by_day[0]
        assert monday.day == 0
        assert monday.day_name == "Monday"
        assert len(monday.lessons) == 2  # 2 lessons on Monday

    def test_lessons_sorted_by_time(self, sample_solution):
        """Lessons within views are sorted by day and time."""
        output = create_timetable_output(sample_solution)

        # Teacher t1 has lessons on day 0 (09:00) and day 2 (10:00)
        t1_lessons = output.views.by_teacher["t1"].lessons
        assert t1_lessons[0].day == 0
        assert t1_lessons[1].day == 2

        # Monday lessons should be sorted by time
        monday_lessons = output.views.by_day[0].lessons
        assert monday_lessons[0].start_time == "09:00"
        assert monday_lessons[1].start_time == "10:00"

    def test_entity_schedule_has_by_day(self, sample_solution):
        """EntitySchedule includes lessons grouped by day."""
        output = create_timetable_output(sample_solution)

        t1_schedule = output.views.by_teacher["t1"]
        assert 0 in t1_schedule.by_day
        assert 2 in t1_schedule.by_day
        assert len(t1_schedule.by_day[0]) == 1  # 1 lesson on Monday
        assert len(t1_schedule.by_day[2]) == 1  # 1 lesson on Wednesday


class TestSolutionToJson:
    """Tests for solution_to_json function."""

    def test_produces_valid_json(self, sample_solution):
        """Produces valid JSON string."""
        json_str = solution_to_json(sample_solution)

        # Should parse without error
        data = json.loads(json_str)
        assert isinstance(data, dict)

    def test_json_has_camel_case_keys(self, sample_solution):
        """JSON uses camelCase keys."""
        json_str = solution_to_json(sample_solution)
        data = json.loads(json_str)

        assert "solveTimeSeconds" in data
        assert "quality" in data
        assert "totalPenalty" in data["quality"]
        assert "hardConstraintsSatisfied" in data["quality"]
        assert "timetable" in data
        assert "views" in data
        assert "byTeacher" in data["views"]
        assert "byClass" in data["views"]
        assert "byRoom" in data["views"]
        assert "byDay" in data["views"]

    def test_json_lessons_have_correct_structure(self, sample_solution):
        """Lesson objects in JSON have correct structure."""
        json_str = solution_to_json(sample_solution)
        data = json.loads(json_str)

        lessons = data["timetable"]["lessons"]
        assert len(lessons) == 3

        lesson = lessons[0]
        assert "lessonId" in lesson
        assert "instance" in lesson
        assert "day" in lesson
        assert "startTime" in lesson
        assert "endTime" in lesson
        assert "roomId" in lesson
        assert "teacherId" in lesson
        assert "classId" in lesson
        assert "subjectId" in lesson


class TestSolutionToDict:
    """Tests for solution_to_dict function."""

    def test_produces_dict(self, sample_solution):
        """Produces dictionary."""
        data = solution_to_dict(sample_solution)

        assert isinstance(data, dict)
        assert "status" in data
        assert "solveTimeSeconds" in data
        assert "quality" in data
        assert "timetable" in data
        assert "views" in data


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_solution(self):
        """Handles empty solution."""
        solution = SolverSolution(
            status=SolverStatus.OPTIMAL,
            assignments=[],
            solve_time_ms=100,
            objective_value=0,
        )

        output = create_timetable_output(solution)

        assert len(output.timetable.lessons) == 0
        assert len(output.views.by_teacher) == 0
        assert len(output.views.by_day) == 0

    def test_infeasible_solution(self):
        """Handles infeasible solution."""
        solution = SolverSolution(
            status=SolverStatus.INFEASIBLE,
            assignments=[],
            solve_time_ms=5000,
        )

        output = create_timetable_output(solution)

        assert output.status == OutputStatus.INFEASIBLE
        assert output.quality.hard_constraints_satisfied is False

    def test_custom_name_mappings(self, sample_solution):
        """Uses custom name mappings when provided."""
        output = create_timetable_output(
            sample_solution,
            teacher_names={"t1": "Custom Teacher"},
            class_names={"c1": "Custom Class"},
            room_names={"r1": "Custom Room"},
        )

        assert output.views.by_teacher["t1"].name == "Custom Teacher"
        assert output.views.by_class["c1"].name == "Custom Class"
        assert output.views.by_room["r1"].name == "Custom Room"

    def test_missing_optional_fields(self):
        """Handles assignments with missing optional fields."""
        assignment = LessonAssignment(
            lesson_id="l1",
            instance=0,
            day=0,
            start_minutes=540,
            end_minutes=600,
            room_id="r1",
            room_name="Room 1",
            teacher_id="t1",
            teacher_name="Teacher 1",
            class_id="c1",
            class_name="Class 1",
            subject_id="s1",
            subject_name="Subject 1",
            # period_id and period_name not set
        )

        output = LessonOutput.from_assignment(assignment)

        assert output.period_id is None
        assert output.period_name is None


class TestTimetableOutputSerialization:
    """Tests for TimetableOutput serialization methods."""

    def test_to_json_method(self, sample_solution):
        """TimetableOutput.to_json() works correctly."""
        output = create_timetable_output(sample_solution)
        json_str = output.to_json()

        data = json.loads(json_str)
        assert "status" in data
        assert data["status"] == "optimal"

    def test_to_dict_method(self, sample_solution):
        """TimetableOutput.to_dict() works correctly."""
        output = create_timetable_output(sample_solution)
        data = output.to_dict()

        assert isinstance(data, dict)
        assert data["status"] == "optimal"
