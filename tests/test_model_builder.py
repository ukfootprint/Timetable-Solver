"""Tests for the TimetableModelBuilder."""

from __future__ import annotations

import pytest

from solver.model_builder import (
    TimetableModelBuilder,
    SolverStatus,
    minutes_to_week_time,
    week_time_to_minutes,
    day_minutes_to_week_minutes,
    format_week_time,
    MINUTES_PER_DAY,
)
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
    SchoolConfig,
)


class TestTimeConversions:
    """Tests for time conversion helpers."""

    def test_minutes_to_week_time(self):
        # Monday 00:00
        assert minutes_to_week_time(0) == (0, 0, 0)
        # Monday 09:30
        assert minutes_to_week_time(570) == (0, 9, 30)
        # Monday 23:59
        assert minutes_to_week_time(1439) == (0, 23, 59)
        # Tuesday 00:00
        assert minutes_to_week_time(1440) == (1, 0, 0)
        # Tuesday 09:00
        assert minutes_to_week_time(1980) == (1, 9, 0)
        # Friday 16:00
        assert minutes_to_week_time(5760 + 960) == (4, 16, 0)

    def test_week_time_to_minutes(self):
        assert week_time_to_minutes(0, 0, 0) == 0
        assert week_time_to_minutes(0, 9, 30) == 570
        assert week_time_to_minutes(1, 9, 0) == 1980
        assert week_time_to_minutes(4, 16, 0) == 5760 + 960

    def test_roundtrip(self):
        for minutes in [0, 570, 1440, 1980, 5760, 7199]:
            day, hour, minute = minutes_to_week_time(minutes)
            assert week_time_to_minutes(day, hour, minute) == minutes

    def test_day_minutes_to_week_minutes(self):
        assert day_minutes_to_week_minutes(0, 540) == 540  # Monday 9:00
        assert day_minutes_to_week_minutes(1, 540) == 1440 + 540  # Tuesday 9:00
        assert day_minutes_to_week_minutes(4, 540) == 4 * 1440 + 540  # Friday 9:00

    def test_format_week_time(self):
        assert format_week_time(570) == "Mon 09:30"
        assert format_week_time(1980) == "Tue 09:00"
        assert format_week_time(5760 + 960) == "Fri 16:00"


@pytest.fixture
def minimal_input() -> TimetableInput:
    """Minimal valid timetable input for testing."""
    return TimetableInput(
        config=SchoolConfig(school_name="Test School", num_days=5),
        teachers=[
            Teacher(id="t1", name="Teacher 1"),
            Teacher(id="t2", name="Teacher 2"),
        ],
        classes=[
            StudentClass(id="c1", name="Class 1"),
            StudentClass(id="c2", name="Class 2"),
        ],
        subjects=[
            Subject(id="s1", name="Subject 1"),
            Subject(id="s2", name="Subject 2"),
        ],
        rooms=[
            Room(id="r1", name="Room 1", type=RoomType.CLASSROOM, capacity=30),
            Room(id="r2", name="Room 2", type=RoomType.CLASSROOM, capacity=30),
        ],
        lessons=[
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="s1", lessons_per_week=3),
            Lesson(id="l2", teacher_id="t2", class_id="c1", subject_id="s2", lessons_per_week=2),
            Lesson(id="l3", teacher_id="t1", class_id="c2", subject_id="s1", lessons_per_week=3),
        ],
        periods=[
            # Monday periods
            Period(id="mon1", name="Period 1", day=0, start_minutes=540, end_minutes=600),
            Period(id="mon2", name="Period 2", day=0, start_minutes=600, end_minutes=660),
            Period(id="mon3", name="Period 3", day=0, start_minutes=680, end_minutes=740),
            # Tuesday periods
            Period(id="tue1", name="Period 1", day=1, start_minutes=540, end_minutes=600),
            Period(id="tue2", name="Period 2", day=1, start_minutes=600, end_minutes=660),
            Period(id="tue3", name="Period 3", day=1, start_minutes=680, end_minutes=740),
            # Wednesday periods
            Period(id="wed1", name="Period 1", day=2, start_minutes=540, end_minutes=600),
            Period(id="wed2", name="Period 2", day=2, start_minutes=600, end_minutes=660),
            Period(id="wed3", name="Period 3", day=2, start_minutes=680, end_minutes=740),
            # Thursday periods
            Period(id="thu1", name="Period 1", day=3, start_minutes=540, end_minutes=600),
            Period(id="thu2", name="Period 2", day=3, start_minutes=600, end_minutes=660),
            Period(id="thu3", name="Period 3", day=3, start_minutes=680, end_minutes=740),
            # Friday periods
            Period(id="fri1", name="Period 1", day=4, start_minutes=540, end_minutes=600),
            Period(id="fri2", name="Period 2", day=4, start_minutes=600, end_minutes=660),
            Period(id="fri3", name="Period 3", day=4, start_minutes=680, end_minutes=740),
        ],
    )


class TestModelBuilder:
    """Tests for TimetableModelBuilder."""

    def test_initialization(self, minimal_input):
        """Test model builder initialization."""
        builder = TimetableModelBuilder(minimal_input)

        assert builder.num_days == 5
        assert builder.week_minutes == 5 * MINUTES_PER_DAY
        assert not builder._variables_created
        assert not builder._constraints_added

    def test_create_variables(self, minimal_input):
        """Test variable creation."""
        builder = TimetableModelBuilder(minimal_input)
        builder.create_variables()

        # Should have variables for each lesson
        assert len(builder.lesson_vars) == 3

        # l1 has 3 instances
        assert len(builder.lesson_vars["l1"]) == 3
        # l2 has 2 instances
        assert len(builder.lesson_vars["l2"]) == 2
        # l3 has 3 instances
        assert len(builder.lesson_vars["l3"]) == 3

        # Check variable structure
        l1_inst0 = builder.lesson_vars["l1"][0]
        assert l1_inst0.lesson_id == "l1"
        assert l1_inst0.instance == 0
        assert l1_inst0.duration == 60  # default

    def test_get_statistics(self, minimal_input):
        """Test statistics gathering."""
        builder = TimetableModelBuilder(minimal_input)
        builder.create_variables()

        stats = builder.get_statistics()

        assert stats["num_lessons"] == 3
        assert stats["num_lesson_instances"] == 8  # 3 + 2 + 3
        assert stats["num_teachers"] == 2
        assert stats["num_rooms"] == 2
        assert stats["num_periods"] == 15
        assert stats["variables_created"] is True

    def test_get_teacher_intervals(self, minimal_input):
        """Test getting intervals for a teacher."""
        builder = TimetableModelBuilder(minimal_input)
        builder.create_variables()

        # Teacher t1 teaches l1 (3 instances) and l3 (3 instances)
        t1_intervals = builder.get_teacher_intervals("t1")
        assert len(t1_intervals) == 6

        # Teacher t2 teaches l2 (2 instances)
        t2_intervals = builder.get_teacher_intervals("t2")
        assert len(t2_intervals) == 2

    def test_get_class_intervals(self, minimal_input):
        """Test getting intervals for a class."""
        builder = TimetableModelBuilder(minimal_input)
        builder.create_variables()

        # Class c1 has l1 (3) and l2 (2) = 5 instances
        c1_intervals = builder.get_class_intervals("c1")
        assert len(c1_intervals) == 5

        # Class c2 has l3 (3)
        c2_intervals = builder.get_class_intervals("c2")
        assert len(c2_intervals) == 3

    def test_solve_simple(self, minimal_input):
        """Test solving a simple problem."""
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        assert solution.is_feasible
        assert len(solution.assignments) == 8  # All lesson instances assigned

    def test_solve_with_teacher_availability(self, minimal_input):
        """Test solving with teacher availability constraints."""
        # Make teacher t1 unavailable Monday morning
        minimal_input.teachers[0].availability = [
            Availability(day=0, start_minutes=540, end_minutes=660, available=False)
        ]

        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        assert solution.is_feasible

        # Check that t1's lessons are not on Monday period 1 or 2
        for assignment in solution.assignments:
            if assignment.teacher_id == "t1":
                if assignment.day == 0:
                    assert assignment.start_minutes >= 680, \
                        "Teacher t1 should not be scheduled during unavailable time"


class TestRoomConstraints:
    """Tests for room-related constraints."""

    def test_room_type_constraint(self):
        """Test that lessons are assigned to correct room types."""
        input_data = TimetableInput(
            config=SchoolConfig(school_name="Test", num_days=5),
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[
                Subject(id="sci", name="Science", requires_specialist_room=True,
                       required_room_type=RoomType.SCIENCE_LAB),
            ],
            rooms=[
                Room(id="r1", name="Classroom", type=RoomType.CLASSROOM),
                Room(id="lab1", name="Science Lab", type=RoomType.SCIENCE_LAB),
            ],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="sci",
                       lessons_per_week=2, duration_minutes=60),
            ],
            periods=[
                Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="p2", name="P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="p3", name="P3", day=1, start_minutes=540, end_minutes=600),
                Period(id="p4", name="P4", day=1, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        solution = builder.solve(time_limit_seconds=30)

        assert solution.is_feasible

        # All science lessons should be in the lab
        for assignment in solution.assignments:
            assert assignment.room_id == "lab1", \
                "Science lessons should be in science lab"


class TestNoOverlap:
    """Tests for no-overlap constraints."""

    def test_teacher_no_overlap(self):
        """Test that same teacher can't be double-booked."""
        input_data = TimetableInput(
            config=SchoolConfig(school_name="Test", num_days=1),
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[
                StudentClass(id="c1", name="Class 1"),
                StudentClass(id="c2", name="Class 2"),
            ],
            subjects=[Subject(id="s1", name="Subject 1")],
            rooms=[
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
                Room(id="r2", name="Room 2", type=RoomType.CLASSROOM),
            ],
            lessons=[
                # Same teacher teaches two different classes
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="s1", lessons_per_week=1),
                Lesson(id="l2", teacher_id="t1", class_id="c2", subject_id="s1", lessons_per_week=1),
            ],
            periods=[
                Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="p2", name="P2", day=0, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        solution = builder.solve(time_limit_seconds=30)

        assert solution.is_feasible

        # Lessons should be at different times
        times = [(a.day, a.start_minutes) for a in solution.assignments]
        assert len(set(times)) == 2, "Teacher's lessons should be at different times"

    def test_class_no_overlap(self):
        """Test that same class can't have two lessons at same time."""
        input_data = TimetableInput(
            config=SchoolConfig(school_name="Test", num_days=1),
            teachers=[
                Teacher(id="t1", name="Teacher 1"),
                Teacher(id="t2", name="Teacher 2"),
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[
                Subject(id="s1", name="Subject 1"),
                Subject(id="s2", name="Subject 2"),
            ],
            rooms=[
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
                Room(id="r2", name="Room 2", type=RoomType.CLASSROOM),
            ],
            lessons=[
                # Same class, different teachers
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="s1", lessons_per_week=1),
                Lesson(id="l2", teacher_id="t2", class_id="c1", subject_id="s2", lessons_per_week=1),
            ],
            periods=[
                Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="p2", name="P2", day=0, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        solution = builder.solve(time_limit_seconds=30)

        assert solution.is_feasible

        # Lessons should be at different times
        times = [(a.day, a.start_minutes) for a in solution.assignments]
        assert len(set(times)) == 2, "Class's lessons should be at different times"


class TestInfeasibility:
    """Tests for infeasible scenarios."""

    def test_too_many_lessons(self):
        """Test infeasibility when there aren't enough slots."""
        input_data = TimetableInput(
            config=SchoolConfig(school_name="Test", num_days=1),
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="s1", name="Subject 1")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # 3 lessons but only 2 slots
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="s1", lessons_per_week=3),
            ],
            periods=[
                Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="p2", name="P2", day=0, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        solution = builder.solve(time_limit_seconds=10)

        assert solution.status == SolverStatus.INFEASIBLE

    def test_no_suitable_room_caught_by_validation(self):
        """Test that missing room types are caught by Pydantic validation."""
        from pydantic import ValidationError

        # This should be caught by Pydantic validation, not the solver
        with pytest.raises(ValidationError, match="requires science_lab"):
            TimetableInput(
                config=SchoolConfig(school_name="Test", num_days=1),
                teachers=[Teacher(id="t1", name="Teacher 1")],
                classes=[StudentClass(id="c1", name="Class 1")],
                subjects=[
                    Subject(id="sci", name="Science", requires_specialist_room=True,
                           required_room_type=RoomType.SCIENCE_LAB),
                ],
                rooms=[
                    # Only classrooms, no lab
                    Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
                ],
                lessons=[
                    Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="sci", lessons_per_week=1),
                ],
                periods=[
                    Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600),
                ],
            )

    def test_room_fully_booked(self):
        """Test infeasibility when room is fully booked."""
        input_data = TimetableInput(
            config=SchoolConfig(school_name="Test", num_days=1),
            teachers=[
                Teacher(id="t1", name="Teacher 1"),
                Teacher(id="t2", name="Teacher 2"),
            ],
            classes=[
                StudentClass(id="c1", name="Class 1"),
                StudentClass(id="c2", name="Class 2"),
            ],
            subjects=[Subject(id="s1", name="Subject 1")],
            rooms=[
                # Only one room
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
            ],
            lessons=[
                # Two lessons that must both use the same room, same time slot
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="s1", lessons_per_week=2),
                Lesson(id="l2", teacher_id="t2", class_id="c2", subject_id="s1", lessons_per_week=2),
            ],
            periods=[
                # Only one period - impossible to fit 4 lesson instances
                Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        solution = builder.solve(time_limit_seconds=10)

        # Should be infeasible - only 1 slot but need to place 4 lessons
        assert solution.status == SolverStatus.INFEASIBLE
