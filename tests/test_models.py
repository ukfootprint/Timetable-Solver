"""Tests for Pydantic models."""

from __future__ import annotations

import pytest
from pathlib import Path

from solver.data.models import (
    Teacher,
    StudentClass,
    Subject,
    Room,
    Lesson,
    Period,
    Availability,
    RoomRequirement,
    RoomType,
    TimetableInput,
    SchoolConfig,
    load_timetable_from_json,
    minutes_to_time,
    time_to_minutes,
)


class TestTimeHelpers:
    """Tests for time conversion helpers."""

    def test_minutes_to_time(self):
        assert minutes_to_time(0) == "00:00"
        assert minutes_to_time(540) == "09:00"
        assert minutes_to_time(750) == "12:30"
        assert minutes_to_time(915) == "15:15"
        assert minutes_to_time(1439) == "23:59"

    def test_time_to_minutes(self):
        assert time_to_minutes("00:00") == 0
        assert time_to_minutes("09:00") == 540
        assert time_to_minutes("12:30") == 750
        assert time_to_minutes("15:15") == 915
        assert time_to_minutes("23:59") == 1439


class TestAvailability:
    """Tests for Availability model."""

    def test_valid_availability(self):
        avail = Availability(
            day=0,
            start_minutes=540,
            end_minutes=600,
            available=False,
            reason="Meeting"
        )
        assert avail.day == 0
        assert avail.start_minutes == 540
        assert avail.end_minutes == 600
        assert avail.available is False

    def test_invalid_time_range(self):
        with pytest.raises(ValueError, match="start_minutes.*must be less than.*end_minutes"):
            Availability(day=0, start_minutes=600, end_minutes=540, available=True)

    def test_equal_start_end(self):
        with pytest.raises(ValueError):
            Availability(day=0, start_minutes=540, end_minutes=540, available=True)


class TestTeacher:
    """Tests for Teacher model."""

    def test_minimal_teacher(self):
        teacher = Teacher(id="t1", name="John Smith")
        assert teacher.id == "t1"
        assert teacher.name == "John Smith"
        assert teacher.subjects == []
        assert teacher.availability == []

    def test_full_teacher(self):
        teacher = Teacher(
            id="t1",
            name="John Smith",
            code="JSM",
            email="j.smith@school.edu",
            subjects=["mat", "sci"],
            max_periods_per_day=5,
            max_periods_per_week=22,
            preferred_rooms=["r101"]
        )
        assert teacher.code == "JSM"
        assert len(teacher.subjects) == 2

    def test_invalid_max_periods(self):
        with pytest.raises(ValueError):
            Teacher(id="t1", name="Test", max_periods_per_day=0)

        with pytest.raises(ValueError):
            Teacher(id="t1", name="Test", max_periods_per_day=15)


class TestSubject:
    """Tests for Subject model."""

    def test_standard_subject(self):
        subject = Subject(id="mat", name="Mathematics")
        assert subject.requires_specialist_room is False
        assert subject.required_room_type is None

    def test_specialist_subject(self):
        subject = Subject(
            id="sci",
            name="Science",
            requires_specialist_room=True,
            required_room_type=RoomType.SCIENCE_LAB
        )
        assert subject.requires_specialist_room is True
        assert subject.required_room_type == RoomType.SCIENCE_LAB

    def test_valid_color(self):
        subject = Subject(id="mat", name="Maths", color="#3B82F6")
        assert subject.color == "#3B82F6"

    def test_invalid_color(self):
        with pytest.raises(ValueError):
            Subject(id="mat", name="Maths", color="red")

        with pytest.raises(ValueError):
            Subject(id="mat", name="Maths", color="#GGG")


class TestRoom:
    """Tests for Room model."""

    def test_classroom(self):
        room = Room(id="r101", name="Room 101", type=RoomType.CLASSROOM, capacity=30)
        assert room.type == RoomType.CLASSROOM
        assert room.accessible is True  # default

    def test_lab(self):
        room = Room(
            id="sci1",
            name="Science Lab 1",
            type=RoomType.SCIENCE_LAB,
            capacity=24,
            equipment=["bunsen_burners", "microscopes"]
        )
        assert len(room.equipment) == 2


class TestPeriod:
    """Tests for Period model."""

    def test_regular_period(self):
        period = Period(
            id="mon1",
            name="Period 1",
            day=0,
            start_minutes=540,
            end_minutes=600
        )
        assert period.duration_minutes == 60
        assert period.is_schedulable is True

    def test_break_period(self):
        period = Period(
            id="break",
            name="Break",
            day=0,
            start_minutes=660,
            end_minutes=680,
            is_break=True
        )
        assert period.is_schedulable is False

    def test_invalid_time_range(self):
        with pytest.raises(ValueError):
            Period(id="p1", name="Test", day=0, start_minutes=600, end_minutes=540)


class TestLesson:
    """Tests for Lesson model."""

    def test_minimal_lesson(self):
        lesson = Lesson(
            id="l1",
            teacher_id="t1",
            class_id="7a",
            subject_id="mat",
            lessons_per_week=5
        )
        assert lesson.duration_minutes == 60  # default
        assert lesson.split_allowed is True  # default

    def test_with_room_requirement(self):
        lesson = Lesson(
            id="l1",
            teacher_id="t1",
            class_id="7a",
            subject_id="sci",
            lessons_per_week=4,
            room_requirement=RoomRequirement(room_type=RoomType.SCIENCE_LAB)
        )
        assert lesson.room_requirement.room_type == RoomType.SCIENCE_LAB


class TestTimetableInput:
    """Tests for the main TimetableInput model."""

    @pytest.fixture
    def minimal_valid_input(self) -> dict:
        """Minimal valid input data with enough periods for feasibility."""
        return {
            "teachers": [{"id": "t1", "name": "Teacher 1"}],
            "classes": [{"id": "7a", "name": "Year 7A"}],
            "subjects": [{"id": "mat", "name": "Maths"}],
            "rooms": [{"id": "r1", "name": "Room 1", "type": "classroom"}],
            "lessons": [
                {"id": "l1", "teacher_id": "t1", "class_id": "7a", "subject_id": "mat", "lessons_per_week": 5}
            ],
            "periods": [
                {"id": "p1", "name": "Period 1", "day": 0, "start_minutes": 540, "end_minutes": 600},
                {"id": "p2", "name": "Period 2", "day": 1, "start_minutes": 540, "end_minutes": 600},
                {"id": "p3", "name": "Period 3", "day": 2, "start_minutes": 540, "end_minutes": 600},
                {"id": "p4", "name": "Period 4", "day": 3, "start_minutes": 540, "end_minutes": 600},
                {"id": "p5", "name": "Period 5", "day": 4, "start_minutes": 540, "end_minutes": 600},
            ]
        }

    def test_valid_input(self, minimal_valid_input):
        """Test that minimal valid input passes validation."""
        timetable = TimetableInput.model_validate(minimal_valid_input)
        assert len(timetable.teachers) == 1
        assert len(timetable.lessons) == 1

    def test_missing_teachers(self, minimal_valid_input):
        """Test validation fails without teachers."""
        del minimal_valid_input["teachers"]
        with pytest.raises(ValueError):
            TimetableInput.model_validate(minimal_valid_input)

    def test_invalid_teacher_reference(self, minimal_valid_input):
        """Test validation fails with invalid teacher reference."""
        minimal_valid_input["lessons"][0]["teacher_id"] = "nonexistent"
        with pytest.raises(ValueError, match="unknown teacher_id"):
            TimetableInput.model_validate(minimal_valid_input)

    def test_invalid_class_reference(self, minimal_valid_input):
        """Test validation fails with invalid class reference."""
        minimal_valid_input["lessons"][0]["class_id"] = "nonexistent"
        with pytest.raises(ValueError, match="unknown class_id"):
            TimetableInput.model_validate(minimal_valid_input)

    def test_invalid_subject_reference(self, minimal_valid_input):
        """Test validation fails with invalid subject reference."""
        minimal_valid_input["lessons"][0]["subject_id"] = "nonexistent"
        with pytest.raises(ValueError, match="unknown subject_id"):
            TimetableInput.model_validate(minimal_valid_input)

    def test_duplicate_teacher_ids(self, minimal_valid_input):
        """Test validation fails with duplicate IDs."""
        minimal_valid_input["teachers"].append({"id": "t1", "name": "Duplicate"})
        with pytest.raises(ValueError, match="Duplicate teacher ID"):
            TimetableInput.model_validate(minimal_valid_input)

    def test_teacher_overload_validation(self):
        """Test validation fails when teacher has more lessons than time slots."""
        # Only 1 period available, but teacher assigned 5 lessons
        data = {
            "teachers": [{"id": "t1", "name": "Teacher 1"}],
            "classes": [{"id": "7a", "name": "Year 7A"}],
            "subjects": [{"id": "mat", "name": "Maths"}],
            "rooms": [{"id": "r1", "name": "Room 1", "type": "classroom"}],
            "lessons": [
                {"id": "l1", "teacher_id": "t1", "class_id": "7a", "subject_id": "mat", "lessons_per_week": 5}
            ],
            "periods": [
                {"id": "p1", "name": "Period 1", "day": 0, "start_minutes": 540, "end_minutes": 600}
            ]
        }
        with pytest.raises(ValueError, match="infeasible"):
            TimetableInput.model_validate(data)

    def test_teacher_load_within_capacity(self):
        """Test validation passes when teacher load is within capacity."""
        # 5 periods available, teacher assigned 5 lessons - should pass
        data = {
            "teachers": [{"id": "t1", "name": "Teacher 1"}],
            "classes": [{"id": "7a", "name": "Year 7A"}],
            "subjects": [{"id": "mat", "name": "Maths"}],
            "rooms": [{"id": "r1", "name": "Room 1", "type": "classroom"}],
            "lessons": [
                {"id": "l1", "teacher_id": "t1", "class_id": "7a", "subject_id": "mat", "lessons_per_week": 5}
            ],
            "periods": [
                {"id": "p1", "name": "Period 1", "day": 0, "start_minutes": 540, "end_minutes": 600},
                {"id": "p2", "name": "Period 2", "day": 1, "start_minutes": 540, "end_minutes": 600},
                {"id": "p3", "name": "Period 3", "day": 2, "start_minutes": 540, "end_minutes": 600},
                {"id": "p4", "name": "Period 4", "day": 3, "start_minutes": 540, "end_minutes": 600},
                {"id": "p5", "name": "Period 5", "day": 4, "start_minutes": 540, "end_minutes": 600},
            ]
        }
        # Should not raise
        timetable = TimetableInput.model_validate(data)
        assert len(timetable.lessons) == 1

    def test_lookup_methods(self, minimal_valid_input):
        """Test entity lookup methods."""
        timetable = TimetableInput.model_validate(minimal_valid_input)

        assert timetable.get_teacher("t1") is not None
        assert timetable.get_teacher("nonexistent") is None
        assert timetable.get_class("7a") is not None
        assert timetable.get_subject("mat") is not None

    def test_query_methods(self, minimal_valid_input):
        """Test query methods."""
        timetable = TimetableInput.model_validate(minimal_valid_input)

        lessons = timetable.get_teacher_lessons("t1")
        assert len(lessons) == 1

        lessons = timetable.get_class_lessons("7a")
        assert len(lessons) == 1

    def test_summary(self, minimal_valid_input):
        """Test summary generation."""
        timetable = TimetableInput.model_validate(minimal_valid_input)
        summary = timetable.summary()

        assert summary["teachers"] == 1
        assert summary["lessons"] == 1
        assert summary["total_lessons_per_week"] == 5


class TestLoadFromJson:
    """Tests for JSON loading."""

    def test_load_sample_file(self):
        """Test loading the sample timetable file."""
        sample_path = Path(__file__).parent.parent / "data" / "sample-timetable.json"

        if not sample_path.exists():
            pytest.skip("Sample file not found")

        timetable = load_timetable_from_json(str(sample_path))

        assert timetable.config.school_name == "Westbrook Academy"
        assert len(timetable.teachers) == 8
        assert len(timetable.classes) == 4
        assert len(timetable.subjects) == 8
        assert len(timetable.rooms) == 11
        assert len(timetable.lessons) == 16
        assert len(timetable.periods) == 40

    def test_load_nonexistent_file(self):
        """Test loading a nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            load_timetable_from_json("/nonexistent/path.json")
