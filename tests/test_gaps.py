"""Tests for gap minimization constraints."""

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
from solver.constraints.gaps import (
    add_teacher_gap_minimization,
    add_class_gap_minimization,
    add_early_finish_preference,
    add_all_gap_constraints,
    GapStats,
)


@pytest.fixture
def basic_input() -> TimetableInput:
    """Create basic timetable input for testing."""
    return TimetableInput(
        teachers=[
            Teacher(id="t1", name="Teacher 1"),
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
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=3),
            Lesson(id="l2", teacher_id="t2", class_id="c2", subject_id="mat", lessons_per_week=2),
        ],
        periods=[
            Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            Period(id="mon3", name="Mon P3", day=0, start_minutes=720, end_minutes=780),  # Gap after break
            Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
        ],
    )


class TestTeacherGapMinimization:
    """Tests for teacher gap minimization constraint."""

    def test_no_constraints_with_few_lessons(self):
        """No constraints when teacher has fewer lessons than minimum."""
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

        penalties = add_teacher_gap_minimization(builder, min_lessons_for_gap=2)
        assert penalties == 0

    def test_adds_penalties_for_potential_gaps(self, basic_input):
        """Adds penalty variables for teachers who could have gaps."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        penalties = add_teacher_gap_minimization(builder, min_lessons_for_gap=2)

        # t1 has 3 lessons (can have gaps), t2 has 2 lessons (can have gaps)
        # Penalties added per day
        assert penalties > 0

    def test_solver_minimizes_gaps(self):
        """Solver prefers compact schedules when possible."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # 2 lessons that can be consecutive or have a gap
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="mon3", name="Mon P3", day=0, start_minutes=720, end_minutes=780),  # Gap period
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        add_teacher_gap_minimization(builder, weight=100)
        builder._constraints_added = True
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # With high gap penalty, lessons should be scheduled consecutively
        # Check that both lessons are in periods 1 and 2 (not period 3 which would create a gap)
        assignments = sorted(solution.assignments, key=lambda a: a.start_minutes)
        if len(assignments) >= 2 and assignments[0].day == assignments[1].day:
            # If on same day, should be consecutive (no gap)
            assert assignments[1].start_minutes == assignments[0].end_minutes


class TestClassGapMinimization:
    """Tests for class gap minimization constraint."""

    def test_adds_penalties_for_class_gaps(self):
        """Adds penalty variables for classes with potential gaps."""
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
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
                Lesson(id="l2", teacher_id="t2", class_id="c1", subject_id="eng", lessons_per_week=2),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="mon3", name="Mon P3", day=0, start_minutes=720, end_minutes=780),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        penalties = add_class_gap_minimization(builder, min_lessons_for_gap=2)

        # Class c1 has 4 lesson instances, can have gaps
        assert penalties > 0


class TestEarlyFinishPreference:
    """Tests for early finish preference constraint."""

    def test_adds_late_penalties(self, basic_input):
        """Adds penalty variables for late finish times."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        penalties = add_early_finish_preference(builder)

        # Should add penalties per teacher per day
        assert penalties > 0

    def test_solver_prefers_early_finish(self):
        """Solver prefers earlier slots when gap penalties are high."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),  # 9:00-10:00
                Period(id="mon2", name="Mon P2", day=0, start_minutes=960, end_minutes=1020),  # 16:00-17:00 (late)
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        add_early_finish_preference(builder, weight=100)
        builder._constraints_added = True
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # With high penalty for late finish, should pick early slot
        assert len(solution.assignments) == 1
        assert solution.assignments[0].start_minutes == 540  # 9:00


class TestAddAllGapConstraints:
    """Tests for combined gap constraints function."""

    def test_returns_stats(self, basic_input):
        """Returns statistics about added constraints."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        stats = add_all_gap_constraints(builder)

        assert isinstance(stats, GapStats)
        # t1 has 3 lessons, t2 has 2 lessons - both can have gaps
        assert stats.teachers_with_gap_constraints == 2

    def test_full_model_with_gap_constraints(self, basic_input):
        """Full model with gap constraints finds solution."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        builder._add_class_no_overlap_constraint()
        builder._add_room_no_overlap_constraint()
        add_all_gap_constraints(builder)
        builder._constraints_added = True
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible


class TestGapCalculation:
    """Tests for gap calculation logic."""

    def test_gap_is_span_minus_teaching_time(self):
        """Gap should be (last_end - first_start) - total_teaching_time."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # 2 lessons of 60 minutes each
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat",
                       lessons_per_week=2, duration_minutes=60),
            ],
            periods=[
                # Force a specific schedule:
                # P1: 9:00-10:00
                # P2: 10:00-11:00 (consecutive, no gap)
                # P3: 12:00-13:00 (1 hour gap)
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                Period(id="mon3", name="Mon P3", day=0, start_minutes=720, end_minutes=780),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        add_teacher_gap_minimization(builder, weight=100)
        builder._constraints_added = True
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Should pick consecutive slots to minimize gap
        day_assignments = [a for a in solution.assignments if a.day == 0]
        if len(day_assignments) == 2:
            starts = sorted([a.start_minutes for a in day_assignments])
            # If consecutive: 540 and 600 (no gap)
            # If with gap: 540 and 720 (60 min gap)
            gap = starts[1] - starts[0] - 60  # span - teaching time
            # With high penalty, should minimize gap
            assert gap == 0 or solution.objective_value > 0


class TestEdgeCases:
    """Tests for edge cases."""

    def test_no_lessons_on_day(self):
        """Handles case where teacher has no lessons on a day."""
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
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
                # Tuesday has no periods, so no lessons possible there
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        # Should not crash
        penalties = add_teacher_gap_minimization(builder)
        assert penalties >= 0

    def test_single_lesson_no_gap_penalty(self):
        """Single lesson on a day should have 0 gap penalty."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
            ],
            periods=[
                # 1 period per day - only 1 lesson possible per day
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        add_teacher_gap_minimization(builder, weight=100, min_lessons_for_gap=2)
        builder._constraints_added = True
        builder.set_objective()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible
        # With only 1 lesson per day, gap penalty should be 0
        assert solution.objective_value == 0
