"""
Pydantic models for the AI Timetabler data model.

Mirrors the TypeScript schemas in schema/timetable.types.ts.

Time conventions:
- Time is represented as minutes from midnight (0-1439)
- Days are 0-4 (Monday-Friday)

Example times:
- 9:00 AM = 540
- 12:30 PM = 750
- 3:15 PM = 915
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# =============================================================================
# Constants and Enums
# =============================================================================

class Day(int, Enum):
    """Day of week: 0=Monday through 4=Friday."""
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4


class RoomType(str, Enum):
    """Type of room/facility."""
    CLASSROOM = "classroom"
    SCIENCE_LAB = "science_lab"
    COMPUTER_LAB = "computer_lab"
    GYM = "gym"
    SPORTS_HALL = "sports_hall"
    ART_ROOM = "art_room"
    MUSIC_ROOM = "music_room"
    WORKSHOP = "workshop"
    LIBRARY = "library"
    AUDITORIUM = "auditorium"
    OTHER = "other"


# Type aliases for documentation
MinutesFromMidnight = Annotated[int, Field(ge=0, le=1439, description="Time as minutes from midnight")]
DayIndex = Annotated[int, Field(ge=0, le=4, description="Day of week (0=Monday, 4=Friday)")]


# =============================================================================
# Helper Functions
# =============================================================================

def minutes_to_time(minutes: int) -> str:
    """Convert minutes from midnight to HH:MM format."""
    h, m = divmod(minutes, 60)
    return f"{h:02d}:{m:02d}"


def time_to_minutes(time_str: str) -> int:
    """Convert HH:MM format to minutes from midnight."""
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def day_name(day: int) -> str:
    """Get day name from index."""
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    return names[day] if 0 <= day <= 4 else f"Day {day}"


# =============================================================================
# Core Entity Models
# =============================================================================

class Availability(BaseModel):
    """
    Availability window for a teacher, class, or room.
    Represents a time range on a specific day.
    """
    model_config = ConfigDict(extra="forbid")

    day: DayIndex = Field(description="Day of week (0-4)")
    start_minutes: MinutesFromMidnight = Field(description="Start time in minutes from midnight")
    end_minutes: MinutesFromMidnight = Field(description="End time in minutes from midnight")
    available: bool = Field(default=True, description="Whether available during this window")
    reason: Optional[str] = Field(default=None, description="Reason for unavailability")

    @model_validator(mode="after")
    def validate_time_range(self) -> "Availability":
        """Ensure start time is before end time."""
        if self.start_minutes >= self.end_minutes:
            raise ValueError(
                f"start_minutes ({self.start_minutes}) must be less than "
                f"end_minutes ({self.end_minutes})"
            )
        return self

    def __str__(self) -> str:
        status = "available" if self.available else "unavailable"
        return (
            f"{day_name(self.day)} {minutes_to_time(self.start_minutes)}-"
            f"{minutes_to_time(self.end_minutes)} ({status})"
        )


class Teacher(BaseModel):
    """Teacher entity."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="Unique identifier")
    name: str = Field(min_length=1, description="Full name")
    code: Optional[str] = Field(default=None, max_length=5, description="Short code (e.g., initials)")
    email: Optional[str] = Field(default=None, description="Email address")
    subjects: list[str] = Field(default_factory=list, description="Subject IDs this teacher can teach")
    availability: list[Availability] = Field(default_factory=list, description="Availability windows")
    max_periods_per_day: Optional[int] = Field(default=None, ge=1, le=12, description="Max periods per day")
    max_periods_per_week: Optional[int] = Field(default=None, ge=1, le=60, description="Max periods per week")
    preferred_rooms: list[str] = Field(default_factory=list, description="Preferred room IDs")

    def __str__(self) -> str:
        return f"{self.name} ({self.code or self.id})"


class StudentClass(BaseModel):
    """
    Student class/group.
    Named 'StudentClass' to avoid collision with Python's 'class' keyword.
    """
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="Unique identifier")
    name: str = Field(min_length=1, description="Class name (e.g., 'Year 7A')")
    year_group: Optional[int] = Field(default=None, ge=1, le=13, description="Year/grade level")
    student_count: Optional[int] = Field(default=None, ge=1, description="Number of students")
    availability: list[Availability] = Field(default_factory=list, description="Class availability")
    home_room: Optional[str] = Field(default=None, description="Home room ID")

    def __str__(self) -> str:
        return self.name


class Subject(BaseModel):
    """Subject/course."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="Unique identifier")
    name: str = Field(min_length=1, description="Subject name")
    code: Optional[str] = Field(default=None, max_length=10, description="Short code")
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color")
    requires_specialist_room: bool = Field(default=False, description="Needs specialist room")
    required_room_type: Optional[RoomType] = Field(default=None, description="Required room type")
    department: Optional[str] = Field(default=None, description="Academic department")

    @model_validator(mode="after")
    def validate_room_requirement(self) -> "Subject":
        """If requires_specialist_room is True, required_room_type should be set."""
        if self.requires_specialist_room and not self.required_room_type:
            # This is a warning, not an error - we allow it but it's unusual
            pass
        return self

    def __str__(self) -> str:
        return f"{self.name} ({self.code or self.id})"


class Room(BaseModel):
    """Room/facility."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="Unique identifier")
    name: str = Field(min_length=1, description="Room name/number")
    type: RoomType = Field(description="Type of room")
    capacity: Optional[int] = Field(default=None, ge=1, description="Max capacity")
    building: Optional[str] = Field(default=None, description="Building name")
    floor: Optional[int] = Field(default=None, description="Floor number")
    availability: list[Availability] = Field(default_factory=list, description="Room availability")
    equipment: list[str] = Field(default_factory=list, description="Available equipment")
    accessible: bool = Field(default=True, description="Wheelchair accessible")

    def __str__(self) -> str:
        return f"{self.name} ({self.type.value})"


class RoomRequirement(BaseModel):
    """Room requirements for a lesson."""
    model_config = ConfigDict(extra="forbid")

    room_type: Optional[RoomType] = Field(default=None, description="Required room type")
    min_capacity: Optional[int] = Field(default=None, ge=1, description="Minimum capacity")
    preferred_rooms: list[str] = Field(default_factory=list, description="Preferred room IDs")
    excluded_rooms: list[str] = Field(default_factory=list, description="Excluded room IDs")
    requires_equipment: list[str] = Field(default_factory=list, description="Required equipment")


class FixedSlot(BaseModel):
    """Fixed time slot assignment."""
    model_config = ConfigDict(extra="forbid")

    day: DayIndex = Field(description="Day of week")
    period_id: str = Field(description="Period ID")


class Lesson(BaseModel):
    """Lesson to be scheduled."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="Unique identifier")
    teacher_id: str = Field(description="Teacher ID")
    class_id: str = Field(description="Class/student group ID")
    subject_id: str = Field(description="Subject ID")
    duration_minutes: int = Field(default=60, ge=15, le=240, description="Duration in minutes")
    lessons_per_week: int = Field(ge=1, le=20, description="Occurrences per week")
    room_requirement: Optional[RoomRequirement] = Field(default=None, description="Room requirements")
    split_allowed: bool = Field(default=True, description="Can split across days")
    consecutive_preferred: bool = Field(default=False, description="Prefer double lessons")
    fixed_slots: list[FixedSlot] = Field(default_factory=list, description="Pre-fixed slots")

    def __str__(self) -> str:
        return f"Lesson {self.id}: {self.subject_id} for {self.class_id}"


class Period(BaseModel):
    """Period in the school day schedule."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="Unique identifier")
    name: str = Field(description="Display name (e.g., 'Period 1')")
    start_minutes: MinutesFromMidnight = Field(description="Start time")
    end_minutes: MinutesFromMidnight = Field(description="End time")
    day: DayIndex = Field(description="Day of week")
    is_break: bool = Field(default=False, description="Is break period")
    is_lunch: bool = Field(default=False, description="Is lunch period")

    @model_validator(mode="after")
    def validate_time_range(self) -> "Period":
        """Ensure start time is before end time."""
        if self.start_minutes >= self.end_minutes:
            raise ValueError(
                f"start_minutes ({self.start_minutes}) must be less than "
                f"end_minutes ({self.end_minutes})"
            )
        return self

    @property
    def duration_minutes(self) -> int:
        """Calculate period duration."""
        return self.end_minutes - self.start_minutes

    @property
    def is_schedulable(self) -> bool:
        """Whether lessons can be scheduled in this period."""
        return not self.is_break and not self.is_lunch

    def __str__(self) -> str:
        time_range = f"{minutes_to_time(self.start_minutes)}-{minutes_to_time(self.end_minutes)}"
        return f"{self.name} ({day_name(self.day)} {time_range})"


# =============================================================================
# Configuration Models
# =============================================================================

class SchoolConfig(BaseModel):
    """School-wide configuration settings."""
    model_config = ConfigDict(extra="forbid")

    school_name: Optional[str] = Field(default=None, description="School name")
    academic_year: Optional[str] = Field(default=None, description="Academic year")
    num_days: int = Field(default=5, ge=1, le=7, description="Days per week")
    default_lesson_duration: int = Field(default=60, ge=15, le=240, description="Default lesson duration")
    day_start_minutes: MinutesFromMidnight = Field(default=540, description="School day start (default 9:00)")
    day_end_minutes: MinutesFromMidnight = Field(default=960, description="School day end (default 16:00)")

    @model_validator(mode="after")
    def validate_day_times(self) -> "SchoolConfig":
        """Ensure school day start is before end."""
        if self.day_start_minutes >= self.day_end_minutes:
            raise ValueError(
                f"day_start_minutes ({self.day_start_minutes}) must be less than "
                f"day_end_minutes ({self.day_end_minutes})"
            )
        return self


# =============================================================================
# Constraint Models
# =============================================================================

class ConstraintBase(BaseModel):
    """Base class for all constraints."""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(default=True, description="Whether this constraint is active")
    weight: int = Field(default=1, ge=0, le=100, description="Priority weight (0=hard, 1-100=soft)")
    description: Optional[str] = Field(default=None, description="Human-readable description")

    @property
    def is_hard(self) -> bool:
        """Hard constraints must be satisfied (weight=0)."""
        return self.weight == 0


class TeacherMaxPeriodsConstraint(ConstraintBase):
    """Constraint on teacher's maximum periods per day/week."""
    teacher_id: str = Field(description="Teacher ID")
    max_per_day: Optional[int] = Field(default=None, ge=1, description="Max periods per day")
    max_per_week: Optional[int] = Field(default=None, ge=1, description="Max periods per week")


class RoomTypeConstraint(ConstraintBase):
    """Constraint requiring specific room type for a subject."""
    subject_id: str = Field(description="Subject ID")
    required_room_type: RoomType = Field(description="Required room type")


class AvailabilityConstraint(ConstraintBase):
    """Constraint on entity availability."""
    entity_type: str = Field(description="Entity type: 'teacher', 'class', or 'room'")
    entity_id: str = Field(description="Entity ID")
    availability: list[Availability] = Field(description="Availability windows")


class ConsecutiveLessonsConstraint(ConstraintBase):
    """Constraint for consecutive lesson preferences."""
    lesson_id: str = Field(description="Lesson ID")
    prefer_consecutive: bool = Field(default=True, description="Whether to prefer consecutive slots")
    max_consecutive: int = Field(default=2, ge=1, le=4, description="Maximum consecutive periods")


class LessonSpreadConstraint(ConstraintBase):
    """Constraint to spread lessons across the week."""
    lesson_id: str = Field(description="Lesson ID")
    min_days_between: int = Field(default=1, ge=0, le=4, description="Minimum days between occurrences")


class RoomCapacityConstraint(ConstraintBase):
    """Constraint ensuring room has sufficient capacity."""
    class_id: str = Field(description="Class ID")
    min_capacity: int = Field(ge=1, description="Required minimum capacity")


class TeacherPreferenceConstraint(ConstraintBase):
    """Soft constraint for teacher time preferences."""
    teacher_id: str = Field(description="Teacher ID")
    preferred_periods: list[str] = Field(default_factory=list, description="Preferred period IDs")
    avoided_periods: list[str] = Field(default_factory=list, description="Periods to avoid")


class ConstraintSet(BaseModel):
    """Collection of all constraints for the timetable."""
    model_config = ConfigDict(extra="forbid")

    teacher_max_periods: list[TeacherMaxPeriodsConstraint] = Field(default_factory=list)
    room_type: list[RoomTypeConstraint] = Field(default_factory=list)
    availability: list[AvailabilityConstraint] = Field(default_factory=list)
    consecutive_lessons: list[ConsecutiveLessonsConstraint] = Field(default_factory=list)
    lesson_spread: list[LessonSpreadConstraint] = Field(default_factory=list)
    room_capacity: list[RoomCapacityConstraint] = Field(default_factory=list)
    teacher_preference: list[TeacherPreferenceConstraint] = Field(default_factory=list)

    @property
    def all_constraints(self) -> list[ConstraintBase]:
        """Get all constraints as a flat list."""
        return (
            self.teacher_max_periods +
            self.room_type +
            self.availability +
            self.consecutive_lessons +
            self.lesson_spread +
            self.room_capacity +
            self.teacher_preference
        )

    @property
    def hard_constraints(self) -> list[ConstraintBase]:
        """Get only hard constraints."""
        return [c for c in self.all_constraints if c.is_hard]

    @property
    def soft_constraints(self) -> list[ConstraintBase]:
        """Get only soft constraints."""
        return [c for c in self.all_constraints if not c.is_hard]


# =============================================================================
# Main Input Model
# =============================================================================

class TimetableInput(BaseModel):
    """
    Complete timetable input data.
    This is the main model for loading and validating timetable data.
    """
    model_config = ConfigDict(extra="forbid")

    # Configuration
    config: SchoolConfig = Field(default_factory=SchoolConfig, description="School configuration")

    # Core entities
    teachers: list[Teacher] = Field(min_length=1, description="Teachers")
    classes: list[StudentClass] = Field(min_length=1, description="Student classes")
    subjects: list[Subject] = Field(min_length=1, description="Subjects")
    rooms: list[Room] = Field(min_length=1, description="Rooms")
    lessons: list[Lesson] = Field(min_length=1, description="Lessons to schedule")
    periods: list[Period] = Field(min_length=1, description="Period structure")

    # Optional constraints (beyond what's embedded in entities)
    constraints: ConstraintSet = Field(default_factory=ConstraintSet, description="Additional constraints")

    # Lookup caches (populated after validation)
    _teacher_map: dict[str, Teacher] = {}
    _class_map: dict[str, StudentClass] = {}
    _subject_map: dict[str, Subject] = {}
    _room_map: dict[str, Room] = {}
    _lesson_map: dict[str, Lesson] = {}
    _period_map: dict[str, Period] = {}

    def model_post_init(self, __context: Any) -> None:
        """Build lookup maps after model initialization."""
        self._teacher_map = {t.id: t for t in self.teachers}
        self._class_map = {c.id: c for c in self.classes}
        self._subject_map = {s.id: s for s in self.subjects}
        self._room_map = {r.id: r for r in self.rooms}
        self._lesson_map = {l.id: l for l in self.lessons}
        self._period_map = {p.id: p for p in self.periods}

    @model_validator(mode="after")
    def validate_references(self) -> "TimetableInput":
        """Validate all cross-entity references."""
        errors: list[str] = []

        # Build ID sets
        teacher_ids = {t.id for t in self.teachers}
        class_ids = {c.id for c in self.classes}
        subject_ids = {s.id for s in self.subjects}
        room_ids = {r.id for r in self.rooms}
        period_ids = {p.id for p in self.periods}

        # Validate lessons
        for lesson in self.lessons:
            if lesson.teacher_id not in teacher_ids:
                errors.append(f"Lesson {lesson.id}: unknown teacher_id '{lesson.teacher_id}'")
            if lesson.class_id not in class_ids:
                errors.append(f"Lesson {lesson.id}: unknown class_id '{lesson.class_id}'")
            if lesson.subject_id not in subject_ids:
                errors.append(f"Lesson {lesson.id}: unknown subject_id '{lesson.subject_id}'")

            # Validate room requirement references
            if lesson.room_requirement:
                for room_id in lesson.room_requirement.preferred_rooms:
                    if room_id not in room_ids:
                        errors.append(f"Lesson {lesson.id}: unknown preferred_room '{room_id}'")
                for room_id in lesson.room_requirement.excluded_rooms:
                    if room_id not in room_ids:
                        errors.append(f"Lesson {lesson.id}: unknown excluded_room '{room_id}'")

            # Validate fixed slots
            for slot in lesson.fixed_slots:
                if slot.period_id not in period_ids:
                    errors.append(f"Lesson {lesson.id}: unknown period_id '{slot.period_id}' in fixed_slots")

        # Validate teacher references
        for teacher in self.teachers:
            for subject_id in teacher.subjects:
                if subject_id not in subject_ids:
                    errors.append(f"Teacher {teacher.id}: unknown subject '{subject_id}'")
            for room_id in teacher.preferred_rooms:
                if room_id not in room_ids:
                    errors.append(f"Teacher {teacher.id}: unknown preferred_room '{room_id}'")

        # Validate class references
        for cls in self.classes:
            if cls.home_room and cls.home_room not in room_ids:
                errors.append(f"Class {cls.id}: unknown home_room '{cls.home_room}'")

        # Validate constraint references
        for constraint in self.constraints.teacher_max_periods:
            if constraint.teacher_id not in teacher_ids:
                errors.append(f"TeacherMaxPeriodsConstraint: unknown teacher_id '{constraint.teacher_id}'")

        for constraint in self.constraints.room_type:
            if constraint.subject_id not in subject_ids:
                errors.append(f"RoomTypeConstraint: unknown subject_id '{constraint.subject_id}'")

        for constraint in self.constraints.consecutive_lessons:
            if constraint.lesson_id not in {l.id for l in self.lessons}:
                errors.append(f"ConsecutiveLessonsConstraint: unknown lesson_id '{constraint.lesson_id}'")

        if errors:
            raise ValueError(f"Reference validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

        return self

    @model_validator(mode="after")
    def validate_no_duplicate_ids(self) -> "TimetableInput":
        """Ensure no duplicate IDs within each entity type."""
        errors: list[str] = []

        def check_duplicates(items: list, entity_name: str) -> None:
            seen: set[str] = set()
            for item in items:
                if item.id in seen:
                    errors.append(f"Duplicate {entity_name} ID: '{item.id}'")
                seen.add(item.id)

        check_duplicates(self.teachers, "teacher")
        check_duplicates(self.classes, "class")
        check_duplicates(self.subjects, "subject")
        check_duplicates(self.rooms, "room")
        check_duplicates(self.lessons, "lesson")
        check_duplicates(self.periods, "period")

        if errors:
            raise ValueError(f"Duplicate ID validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

        return self

    @model_validator(mode="after")
    def validate_logical_consistency(self) -> "TimetableInput":
        """Validate logical consistency of the data."""
        errors: list[str] = []
        warnings: list[str] = []

        # Check if specialist room subjects have matching rooms
        for subject in self.subjects:
            if subject.requires_specialist_room and subject.required_room_type:
                matching_rooms = [r for r in self.rooms if r.type == subject.required_room_type]
                if not matching_rooms:
                    errors.append(
                        f"Subject '{subject.name}' requires {subject.required_room_type.value} "
                        f"but no such room exists"
                    )

        # Check teacher workload against limits
        schedulable_periods = [p for p in self.periods if p.is_schedulable]
        max_teacher_capacity = len(schedulable_periods)  # Max periods any teacher can have

        for teacher in self.teachers:
            teacher_lessons = [l for l in self.lessons if l.teacher_id == teacher.id]
            total_periods = sum(l.lessons_per_week for l in teacher_lessons)

            # Check physical impossibility (more lessons than time slots)
            if total_periods > max_teacher_capacity:
                errors.append(
                    f"Teacher '{teacher.name}' has {total_periods} lessons but only "
                    f"{max_teacher_capacity} time slots exist (infeasible)"
                )

            # Check against teacher's preference (soft limit)
            elif teacher.max_periods_per_week and total_periods > teacher.max_periods_per_week:
                warnings.append(
                    f"Teacher '{teacher.name}' has {total_periods} periods but max is "
                    f"{teacher.max_periods_per_week}"
                )

        # Check schedulable slots vs lessons
        total_lessons = sum(l.lessons_per_week for l in self.lessons)
        total_slots = len(schedulable_periods) * len(self.rooms)

        if total_lessons > total_slots:
            warnings.append(
                f"Total lessons ({total_lessons}) exceeds available room-slots ({total_slots})"
            )

        # For now, we only raise on errors, not warnings
        # Warnings could be logged or returned separately
        if errors:
            raise ValueError(f"Logical consistency validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

        return self

    # -------------------------------------------------------------------------
    # Lookup Methods
    # -------------------------------------------------------------------------

    def get_teacher(self, teacher_id: str) -> Optional[Teacher]:
        """Get teacher by ID."""
        return self._teacher_map.get(teacher_id)

    def get_class(self, class_id: str) -> Optional[StudentClass]:
        """Get class by ID."""
        return self._class_map.get(class_id)

    def get_subject(self, subject_id: str) -> Optional[Subject]:
        """Get subject by ID."""
        return self._subject_map.get(subject_id)

    def get_room(self, room_id: str) -> Optional[Room]:
        """Get room by ID."""
        return self._room_map.get(room_id)

    def get_lesson(self, lesson_id: str) -> Optional[Lesson]:
        """Get lesson by ID."""
        return self._lesson_map.get(lesson_id)

    def get_period(self, period_id: str) -> Optional[Period]:
        """Get period by ID."""
        return self._period_map.get(period_id)

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def get_teacher_lessons(self, teacher_id: str) -> list[Lesson]:
        """Get all lessons for a teacher."""
        return [l for l in self.lessons if l.teacher_id == teacher_id]

    def get_class_lessons(self, class_id: str) -> list[Lesson]:
        """Get all lessons for a class."""
        return [l for l in self.lessons if l.class_id == class_id]

    def get_subject_lessons(self, subject_id: str) -> list[Lesson]:
        """Get all lessons for a subject."""
        return [l for l in self.lessons if l.subject_id == subject_id]

    def get_rooms_by_type(self, room_type: RoomType) -> list[Room]:
        """Get all rooms of a specific type."""
        return [r for r in self.rooms if r.type == room_type]

    def get_schedulable_periods(self) -> list[Period]:
        """Get periods that can have lessons scheduled."""
        return [p for p in self.periods if p.is_schedulable]

    def get_periods_by_day(self, day: int) -> list[Period]:
        """Get all periods for a specific day."""
        return sorted(
            [p for p in self.periods if p.day == day],
            key=lambda p: p.start_minutes
        )

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    @property
    def total_lessons_per_week(self) -> int:
        """Total number of lesson instances per week."""
        return sum(l.lessons_per_week for l in self.lessons)

    @property
    def total_schedulable_slots(self) -> int:
        """Total available room-period slots."""
        return len(self.get_schedulable_periods()) * len(self.rooms)

    def summary(self) -> dict[str, Any]:
        """Get a summary of the timetable data."""
        return {
            "school_name": self.config.school_name,
            "academic_year": self.config.academic_year,
            "teachers": len(self.teachers),
            "classes": len(self.classes),
            "subjects": len(self.subjects),
            "rooms": len(self.rooms),
            "lessons": len(self.lessons),
            "periods": len(self.periods),
            "schedulable_periods": len(self.get_schedulable_periods()),
            "total_lessons_per_week": self.total_lessons_per_week,
            "total_schedulable_slots": self.total_schedulable_slots,
        }


# =============================================================================
# JSON Loading Helper
# =============================================================================

def load_timetable_from_json(path: str) -> TimetableInput:
    """
    Load and validate timetable data from a JSON file.

    The JSON structure should match the TypeScript schema, with snake_case
    field names (Pydantic handles the conversion).

    Args:
        path: Path to the JSON file

    Returns:
        Validated TimetableInput model

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If invalid JSON
        pydantic.ValidationError: If validation fails
    """
    import json
    from pathlib import Path

    json_path = Path(path)
    with open(json_path) as f:
        data = json.load(f)

    # Convert from TypeScript camelCase to Python snake_case if needed
    # The JSON sample uses camelCase, so we need to handle both
    converted_data = _convert_keys_to_snake_case(data)

    # Move top-level config fields into config object
    config_fields = ["school_name", "academic_year", "num_days",
                     "default_lesson_duration", "day_start_minutes", "day_end_minutes"]
    config_data = {}
    for field in config_fields:
        if field in converted_data:
            config_data[field] = converted_data.pop(field)

    if config_data:
        converted_data["config"] = config_data

    return TimetableInput.model_validate(converted_data)


def _convert_keys_to_snake_case(obj: Any) -> Any:
    """Recursively convert dictionary keys from camelCase to snake_case."""
    import re

    def to_snake_case(name: str) -> str:
        # Handle common patterns
        name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
        name = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', name)
        return name.lower()

    if isinstance(obj, dict):
        return {to_snake_case(k): _convert_keys_to_snake_case(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_keys_to_snake_case(item) for item in obj]
    else:
        return obj
