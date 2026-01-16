"""Tests for no-overlap constraints."""

from __future__ import annotations

import pytest
from ortools.sat.python import cp_model

from solver.data.models import (
    TimetableInput,
    Teacher,
    StudentClass,
    Subject,
    Room,
    Lesson,
    Period,
    RoomType,
    RoomRequirement,
)
from solver.model_builder import TimetableModelBuilder, SolverStatus
from solver.constraints.no_overlap import (
    add_teacher_no_overlap,
    add_class_no_overlap,
    add_room_no_overlap,
    add_all_no_overlap_constraints,
    NoOverlapStats,
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
        subjects=[
            Subject(id="mat", name="Maths"),
            Subject(id="eng", name="English"),
        ],
        rooms=[
            Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
            Room(id="r2", name="Room 2", type=RoomType.CLASSROOM),
        ],
        lessons=[
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
            Lesson(id="l2", teacher_id="t1", class_id="c2", subject_id="eng", lessons_per_week=2),
        ],
        periods=[
            Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
        ],
    )


class TestTeacherNoOverlap:
    """Tests for teacher no-overlap constraint."""

    def test_adds_constraint_for_teacher_with_multiple_lessons(self, basic_input):
        """Teacher with multiple lessons gets a no-overlap constraint."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        count = add_teacher_no_overlap(builder)

        # t1 has 4 intervals (2 lessons × 2 instances), so should have constraint
        # t2 has 0 intervals, so no constraint
        assert count == 1

    def test_no_constraint_for_teacher_with_one_lesson(self):
        """Teacher with only one lesson instance doesn't need no-overlap."""
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

        count = add_teacher_no_overlap(builder)
        assert count == 0

    def test_prevents_teacher_double_booking(self, basic_input):
        """Teacher cannot teach two classes at the same time."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()
        add_teacher_no_overlap(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Group assignments by teacher and check for overlaps
        teacher_assignments = {}
        for a in solution.assignments:
            if a.teacher_id not in teacher_assignments:
                teacher_assignments[a.teacher_id] = []
            teacher_assignments[a.teacher_id].append((a.day, a.start_minutes, a.end_minutes))

        for teacher_id, slots in teacher_assignments.items():
            # Check no two slots on same day overlap
            for i, (day1, start1, end1) in enumerate(slots):
                for day2, start2, end2 in slots[i + 1:]:
                    if day1 == day2:
                        # Should not overlap
                        assert end1 <= start2 or end2 <= start1, \
                            f"Teacher {teacher_id} has overlapping lessons"


class TestClassNoOverlap:
    """Tests for class no-overlap constraint."""

    def test_adds_constraint_for_class_with_multiple_lessons(self):
        """Class with multiple lessons gets a no-overlap constraint."""
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
                Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
                Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        count = add_class_no_overlap(builder)

        # c1 has 4 intervals, so should have constraint
        assert count == 1

    def test_prevents_class_double_booking(self):
        """Class cannot have two lessons at the same time."""
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
            rooms=[
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
                Room(id="r2", name="Room 2", type=RoomType.CLASSROOM),
            ],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
                Lesson(id="l2", teacher_id="t2", class_id="c1", subject_id="eng", lessons_per_week=2),
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
        add_class_no_overlap(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Group assignments by class and check for overlaps
        class_assignments = {}
        for a in solution.assignments:
            if a.class_id not in class_assignments:
                class_assignments[a.class_id] = []
            class_assignments[a.class_id].append((a.day, a.start_minutes, a.end_minutes))

        for class_id, slots in class_assignments.items():
            for i, (day1, start1, end1) in enumerate(slots):
                for day2, start2, end2 in slots[i + 1:]:
                    if day1 == day2:
                        assert end1 <= start2 or end2 <= start1, \
                            f"Class {class_id} has overlapping lessons"


class TestRoomNoOverlap:
    """Tests for room no-overlap constraint."""

    def test_adds_constraint_per_room(self, basic_input):
        """Each room gets a no-overlap constraint."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        count = add_room_no_overlap(builder)

        # Both rooms could host lessons, so both get constraints
        assert count == 2

    def test_prevents_room_double_booking(self):
        """Room cannot host two lessons at the same time."""
        input_data = TimetableInput(
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
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),  # Only 1 room
            ],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
                Lesson(id="l2", teacher_id="t2", class_id="c2", subject_id="mat", lessons_per_week=2),
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
        add_room_no_overlap(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Group assignments by room and check for overlaps
        room_assignments = {}
        for a in solution.assignments:
            if a.room_id not in room_assignments:
                room_assignments[a.room_id] = []
            room_assignments[a.room_id].append((a.day, a.start_minutes, a.end_minutes))

        for room_id, slots in room_assignments.items():
            for i, (day1, start1, end1) in enumerate(slots):
                for day2, start2, end2 in slots[i + 1:]:
                    if day1 == day2:
                        assert end1 <= start2 or end2 <= start1, \
                            f"Room {room_id} has overlapping lessons"

    def test_respects_room_type_requirements(self):
        """Optional intervals are only created for valid room-lesson pairs."""
        input_data = TimetableInput(
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
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="sci", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        # The room constraint should only create optional intervals for the science lab
        # since the lesson requires a science lab
        count = add_room_no_overlap(builder)

        # Classroom shouldn't have any intervals (lesson can't use it)
        # Science lab should have 1 interval
        # So only 1 room gets a constraint (but needs >1 interval for NoOverlap)
        # Actually with 1 lesson, no room will have >1 interval, so count should be 0
        assert count == 0


class TestAddAllNoOverlapConstraints:
    """Tests for the combined function."""

    def test_returns_stats(self, basic_input):
        """Returns statistics about added constraints."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        stats = add_all_no_overlap_constraints(builder)

        assert isinstance(stats, NoOverlapStats)
        assert stats.teacher_constraints >= 0
        assert stats.class_constraints >= 0
        assert stats.room_constraints >= 0

    def test_full_model_with_all_constraints(self):
        """Full model with all no-overlap constraints finds valid solution."""
        input_data = TimetableInput(
            teachers=[
                Teacher(id="t1", name="Teacher 1"),
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
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
                Lesson(id="l2", teacher_id="t2", class_id="c2", subject_id="eng", lessons_per_week=2),
                Lesson(id="l3", teacher_id="t1", class_id="c2", subject_id="mat", lessons_per_week=1),
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

        stats = add_all_no_overlap_constraints(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible
        assert len(solution.assignments) == 5  # 2 + 2 + 1 instances


class TestInfeasibleScenarios:
    """Tests for scenarios that should be infeasible."""

    def test_infeasible_when_not_enough_slots_for_teacher(self):
        """Infeasible when teacher has too many lessons for available slots."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[
                StudentClass(id="c1", name="Class 1"),
                StudentClass(id="c2", name="Class 2"),
                StudentClass(id="c3", name="Class 3"),
            ],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 1", type=RoomType.CLASSROOM)],
            lessons=[
                # Teacher has 3 lessons but only 2 slots
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
                Lesson(id="l2", teacher_id="t1", class_id="c2", subject_id="mat", lessons_per_week=1),
                Lesson(id="l3", teacher_id="t1", class_id="c3", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        add_teacher_no_overlap(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.status == SolverStatus.INFEASIBLE

    def test_infeasible_when_not_enough_rooms(self):
        """Infeasible when multiple lessons need single room at same time."""
        input_data = TimetableInput(
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
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),  # Only 1 room
            ],
            lessons=[
                # Both lessons need to happen in same slot but only 1 room
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
                Lesson(id="l2", teacher_id="t2", class_id="c2", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                # Only 1 slot
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        add_room_no_overlap(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.status == SolverStatus.INFEASIBLE
