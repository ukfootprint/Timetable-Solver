"""Tests for availability constraints."""

from __future__ import annotations

import pytest

from solver.data.models import (
    TimetableInput,
    Teacher,
    StudentClass,
    Subject,
    Room,
    Lesson,
    Period,
    Availability,
    RoomType,
)
from solver.model_builder import TimetableModelBuilder, SolverStatus
from solver.constraints.availability import (
    add_teacher_unavailability,
    add_class_unavailability,
    add_school_day_constraints,
    add_break_avoidance,
    add_all_availability_constraints,
    AvailabilityStats,
    day_minutes_to_week_minutes,
)


class TestDayMinutesToWeekMinutes:
    """Tests for time conversion helper."""

    def test_monday_morning(self):
        # Monday 9:00 AM
        assert day_minutes_to_week_minutes(0, 540) == 540

    def test_tuesday_morning(self):
        # Tuesday 9:00 AM = 1440 + 540 = 1980
        assert day_minutes_to_week_minutes(1, 540) == 1980

    def test_friday_afternoon(self):
        # Friday 3:00 PM = 4 * 1440 + 900 = 6660
        assert day_minutes_to_week_minutes(4, 900) == 6660


class TestTeacherUnavailability:
    """Tests for teacher unavailability constraints."""

    def test_teacher_with_no_unavailability(self):
        """Teacher without unavailability adds no constraints."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        count = add_teacher_unavailability(builder)
        assert count == 0

    def test_teacher_unavailability_adds_constraints(self):
        """Teacher with unavailability adds constraints for each lesson instance."""
        input_data = TimetableInput(
            teachers=[
                Teacher(
                    id="t1",
                    name="Teacher 1",
                    availability=[
                        Availability(day=0, start_minutes=540, end_minutes=600, available=False, reason="Meeting"),
                    ]
                ),
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        count = add_teacher_unavailability(builder)
        # 1 teacher * 1 unavailability window * 2 lesson instances
        assert count == 2

    def test_respects_teacher_unavailability(self):
        """Solver respects teacher unavailability constraint."""
        input_data = TimetableInput(
            teachers=[
                Teacher(
                    id="t1",
                    name="Teacher 1",
                    availability=[
                        # Unavailable Monday morning
                        Availability(day=0, start_minutes=540, end_minutes=660, available=False),
                    ]
                ),
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        add_teacher_unavailability(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible
        assert len(solution.assignments) == 1

        # Should be scheduled on Tuesday, not Monday
        assignment = solution.assignments[0]
        assert assignment.day == 1  # Tuesday

    def test_infeasible_when_all_slots_unavailable(self):
        """Infeasible when teacher is unavailable for all slots."""
        input_data = TimetableInput(
            teachers=[
                Teacher(
                    id="t1",
                    name="Teacher 1",
                    availability=[
                        # Unavailable all day Monday (0-1439 covers whole day)
                        Availability(day=0, start_minutes=0, end_minutes=1439, available=False),
                    ]
                ),
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                # Only Monday slots available
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        add_teacher_unavailability(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.status == SolverStatus.INFEASIBLE


class TestClassUnavailability:
    """Tests for class unavailability constraints."""

    def test_respects_class_unavailability(self):
        """Solver respects class unavailability constraint."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[
                StudentClass(
                    id="c1",
                    name="Class 1",
                    availability=[
                        # Class unavailable Monday morning (assembly)
                        Availability(day=0, start_minutes=540, end_minutes=600, available=False, reason="Assembly"),
                    ]
                ),
            ],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        add_class_unavailability(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible
        assert len(solution.assignments) == 1

        # Should be scheduled on Tuesday
        assignment = solution.assignments[0]
        assert assignment.day == 1


class TestSchoolDayConstraints:
    """Tests for school day boundary constraints."""

    def test_adds_constraints_per_day(self):
        """Adds boundary constraints for each day with periods."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        count = add_school_day_constraints(builder)
        # 1 lesson instance * 2 days with periods = 2 constraints
        assert count == 2


class TestBreakAvoidance:
    """Tests for break avoidance constraints."""

    def test_no_constraints_without_breaks(self):
        """No constraints added when no break periods exist."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        count = add_break_avoidance(builder)
        assert count == 0

    def test_adds_constraints_for_breaks(self):
        """Adds constraints for each break period."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="break", name="Break", day=0, start_minutes=600, end_minutes=620, is_break=True),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=620, end_minutes=680),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        count = add_break_avoidance(builder)
        # 1 break * 2 lesson instances = 2 constraints
        assert count == 2

    def test_adds_constraints_for_lunch(self):
        """Adds constraints for lunch periods."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="lunch", name="Lunch", day=0, start_minutes=720, end_minutes=780, is_lunch=True),
                Period(id="mon3", name="Mon P3", day=0, start_minutes=780, end_minutes=840),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        count = add_break_avoidance(builder)
        # 1 lunch * 1 lesson instance = 1 constraint
        assert count == 1


class TestAddAllAvailabilityConstraints:
    """Tests for the combined availability constraints function."""

    def test_returns_stats(self):
        """Returns statistics about added constraints."""
        input_data = TimetableInput(
            teachers=[
                Teacher(
                    id="t1",
                    name="Teacher 1",
                    availability=[
                        Availability(day=0, start_minutes=540, end_minutes=600, available=False),
                    ]
                ),
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="break", name="Break", day=0, start_minutes=600, end_minutes=620, is_break=True),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=620, end_minutes=680),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        stats = add_all_availability_constraints(builder)

        assert isinstance(stats, AvailabilityStats)
        assert stats.teachers_with_unavailability == 1
        assert stats.teacher_unavailability_constraints == 1
        assert stats.break_avoidance_constraints == 1

    def test_full_model_with_all_constraints(self):
        """Full model with all availability constraints finds valid solution."""
        input_data = TimetableInput(
            teachers=[
                Teacher(
                    id="t1",
                    name="Teacher 1",
                    availability=[
                        # Unavailable Monday first period
                        Availability(day=0, start_minutes=540, end_minutes=600, available=False),
                    ]
                ),
                Teacher(id="t2", name="Teacher 2"),
            ],
            classes=[
                StudentClass(id="c1", name="Class 1"),
                StudentClass(id="c2", name="Class 2"),
            ],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
                Room(id="r2", name="Room 2", type=RoomType.CLASSROOM),
            ],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
                Lesson(id="l2", teacher_id="t2", class_id="c2", subject_id="mat", lessons_per_week=2),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="break", name="Break", day=0, start_minutes=660, end_minutes=680, is_break=True),
                Period(id="mon3", name="Mon P3", day=0, start_minutes=680, end_minutes=740),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        add_all_availability_constraints(builder)
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        builder._add_room_no_overlap_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Check teacher 1's lessons are not on Monday first period
        t1_assignments = [a for a in solution.assignments if a.teacher_id == "t1"]
        for a in t1_assignments:
            # Should not be Monday (day 0) first period (starting at 540)
            if a.day == 0:
                assert a.start_minutes != 540
