"""
Sample data generator for testing the timetable solver.

This module generates realistic school timetable data for testing
purposes, with configurable size and complexity.

Usage:
    from solver.data.generator import generate_sample_school, generate_small_school

    # Generate with custom config
    school = generate_sample_school(GeneratorConfig(num_teachers=30))

    # Quick test data
    small_school = generate_small_school()

    # Stress test data
    large_school = generate_large_school()
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .models import (
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
    RoomRequirement,
)


# =============================================================================
# Name Data
# =============================================================================

FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "David", "William", "Richard", "Joseph",
    "Thomas", "Christopher", "Sarah", "Jessica", "Emily", "Ashley", "Amanda",
    "Elizabeth", "Jennifer", "Rachel", "Laura", "Nicole", "Emma", "Olivia",
    "Sophia", "Isabella", "Charlotte", "Daniel", "Matthew", "Andrew", "Joshua",
    "Alexander", "Benjamin", "Samuel", "Henry", "Sebastian", "Oliver", "Grace",
    "Hannah", "Abigail", "Natalie", "Victoria", "Lucy", "Sophie", "Mia", "Lily",
    "Evelyn", "Harper", "Amelia", "Eleanor", "Chloe", "Zoe", "Marcus", "Nathan",
    "Ryan", "Kevin", "Brian", "George", "Edward", "Patrick", "Simon", "Peter",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Evans", "Turner", "Phillips", "Collins", "Edwards", "Stewart",
    "Morris", "Murphy", "Cook", "Rogers", "Morgan", "Peterson", "Cooper", "Reed",
]


# =============================================================================
# Subject Definitions
# =============================================================================

CORE_SUBJECTS = [
    {"id": "eng", "name": "English", "code": "ENG", "color": "#3B82F6", "department": "Languages", "lessons_per_week": 5},
    {"id": "mat", "name": "Mathematics", "code": "MAT", "color": "#10B981", "department": "Mathematics", "lessons_per_week": 5},
    {"id": "sci", "name": "Science", "code": "SCI", "color": "#8B5CF6", "department": "Sciences", "lessons_per_week": 4,
     "requires_specialist_room": True, "required_room_type": RoomType.SCIENCE_LAB},
    {"id": "his", "name": "History", "code": "HIS", "color": "#F59E0B", "department": "Humanities", "lessons_per_week": 2},
    {"id": "geo", "name": "Geography", "code": "GEO", "color": "#06B6D4", "department": "Humanities", "lessons_per_week": 2},
]

SPECIALIST_SUBJECTS = [
    {"id": "pe", "name": "Physical Education", "code": "PE", "color": "#EF4444", "department": "Physical Education",
     "lessons_per_week": 2, "requires_specialist_room": True, "required_room_type": RoomType.GYM},
    {"id": "art", "name": "Art", "code": "ART", "color": "#EC4899", "department": "Creative Arts", "lessons_per_week": 1,
     "requires_specialist_room": True, "required_room_type": RoomType.ART_ROOM},
    {"id": "mus", "name": "Music", "code": "MUS", "color": "#A855F7", "department": "Creative Arts", "lessons_per_week": 1,
     "requires_specialist_room": True, "required_room_type": RoomType.MUSIC_ROOM},
    {"id": "dra", "name": "Drama", "code": "DRA", "color": "#F97316", "department": "Creative Arts", "lessons_per_week": 1},
    {"id": "cmp", "name": "Computing", "code": "CMP", "color": "#6366F1", "department": "Technology", "lessons_per_week": 1,
     "requires_specialist_room": True, "required_room_type": RoomType.COMPUTER_LAB},
    {"id": "fre", "name": "French", "code": "FRE", "color": "#14B8A6", "department": "Languages", "lessons_per_week": 2},
    {"id": "spa", "name": "Spanish", "code": "SPA", "color": "#F43F5E", "department": "Languages", "lessons_per_week": 2},
    {"id": "rel", "name": "Religious Studies", "code": "RS", "color": "#84CC16", "department": "Humanities", "lessons_per_week": 1},
]

# Unavailability reasons
UNAVAILABILITY_REASONS = [
    "Staff meeting",
    "Professional development",
    "Part-time schedule",
    "Administrative duties",
    "Department meeting",
    "External commitment",
    "Late start arrangement",
    "Early finish arrangement",
]


# =============================================================================
# Generator Configuration
# =============================================================================

@dataclass
class GeneratorConfig:
    """Configuration for data generation.

    Note: The default configuration is designed to create solvable problems.
    Key constraints for feasibility:
    - Total lesson instances must not exceed (periods_per_day * num_days * num_rooms)
    - No teacher should have more lessons than (periods_per_day * num_days)
    - Recommended utilization: 50-80% of available room-slots
    """
    # Entity counts
    num_teachers: int = 20
    num_classes: int = 15
    num_rooms: int = 15  # Increased from 8 to ensure feasibility
    lessons_per_class_per_week: int = 18  # Reduced from 25 to ensure feasibility

    # Teacher settings
    teacher_min_subjects: int = 2
    teacher_max_subjects: int = 4
    teacher_min_unavailability: int = 0
    teacher_max_unavailability: int = 3
    teacher_min_periods_per_day: int = 5
    teacher_max_periods_per_day: int = 7

    # Class settings
    min_students: int = 20
    max_students: int = 30
    year_groups: list[int] = field(default_factory=lambda: [7, 8, 9, 10, 11])

    # Room settings
    classroom_capacity_min: int = 25
    classroom_capacity_max: int = 32
    specialist_capacity_min: int = 20
    specialist_capacity_max: int = 28

    # Period settings
    num_days: int = 5
    periods_per_day: int = 6
    day_start_minutes: int = 540  # 9:00 AM
    period_duration: int = 60
    break_after_period: int = 2  # Break after period 2
    break_duration: int = 20
    lunch_after_period: int = 4  # Lunch after period 4
    lunch_duration: int = 60

    # Subject selection
    include_specialist_subjects: bool = True
    num_specialist_subjects: int = 6

    # Randomization
    seed: Optional[int] = None


# =============================================================================
# Generator Functions
# =============================================================================

def generate_sample_school(config: GeneratorConfig | None = None) -> TimetableInput:
    """
    Generate a sample school timetable input.

    Args:
        config: Generator configuration (uses defaults if None)

    Returns:
        TimetableInput with generated data
    """
    if config is None:
        config = GeneratorConfig()

    # Set random seed if provided (at start of generation for reproducibility)
    if config.seed is not None:
        random.seed(config.seed)

    # Generate all entities
    subjects = _generate_subjects(config)
    teachers = _generate_teachers(config, subjects)
    classes = _generate_classes(config)
    rooms = _generate_rooms(config, subjects)
    periods = _generate_periods(config)
    lessons = _generate_lessons(config, teachers, classes, subjects)

    return TimetableInput(
        config=SchoolConfig(
            school_name="Generated Test School",
            academic_year="2024-2025",
            num_days=config.num_days,
            default_lesson_duration=config.period_duration,
            day_start_minutes=config.day_start_minutes,
            day_end_minutes=_calculate_day_end(config),
        ),
        teachers=teachers,
        classes=classes,
        subjects=subjects,
        rooms=rooms,
        lessons=lessons,
        periods=periods,
    )


def generate_small_school(seed: int | None = None) -> TimetableInput:
    """
    Generate a small school for quick testing.

    - 10 teachers
    - 8 classes (2 per year group for years 7-10)
    - 8 rooms
    - ~120 lesson instances (~50% utilization)

    Args:
        seed: Random seed for reproducibility

    Returns:
        TimetableInput with small school data
    """
    config = GeneratorConfig(
        num_teachers=10,
        num_classes=8,
        num_rooms=8,  # Increased from 6 for feasibility
        lessons_per_class_per_week=15,  # Reduced from 20 for feasibility
        year_groups=[7, 8, 9, 10],
        num_specialist_subjects=4,
        seed=seed,
    )
    return generate_sample_school(config)


def generate_medium_school(seed: int | None = None) -> TimetableInput:
    """
    Generate a medium-sized school for standard testing.

    - 25 teachers
    - 20 classes (4 per year group)
    - 18 rooms
    - ~360 lesson instances (~67% utilization)

    Args:
        seed: Random seed for reproducibility

    Returns:
        TimetableInput with medium school data
    """
    config = GeneratorConfig(
        num_teachers=25,
        num_classes=20,
        num_rooms=18,  # Increased from 12 for feasibility
        lessons_per_class_per_week=18,  # Reduced from 25 for feasibility
        num_specialist_subjects=6,
        seed=seed,
    )
    return generate_sample_school(config)


def generate_large_school(seed: int | None = None) -> TimetableInput:
    """
    Generate a large school for stress testing.

    - 80 teachers
    - 60 classes (12 per year group)
    - 60 rooms
    - ~1080 lesson instances (~60% utilization)

    Args:
        seed: Random seed for reproducibility

    Returns:
        TimetableInput with large school data
    """
    config = GeneratorConfig(
        num_teachers=80,
        num_classes=60,
        num_rooms=60,  # Increased from 40 for feasibility
        lessons_per_class_per_week=18,  # Reduced from 25 for feasibility
        teacher_max_unavailability=2,  # Fewer constraints for feasibility
        num_specialist_subjects=8,
        seed=seed,
    )
    return generate_sample_school(config)


# =============================================================================
# Private Generator Helpers
# =============================================================================

def _generate_subjects(config: GeneratorConfig) -> list[Subject]:
    """Generate subjects based on configuration."""
    subjects = []

    # Always include core subjects
    for subj_data in CORE_SUBJECTS:
        subjects.append(_create_subject(subj_data))

    # Add specialist subjects
    if config.include_specialist_subjects:
        selected = random.sample(
            SPECIALIST_SUBJECTS,
            min(config.num_specialist_subjects, len(SPECIALIST_SUBJECTS))
        )
        for subj_data in selected:
            subjects.append(_create_subject(subj_data))

    return subjects


def _create_subject(data: dict) -> Subject:
    """Create a Subject from data dictionary."""
    return Subject(
        id=data["id"],
        name=data["name"],
        code=data.get("code"),
        color=data.get("color"),
        department=data.get("department"),
        requires_specialist_room=data.get("requires_specialist_room", False),
        required_room_type=data.get("required_room_type"),
    )


def _generate_teachers(config: GeneratorConfig, subjects: list[Subject]) -> list[Teacher]:
    """Generate teachers with assigned subjects."""
    teachers = []
    used_names = set()

    # Group subjects by type for assignment
    core_subject_ids = [s.id for s in subjects if s.id in [c["id"] for c in CORE_SUBJECTS]]
    specialist_subject_ids = [s.id for s in subjects if s.id not in core_subject_ids]

    for i in range(config.num_teachers):
        # Generate unique name
        while True:
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            full_name = f"{first} {last}"
            if full_name not in used_names:
                used_names.add(full_name)
                break

        # Create teacher code (initials + number if needed)
        code = f"{first[0]}{last[:2].upper()}"
        if any(t.code == code for t in teachers):
            code = f"{code}{i}"

        # Assign subjects (prefer grouping related subjects)
        num_subjects = random.randint(config.teacher_min_subjects, config.teacher_max_subjects)

        # Decide if teacher is primarily core or specialist
        if random.random() < 0.7 and core_subject_ids:
            # Core teacher
            teacher_subjects = _select_related_subjects(core_subject_ids, num_subjects)
        elif specialist_subject_ids:
            # Specialist teacher
            teacher_subjects = _select_related_subjects(specialist_subject_ids, num_subjects)
        else:
            teacher_subjects = random.sample(
                [s.id for s in subjects],
                min(num_subjects, len(subjects))
            )

        # Generate unavailability
        unavailability = _generate_unavailability(
            config.num_days,
            config.periods_per_day,
            config.day_start_minutes,
            config.period_duration,
            random.randint(config.teacher_min_unavailability, config.teacher_max_unavailability)
        )

        # Set max periods
        max_per_day = random.randint(config.teacher_min_periods_per_day, config.teacher_max_periods_per_day)
        max_per_week = max_per_day * config.num_days - random.randint(0, 5)

        teachers.append(Teacher(
            id=f"t{i+1}",
            name=full_name,
            code=code,
            subjects=teacher_subjects,
            availability=unavailability,
            max_periods_per_day=max_per_day,
            max_periods_per_week=max_per_week,
        ))

    return teachers


def _select_related_subjects(subject_ids: list[str], num: int) -> list[str]:
    """Select subjects, preferring related ones."""
    if len(subject_ids) <= num:
        return subject_ids.copy()

    # Start with one subject
    selected = [random.choice(subject_ids)]

    # Add more, preferring related subjects
    remaining = [s for s in subject_ids if s not in selected]
    while len(selected) < num and remaining:
        next_subj = random.choice(remaining)
        selected.append(next_subj)
        remaining.remove(next_subj)

    return selected


def _generate_unavailability(
    num_days: int,
    periods_per_day: int,
    day_start: int,
    period_duration: int,
    num_slots: int,
) -> list[Availability]:
    """Generate random unavailability slots."""
    unavailability = []

    for _ in range(num_slots):
        day = random.randint(0, num_days - 1)

        # Choose start period (avoiding overlap with existing)
        start_period = random.randint(0, periods_per_day - 1)
        num_periods = random.randint(1, min(3, periods_per_day - start_period))

        start_minutes = day_start + (start_period * period_duration)
        end_minutes = start_minutes + (num_periods * period_duration)

        unavailability.append(Availability(
            day=day,
            start_minutes=start_minutes,
            end_minutes=end_minutes,
            available=False,
            reason=random.choice(UNAVAILABILITY_REASONS),
        ))

    return unavailability


def _generate_classes(config: GeneratorConfig) -> list[StudentClass]:
    """Generate student classes."""
    classes = []
    class_index = 0

    # Distribute classes across year groups
    classes_per_year = config.num_classes // len(config.year_groups)
    extra = config.num_classes % len(config.year_groups)

    for year in config.year_groups:
        num_for_year = classes_per_year + (1 if extra > 0 else 0)
        extra -= 1

        for set_num in range(num_for_year):
            set_letter = chr(ord('A') + set_num)
            classes.append(StudentClass(
                id=f"{year}{set_letter.lower()}",
                name=f"Year {year}{set_letter}",
                year_group=year,
                student_count=random.randint(config.min_students, config.max_students),
            ))
            class_index += 1

    return classes


def _generate_rooms(config: GeneratorConfig, subjects: list[Subject]) -> list[Room]:
    """Generate rooms including specialist rooms."""
    rooms = []

    # Determine required specialist rooms from subjects
    required_room_types = set()
    for subj in subjects:
        if subj.required_room_type:
            required_room_types.add(subj.required_room_type)

    num_specialist_types = len(required_room_types)

    # We MUST create at least one room per required specialist type
    # Calculate remaining rooms for classrooms
    classroom_count = max(2, config.num_rooms - num_specialist_types)

    # Generate classrooms
    for i in range(classroom_count):
        floor = (i // 4) + 1
        room_num = 100 + (floor * 100) + (i % 4) + 1

        rooms.append(Room(
            id=f"r{room_num}",
            name=f"Room {room_num}",
            type=RoomType.CLASSROOM,
            capacity=random.randint(config.classroom_capacity_min, config.classroom_capacity_max),
            building="Main Building",
            floor=floor,
        ))

    # Generate specialist rooms (one per required type)
    room_type_counts: dict[RoomType, int] = {}

    for room_type in required_room_types:
        room_type_counts[room_type] = room_type_counts.get(room_type, 0) + 1
        count = room_type_counts[room_type]

        room_name = _get_specialist_room_name(room_type, count)
        room_id = _get_specialist_room_id(room_type, count)

        rooms.append(Room(
            id=room_id,
            name=room_name,
            type=room_type,
            capacity=random.randint(config.specialist_capacity_min, config.specialist_capacity_max),
            building=_get_specialist_building(room_type),
            floor=0,
            equipment=_get_room_equipment(room_type),
        ))

    return rooms


def _get_specialist_room_name(room_type: RoomType, count: int) -> str:
    """Get display name for specialist room."""
    type_names = {
        RoomType.SCIENCE_LAB: f"Science Lab {count}",
        RoomType.COMPUTER_LAB: f"Computer Suite {count}",
        RoomType.GYM: f"Gymnasium" if count == 1 else f"Sports Hall {count}",
        RoomType.SPORTS_HALL: f"Sports Hall {count}",
        RoomType.ART_ROOM: f"Art Studio {count}",
        RoomType.MUSIC_ROOM: f"Music Room {count}",
        RoomType.WORKSHOP: f"Workshop {count}",
        RoomType.LIBRARY: f"Library",
        RoomType.AUDITORIUM: f"Auditorium",
    }
    return type_names.get(room_type, f"{room_type.value.replace('_', ' ').title()} {count}")


def _get_specialist_room_id(room_type: RoomType, count: int) -> str:
    """Get ID for specialist room."""
    type_prefixes = {
        RoomType.SCIENCE_LAB: "sci",
        RoomType.COMPUTER_LAB: "cmp",
        RoomType.GYM: "gym",
        RoomType.SPORTS_HALL: "sph",
        RoomType.ART_ROOM: "art",
        RoomType.MUSIC_ROOM: "mus",
        RoomType.WORKSHOP: "wrk",
        RoomType.LIBRARY: "lib",
        RoomType.AUDITORIUM: "aud",
    }
    prefix = type_prefixes.get(room_type, room_type.value[:3])
    return f"{prefix}{count}"


def _get_specialist_building(room_type: RoomType) -> str:
    """Get building name for specialist room."""
    buildings = {
        RoomType.SCIENCE_LAB: "Science Block",
        RoomType.COMPUTER_LAB: "Technology Block",
        RoomType.GYM: "Sports Centre",
        RoomType.SPORTS_HALL: "Sports Centre",
        RoomType.ART_ROOM: "Creative Arts Block",
        RoomType.MUSIC_ROOM: "Creative Arts Block",
    }
    return buildings.get(room_type, "Main Building")


def _get_room_equipment(room_type: RoomType) -> list[str]:
    """Get equipment list for room type."""
    equipment = {
        RoomType.SCIENCE_LAB: ["bunsen_burners", "fume_hood", "microscopes", "safety_equipment"],
        RoomType.COMPUTER_LAB: ["computers", "projector", "interactive_whiteboard"],
        RoomType.GYM: ["mats", "balls", "climbing_equipment"],
        RoomType.ART_ROOM: ["easels", "kiln", "sinks", "storage"],
        RoomType.MUSIC_ROOM: ["piano", "percussion", "audio_equipment"],
    }
    return equipment.get(room_type, [])


def _generate_periods(config: GeneratorConfig) -> list[Period]:
    """Generate period structure for the week."""
    periods = []

    for day in range(config.num_days):
        current_time = config.day_start_minutes
        period_num = 1

        for p in range(config.periods_per_day):
            period_id = f"d{day}p{period_num}"
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            period_name = f"{day_names[day]} P{period_num}"

            periods.append(Period(
                id=period_id,
                name=period_name,
                day=day,
                start_minutes=current_time,
                end_minutes=current_time + config.period_duration,
                is_break=False,
                is_lunch=False,
            ))

            current_time += config.period_duration

            # Add break after specified period
            if period_num == config.break_after_period:
                current_time += config.break_duration

            # Add lunch after specified period
            if period_num == config.lunch_after_period:
                current_time += config.lunch_duration

            period_num += 1

    return periods


def _calculate_day_end(config: GeneratorConfig) -> int:
    """Calculate when the school day ends."""
    total_teaching = config.periods_per_day * config.period_duration
    total_breaks = config.break_duration + config.lunch_duration
    return config.day_start_minutes + total_teaching + total_breaks


def _generate_lessons(
    config: GeneratorConfig,
    teachers: list[Teacher],
    classes: list[StudentClass],
    subjects: list[Subject],
) -> list[Lesson]:
    """Generate lessons for all classes.

    This function ensures:
    - No teacher is assigned more lessons than available slots
    - Teacher loads are balanced across available teachers
    - Each class gets approximately lessons_per_class_per_week lessons
    """
    lessons = []
    lesson_id = 1

    # Maximum lessons a teacher can have (all available slots)
    max_teacher_slots = config.num_days * config.periods_per_day

    # Track teacher lesson counts to avoid overloading
    teacher_lesson_count: dict[str, int] = {t.id: 0 for t in teachers}

    # Build teacher lookup by subject
    teachers_by_subject: dict[str, list[Teacher]] = {}
    for teacher in teachers:
        for subj_id in teacher.subjects:
            if subj_id not in teachers_by_subject:
                teachers_by_subject[subj_id] = []
            teachers_by_subject[subj_id].append(teacher)

    # Subject data with lessons per week
    subject_lessons = {}
    for subj_data in CORE_SUBJECTS + SPECIALIST_SUBJECTS:
        subject_lessons[subj_data["id"]] = subj_data.get("lessons_per_week", 1)

    for cls in classes:
        total_lessons = 0
        target = config.lessons_per_class_per_week

        # Assign lessons for each subject
        for subject in subjects:
            # Get lessons per week for this subject
            lessons_per_week = subject_lessons.get(subject.id, 1)

            # Find teachers who can teach this subject
            available_teachers = teachers_by_subject.get(subject.id, [])
            if not available_teachers:
                continue

            # Filter teachers who have capacity for these lessons
            teachers_with_capacity = [
                t for t in available_teachers
                if teacher_lesson_count[t.id] + lessons_per_week <= max_teacher_slots
            ]

            if not teachers_with_capacity:
                # No teacher has capacity - skip this subject for this class
                continue

            # Select teacher with fewest current lessons (load balancing)
            teacher = min(teachers_with_capacity, key=lambda t: teacher_lesson_count[t.id])

            # Create room requirement if needed
            room_requirement = None
            if subject.required_room_type:
                room_requirement = RoomRequirement(
                    room_type=subject.required_room_type,
                )

            # Create lesson
            lessons.append(Lesson(
                id=f"l{lesson_id}",
                teacher_id=teacher.id,
                class_id=cls.id,
                subject_id=subject.id,
                duration_minutes=config.period_duration,
                lessons_per_week=lessons_per_week,
                room_requirement=room_requirement,
            ))

            # Update teacher lesson count
            teacher_lesson_count[teacher.id] += lessons_per_week

            total_lessons += lessons_per_week
            lesson_id += 1

            if total_lessons >= target:
                break

    return lessons


# =============================================================================
# Utility Functions
# =============================================================================

def save_generated_school(school: TimetableInput, filepath: str) -> None:
    """
    Save generated school data to a JSON file.

    Args:
        school: Generated TimetableInput
        filepath: Path to save JSON file
    """
    import json
    from pathlib import Path

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to JSON-friendly format
    data = _timetable_to_dict(school)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _timetable_to_dict(school: TimetableInput) -> dict:
    """Convert TimetableInput to dictionary for JSON serialization."""
    return {
        "schoolName": school.config.school_name,
        "academicYear": school.config.academic_year,
        "numDays": school.config.num_days,
        "defaultLessonDuration": school.config.default_lesson_duration,
        "dayStartMinutes": school.config.day_start_minutes,
        "dayEndMinutes": school.config.day_end_minutes,
        "teachers": [
            {
                "id": t.id,
                "name": t.name,
                "code": t.code,
                "subjects": t.subjects,
                "maxPeriodsPerDay": t.max_periods_per_day,
                "maxPeriodsPerWeek": t.max_periods_per_week,
                "availability": [
                    {
                        "day": a.day,
                        "startMinutes": a.start_minutes,
                        "endMinutes": a.end_minutes,
                        "available": a.available,
                        "reason": a.reason,
                    }
                    for a in t.availability
                ] if t.availability else [],
            }
            for t in school.teachers
        ],
        "classes": [
            {
                "id": c.id,
                "name": c.name,
                "yearGroup": c.year_group,
                "studentCount": c.student_count,
            }
            for c in school.classes
        ],
        "subjects": [
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "color": s.color,
                "department": s.department,
                "requiresSpecialistRoom": s.requires_specialist_room,
                "requiredRoomType": s.required_room_type.value if s.required_room_type else None,
            }
            for s in school.subjects
        ],
        "rooms": [
            {
                "id": r.id,
                "name": r.name,
                "type": r.type.value,
                "capacity": r.capacity,
                "building": r.building,
                "floor": r.floor,
                "equipment": r.equipment,
            }
            for r in school.rooms
        ],
        "lessons": [
            {
                "id": l.id,
                "teacherId": l.teacher_id,
                "classId": l.class_id,
                "subjectId": l.subject_id,
                "durationMinutes": l.duration_minutes,
                "lessonsPerWeek": l.lessons_per_week,
                "roomRequirement": {
                    "roomType": l.room_requirement.room_type.value if l.room_requirement and l.room_requirement.room_type else None,
                } if l.room_requirement else None,
            }
            for l in school.lessons
        ],
        "periods": [
            {
                "id": p.id,
                "name": p.name,
                "day": p.day,
                "startMinutes": p.start_minutes,
                "endMinutes": p.end_minutes,
                "isBreak": p.is_break,
                "isLunch": p.is_lunch,
            }
            for p in school.periods
        ],
    }


def get_generation_stats(school: TimetableInput) -> dict:
    """
    Get statistics about generated school data.

    Args:
        school: Generated TimetableInput

    Returns:
        Dictionary with statistics
    """
    total_lesson_instances = sum(l.lessons_per_week for l in school.lessons)
    schedulable_periods = len(school.get_schedulable_periods())
    total_slots = schedulable_periods * len(school.rooms)

    # Count subjects with requirements
    subjects_with_room_req = sum(1 for s in school.subjects if s.required_room_type)

    # Teacher workload
    teacher_workloads = {}
    for lesson in school.lessons:
        teacher_workloads[lesson.teacher_id] = teacher_workloads.get(lesson.teacher_id, 0) + lesson.lessons_per_week

    avg_workload = sum(teacher_workloads.values()) / len(teacher_workloads) if teacher_workloads else 0
    max_workload = max(teacher_workloads.values()) if teacher_workloads else 0

    # Feasibility checks
    utilization = total_lesson_instances / total_slots * 100 if total_slots > 0 else 0
    max_teacher_capacity = schedulable_periods  # A teacher can't exceed available periods
    is_feasible = (
        utilization <= 100 and  # Room capacity not exceeded
        max_workload <= max_teacher_capacity  # No teacher overloaded
    )

    return {
        "teachers": len(school.teachers),
        "classes": len(school.classes),
        "subjects": len(school.subjects),
        "rooms": len(school.rooms),
        "lessons": len(school.lessons),
        "lesson_instances": total_lesson_instances,
        "periods": len(school.periods),
        "schedulable_periods": schedulable_periods,
        "total_slots": total_slots,
        "utilization_percent": round(utilization, 1),
        "subjects_with_room_requirements": subjects_with_room_req,
        "average_teacher_workload": round(avg_workload, 1),
        "max_teacher_workload": max_workload,
        "max_teacher_capacity": max_teacher_capacity,
        "is_feasible": is_feasible,
    }
