"""Tests for data loading and validation."""

import pytest
import json
import tempfile
from pathlib import Path

from solver.data.loader import load_school_data, validate_school_data, DataValidationError


@pytest.fixture
def valid_data():
    """Minimal valid school data."""
    return {
        "teachers": [{"id": "t1", "name": "Teacher 1"}],
        "rooms": [{"id": "r1", "name": "Room 1"}],
        "groups": [{"id": "g1", "name": "Group 1"}],
        "subjects": [{"id": "s1", "name": "Subject 1"}],
        "lessons": [
            {"id": "l1", "teacher_id": "t1", "group_id": "g1", "subject_id": "s1"}
        ],
    }


class TestValidation:
    """Tests for data validation."""

    def test_valid_data_passes(self, valid_data):
        """Valid data should pass validation without errors."""
        validate_school_data(valid_data)  # Should not raise

    def test_missing_required_field(self, valid_data):
        """Missing required fields should raise an error."""
        del valid_data["teachers"]
        with pytest.raises(DataValidationError, match="Missing required field: teachers"):
            validate_school_data(valid_data)

    def test_invalid_teacher_reference(self, valid_data):
        """Invalid teacher reference should raise an error."""
        valid_data["lessons"][0]["teacher_id"] = "nonexistent"
        with pytest.raises(DataValidationError, match="unknown teacher"):
            validate_school_data(valid_data)

    def test_invalid_room_reference_in_availability(self, valid_data):
        """Invalid teacher in availability should raise an error."""
        valid_data["teacher_availability"] = {
            "nonexistent": [{"day": 0, "period": 1}]
        }
        with pytest.raises(DataValidationError, match="unknown teacher"):
            validate_school_data(valid_data)

    def test_duplicate_lesson_ids(self, valid_data):
        """Duplicate lesson IDs should raise an error."""
        valid_data["lessons"].append(
            {"id": "l1", "teacher_id": "t1", "group_id": "g1", "subject_id": "s1"}
        )
        with pytest.raises(DataValidationError, match="Duplicate lesson ID"):
            validate_school_data(valid_data)


class TestFileLoading:
    """Tests for loading data from files."""

    def test_load_valid_file(self, valid_data):
        """Should successfully load a valid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_data, f)
            f.flush()
            loaded = load_school_data(f.name)

        assert loaded["teachers"] == valid_data["teachers"]
        assert loaded["lessons"] == valid_data["lessons"]

    def test_load_nonexistent_file(self):
        """Should raise FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            load_school_data("/nonexistent/path.json")

    def test_load_invalid_json(self):
        """Should raise JSONDecodeError for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {")
            f.flush()

            with pytest.raises(json.JSONDecodeError):
                load_school_data(f.name)
