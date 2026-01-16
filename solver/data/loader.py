"""Load and validate school data from JSON files."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Union


class DataValidationError(Exception):
    """Raised when school data fails validation."""
    pass


def load_school_data(path: Union[str, Path]) -> dict:
    """
    Load school data from a JSON file.

    Args:
        path: Path to the JSON file

    Returns:
        Validated school data dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file isn't valid JSON
        DataValidationError: If the data fails validation
    """
    path = Path(path)

    with open(path) as f:
        data = json.load(f)

    validate_school_data(data)
    return data


def validate_school_data(data: dict) -> None:
    """
    Validate school data structure and references.

    Args:
        data: School data dictionary

    Raises:
        DataValidationError: If validation fails
    """
    errors = []

    # Required top-level fields
    required_fields = ["lessons", "teachers", "rooms", "groups", "subjects"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        raise DataValidationError("; ".join(errors))

    # Build ID sets for reference validation
    teacher_ids = {t["id"] for t in data["teachers"]}
    room_ids = {r["id"] for r in data["rooms"]}
    group_ids = {g["id"] for g in data["groups"]}
    subject_ids = {s["id"] for s in data["subjects"]}

    # Validate lessons
    for i, lesson in enumerate(data["lessons"]):
        if "id" not in lesson:
            errors.append(f"Lesson {i} missing 'id'")
            continue

        lesson_id = lesson["id"]

        if "teacher_id" not in lesson:
            errors.append(f"Lesson {lesson_id} missing 'teacher_id'")
        elif lesson["teacher_id"] not in teacher_ids:
            errors.append(f"Lesson {lesson_id} references unknown teacher: {lesson['teacher_id']}")

        if "group_id" not in lesson:
            errors.append(f"Lesson {lesson_id} missing 'group_id'")
        elif lesson["group_id"] not in group_ids:
            errors.append(f"Lesson {lesson_id} references unknown group: {lesson['group_id']}")

        if "subject_id" not in lesson:
            errors.append(f"Lesson {lesson_id} missing 'subject_id'")
        elif lesson["subject_id"] not in subject_ids:
            errors.append(f"Lesson {lesson_id} references unknown subject: {lesson['subject_id']}")

    # Validate teacher availability references
    if "teacher_availability" in data:
        for teacher_id in data["teacher_availability"]:
            if teacher_id not in teacher_ids:
                errors.append(f"Teacher availability references unknown teacher: {teacher_id}")

    # Check for duplicate IDs
    def check_duplicates(items: list, name: str):
        ids = [item["id"] for item in items if "id" in item]
        seen = set()
        for id_ in ids:
            if id_ in seen:
                errors.append(f"Duplicate {name} ID: {id_}")
            seen.add(id_)

    check_duplicates(data["lessons"], "lesson")
    check_duplicates(data["teachers"], "teacher")
    check_duplicates(data["rooms"], "room")
    check_duplicates(data["groups"], "group")
    check_duplicates(data["subjects"], "subject")

    if errors:
        raise DataValidationError("; ".join(errors))
