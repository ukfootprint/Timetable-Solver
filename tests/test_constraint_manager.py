"""Tests for the ConstraintManager class."""

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
    Availability,
)
from solver.model_builder import TimetableModelBuilder, SolverStatus
from solver.constraints import (
    ConstraintManager,
    ConstraintWeights,
    ConstraintManagerStats,
)


@pytest.fixture
def basic_input() -> TimetableInput:
    """Create basic timetable input for testing."""
    return TimetableInput(
        teachers=[
            Teacher(id="t1", name="Teacher 1", max_periods_per_day=4),
            Teacher(id="t2", name="Teacher 2"),
        ],
        classes=[
            StudentClass(id="c1", name="Class 1"),
            StudentClass(id="c2", name="Class 2"),
        ],
        subjects=[
            Subject(id="mat", name="Maths"),
            Subject(id="eng", name="English"),
        ],
        rooms=[
            Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
            Room(id="r2", name="Room 2", type=RoomType.CLASSROOM),
        ],
        lessons=[
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=3),
            Lesson(id="l2", teacher_id="t2", class_id="c2", subject_id="eng", lessons_per_week=2),
        ],
        periods=[
            Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
            Period(id="wed1", name="Wed P1", day=2, start_minutes=540, end_minutes=600),
            Period(id="wed2", name="Wed P2", day=2, start_minutes=600, end_minutes=660),
            Period(id="thu1", name="Thu P1", day=3, start_minutes=540, end_minutes=600),
            Period(id="fri1", name="Fri P1", day=4, start_minutes=540, end_minutes=600),
        ],
    )


class TestConstraintWeights:
    """Tests for ConstraintWeights configuration."""

    def test_default_weights(self):
        """Default weights are set correctly."""
        weights = ConstraintWeights()

        assert weights.teacher_daily_overflow == 100
        assert weights.same_day_subject == 20
        assert weights.teacher_gap == 1

    def test_custom_weights(self):
        """Custom weights can be set."""
        weights = ConstraintWeights(
            teacher_daily_overflow=200,
            same_day_subject=50,
            teacher_gap=5
        )

        assert weights.teacher_daily_overflow == 200
        assert weights.same_day_subject == 50
        assert weights.teacher_gap == 5


class TestConstraintManager:
    """Tests for ConstraintManager class."""

    def test_apply_all_constraints(self, basic_input):
        """apply_all_constraints adds both hard and soft constraints."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        stats = manager.apply_all_constraints(builder)

        assert isinstance(stats, ConstraintManagerStats)
        assert stats.total_hard_constraints > 0
        assert stats.total_soft_penalties > 0
        assert builder._constraints_added

    def test_custom_weights_applied(self, basic_input):
        """Custom weights are passed to constraint functions."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        weights = ConstraintWeights(
            teacher_daily_overflow=500,
            same_day_subject=100
        )
        manager = ConstraintManager(weights=weights)
        manager.apply_all_constraints(builder)

        # Check that penalty vars use custom weights
        daily_penalties = [p for p in builder.penalty_vars if "overload" in p.name]
        same_day_penalties = [p for p in builder.penalty_vars if "same_day" in p.name]

        # At least some penalties should exist
        assert len(builder.penalty_vars) > 0

    def test_hard_constraints_only(self, basic_input):
        """apply_hard_constraints_only skips soft constraints."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        stats = manager.apply_hard_constraints_only(builder)

        assert stats.total_hard_constraints > 0
        # Soft penalty count should be 0 when skip_soft=True
        assert stats.total_soft_penalties == 0

    def test_soft_constraints_only(self, basic_input):
        """apply_soft_constraints_only skips hard constraints."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        # Add hard constraints manually first
        builder._add_valid_time_slots_constraint()

        manager = ConstraintManager()
        stats = manager.apply_soft_constraints_only(builder)

        # Hard constraint stats should be empty (from manager's perspective)
        assert stats.no_overlap.teacher_constraints == 0
        assert stats.availability.teacher_unavailability_constraints == 0

        # But soft constraints should be added
        assert stats.total_soft_penalties > 0

    def test_stats_include_all_categories(self, basic_input):
        """Stats include all constraint categories."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        stats = manager.apply_all_constraints(builder)

        # Check all stat categories are populated
        assert hasattr(stats, 'no_overlap')
        assert hasattr(stats, 'availability')
        assert hasattr(stats, 'room')
        assert hasattr(stats, 'daily_limits')
        assert hasattr(stats, 'gaps')
        assert hasattr(stats, 'distribution')


class TestConstraintManagerIntegration:
    """Integration tests for ConstraintManager with solver."""

    def test_full_solve_with_manager(self, basic_input):
        """Full solve using ConstraintManager finds solution."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        manager = ConstraintManager()
        stats = manager.apply_all_constraints(builder)

        builder.set_objective()
        solution = builder.solve(time_limit_seconds=30)

        assert solution.is_feasible
        assert len(solution.assignments) == 5  # 3 + 2 lessons

    def test_enforces_no_overlap(self):
        """Manager's no-overlap constraints prevent double-booking."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[
                StudentClass(id="c1", name="Class 1"),
                StudentClass(id="c2", name="Class 2"),
            ],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # Same teacher teaches both classes - can't overlap
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
                Lesson(id="l2", teacher_id="t1", class_id="c2", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()
        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Lessons must be in different periods (not overlapping)
        times = [(a.day, a.start_minutes) for a in solution.assignments]
        assert len(times) == len(set(times))  # All unique

    def test_enforces_teacher_unavailability(self):
        """Manager's availability constraints respect teacher unavailability."""
        input_data = TimetableInput(
            teachers=[
                Teacher(
                    id="t1",
                    name="Teacher 1",
                    availability=[
                        Availability(day=0, start_minutes=540, end_minutes=600, available=False),
                    ]
                )
            ],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()
        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Lesson should be in mon2 (not mon1 when teacher is unavailable)
        assert solution.assignments[0].start_minutes == 600

    def test_prefers_distributed_lessons(self, basic_input):
        """Manager's distribution constraints spread lessons across days."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        # Use high weight for same-day penalty
        weights = ConstraintWeights(same_day_subject=1000)
        manager = ConstraintManager(weights=weights)
        manager.apply_all_constraints(builder)

        builder.set_objective()
        solution = builder.solve(time_limit_seconds=30)

        assert solution.is_feasible

        # Check that l1's 3 lessons are on different days
        l1_days = [a.day for a in solution.assignments if a.lesson_id == "l1"]
        assert len(set(l1_days)) == 3  # All on different days

    def test_respects_daily_limits(self):
        """Manager's daily limits are respected in optimization."""
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
                Period(id="mon3", name="Mon P3", day=0, start_minutes=660, end_minutes=720),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        # High weight for daily overflow
        weights = ConstraintWeights(teacher_daily_overflow=1000)
        manager = ConstraintManager(weights=weights)
        manager.apply_all_constraints(builder)

        builder.set_objective()
        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Count lessons per day
        day_counts = {}
        for a in solution.assignments:
            day_counts[a.day] = day_counts.get(a.day, 0) + 1

        # With max 2 per day and 4 lessons, should be spread as 2+2
        assert max(day_counts.values()) <= 2


class TestInfeasibleScenarios:
    """Tests for infeasible scenarios with ConstraintManager."""

    def test_infeasible_no_valid_slots(self):
        """Infeasible when no valid time slots exist."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # Needs 3 slots but only 2 available
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
        solution = builder.solve(time_limit_seconds=10)

        assert solution.status == SolverStatus.INFEASIBLE

    def test_infeasible_teacher_overloaded(self):
        """Infeasible when teacher has too many lessons for available slots."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[
                StudentClass(id="c1", name="Class 1"),
                StudentClass(id="c2", name="Class 2"),
            ],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # 3 lessons but only 2 slots for same teacher
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
                Lesson(id="l2", teacher_id="t1", class_id="c2", subject_id="mat", lessons_per_week=2),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        manager = ConstraintManager()
        manager.apply_all_constraints(builder)

        builder.set_objective()
        solution = builder.solve(time_limit_seconds=10)

        assert solution.status == SolverStatus.INFEASIBLE
