"""Tests for room assignment and suitability constraints."""

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
    RoomRequirement,
)
from solver.model_builder import TimetableModelBuilder, SolverStatus
from solver.constraints.rooms import (
    get_valid_rooms_for_lesson,
    add_room_assignment_constraints,
    add_room_no_overlap_with_optional_intervals,
    add_all_room_constraints,
    analyze_room_assignments,
    get_lessons_without_valid_rooms,
    RoomConstraintStats,
)


@pytest.fixture
def basic_input() -> TimetableInput:
    """Create basic timetable input for testing."""
    return TimetableInput(
        teachers=[Teacher(id="t1", name="Teacher 1")],
        classes=[StudentClass(id="c1", name="Class 1", student_count=25)],
        subjects=[Subject(id="mat", name="Maths")],
        rooms=[
            Room(id="r1", name="Room 1", type=RoomType.CLASSROOM, capacity=30),
            Room(id="r2", name="Room 2", type=RoomType.CLASSROOM, capacity=20),
        ],
        lessons=[
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
        ],
        periods=[
            Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
        ],
    )


class TestGetValidRoomsForLesson:
    """Tests for room filtering based on requirements."""

    def test_all_rooms_valid_when_no_requirements(self, basic_input):
        """All rooms are valid when no specific requirements."""
        builder = TimetableModelBuilder(basic_input)
        builder.create_variables()

        lesson = basic_input.lessons[0]
        valid_rooms = get_valid_rooms_for_lesson(builder, lesson)

        # Only room 1 has capacity >= 25, room 2 has capacity 20
        assert 0 in valid_rooms  # r1 with capacity 30
        assert 1 not in valid_rooms  # r2 with capacity 20 < 25

    def test_filters_by_room_type(self):
        """Filters rooms by required room type."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[
                Subject(id="sci", name="Science", requires_specialist_room=True,
                       required_room_type=RoomType.SCIENCE_LAB),
            ],
            rooms=[
                Room(id="r1", name="Classroom", type=RoomType.CLASSROOM, capacity=30),
                Room(id="lab1", name="Science Lab", type=RoomType.SCIENCE_LAB, capacity=24),
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

        lesson = input_data.lessons[0]
        valid_rooms = get_valid_rooms_for_lesson(builder, lesson)

        assert valid_rooms == [1]  # Only the science lab

    def test_filters_by_lesson_room_type_requirement(self):
        """Lesson's explicit room type requirement overrides subject."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="pe", name="PE")],
            rooms=[
                Room(id="r1", name="Classroom", type=RoomType.CLASSROOM),
                Room(id="gym", name="Gymnasium", type=RoomType.GYM),
            ],
            lessons=[
                Lesson(
                    id="l1", teacher_id="t1", class_id="c1", subject_id="pe",
                    lessons_per_week=1,
                    room_requirement=RoomRequirement(room_type=RoomType.GYM)
                ),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        lesson = input_data.lessons[0]
        valid_rooms = get_valid_rooms_for_lesson(builder, lesson)

        assert valid_rooms == [1]  # Only the gym

    def test_filters_by_capacity(self):
        """Filters rooms by minimum capacity."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1", student_count=28)],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[
                Room(id="r1", name="Small Room", type=RoomType.CLASSROOM, capacity=20),
                Room(id="r2", name="Medium Room", type=RoomType.CLASSROOM, capacity=25),
                Room(id="r3", name="Large Room", type=RoomType.CLASSROOM, capacity=35),
            ],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        lesson = input_data.lessons[0]
        valid_rooms = get_valid_rooms_for_lesson(builder, lesson)

        # Only r3 (capacity 35) >= class size 28
        assert valid_rooms == [2]

    def test_filters_excluded_rooms(self):
        """Excludes specific rooms."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
                Room(id="r2", name="Room 2", type=RoomType.CLASSROOM),
                Room(id="r3", name="Room 3", type=RoomType.CLASSROOM),
            ],
            lessons=[
                Lesson(
                    id="l1", teacher_id="t1", class_id="c1", subject_id="mat",
                    lessons_per_week=1,
                    room_requirement=RoomRequirement(excluded_rooms=["r1", "r3"])
                ),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        lesson = input_data.lessons[0]
        valid_rooms = get_valid_rooms_for_lesson(builder, lesson)

        assert valid_rooms == [1]  # Only r2

    def test_specific_room_requirement(self):
        """Restricts to specific preferred rooms."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
                Room(id="r2", name="Room 2", type=RoomType.CLASSROOM),
                Room(id="r3", name="Room 3", type=RoomType.CLASSROOM),
            ],
            lessons=[
                Lesson(
                    id="l1", teacher_id="t1", class_id="c1", subject_id="mat",
                    lessons_per_week=1,
                    room_requirement=RoomRequirement(preferred_rooms=["r2"])
                ),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        lesson = input_data.lessons[0]
        valid_rooms = get_valid_rooms_for_lesson(builder, lesson)

        assert valid_rooms == [1]  # Only r2

    def test_equipment_requirement(self):
        """Filters by required equipment."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="cs", name="Computer Science")],
            rooms=[
                Room(id="r1", name="Classroom", type=RoomType.CLASSROOM),
                Room(id="comp1", name="Computer Lab", type=RoomType.COMPUTER_LAB,
                     equipment=["computers", "projector"]),
                Room(id="comp2", name="Computer Lab 2", type=RoomType.COMPUTER_LAB,
                     equipment=["computers"]),
            ],
            lessons=[
                Lesson(
                    id="l1", teacher_id="t1", class_id="c1", subject_id="cs",
                    lessons_per_week=1,
                    room_requirement=RoomRequirement(
                        room_type=RoomType.COMPUTER_LAB,
                        requires_equipment=["computers", "projector"]
                    )
                ),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        lesson = input_data.lessons[0]
        valid_rooms = get_valid_rooms_for_lesson(builder, lesson)

        # Only comp1 has both computers and projector
        assert valid_rooms == [1]


class TestRoomAssignmentConstraints:
    """Tests for AddAllowedAssignments constraints."""

    def test_adds_constraints_when_rooms_filtered(self):
        """Adds constraints when some rooms are not valid."""
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

        count = add_room_assignment_constraints(builder)

        # 1 lesson * 1 instance = 1 constraint
        assert count == 1

    def test_no_constraints_when_all_rooms_valid(self):
        """No constraints added when all rooms are valid."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
                Room(id="r2", name="Room 2", type=RoomType.CLASSROOM),
            ],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        count = add_room_assignment_constraints(builder)

        assert count == 0  # No filtering needed

    def test_solver_respects_room_type_constraint(self):
        """Solver assigns lessons to correct room types."""
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
        add_room_assignment_constraints(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible
        assert len(solution.assignments) == 1
        assert solution.assignments[0].room_id == "lab1"


class TestRoomNoOverlapWithOptionalIntervals:
    """Tests for room no-overlap using optional intervals."""

    def test_creates_optional_intervals(self):
        """Creates optional intervals for potential room assignments."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
                Room(id="r2", name="Room 2", type=RoomType.CLASSROOM),
            ],
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

        constraints, intervals = add_room_no_overlap_with_optional_intervals(builder)

        # 2 rooms * 2 lesson instances = 4 optional intervals
        assert intervals == 4
        # Each room gets a constraint (both have >1 possible interval)
        assert constraints == 2

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
        add_room_no_overlap_with_optional_intervals(builder)
        builder._add_valid_time_slots_constraint()
        builder._add_teacher_no_overlap_constraint()
        builder._add_class_no_overlap_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.is_feasible

        # Check no room has overlapping lessons
        room_slots = {}
        for a in solution.assignments:
            key = (a.room_id, a.day, a.start_minutes)
            assert key not in room_slots, f"Room {a.room_id} double-booked"
            room_slots[key] = a.lesson_id


class TestAddAllRoomConstraints:
    """Tests for combined room constraints function."""

    def test_returns_stats(self):
        """Returns statistics about constraints added."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1", student_count=25)],
            subjects=[
                Subject(id="sci", name="Science", requires_specialist_room=True,
                       required_room_type=RoomType.SCIENCE_LAB),
            ],
            rooms=[
                Room(id="r1", name="Classroom", type=RoomType.CLASSROOM, capacity=30),
                Room(id="lab1", name="Science Lab", type=RoomType.SCIENCE_LAB, capacity=24),
            ],
            lessons=[
                Lesson(
                    id="l1", teacher_id="t1", class_id="c1", subject_id="sci",
                    lessons_per_week=1,
                    room_requirement=RoomRequirement(min_capacity=20)
                ),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        stats = add_all_room_constraints(builder, include_soft_constraints=False)

        assert isinstance(stats, RoomConstraintStats)
        assert stats.lessons_with_room_type_requirement == 1
        assert stats.lessons_with_capacity_requirement == 1


class TestDiagnosticFunctions:
    """Tests for diagnostic/debugging functions."""

    def test_analyze_room_assignments(self):
        """Analyzes room suitability for lessons."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1", student_count=25)],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[
                Room(id="r1", name="Large Room", type=RoomType.CLASSROOM, capacity=30),
                Room(id="r2", name="Small Room", type=RoomType.CLASSROOM, capacity=20),
            ],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        analysis = analyze_room_assignments(builder)

        assert "l1" in analysis
        assert len(analysis["l1"]) == 2
        assert analysis["l1"][0].is_valid is True  # r1 is valid
        assert analysis["l1"][1].is_valid is False  # r2 too small

    def test_get_lessons_without_valid_rooms(self):
        """Finds lessons that have no valid rooms due to capacity."""
        # Note: Room type mismatches are caught by Pydantic validation,
        # so we test capacity-based filtering instead
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1", student_count=100)],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[
                # All rooms too small for class of 100
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM, capacity=30),
                Room(id="r2", name="Room 2", type=RoomType.CLASSROOM, capacity=25),
            ],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()

        problematic = get_lessons_without_valid_rooms(builder)

        assert len(problematic) == 1
        assert problematic[0][0] == "l1"
        assert any("capacity" in reason.lower() for reason in problematic[0][1])


class TestInfeasibleScenarios:
    """Tests for scenarios that should be infeasible."""

    def test_infeasible_when_no_room_of_required_type(self):
        """Room type mismatch is caught by Pydantic validation."""
        # Pydantic validates that specialist room types exist, so this
        # raises ValidationError before the solver runs
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="requires science_lab"):
            TimetableInput(
                teachers=[Teacher(id="t1", name="Teacher 1")],
                classes=[StudentClass(id="c1", name="Class 1")],
                subjects=[
                    Subject(id="sci", name="Science", requires_specialist_room=True,
                           required_room_type=RoomType.SCIENCE_LAB),
                ],
                rooms=[
                    Room(id="r1", name="Classroom", type=RoomType.CLASSROOM),
                ],
                lessons=[
                    Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="sci", lessons_per_week=1),
                ],
                periods=[
                    Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
                ],
            )

    def test_infeasible_when_all_rooms_excluded(self):
        """Infeasible when all rooms are excluded for a lesson."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM),
                Room(id="r2", name="Room 2", type=RoomType.CLASSROOM),
            ],
            lessons=[
                Lesson(
                    id="l1", teacher_id="t1", class_id="c1", subject_id="mat",
                    lessons_per_week=1,
                    room_requirement=RoomRequirement(excluded_rooms=["r1", "r2"])
                ),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        add_room_assignment_constraints(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.status == SolverStatus.INFEASIBLE

    def test_infeasible_when_capacity_insufficient(self):
        """Infeasible when no room has sufficient capacity."""
        input_data = TimetableInput(
            teachers=[Teacher(id="t1", name="Teacher 1")],
            classes=[StudentClass(id="c1", name="Class 1", student_count=50)],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[
                Room(id="r1", name="Room 1", type=RoomType.CLASSROOM, capacity=30),
                Room(id="r2", name="Room 2", type=RoomType.CLASSROOM, capacity=25),
            ],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
            ],
            periods=[
                Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        builder.create_variables()
        add_room_assignment_constraints(builder)
        builder._add_valid_time_slots_constraint()

        solution = builder.solve(time_limit_seconds=10)

        assert solution.status == SolverStatus.INFEASIBLE
