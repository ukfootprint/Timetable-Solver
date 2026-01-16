"""Tests for solution extractor."""

from __future__ import annotations

import json
import pytest

from solver.data.models import (
    TimetableInput,
    Teacher,
    StudentClass,
    Subject,
    Room,
    Lesson,
    Period,
    RoomType,
)
from solver.model_builder import TimetableModelBuilder
from solver.constraints import ConstraintManager
from solver.output.extractor import (
    SolutionExtractor,
    extract_solution,
    extract_to_json,
    extract_to_dict,
    minutes_to_time_string,
    week_minutes_to_day_time,
    group_by_teacher,
    group_by_class,
    group_by_room,
    group_by_day,
    sort_lessons,
)
from solver.output.schema import OutputStatus, LessonOutput


@pytest.fixture
def basic_input() -> TimetableInput:
    """Create basic timetable input for testing."""
    return TimetableInput(
        teachers=[
            Teacher(id="t1", name="Mr Smith"),
            Teacher(id="t2", name="Ms Jones"),
        ],
        classes=[
            StudentClass(id="c1", name="Year 10A"),
        ],
        subjects=[
            Subject(id="mat", name="Maths"),
            Subject(id="eng", name="English"),
        ],
        rooms=[
            Room(id="r1", name="Room 101", type=RoomType.CLASSROOM),
            Room(id="r2", name="Room 102", type=RoomType.CLASSROOM),
        ],
        lessons=[
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
            Lesson(id="l2", teacher_id="t2", class_id="c1", subject_id="eng", lessons_per_week=1),
        ],
        periods=[
            Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            Period(id="wed1", name="Wed P1", day=2, start_minutes=540, end_minutes=600),
        ],
    )


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_minutes_to_time_string(self):
        """Converts minutes to HH:MM format."""
        assert minutes_to_time_string(0) == "00:00"
        assert minutes_to_time_string(540) == "09:00"
        assert minutes_to_time_string(825) == "13:45"
        assert minutes_to_time_string(1439) == "23:59"

    def test_week_minutes_to_day_time(self):
        """Converts week minutes to (day, day_minutes)."""
        # Monday 9:00
        assert week_minutes_to_day_time(540) == (0, 540)
        # Tuesday 9:00
        assert week_minutes_to_day_time(1440 + 540) == (1, 540)
        # Wednesday 10:30
        assert week_minutes_to_day_time(2880 + 630) == (2, 630)

    def test_group_by_teacher(self):
        """Groups lessons by teacher."""
        lessons = [
            LessonOutput(
                lessonId="l1", instance=0, day=0, startTime="09:00", endTime="10:00",
                roomId="r1", teacherId="t1", classId="c1", subjectId="mat"
            ),
            LessonOutput(
                lessonId="l2", instance=0, day=0, startTime="10:00", endTime="11:00",
                roomId="r1", teacherId="t2", classId="c1", subjectId="eng"
            ),
            LessonOutput(
                lessonId="l1", instance=1, day=1, startTime="09:00", endTime="10:00",
                roomId="r1", teacherId="t1", classId="c1", subjectId="mat"
            ),
        ]

        grouped = group_by_teacher(lessons)

        assert "t1" in grouped
        assert "t2" in grouped
        assert len(grouped["t1"]) == 2
        assert len(grouped["t2"]) == 1

    def test_group_by_class(self):
        """Groups lessons by class."""
        lessons = [
            LessonOutput(
                lessonId="l1", instance=0, day=0, startTime="09:00", endTime="10:00",
                roomId="r1", teacherId="t1", classId="c1", subjectId="mat"
            ),
            LessonOutput(
                lessonId="l2", instance=0, day=0, startTime="10:00", endTime="11:00",
                roomId="r1", teacherId="t2", classId="c2", subjectId="eng"
            ),
        ]

        grouped = group_by_class(lessons)

        assert "c1" in grouped
        assert "c2" in grouped
        assert len(grouped["c1"]) == 1
        assert len(grouped["c2"]) == 1

    def test_group_by_room(self):
        """Groups lessons by room."""
        lessons = [
            LessonOutput(
                lessonId="l1", instance=0, day=0, startTime="09:00", endTime="10:00",
                roomId="r1", teacherId="t1", classId="c1", subjectId="mat"
            ),
            LessonOutput(
                lessonId="l2", instance=0, day=0, startTime="10:00", endTime="11:00",
                roomId="r2", teacherId="t2", classId="c1", subjectId="eng"
            ),
        ]

        grouped = group_by_room(lessons)

        assert "r1" in grouped
        assert "r2" in grouped

    def test_group_by_day(self):
        """Groups lessons by day."""
        lessons = [
            LessonOutput(
                lessonId="l1", instance=0, day=0, startTime="09:00", endTime="10:00",
                roomId="r1", teacherId="t1", classId="c1", subjectId="mat"
            ),
            LessonOutput(
                lessonId="l1", instance=1, day=2, startTime="09:00", endTime="10:00",
                roomId="r1", teacherId="t1", classId="c1", subjectId="mat"
            ),
        ]

        grouped = group_by_day(lessons)

        assert 0 in grouped
        assert 2 in grouped
        assert len(grouped[0]) == 1
        assert len(grouped[2]) == 1

    def test_sort_lessons(self):
        """Sorts lessons by day then time."""
        lessons = [
            LessonOutput(
                lessonId="l1", instance=0, day=2, startTime="09:00", endTime="10:00",
                roomId="r1", teacherId="t1", classId="c1", subjectId="mat"
            ),
            LessonOutput(
                lessonId="l2", instance=0, day=0, startTime="10:00", endTime="11:00",
                roomId="r1", teacherId="t1", classId="c1", subjectId="mat"
            ),
            LessonOutput(
                lessonId="l3", instance=0, day=0, startTime="09:00", endTime="10:00",
                roomId="r1", teacherId="t1", classId="c1", subjectId="mat"
            ),
        ]

        sorted_lessons = sort_lessons(lessons)

        assert sorted_lessons[0].lesson_id == "l3"  # Day 0, 09:00
        assert sorted_lessons[1].lesson_id == "l2"  # Day 0, 10:00
        assert sorted_lessons[2].lesson_id == "l1"  # Day 2, 09:00


class TestSolutionExtractor:
    """Tests for SolutionExtractor class."""

    def test_extract_feasible_solution(self, basic_input):
        """Extracts feasible solution correctly."""
        from ortools.sat.python import cp_model

        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30
        status = solver.Solve(builder.model)

        extractor = SolutionExtractor()
        output = extractor.extract(solver, builder, status)

        assert output.status in (OutputStatus.OPTIMAL, OutputStatus.FEASIBLE)
        assert len(output.timetable.lessons) == 3  # 2 + 1 lessons
        assert output.quality.hard_constraints_satisfied is True

    def test_extract_includes_all_metadata(self, basic_input):
        """Extracted lessons include all metadata."""
        from ortools.sat.python import cp_model

        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()

        solver = cp_model.CpSolver()
        status = solver.Solve(builder.model)

        extractor = SolutionExtractor()
        output = extractor.extract(solver, builder, status)

        # Check first lesson has all fields
        lesson = output.timetable.lessons[0]
        assert lesson.lesson_id is not None
        assert lesson.teacher_id is not None
        assert lesson.class_id is not None
        assert lesson.subject_id is not None
        assert lesson.room_id is not None
        assert lesson.start_time is not None
        assert lesson.end_time is not None

    def test_extract_creates_views(self, basic_input):
        """Extracted solution includes all views."""
        from ortools.sat.python import cp_model

        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()

        solver = cp_model.CpSolver()
        status = solver.Solve(builder.model)

        extractor = SolutionExtractor()
        output = extractor.extract(solver, builder, status)

        # Check views are populated
        assert len(output.views.by_teacher) > 0
        assert len(output.views.by_class) > 0
        assert len(output.views.by_room) > 0
        assert len(output.views.by_day) > 0

    def test_extract_handles_infeasible(self):
        """Handles infeasible solution gracefully."""
        from ortools.sat.python import cp_model

        # Create an infeasible scenario
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # 3 lessons but only 2 slots
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=3),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()

        solver = cp_model.CpSolver()
        status = solver.Solve(builder.model)

        extractor = SolutionExtractor()
        output = extractor.extract(solver, builder, status)

        assert output.status == OutputStatus.INFEASIBLE
        assert len(output.timetable.lessons) == 0
        assert output.quality.hard_constraints_satisfied is False

    def test_extract_quality_metrics(self, basic_input):
        """Extracts quality metrics correctly."""
        from ortools.sat.python import cp_model

        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()

        solver = cp_model.CpSolver()
        status = solver.Solve(builder.model)

        extractor = SolutionExtractor()
        output = extractor.extract(solver, builder, status)

        assert output.quality.total_penalty >= 0
        assert isinstance(output.quality.soft_constraint_scores, dict)


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_extract_solution_function(self, basic_input):
        """extract_solution function works correctly."""
        from ortools.sat.python import cp_model

        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()

        solver = cp_model.CpSolver()
        status = solver.Solve(builder.model)

        output = extract_solution(solver, builder, status)

        assert output.status in (OutputStatus.OPTIMAL, OutputStatus.FEASIBLE)

    def test_extract_to_json_function(self, basic_input):
        """extract_to_json function produces valid JSON."""
        from ortools.sat.python import cp_model

        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()

        solver = cp_model.CpSolver()
        status = solver.Solve(builder.model)

        json_str = extract_to_json(solver, builder, status)

        # Should parse without error
        data = json.loads(json_str)
        assert "status" in data
        assert "timetable" in data

    def test_extract_to_dict_function(self, basic_input):
        """extract_to_dict function produces dictionary."""
        from ortools.sat.python import cp_model

        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()

        solver = cp_model.CpSolver()
        status = solver.Solve(builder.model)

        data = extract_to_dict(solver, builder, status)

        assert isinstance(data, dict)
        assert "status" in data


class TestViewsCorrectness:
    """Tests for correctness of extracted views."""

    def test_teacher_view_has_correct_lessons(self, basic_input):
        """Teacher view contains only their lessons."""
        from ortools.sat.python import cp_model

        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()

        solver = cp_model.CpSolver()
        status = solver.Solve(builder.model)

        extractor = SolutionExtractor()
        output = extractor.extract(solver, builder, status)

        # t1 teaches l1 (2 instances)
        if "t1" in output.views.by_teacher:
            t1_lessons = output.views.by_teacher["t1"].lessons
            for lesson in t1_lessons:
                assert lesson.teacher_id == "t1"

        # t2 teaches l2 (1 instance)
        if "t2" in output.views.by_teacher:
            t2_lessons = output.views.by_teacher["t2"].lessons
            for lesson in t2_lessons:
                assert lesson.teacher_id == "t2"

    def test_day_view_has_correct_lessons(self, basic_input):
        """Day view contains only lessons on that day."""
        from ortools.sat.python import cp_model

        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()

        solver = cp_model.CpSolver()
        status = solver.Solve(builder.model)

        extractor = SolutionExtractor()
        output = extractor.extract(solver, builder, status)

        for day, day_schedule in output.views.by_day.items():
            for lesson in day_schedule.lessons:
                assert lesson.day == day

    def test_entity_schedule_by_day_correct(self, basic_input):
        """Entity schedule byDay grouping is correct."""
        from ortools.sat.python import cp_model

        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()

        solver = cp_model.CpSolver()
        status = solver.Solve(builder.model)

        extractor = SolutionExtractor()
        output = extractor.extract(solver, builder, status)

        for teacher_id, teacher_schedule in output.views.by_teacher.items():
            for day, lessons in teacher_schedule.by_day.items():
                for lesson in lessons:
                    assert lesson.day == day
                    assert lesson.teacher_id == teacher_id
