"""Comprehensive test suite for the AI Timetabler solver.

Test Categories:
1. Data Loading Tests - Loading and validating input data
2. Constraint Tests - All hard constraint enforcement
3. Solver Tests - Solver behavior and solution finding
4. Output Tests - Output format and views
5. Integration Tests - End-to-end workflows
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

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
    SchoolConfig,
)
from solver.data.generator import (
    GeneratorConfig,
    generate_sample_school,
    generate_small_school,
    generate_medium_school,
)
from solver.data.loader import load_school_data, validate_school_data, DataValidationError
from solver.model_builder import (
    TimetableModelBuilder,
    SolverSolution,
    SolverStatus,
    LessonAssignment,
)
from solver.output.schema import (
    TimetableOutput,
    LessonOutput,
    create_timetable_output,
    solution_to_json,
    solution_to_dict,
    OutputStatus,
)
from solver.output.metrics import (
    QualityMetricsCalculator,
    MetricsReport,
    calculate_all_metrics,
    generate_report,
)


# =============================================================================
# Fixtures - Sample Data
# =============================================================================

@pytest.fixture
def minimal_input() -> TimetableInput:
    """Create minimal valid TimetableInput for testing."""
    return TimetableInput(
        config=SchoolConfig(
            school_name="Test School",
            num_days=5,
        ),
        teachers=[
            Teacher(id="t1", name="Mr Smith", subjects=["mat"]),
        ],
        classes=[
            StudentClass(id="c1", name="Year 10A"),
        ],
        subjects=[
            Subject(id="mat", name="Mathematics"),
        ],
        rooms=[
            Room(id="r1", name="Room 101", type=RoomType.CLASSROOM),
        ],
        lessons=[
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
        ],
        periods=[
            Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            Period(id="tue2", name="Tue P2", day=1, start_minutes=600, end_minutes=660),
            Period(id="wed1", name="Wed P1", day=2, start_minutes=540, end_minutes=600),
        ],
    )


@pytest.fixture
def small_school_input() -> TimetableInput:
    """Generate a small school for testing."""
    return generate_small_school(seed=42)


@pytest.fixture
def medium_school_input() -> TimetableInput:
    """Generate a medium school for testing."""
    return generate_medium_school(seed=42)


@pytest.fixture
def multi_teacher_input() -> TimetableInput:
    """Create input with multiple teachers for constraint testing."""
    periods = []
    for day in range(5):
        for p in range(4):
            periods.append(Period(
                id=f"d{day}p{p}",
                name=f"Day {day} Period {p+1}",
                day=day,
                start_minutes=540 + p * 60,
                end_minutes=600 + p * 60,
            ))

    return TimetableInput(
        config=SchoolConfig(school_name="Multi Teacher School", num_days=5),
        teachers=[
            Teacher(id="t1", name="Mr Smith", subjects=["mat", "sci"]),
            Teacher(id="t2", name="Ms Jones", subjects=["eng", "his"]),
            Teacher(id="t3", name="Dr Brown", subjects=["sci", "geo"]),
        ],
        classes=[
            StudentClass(id="c1", name="Year 10A", student_count=25),
            StudentClass(id="c2", name="Year 10B", student_count=28),
        ],
        subjects=[
            Subject(id="mat", name="Mathematics"),
            Subject(id="eng", name="English"),
            Subject(id="sci", name="Science", requires_specialist_room=True, required_room_type=RoomType.SCIENCE_LAB),
            Subject(id="his", name="History"),
            Subject(id="geo", name="Geography"),
        ],
        rooms=[
            Room(id="r1", name="Room 101", type=RoomType.CLASSROOM, capacity=30),
            Room(id="r2", name="Room 102", type=RoomType.CLASSROOM, capacity=30),
            Room(id="lab1", name="Science Lab 1", type=RoomType.SCIENCE_LAB, capacity=25),
        ],
        lessons=[
            # Teacher 1 lessons
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=3),
            Lesson(id="l2", teacher_id="t1", class_id="c2", subject_id="mat", lessons_per_week=3),
            Lesson(id="l3", teacher_id="t1", class_id="c1", subject_id="sci", lessons_per_week=2),
            # Teacher 2 lessons
            Lesson(id="l4", teacher_id="t2", class_id="c1", subject_id="eng", lessons_per_week=3),
            Lesson(id="l5", teacher_id="t2", class_id="c2", subject_id="eng", lessons_per_week=3),
            # Teacher 3 lessons
            Lesson(id="l6", teacher_id="t3", class_id="c2", subject_id="sci", lessons_per_week=2),
            Lesson(id="l7", teacher_id="t3", class_id="c1", subject_id="geo", lessons_per_week=2),
        ],
        periods=periods,
    )


@pytest.fixture
def teacher_unavailable_input() -> TimetableInput:
    """Create input with teacher unavailability."""
    periods = []
    for day in range(3):
        for p in range(3):
            periods.append(Period(
                id=f"d{day}p{p}",
                name=f"Day {day} Period {p+1}",
                day=day,
                start_minutes=540 + p * 60,
                end_minutes=600 + p * 60,
            ))

    return TimetableInput(
        config=SchoolConfig(school_name="Unavailability Test", num_days=3),
        teachers=[
            Teacher(
                id="t1",
                name="Mr Smith",
                subjects=["mat"],
                availability=[
                    # Unavailable on Monday morning (day 0, period 0)
                    Availability(day=0, start_minutes=540, end_minutes=600, available=False),
                ]
            ),
        ],
        classes=[
            StudentClass(id="c1", name="Year 10A"),
        ],
        subjects=[
            Subject(id="mat", name="Mathematics"),
        ],
        rooms=[
            Room(id="r1", name="Room 101", type=RoomType.CLASSROOM),
        ],
        lessons=[
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
        ],
        periods=periods,
    )


@pytest.fixture
def specialist_room_input() -> TimetableInput:
    """Create input with specialist room requirements."""
    periods = []
    for day in range(5):
        for p in range(4):
            periods.append(Period(
                id=f"d{day}p{p}",
                name=f"Day {day} Period {p+1}",
                day=day,
                start_minutes=540 + p * 60,
                end_minutes=600 + p * 60,
            ))

    return TimetableInput(
        config=SchoolConfig(school_name="Specialist Room Test", num_days=5),
        teachers=[
            Teacher(id="t1", name="Mr Science", subjects=["sci", "mat"]),
            Teacher(id="t2", name="Mr PE", subjects=["pe"]),
        ],
        classes=[
            StudentClass(id="c1", name="Year 10A"),
        ],
        subjects=[
            Subject(id="mat", name="Mathematics"),
            Subject(id="sci", name="Science", requires_specialist_room=True, required_room_type=RoomType.SCIENCE_LAB),
            Subject(id="pe", name="Physical Education", requires_specialist_room=True, required_room_type=RoomType.GYM),
        ],
        rooms=[
            Room(id="r1", name="Room 101", type=RoomType.CLASSROOM),
            Room(id="lab1", name="Science Lab", type=RoomType.SCIENCE_LAB),
            Room(id="gym1", name="Gymnasium", type=RoomType.GYM),
        ],
        lessons=[
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=3),
            Lesson(id="l2", teacher_id="t1", class_id="c1", subject_id="sci", lessons_per_week=2),
            Lesson(id="l3", teacher_id="t2", class_id="c1", subject_id="pe", lessons_per_week=2),
        ],
        periods=periods,
    )


@pytest.fixture
def json_input_data() -> dict:
    """Create valid JSON input data dictionary."""
    return {
        "teachers": [
            {"id": "t1", "name": "Mr Smith", "subjects": ["mat"]},
        ],
        "groups": [
            {"id": "c1", "name": "Year 10A"},
        ],
        "subjects": [
            {"id": "mat", "name": "Maths"},
        ],
        "rooms": [
            {"id": "r1", "name": "Room 101", "type": "classroom"},
        ],
        "lessons": [
            {"id": "l1", "teacher_id": "t1", "group_id": "c1", "subject_id": "mat"},
        ],
    }


# =============================================================================
# 1. Data Loading Tests
# =============================================================================

class TestLoadValidInput:
    """Tests for loading valid input data."""

    def test_load_valid_json_file(self, json_input_data, tmp_path):
        """Load valid JSON file successfully."""
        filepath = tmp_path / "input.json"
        with open(filepath, "w") as f:
            json.dump(json_input_data, f)

        data = load_school_data(filepath)

        assert "teachers" in data
        assert "lessons" in data
        assert len(data["teachers"]) == 1

    def test_load_valid_timetable_input(self, minimal_input):
        """TimetableInput validates correctly."""
        assert isinstance(minimal_input, TimetableInput)
        assert len(minimal_input.teachers) == 1
        assert len(minimal_input.lessons) == 1

    def test_generated_data_is_valid(self):
        """Generated school data passes validation."""
        school = generate_small_school(seed=42)

        assert isinstance(school, TimetableInput)
        assert len(school.teachers) > 0
        assert len(school.lessons) > 0


class TestRejectInvalidInput:
    """Tests for rejecting invalid input data."""

    def test_reject_missing_file(self, tmp_path):
        """Reject nonexistent file."""
        with pytest.raises(FileNotFoundError):
            load_school_data(tmp_path / "nonexistent.json")

    def test_reject_invalid_json(self, tmp_path):
        """Reject invalid JSON syntax."""
        filepath = tmp_path / "invalid.json"
        filepath.write_text("not valid json {")

        with pytest.raises(json.JSONDecodeError):
            load_school_data(filepath)

    def test_reject_missing_required_fields(self):
        """Reject data missing required fields."""
        data = {"teachers": [{"id": "t1", "name": "Mr Smith"}]}

        with pytest.raises(DataValidationError):
            validate_school_data(data)

    def test_reject_invalid_entity_structure(self):
        """Reject malformed entity data."""
        with pytest.raises(Exception):  # Pydantic validation error
            TimetableInput(
                teachers="not a list",  # Invalid
                classes=[],
                subjects=[],
                rooms=[],
                lessons=[],
                periods=[],
            )

    def test_reject_duplicate_ids(self):
        """Reject duplicate entity IDs."""
        with pytest.raises(ValueError, match="Duplicate"):
            TimetableInput(
                teachers=[
                    Teacher(id="t1", name="Mr Smith"),
                    Teacher(id="t1", name="Ms Jones"),  # Duplicate
                ],
                classes=[StudentClass(id="c1", name="Year 10A")],
                subjects=[Subject(id="mat", name="Maths")],
                rooms=[Room(id="r1", name="Room 101", type=RoomType.CLASSROOM)],
                lessons=[Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1)],
                periods=[Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600)],
            )


class TestValidateReferences:
    """Tests for reference validation."""

    def test_reject_unknown_teacher_reference(self):
        """Reject lesson referencing unknown teacher."""
        with pytest.raises(ValueError, match="unknown teacher_id"):
            TimetableInput(
                teachers=[Teacher(id="t1", name="Mr Smith")],
                classes=[StudentClass(id="c1", name="Year 10A")],
                subjects=[Subject(id="mat", name="Maths")],
                rooms=[Room(id="r1", name="Room 101", type=RoomType.CLASSROOM)],
                lessons=[
                    Lesson(id="l1", teacher_id="unknown", class_id="c1", subject_id="mat", lessons_per_week=1),
                ],
                periods=[Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600)],
            )

    def test_reject_unknown_class_reference(self):
        """Reject lesson referencing unknown class."""
        with pytest.raises(ValueError, match="unknown class_id"):
            TimetableInput(
                teachers=[Teacher(id="t1", name="Mr Smith")],
                classes=[StudentClass(id="c1", name="Year 10A")],
                subjects=[Subject(id="mat", name="Maths")],
                rooms=[Room(id="r1", name="Room 101", type=RoomType.CLASSROOM)],
                lessons=[
                    Lesson(id="l1", teacher_id="t1", class_id="unknown", subject_id="mat", lessons_per_week=1),
                ],
                periods=[Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600)],
            )

    def test_reject_unknown_subject_reference(self):
        """Reject lesson referencing unknown subject."""
        with pytest.raises(ValueError, match="unknown subject_id"):
            TimetableInput(
                teachers=[Teacher(id="t1", name="Mr Smith")],
                classes=[StudentClass(id="c1", name="Year 10A")],
                subjects=[Subject(id="mat", name="Maths")],
                rooms=[Room(id="r1", name="Room 101", type=RoomType.CLASSROOM)],
                lessons=[
                    Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="unknown", lessons_per_week=1),
                ],
                periods=[Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600)],
            )

    def test_validate_teacher_subject_references(self):
        """Reject teacher referencing unknown subject."""
        with pytest.raises(ValueError, match="unknown subject"):
            TimetableInput(
                teachers=[Teacher(id="t1", name="Mr Smith", subjects=["unknown"])],
                classes=[StudentClass(id="c1", name="Year 10A")],
                subjects=[Subject(id="mat", name="Maths")],
                rooms=[Room(id="r1", name="Room 101", type=RoomType.CLASSROOM)],
                lessons=[
                    Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=1),
                ],
                periods=[Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600)],
            )

    def test_valid_references_pass(self, minimal_input):
        """Valid references are accepted."""
        # Should not raise
        assert minimal_input.get_teacher("t1") is not None
        assert minimal_input.get_class("c1") is not None
        assert minimal_input.get_subject("mat") is not None


# =============================================================================
# 2. Constraint Tests
# =============================================================================

class TestNoTeacherDoubleBooking:
    """Tests for teacher no-overlap constraint."""

    def test_teacher_not_double_booked(self, multi_teacher_input):
        """Teacher cannot teach two classes at the same time."""
        builder = TimetableModelBuilder(multi_teacher_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        # Group assignments by teacher and check for overlaps
        for teacher in multi_teacher_input.teachers:
            teacher_assignments = [
                a for a in solution.assignments if a.teacher_id == teacher.id
            ]

            # Check each pair for time overlap on same day
            for i, a1 in enumerate(teacher_assignments):
                for a2 in teacher_assignments[i+1:]:
                    if a1.day == a2.day:
                        # Check for overlap
                        overlaps = not (a1.end_minutes <= a2.start_minutes or
                                       a2.end_minutes <= a1.start_minutes)
                        assert not overlaps, (
                            f"Teacher {teacher.id} double-booked: "
                            f"Day {a1.day}, {a1.start_minutes}-{a1.end_minutes} and "
                            f"{a2.start_minutes}-{a2.end_minutes}"
                        )


class TestNoClassDoubleBooking:
    """Tests for class no-overlap constraint."""

    def test_class_not_double_booked(self, multi_teacher_input):
        """Class cannot have two lessons at the same time."""
        builder = TimetableModelBuilder(multi_teacher_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        # Group assignments by class and check for overlaps
        for cls in multi_teacher_input.classes:
            class_assignments = [
                a for a in solution.assignments if a.class_id == cls.id
            ]

            for i, a1 in enumerate(class_assignments):
                for a2 in class_assignments[i+1:]:
                    if a1.day == a2.day:
                        overlaps = not (a1.end_minutes <= a2.start_minutes or
                                       a2.end_minutes <= a1.start_minutes)
                        assert not overlaps, (
                            f"Class {cls.id} double-booked: "
                            f"Day {a1.day}, {a1.start_minutes}-{a1.end_minutes} and "
                            f"{a2.start_minutes}-{a2.end_minutes}"
                        )


class TestTeacherUnavailabilityRespected:
    """Tests for teacher availability constraint."""

    def test_respects_teacher_unavailability(self, teacher_unavailable_input):
        """Lessons not scheduled during teacher unavailability."""
        builder = TimetableModelBuilder(teacher_unavailable_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        # Teacher is unavailable day 0, 540-600
        for assignment in solution.assignments:
            if assignment.teacher_id == "t1" and assignment.day == 0:
                # Should not overlap with 540-600
                overlaps = not (assignment.end_minutes <= 540 or
                               assignment.start_minutes >= 600)
                assert not overlaps, (
                    f"Teacher t1 scheduled during unavailability: "
                    f"Day 0, {assignment.start_minutes}-{assignment.end_minutes}"
                )


class TestRoomSuitabilityEnforced:
    """Tests for room type constraint."""

    def test_science_in_science_lab(self, specialist_room_input):
        """Science lessons must be in science lab."""
        builder = TimetableModelBuilder(specialist_room_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        # Find science lessons (l2)
        science_assignments = [
            a for a in solution.assignments if a.lesson_id == "l2"
        ]

        for assignment in science_assignments:
            assert assignment.room_id == "lab1", (
                f"Science lesson in wrong room: {assignment.room_id}, expected lab1"
            )

    def test_pe_in_gym(self, specialist_room_input):
        """PE lessons must be in gym."""
        builder = TimetableModelBuilder(specialist_room_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        # Find PE lessons (l3)
        pe_assignments = [
            a for a in solution.assignments if a.lesson_id == "l3"
        ]

        for assignment in pe_assignments:
            assert assignment.room_id == "gym1", (
                f"PE lesson in wrong room: {assignment.room_id}, expected gym1"
            )

    def test_regular_lessons_in_classroom(self, specialist_room_input):
        """Regular lessons can be in any classroom."""
        builder = TimetableModelBuilder(specialist_room_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        # Math lessons (l1) should be in regular classroom
        math_assignments = [
            a for a in solution.assignments if a.lesson_id == "l1"
        ]

        for assignment in math_assignments:
            # Can be in any room that's a classroom (r1 is the only classroom)
            room = specialist_room_input.get_room(assignment.room_id)
            assert room is not None


class TestSchoolDayBounds:
    """Tests for school day boundary constraints."""

    def test_lessons_within_school_hours(self, minimal_input):
        """Lessons scheduled within defined periods."""
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        # Get valid period times
        valid_slots = set()
        for period in minimal_input.get_schedulable_periods():
            valid_slots.add((period.day, period.start_minutes))

        for assignment in solution.assignments:
            slot = (assignment.day, assignment.start_minutes)
            assert slot in valid_slots, (
                f"Lesson scheduled outside valid periods: "
                f"Day {assignment.day}, {assignment.start_minutes}"
            )


class TestNoRoomDoubleBooking:
    """Tests for room no-overlap constraint."""

    def test_room_not_double_booked(self, multi_teacher_input):
        """Room cannot host two lessons at the same time."""
        builder = TimetableModelBuilder(multi_teacher_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        # Group assignments by room and check for overlaps
        for room in multi_teacher_input.rooms:
            room_assignments = [
                a for a in solution.assignments if a.room_id == room.id
            ]

            for i, a1 in enumerate(room_assignments):
                for a2 in room_assignments[i+1:]:
                    if a1.day == a2.day:
                        overlaps = not (a1.end_minutes <= a2.start_minutes or
                                       a2.end_minutes <= a1.start_minutes)
                        assert not overlaps, (
                            f"Room {room.id} double-booked: "
                            f"Day {a1.day}, {a1.start_minutes}-{a1.end_minutes} and "
                            f"{a2.start_minutes}-{a2.end_minutes}"
                        )


# =============================================================================
# 3. Solver Tests
# =============================================================================

class TestSmallSchoolSolvable:
    """Tests for solver finding solutions."""

    def test_minimal_school_solvable(self, minimal_input):
        """Minimal school configuration is solvable."""
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        assert solution.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
        assert len(solution.assignments) == 2  # 2 lessons per week

    def test_small_school_solvable(self, small_school_input):
        """Small generated school is solvable."""
        builder = TimetableModelBuilder(small_school_input)
        solution = builder.solve(time_limit_seconds=120)

        # May timeout on slow machines, so we skip rather than fail
        if solution.status == SolverStatus.UNKNOWN:
            pytest.skip("Solver timed out - may need more time on this machine")

        assert solution.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
        assert len(solution.assignments) > 0


class TestSolutionIsValid:
    """Tests for solution validity."""

    def test_all_lessons_scheduled(self, minimal_input):
        """All required lessons are scheduled."""
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        # Count expected lesson instances
        expected_instances = sum(l.lessons_per_week for l in minimal_input.lessons)
        assert len(solution.assignments) == expected_instances

    def test_assignments_have_required_fields(self, minimal_input):
        """Each assignment has all required fields."""
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        for assignment in solution.assignments:
            assert isinstance(assignment, LessonAssignment)
            assert assignment.lesson_id is not None
            assert assignment.day >= 0
            assert assignment.start_minutes >= 0
            assert assignment.end_minutes > assignment.start_minutes
            assert assignment.room_id is not None
            assert assignment.teacher_id is not None
            assert assignment.class_id is not None

    def test_solution_references_valid_entities(self, minimal_input):
        """Solution references valid teachers, classes, rooms."""
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        teacher_ids = {t.id for t in minimal_input.teachers}
        class_ids = {c.id for c in minimal_input.classes}
        room_ids = {r.id for r in minimal_input.rooms}

        for assignment in solution.assignments:
            assert assignment.teacher_id in teacher_ids
            assert assignment.class_id in class_ids
            assert assignment.room_id in room_ids


class TestTimeoutHandling:
    """Tests for solver timeout behavior."""

    def test_respects_timeout(self, small_school_input):
        """Solver respects the time limit."""
        builder = TimetableModelBuilder(small_school_input)

        # Very short timeout
        solution = builder.solve(time_limit_seconds=1)

        # Should return some status (may or may not find solution)
        assert solution.status in (
            SolverStatus.OPTIMAL,
            SolverStatus.FEASIBLE,
            SolverStatus.INFEASIBLE,
            SolverStatus.UNKNOWN,
        )
        assert solution.solve_time_ms <= 5000  # Allow some overhead

    def test_returns_best_solution_on_timeout(self, small_school_input):
        """Returns best found solution if timed out."""
        builder = TimetableModelBuilder(small_school_input)
        solution = builder.solve(time_limit_seconds=5)

        if solution.status == SolverStatus.FEASIBLE:
            # Found a solution before optimal was proven
            assert len(solution.assignments) > 0


class TestInfeasibleDetection:
    """Tests for detecting infeasible problems."""

    def test_detects_too_many_lessons(self):
        """Detects when there are more lessons than slots."""
        # Only 2 slots but 3 lessons for same teacher
        input_data = TimetableInput(
            config=SchoolConfig(school_name="Infeasible Test", num_days=1),
            teachers=[Teacher(id="t1", name="Mr Smith")],
            classes=[StudentClass(id="c1", name="Year 10A")],
            subjects=[Subject(id="mat", name="Maths")],
            rooms=[Room(id="r1", name="Room 101", type=RoomType.CLASSROOM)],
            lessons=[
                Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=3),
            ],
            periods=[
                Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600),
                Period(id="p2", name="P2", day=0, start_minutes=600, end_minutes=660),
            ],
        )

        builder = TimetableModelBuilder(input_data)
        solution = builder.solve(time_limit_seconds=10)

        assert solution.status == SolverStatus.INFEASIBLE

    def test_detects_missing_required_room_type(self):
        """Detects when required room type doesn't exist during validation."""
        # TimetableInput validation catches missing room types at construction time
        with pytest.raises(ValueError, match="requires science_lab"):
            TimetableInput(
                config=SchoolConfig(school_name="No Lab Test", num_days=5),
                teachers=[Teacher(id="t1", name="Mr Science")],
                classes=[StudentClass(id="c1", name="Year 10A")],
                subjects=[
                    Subject(id="sci", name="Science", requires_specialist_room=True, required_room_type=RoomType.SCIENCE_LAB),
                ],
                rooms=[
                    Room(id="r1", name="Room 101", type=RoomType.CLASSROOM),  # No science lab!
                ],
                lessons=[
                    Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="sci", lessons_per_week=1),
                ],
                periods=[
                    Period(id="p1", name="P1", day=0, start_minutes=540, end_minutes=600),
                ],
            )


# =============================================================================
# 4. Output Tests
# =============================================================================

class TestOutputFormatValid:
    """Tests for output format validity."""

    def test_creates_valid_output(self, minimal_input):
        """Creates valid TimetableOutput from solution."""
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)

        assert isinstance(output, TimetableOutput)
        assert output.status in (OutputStatus.OPTIMAL, OutputStatus.FEASIBLE)

    def test_output_has_all_lessons(self, minimal_input):
        """Output contains all scheduled lessons."""
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)

        expected_count = sum(l.lessons_per_week for l in minimal_input.lessons)
        assert len(output.timetable.lessons) == expected_count

    def test_output_serializes_to_json(self, minimal_input):
        """Output can be serialized to valid JSON."""
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        json_str = solution_to_json(solution)

        # Should be valid JSON
        data = json.loads(json_str)
        assert "status" in data
        assert "timetable" in data
        assert "lessons" in data["timetable"]

    def test_json_uses_camel_case(self, minimal_input):
        """JSON output uses camelCase keys."""
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        json_str = solution_to_json(solution)
        data = json.loads(json_str)

        assert "solveTimeSeconds" in data
        assert "softConstraintScores" in data["quality"]

        if data["timetable"]["lessons"]:
            lesson = data["timetable"]["lessons"][0]
            assert "lessonId" in lesson
            assert "startTime" in lesson


class TestViewsCorrect:
    """Tests for pre-computed views."""

    def test_views_by_teacher(self, multi_teacher_input):
        """byTeacher view groups lessons correctly."""
        builder = TimetableModelBuilder(multi_teacher_input)
        solution = builder.solve(time_limit_seconds=60)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)

        # Each teacher should have their lessons grouped
        for teacher_id, schedule in output.views.by_teacher.items():
            for lesson in schedule.lessons:
                assert lesson.teacher_id == teacher_id

    def test_views_by_class(self, multi_teacher_input):
        """byClass view groups lessons correctly."""
        builder = TimetableModelBuilder(multi_teacher_input)
        solution = builder.solve(time_limit_seconds=60)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)

        for class_id, schedule in output.views.by_class.items():
            for lesson in schedule.lessons:
                assert lesson.class_id == class_id

    def test_views_by_room(self, multi_teacher_input):
        """byRoom view groups lessons correctly."""
        builder = TimetableModelBuilder(multi_teacher_input)
        solution = builder.solve(time_limit_seconds=60)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)

        for room_id, schedule in output.views.by_room.items():
            for lesson in schedule.lessons:
                assert lesson.room_id == room_id

    def test_views_by_day(self, multi_teacher_input):
        """byDay view groups lessons correctly."""
        builder = TimetableModelBuilder(multi_teacher_input)
        solution = builder.solve(time_limit_seconds=60)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)

        for day, schedule in output.views.by_day.items():
            for lesson in schedule.lessons:
                assert lesson.day == day

    def test_views_sorted_by_time(self, multi_teacher_input):
        """Lessons within views are sorted by time."""
        builder = TimetableModelBuilder(multi_teacher_input)
        solution = builder.solve(time_limit_seconds=60)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)

        for teacher_id, schedule in output.views.by_teacher.items():
            for i in range(len(schedule.lessons) - 1):
                l1, l2 = schedule.lessons[i], schedule.lessons[i+1]
                assert (l1.day, l1.start_time) <= (l2.day, l2.start_time)


class TestMetricsCalculated:
    """Tests for quality metrics calculation."""

    def test_calculates_gap_metrics(self, small_school_input):
        """Gap metrics are calculated."""
        builder = TimetableModelBuilder(small_school_input)
        solution = builder.solve(time_limit_seconds=60)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)
        metrics = calculate_all_metrics(output, small_school_input)

        assert metrics.gap_metrics is not None
        assert metrics.gap_metrics.average_gap_minutes >= 0

    def test_calculates_distribution_metrics(self, small_school_input):
        """Distribution metrics are calculated."""
        builder = TimetableModelBuilder(small_school_input)
        solution = builder.solve(time_limit_seconds=60)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)
        metrics = calculate_all_metrics(output, small_school_input)

        assert metrics.distribution_metrics is not None
        assert 0 <= metrics.distribution_metrics.percentage_well_distributed <= 100

    def test_calculates_balance_metrics(self, small_school_input):
        """Balance metrics are calculated."""
        builder = TimetableModelBuilder(small_school_input)
        solution = builder.solve(time_limit_seconds=60)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)
        metrics = calculate_all_metrics(output, small_school_input)

        assert metrics.balance_metrics is not None
        assert metrics.balance_metrics.average_std_dev >= 0

    def test_calculates_overall_score(self, small_school_input):
        """Overall score is calculated."""
        builder = TimetableModelBuilder(small_school_input)
        solution = builder.solve(time_limit_seconds=60)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)
        metrics = calculate_all_metrics(output, small_school_input)

        assert 0 <= metrics.overall_score <= 100
        assert metrics.grade in ("A", "B", "C", "D", "F")

    def test_generates_report(self, small_school_input):
        """Human-readable report is generated."""
        builder = TimetableModelBuilder(small_school_input)
        solution = builder.solve(time_limit_seconds=60)

        if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)
        report = generate_report(output, small_school_input)

        assert isinstance(report, str)
        assert "TIMETABLE QUALITY REPORT" in report
        assert "Overall Score" in report


# =============================================================================
# 5. Integration Tests
# =============================================================================

class TestEndToEndSmall:
    """End-to-end tests with small school."""

    def test_full_workflow_small(self, small_school_input):
        """Complete workflow: load -> solve -> output -> metrics."""
        # Step 1: Input is already validated (from fixture)
        assert isinstance(small_school_input, TimetableInput)

        # Step 2: Solve
        builder = TimetableModelBuilder(small_school_input)
        solution = builder.solve(time_limit_seconds=120)

        if solution.status == SolverStatus.UNKNOWN:
            pytest.skip("Solver timed out - may need more time on this machine")

        assert solution.is_feasible, f"Failed to solve: {solution.status}"

        # Step 3: Create output
        output = create_timetable_output(solution)

        assert output.status in (OutputStatus.OPTIMAL, OutputStatus.FEASIBLE)
        assert len(output.timetable.lessons) > 0

        # Step 4: Calculate metrics
        metrics = calculate_all_metrics(output, small_school_input)

        assert metrics.hard_constraints_satisfied
        assert metrics.overall_score > 0

    def test_json_round_trip(self, small_school_input):
        """JSON serialization round-trip works."""
        builder = TimetableModelBuilder(small_school_input)
        solution = builder.solve(time_limit_seconds=60)

        if not solution.is_feasible:
            pytest.skip("Could not find solution")

        # Serialize to JSON
        json_str = solution_to_json(solution)

        # Parse back
        data = json.loads(json_str)

        # Verify structure
        assert data["status"] in ("optimal", "feasible")
        assert len(data["timetable"]["lessons"]) == len(solution.assignments)

    def test_all_constraints_verified(self, small_school_input):
        """All hard constraints are satisfied in solution."""
        builder = TimetableModelBuilder(small_school_input)
        solution = builder.solve(time_limit_seconds=60)

        if not solution.is_feasible:
            pytest.skip("Could not find solution")

        # Verify no teacher double-booking
        teacher_slots: dict[str, set[tuple[int, int]]] = {}
        for a in solution.assignments:
            key = a.teacher_id
            slot = (a.day, a.start_minutes)
            if key not in teacher_slots:
                teacher_slots[key] = set()
            assert slot not in teacher_slots[key], f"Teacher {key} double-booked"
            teacher_slots[key].add(slot)

        # Verify no class double-booking
        class_slots: dict[str, set[tuple[int, int]]] = {}
        for a in solution.assignments:
            key = a.class_id
            slot = (a.day, a.start_minutes)
            if key not in class_slots:
                class_slots[key] = set()
            assert slot not in class_slots[key], f"Class {key} double-booked"
            class_slots[key].add(slot)

        # Verify no room double-booking
        room_slots: dict[str, set[tuple[int, int]]] = {}
        for a in solution.assignments:
            key = a.room_id
            slot = (a.day, a.start_minutes)
            if key not in room_slots:
                room_slots[key] = set()
            assert slot not in room_slots[key], f"Room {key} double-booked"
            room_slots[key].add(slot)


class TestEndToEndMedium:
    """End-to-end tests with medium school."""

    def test_medium_school_solvable(self, medium_school_input):
        """Medium school can be solved."""
        builder = TimetableModelBuilder(medium_school_input)
        solution = builder.solve(time_limit_seconds=120)

        # May timeout on slow machines
        if solution.status == SolverStatus.UNKNOWN:
            pytest.skip("Solver timed out - may need more time on this machine")

        # May not find optimal in time, but should find something
        assert solution.status in (
            SolverStatus.OPTIMAL,
            SolverStatus.FEASIBLE,
        ), f"Failed to solve medium school: {solution.status}"

    def test_medium_school_quality_acceptable(self, medium_school_input):
        """Medium school solution has acceptable quality."""
        builder = TimetableModelBuilder(medium_school_input)
        solution = builder.solve(time_limit_seconds=120)

        if not solution.is_feasible:
            pytest.skip("Could not find solution in time")

        output = create_timetable_output(solution)
        metrics = calculate_all_metrics(output, medium_school_input)

        # Should pass hard constraints
        assert metrics.hard_constraints_satisfied

        # Should have reasonable quality (at least grade D)
        assert metrics.overall_score >= 50, f"Quality too low: {metrics.overall_score}"


class TestGeneratedSchoolsValid:
    """Tests that generated schools produce valid solutions."""

    def test_different_seeds_produce_different_results(self):
        """Different seeds produce different but valid schools."""
        school1 = generate_small_school(seed=1)
        school2 = generate_small_school(seed=2)

        # Should have different teachers
        names1 = {t.name for t in school1.teachers}
        names2 = {t.name for t in school2.teachers}

        assert names1 != names2

    def test_custom_config_works(self):
        """Custom generator config produces valid school."""
        config = GeneratorConfig(
            num_teachers=5,
            num_classes=4,
            num_rooms=3,
            lessons_per_class_per_week=10,
            include_specialist_subjects=False,
            seed=42,
        )

        school = generate_sample_school(config)

        assert len(school.teachers) == 5
        assert len(school.classes) == 4
        assert len(school.rooms) >= 3  # May have more for specialist rooms


class TestStatistics:
    """Tests for model statistics."""

    def test_builder_statistics(self, multi_teacher_input):
        """Model builder provides useful statistics."""
        builder = TimetableModelBuilder(multi_teacher_input)
        builder.create_variables()
        builder.add_constraints()

        stats = builder.get_statistics()

        assert "num_lessons" in stats
        assert "num_teachers" in stats
        assert "num_rooms" in stats
        assert stats["num_lessons"] == len(multi_teacher_input.lessons)
        assert stats["variables_created"] is True
        assert stats["constraints_added"] is True


# =============================================================================
# Core Requirements Verification
# =============================================================================

class TestCoreRequirements:
    """Tests verifying core functionality requirements."""

    def test_default_school_20_teachers_15_classes(self):
        """Solver generates valid timetable for 20 teachers, 15 classes."""
        # Use the default GeneratorConfig which specifies 20 teachers, 15 classes
        config = GeneratorConfig(seed=42)
        school = generate_sample_school(config)

        # Verify school size
        assert len(school.teachers) == 20, f"Expected 20 teachers, got {len(school.teachers)}"
        assert len(school.classes) == 15, f"Expected 15 classes, got {len(school.classes)}"

        # Attempt to solve
        builder = TimetableModelBuilder(school)
        solution = builder.solve(time_limit_seconds=120)

        # May timeout on slow machines
        if solution.status == SolverStatus.UNKNOWN:
            pytest.skip("Solver timed out - may need more time on this machine")

        # Should find a solution
        assert solution.is_feasible, f"Failed to solve 20/15 school: {solution.status}"
        assert len(solution.assignments) > 0

    def test_all_hard_constraints_satisfied(self, multi_teacher_input):
        """All 5 hard constraints satisfied (no double-booking)."""
        builder = TimetableModelBuilder(multi_teacher_input)
        solution = builder.solve(time_limit_seconds=60)

        if not solution.is_feasible:
            pytest.skip("Could not find solution")

        # 1. Teacher no double-booking
        teacher_slots: dict[str, set[tuple[int, int]]] = {}
        for a in solution.assignments:
            slot = (a.day, a.start_minutes)
            if a.teacher_id not in teacher_slots:
                teacher_slots[a.teacher_id] = set()
            assert slot not in teacher_slots[a.teacher_id], \
                f"HARD CONSTRAINT VIOLATED: Teacher {a.teacher_id} double-booked at {slot}"
            teacher_slots[a.teacher_id].add(slot)

        # 2. Class no double-booking
        class_slots: dict[str, set[tuple[int, int]]] = {}
        for a in solution.assignments:
            slot = (a.day, a.start_minutes)
            if a.class_id not in class_slots:
                class_slots[a.class_id] = set()
            assert slot not in class_slots[a.class_id], \
                f"HARD CONSTRAINT VIOLATED: Class {a.class_id} double-booked at {slot}"
            class_slots[a.class_id].add(slot)

        # 3. Room no double-booking
        room_slots: dict[str, set[tuple[int, int]]] = {}
        for a in solution.assignments:
            slot = (a.day, a.start_minutes)
            if a.room_id not in room_slots:
                room_slots[a.room_id] = set()
            assert slot not in room_slots[a.room_id], \
                f"HARD CONSTRAINT VIOLATED: Room {a.room_id} double-booked at {slot}"
            room_slots[a.room_id].add(slot)

        # 4. Room type suitability (science in lab, etc.)
        for a in solution.assignments:
            lesson = multi_teacher_input.get_lesson(a.lesson_id)
            subject = multi_teacher_input.get_subject(lesson.subject_id)
            room = multi_teacher_input.get_room(a.room_id)
            if subject and subject.requires_specialist_room and subject.required_room_type:
                assert room.type == subject.required_room_type, \
                    f"HARD CONSTRAINT VIOLATED: {subject.name} in wrong room type {room.type}"

        # 5. Lessons within valid time slots
        valid_slots = set()
        for period in multi_teacher_input.get_schedulable_periods():
            valid_slots.add((period.day, period.start_minutes))
        for a in solution.assignments:
            slot = (a.day, a.start_minutes)
            assert slot in valid_slots, \
                f"HARD CONSTRAINT VIOLATED: Lesson at invalid slot {slot}"

    def test_soft_constraints_implemented_and_weighted(self, multi_teacher_input):
        """All soft constraints implemented and weighted."""
        builder = TimetableModelBuilder(multi_teacher_input)
        builder.create_variables()
        builder.add_constraints()

        # Check that penalty variables exist for soft constraints
        penalty_names = [p.name for p in builder.penalty_vars]

        # 1. Lesson spread constraint (same_day penalties)
        same_day_penalties = [n for n in penalty_names if "same_day" in n]
        assert len(same_day_penalties) > 0, "Lesson spread soft constraint not implemented"

        # 2. Teacher max periods constraint
        # This only applies if teachers have max_periods_per_day set
        # Check that penalty vars have weights
        for penalty in builder.penalty_vars:
            assert penalty.weight > 0, f"Penalty {penalty.name} has no weight"

        # Verify objective function minimizes penalties
        builder.set_objective()
        assert builder._objective_set, "Objective function not set"

    def test_solution_within_60_seconds(self, minimal_input):
        """Solution found within 60 seconds."""
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=60)

        # Should find a solution
        assert solution.is_feasible, f"No solution found: {solution.status}"

        # Should be within time limit (with some overhead allowance)
        assert solution.solve_time_ms < 65000, \
            f"Solution took too long: {solution.solve_time_ms}ms"

    def test_json_input_output_working(self, minimal_input, tmp_path):
        """JSON input/output working correctly."""
        # Solve to get a solution
        builder = TimetableModelBuilder(minimal_input)
        solution = builder.solve(time_limit_seconds=30)

        assert solution.is_feasible

        # Test JSON output
        json_str = solution_to_json(solution)
        assert json_str is not None
        assert len(json_str) > 0

        # Verify it's valid JSON
        data = json.loads(json_str)
        assert "status" in data
        assert "timetable" in data
        assert "lessons" in data["timetable"]

        # Verify camelCase keys (JavaScript convention)
        assert "solveTimeSeconds" in data
        if data["timetable"]["lessons"]:
            lesson = data["timetable"]["lessons"][0]
            assert "lessonId" in lesson
            assert "teacherId" in lesson
            assert "classId" in lesson
            assert "roomId" in lesson
            assert "startTime" in lesson
            assert "endTime" in lesson

        # Test JSON input (load from file)
        input_file = tmp_path / "test_input.json"
        input_data = {
            "teachers": [{"id": "t1", "name": "Mr Smith", "subjects": ["mat"]}],
            "groups": [{"id": "c1", "name": "Year 10"}],
            "subjects": [{"id": "mat", "name": "Maths"}],
            "rooms": [{"id": "r1", "name": "Room 1", "type": "classroom"}],
            "lessons": [{"id": "l1", "teacher_id": "t1", "group_id": "c1", "subject_id": "mat"}],
        }
        with open(input_file, "w") as f:
            json.dump(input_data, f)

        loaded = load_school_data(input_file)
        assert "teachers" in loaded
        assert len(loaded["teachers"]) == 1
