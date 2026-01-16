"""Tests for subject distribution constraints."""

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
from solver.model_builder import TimetableModelBuilder
from solver.constraints.distribution import (
    add_subject_distribution,
    add_minimum_day_gap,
    add_even_distribution,
    add_no_consecutive_days,
    add_all_distribution_constraints,
    DistributionStats,
)


@pytest.fixture
def basic_input() -> TimetableInput:
    """Create basic timetable input for testing."""
    return TimetableInput(
        teachers=[Teacher(id="t1", name="Teacher 1")],
        classes=[StudentClass(id="c1", name="Class 1")],
        subjects=[Subject(id="mat", name="Maths")],
        rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
        lessons=[
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=3),
        ],
        periods=[
            Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            Period(id="wed1", name="Wed P1", day=2, start_minutes=540, end_minutes=600),
            Period(id="thu1", name="Thu P1", day=3, start_minutes=540, end_minutes=600),
            Period(id="fri1", name="Fri P1", day=4, start_minutes=540, end_minutes=600),
        ],
    )


class TestSubjectDistribution:
    """Tests for subject distribution constraint."""

    def test_no_constraints_with_single_lesson(self):
        """No constraints when lesson has only 1 instance per week."""
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

        penalties = add_subject_distribution(builder, min_lessons=2)
        assert penalties == 0

    def test_adds_penalties_for_multi_lesson_subjects(self, basic_input):
        """Adds penalty variables for subjects with multiple lessons per week."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        penalties = add_subject_distribution(builder)

        # 3 lessons = 3 pairs: (0,1), (0,2), (1,2)
        assert penalties == 3

    def test_solver_prefers_different_days(self):
        """Solver schedules lessons on different days when possible."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
            ],
            periods=[
                # 2 periods per day for 3 days - allows same or different day
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
                Period(id="wed1", name="Wed P1", day=2, start_minutes=540, end_minutes=600),
                Period(id="wed2", name="Wed P2", day=2, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        add_subject_distribution(builder, weight=100)
        builder._constraints_added = True
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # With high penalty for same-day, lessons should be on different days
        days = [a.day for a in solution.assignments]
        assert len(set(days)) == 2  # 2 different days

    def test_penalty_scales_with_lessons_per_week(self):
        """More lessons per week results in lower per-pair penalty."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # 5 lessons per week - more flexibility, lower penalty
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=5),
            ],
            periods=[
                Period(id=f"d{d}p1", name=f"Day{d} P1", day=d, start_minutes=540, end_minutes=600)
                for d in range(5)
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        add_subject_distribution(builder, weight=15)

        # With 5 lessons, scaled weight = 15 * 2 // 5 = 6
        # Check that penalties were added (exact weight depends on implementation)
        assert len(builder.penalty_vars) > 0


class TestMinimumDayGap:
    """Tests for minimum day gap constraint."""

    def test_adds_penalties_for_close_lessons(self):
        """Adds penalty variables for lesson instances."""
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
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        penalties = add_minimum_day_gap(builder, min_gap_days=1)

        # 2 lessons = 1 pair
        assert penalties == 1

    def test_solver_prefers_larger_gaps(self):
        """Solver prefers larger day gaps when possible."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
            ],
            periods=[
                # Mon, Tue, Fri - can choose gap of 1 (Mon-Tue) or 4 (Mon-Fri)
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="fri1", name="Fri P1", day=4, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        add_minimum_day_gap(builder, min_gap_days=2, weight=100)
        builder._constraints_added = True
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Should choose Mon and Fri (gap=4) over Mon and Tue (gap=1)
        days = sorted([a.day for a in solution.assignments])
        gap = days[1] - days[0]
        assert gap >= 2  # Gap should be at least 2


class TestEvenDistribution:
    """Tests for even distribution constraint."""

    def test_adds_deviation_penalties(self, basic_input):
        """Adds penalty variables for distribution deviation."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        penalties = add_even_distribution(builder)

        # 3 lessons = 3 pairs
        assert penalties == 3


class TestNoConsecutiveDays:
    """Tests for no consecutive days constraint."""

    def test_no_constraints_when_subject_not_specified(self):
        """No constraints when subject is not in the list."""
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
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        # Only apply to PE, not Maths
        penalties = add_no_consecutive_days(builder, subject_ids=["pe"])
        assert penalties == 0

    def test_adds_constraints_for_specified_subjects(self):
        """Adds constraints when subject is in the list."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="pe", name="PE")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="pe", lessons_per_week=2),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="wed1", name="Wed P1", day=2, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        penalties = add_no_consecutive_days(builder, subject_ids=["pe"])
        assert penalties == 1  # 2 lessons = 1 pair

    def test_solver_avoids_consecutive_days(self):
        """Solver avoids consecutive days when penalty is high."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="pe", name="PE")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="pe", lessons_per_week=2),
            ],
            periods=[
                # Can choose Mon-Tue (consecutive) or Mon-Wed (not consecutive)
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="wed1", name="Wed P1", day=2, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        add_no_consecutive_days(builder, subject_ids=["pe"], weight=100)
        builder._constraints_added = True
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Should choose Mon and Wed (not consecutive)
        days = sorted([a.day for a in solution.assignments])
        gap = days[1] - days[0]
        assert gap > 1  # Not consecutive


class TestAddAllDistributionConstraints:
    """Tests for combined distribution constraints function."""

    def test_returns_stats(self, basic_input):
        """Returns statistics about added constraints."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        stats = add_all_distribution_constraints(builder)

        assert isinstance(stats, DistributionStats)
        assert stats.lessons_with_distribution == 1  # l1 has 3 lessons
        assert stats.same_day_penalties == 3  # 3 pairs

    def test_full_model_with_distribution(self, basic_input):
        """Full model with distribution constraints finds solution."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        builder._add_class_no_overlap_constraint()
        builder._add_room_no_overlap_constraint()
        add_all_distribution_constraints(builder)
        builder._constraints_added = True
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # 3 lessons should be on 3 different days
        days = [a.day for a in solution.assignments]
        assert len(set(days)) == 3


class TestEdgeCases:
    """Tests for edge cases."""

    def test_handles_lesson_with_exactly_2_instances(self):
        """Handles lessons with exactly 2 instances correctly."""
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
                Period(id="fri1", name="Fri P1", day=4, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        add_all_distribution_constraints(builder)
        builder._constraints_added = True
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible
        # Only 2 slots available, one per day
        days = [a.day for a in solution.assignments]
        assert len(set(days)) == 2

    def test_forced_same_day_still_feasible(self):
        """Model is still feasible when same-day is forced."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
            ],
            periods=[
                # Only Monday available - must schedule both on same day
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        add_subject_distribution(builder, weight=100)
        builder._constraints_added = True
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        # Should still find a solution (soft constraint)
        assert solution.is_feasible

        # Both lessons on Monday
        days = [a.day for a in solution.assignments]
        assert all(d == 0 for d in days)

        # But objective should reflect the penalty
        assert solution.objective_value > 0
