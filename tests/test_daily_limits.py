"""Tests for daily limit constraints."""

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
    RoomType,
)
from solver.model_builder import TimetableModelBuilder, SolverStatus
from solver.constraints.daily_limits import (
    add_teacher_max_periods_per_day,
    add_class_max_periods_per_day,
    add_teacher_max_periods_per_week,
    add_balanced_daily_workload,
    add_minimum_lessons_per_day,
    add_all_daily_limit_constraints,
    DailyLimitStats,
)


@pytest.fixture
def basic_input() -> TimetableInput:
    """Create basic timetable input for testing."""
    return TimetableInput(
        teachers=[
            Teacher(id="t1", name="Teacher 1", max_periods_per_day=3),
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
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=4),
            Lesson(id="l2", teacher_id="t2", class_id="c2", subject_id="mat", lessons_per_week=3),
        ],
        periods=[
            Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            Period(id="mon3", name="Mon P3", day=0, start_minutes=660, end_minutes=720),
            Period(id="mon4", name="Mon P4", day=0, start_minutes=720, end_minutes=780),
            Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
        ],
    )


class TestTeacherMaxPeriodsPerDay:
    """Tests for teacher daily limit constraints."""

    def test_no_constraints_without_limits(self):
        """No constraints added when teachers have no limits."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],  # No max_periods_per_day
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        penalties = add_teacher_max_periods_per_day(builder)
        assert penalties == 0

    def test_adds_constraints_with_limit(self, basic_input):
        """Adds constraints when teacher has a limit."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        penalties = add_teacher_max_periods_per_day(builder)

        # t1 has 4 lessons, max 3 per day, 2 days => could overflow
        # Should add penalty vars for days where overflow is possible
        assert penalties > 0

    def test_uses_default_max(self):
        """Uses default max when teacher doesn't specify."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],  # No limit
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=4),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="mon3", name="Mon P3", day=0, start_minutes=660, end_minutes=720),
                Period(id="mon4", name="Mon P4", day=0, start_minutes=720, end_minutes=780),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        # With default_max=2, should add penalties
        penalties = add_teacher_max_periods_per_day(builder, default_max=2)
        assert penalties > 0

    def test_solver_respects_soft_constraint(self):
        """Solver tries to minimize overflow penalties."""
        input_data = TimetableInput(
            teachers=[
                Teacher(id="t1", name="Teacher 1", max_periods_per_day=2),
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # 4 lessons, max 2 per day, 2 days available
                # Ideal: 2 per day
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=4),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        add_teacher_max_periods_per_day(builder, weight=100)
        builder._constraints_added = True  # Mark constraints as added
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Count lessons per day
        day_counts = {}
        for a in solution.assignments:
            day_counts[a.day] = day_counts.get(a.day, 0) + 1

        # Should spread evenly (2 per day) to minimize penalty
        for day, count in day_counts.items():
            assert count <= 2, f"Day {day} has {count} lessons, expected max 2"


class TestClassMaxPeriodsPerDay:
    """Tests for class daily limit constraints."""

    def test_adds_constraints_with_default(self):
        """Adds constraints when default max is specified."""
        input_data = TimetableInput(
            teachers=[
                Teacher(id="t1", name="Teacher 1"),
                Teacher(id="t2", name="Teacher 2"),
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[
                Subject(id="mat", name="Maths"),
                Subject(id="eng", name="English"),
            ],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=3),
                Lesson(id="l2", teacher_id="t2", class_id="c1", subject_id="eng", lessons_per_week=3),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="mon3", name="Mon P3", day=0, start_minutes=660, end_minutes=720),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
                Period(id="tue3", name="Tue P3", day=1, start_minutes=660, end_minutes=720),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        # Class has 6 lessons, default max 4 per day
        penalties = add_class_max_periods_per_day(builder, default_max=4)
        assert penalties > 0


class TestTeacherMaxPeriodsPerWeek:
    """Tests for teacher weekly limit constraints."""

    def test_adds_penalty_when_over_weekly_limit(self):
        """Adds penalty when scheduled lessons exceed weekly limit."""
        input_data = TimetableInput(
            teachers=[
                Teacher(id="t1", name="Teacher 1", max_periods_per_week=3),
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # 4 lessons but max 3 per week
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=4),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        penalties = add_teacher_max_periods_per_week(builder)
        # 4 lessons - 3 max = 1 overflow
        assert penalties == 1

    def test_no_penalty_when_within_limit(self):
        """No penalty when lessons are within weekly limit."""
        input_data = TimetableInput(
            teachers=[
                Teacher(id="t1", name="Teacher 1", max_periods_per_week=10),
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=4),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        penalties = add_teacher_max_periods_per_week(builder)
        assert penalties == 0


class TestBalancedDailyWorkload:
    """Tests for balanced workload soft constraint."""

    def test_adds_penalties_for_imbalance(self):
        """Adds penalties for workload deviation from average."""
        # Need enough lessons so target_per_day > 0
        # With 10 lessons and 5 days, target = 10 // 5 = 2
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=10),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
                Period(id="wed1", name="Wed P1", day=2, start_minutes=540, end_minutes=600),
                Period(id="wed2", name="Wed P2", day=2, start_minutes=600, end_minutes=660),
                Period(id="thu1", name="Thu P1", day=3, start_minutes=540, end_minutes=600),
                Period(id="thu2", name="Thu P2", day=3, start_minutes=600, end_minutes=660),
                Period(id="fri1", name="Fri P1", day=4, start_minutes=540, end_minutes=600),
                Period(id="fri2", name="Fri P2", day=4, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        penalties = add_balanced_daily_workload(builder)
        # Should add penalties for each of 5 days
        assert penalties == 5


class TestMinimumLessonsPerDay:
    """Tests for minimum lessons per day constraint."""

    def test_adds_fragmentation_penalties(self):
        """Adds penalties for having just 1 lesson on a day."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=3),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        penalties = add_minimum_lessons_per_day(builder, min_lessons=2)
        # Should add penalties for days that could have just 1 lesson
        assert penalties > 0


class TestAddAllDailyLimitConstraints:
    """Tests for combined daily limit constraints function."""

    def test_returns_stats(self, basic_input):
        """Returns statistics about added constraints."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        stats = add_all_daily_limit_constraints(builder)

        assert isinstance(stats, DailyLimitStats)
        assert stats.teachers_with_limits == 1  # Only t1 has max_periods_per_day

    def test_full_model_with_all_constraints(self, basic_input):
        """Full model with all daily constraints finds solution."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        builder._add_class_no_overlap_constraint()
        builder._add_room_no_overlap_constraint()
        add_all_daily_limit_constraints(builder)
        builder._constraints_added = True  # Mark constraints as added
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible


class TestSolverWithDailyLimits:
    """Integration tests for solver with daily limits."""

    def test_respects_daily_limits_in_solution(self):
        """Solver produces solution respecting daily limits when possible."""
        input_data = TimetableInput(
            teachers=[
                Teacher(id="t1", name="Teacher 1", max_periods_per_day=2),
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=4),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        add_teacher_max_periods_per_day(builder, weight=100)
        builder._constraints_added = True  # Mark constraints as added
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # With high penalty weight, should respect the 2 per day limit
        day_counts = {}
        for a in solution.assignments:
            day_counts[a.day] = day_counts.get(a.day, 0) + 1

        for day, count in day_counts.items():
            assert count <= 2

    def test_penalizes_overflow_when_unavoidable(self):
        """Solution has non-zero objective when overflow is unavoidable."""
        input_data = TimetableInput(
            teachers=[
                Teacher(id="t1", name="Teacher 1", max_periods_per_day=2),
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # 3 lessons but only 1 day with max 2 => must overflow
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=3),
            ],
            periods=[
                # Only Monday available
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="mon3", name="Mon P3", day=0, start_minutes=660, end_minutes=720),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        add_teacher_max_periods_per_day(builder, weight=100)
        builder._constraints_added = True  # Mark constraints as added
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible
        # Objective should reflect overflow penalty (3 - 2 = 1 overflow * 100 weight)
        assert solution.objective_value is not None
        assert solution.objective_value > 0
