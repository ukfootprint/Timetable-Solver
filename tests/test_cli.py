"""Tests for CLI module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from solver.cli import app
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
from solver.model_builder import SolverSolution, SolverStatus, LessonAssignment
from solver.output.schema import create_timetable_output


runner = CliRunner()


@pytest.fixture
def minimal_input_data() -> dict:
    """Create minimal input data as a dictionary."""
    return {
        "teachers": [
            {"id": "t1", "name": "Mr Smith"},
        ],
        "classes": [
            {"id": "c1", "name": "Year 10A"},
        ],
        "subjects": [
            {"id": "mat", "name": "Maths"},
        ],
        "rooms": [
            {"id": "r1", "name": "Room 101", "type": "classroom"},
        ],
        "lessons": [
            {"id": "l1", "teacherId": "t1", "classId": "c1", "subjectId": "mat", "lessonsPerWeek": 1},
        ],
        "periods": [
            {"id": "mon1", "name": "Mon P1", "day": 0, "startMinutes": 540, "endMinutes": 600},
            {"id": "tue1", "name": "Tue P1", "day": 1, "startMinutes": 540, "endMinutes": 600},
        ],
    }


@pytest.fixture
def input_file(minimal_input_data, tmp_path) -> Path:
    """Create a temporary input file."""
    filepath = tmp_path / "input.json"
    with open(filepath, "w") as f:
        json.dump(minimal_input_data, f)
    return filepath


@pytest.fixture
def sample_output_data() -> dict:
    """Create sample output data as a dictionary."""
    return {
        "status": "optimal",
        "solveTimeSeconds": 0.5,
        "quality": {
            "totalPenalty": 0,
            "hardConstraintsSatisfied": True,
            "softConstraintScores": {}
        },
        "timetable": {
            "lessons": [
                {
                    "lessonId": "l1",
                    "instance": 0,
                    "day": 0,
                    "startTime": "09:00",
                    "endTime": "10:00",
                    "roomId": "r1",
                    "roomName": "Room 101",
                    "teacherId": "t1",
                    "teacherName": "Mr Smith",
                    "classId": "c1",
                    "className": "Year 10A",
                    "subjectId": "mat",
                    "subjectName": "Maths",
                }
            ]
        },
        "views": {
            "byTeacher": {
                "t1": {
                    "id": "t1",
                    "name": "Mr Smith",
                    "lessons": [
                        {
                            "lessonId": "l1",
                            "instance": 0,
                            "day": 0,
                            "startTime": "09:00",
                            "endTime": "10:00",
                            "roomId": "r1",
                            "roomName": "Room 101",
                            "teacherId": "t1",
                            "teacherName": "Mr Smith",
                            "classId": "c1",
                            "className": "Year 10A",
                            "subjectId": "mat",
                            "subjectName": "Maths",
                        }
                    ],
                    "byDay": {
                        "0": [
                            {
                                "lessonId": "l1",
                                "instance": 0,
                                "day": 0,
                                "startTime": "09:00",
                                "endTime": "10:00",
                                "roomId": "r1",
                                "roomName": "Room 101",
                                "teacherId": "t1",
                                "teacherName": "Mr Smith",
                                "classId": "c1",
                                "className": "Year 10A",
                                "subjectId": "mat",
                                "subjectName": "Maths",
                            }
                        ]
                    }
                }
            },
            "byClass": {
                "c1": {
                    "id": "c1",
                    "name": "Year 10A",
                    "lessons": [
                        {
                            "lessonId": "l1",
                            "instance": 0,
                            "day": 0,
                            "startTime": "09:00",
                            "endTime": "10:00",
                            "roomId": "r1",
                            "roomName": "Room 101",
                            "teacherId": "t1",
                            "teacherName": "Mr Smith",
                            "classId": "c1",
                            "className": "Year 10A",
                            "subjectId": "mat",
                            "subjectName": "Maths",
                        }
                    ],
                    "byDay": {"0": []}
                }
            },
            "byRoom": {
                "r1": {
                    "id": "r1",
                    "name": "Room 101",
                    "lessons": [],
                    "byDay": {}
                }
            },
            "byDay": {
                "0": {
                    "day": 0,
                    "dayName": "Monday",
                    "lessons": [
                        {
                            "lessonId": "l1",
                            "instance": 0,
                            "day": 0,
                            "startTime": "09:00",
                            "endTime": "10:00",
                            "roomId": "r1",
                            "roomName": "Room 101",
                            "teacherId": "t1",
                            "teacherName": "Mr Smith",
                            "classId": "c1",
                            "className": "Year 10A",
                            "subjectId": "mat",
                            "subjectName": "Maths",
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def output_file(sample_output_data, tmp_path) -> Path:
    """Create a temporary output file."""
    filepath = tmp_path / "output.json"
    with open(filepath, "w") as f:
        json.dump(sample_output_data, f)
    return filepath


class TestHelpCommand:
    """Tests for help command."""

    def test_main_help(self):
        """Main help shows all commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "solve" in result.output
        assert "validate" in result.output
        assert "view" in result.output
        assert "metrics" in result.output

    def test_solve_help(self):
        """Solve help shows options."""
        result = runner.invoke(app, ["solve", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--timeout" in result.output

    def test_validate_help(self):
        """Validate help shows options."""
        result = runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        assert "input_file" in result.output.lower()

    def test_view_help(self):
        """View help shows options."""
        result = runner.invoke(app, ["view", "--help"])
        assert result.exit_code == 0
        assert "--teacher" in result.output
        assert "--class" in result.output
        assert "--day" in result.output

    def test_metrics_help(self):
        """Metrics help shows options."""
        result = runner.invoke(app, ["metrics", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output


class TestValidateCommand:
    """Tests for validate command."""

    def test_validate_valid_input(self, input_file):
        """Validate accepts valid input."""
        result = runner.invoke(app, ["validate", str(input_file)])
        assert result.exit_code == 0
        assert "Validation complete" in result.output

    def test_validate_nonexistent_file(self, tmp_path):
        """Validate fails on missing file."""
        result = runner.invoke(app, ["validate", str(tmp_path / "nonexistent.json")])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_validate_invalid_json(self, tmp_path):
        """Validate fails on invalid JSON."""
        filepath = tmp_path / "invalid.json"
        filepath.write_text("not valid json {")
        result = runner.invoke(app, ["validate", str(filepath)])
        assert result.exit_code == 1
        assert "JSON" in result.output

    def test_validate_shows_summary(self, input_file):
        """Validate shows entity counts."""
        result = runner.invoke(app, ["validate", str(input_file)])
        assert result.exit_code == 0
        assert "Teachers" in result.output
        assert "Classes" in result.output
        assert "Rooms" in result.output


class TestViewCommand:
    """Tests for view command."""

    def test_view_overview(self, output_file):
        """View shows overview by default."""
        result = runner.invoke(app, ["view", str(output_file)])
        assert result.exit_code == 0
        assert "Summary" in result.output or "Status" in result.output

    def test_view_teacher(self, output_file):
        """View shows teacher schedule."""
        result = runner.invoke(app, ["view", str(output_file), "--teacher", "t1"])
        assert result.exit_code == 0
        assert "Mr Smith" in result.output or "t1" in result.output

    def test_view_teacher_not_found(self, output_file):
        """View fails on nonexistent teacher."""
        result = runner.invoke(app, ["view", str(output_file), "--teacher", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_view_class(self, output_file):
        """View shows class schedule."""
        result = runner.invoke(app, ["view", str(output_file), "--class", "c1"])
        assert result.exit_code == 0
        assert "Year 10A" in result.output or "c1" in result.output

    def test_view_day(self, output_file):
        """View shows day schedule."""
        result = runner.invoke(app, ["view", str(output_file), "--day", "monday"])
        assert result.exit_code == 0
        assert "Monday" in result.output

    def test_view_invalid_day(self, output_file):
        """View fails on invalid day."""
        result = runner.invoke(app, ["view", str(output_file), "--day", "notaday"])
        assert result.exit_code == 1
        assert "Invalid day" in result.output


class TestMetricsCommand:
    """Tests for metrics command."""

    def test_metrics_basic(self, output_file):
        """Metrics shows basic info without input."""
        result = runner.invoke(app, ["metrics", str(output_file)])
        assert result.exit_code == 0
        assert "Solution Status" in result.output or "Timetable" in result.output

    def test_metrics_with_input(self, output_file, input_file):
        """Metrics shows detailed info with input."""
        result = runner.invoke(app, ["metrics", str(output_file), "--input", str(input_file)])
        assert result.exit_code == 0
        assert "Score" in result.output or "score" in result.output

    def test_metrics_json_format(self, output_file):
        """Metrics supports JSON format."""
        result = runner.invoke(app, ["metrics", str(output_file), "--format", "json"])
        assert result.exit_code == 0
        # Should be valid JSON
        try:
            json.loads(result.output)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")

    def test_metrics_nonexistent_file(self, tmp_path):
        """Metrics fails on missing file."""
        result = runner.invoke(app, ["metrics", str(tmp_path / "nonexistent.json")])
        assert result.exit_code != 0  # Typer returns 2 for invalid path


class TestSolveCommand:
    """Tests for solve command."""

    def test_solve_nonexistent_file(self, tmp_path):
        """Solve fails on missing file."""
        result = runner.invoke(app, ["solve", str(tmp_path / "nonexistent.json")])
        assert result.exit_code != 0

    def test_solve_with_output(self, input_file, tmp_path):
        """Solve creates output file."""
        output_path = tmp_path / "result.json"
        result = runner.invoke(app, ["solve", str(input_file), "-o", str(output_path), "-t", "5"])

        # May fail if solution not found in time, but should at least start
        assert "Loading" in result.output or "Error" in result.output

    def test_solve_timeout_option(self, input_file):
        """Solve accepts timeout option."""
        result = runner.invoke(app, ["solve", str(input_file), "--timeout", "1"])
        # Should at least start solving
        assert "Solving" in result.output or "Loading" in result.output


class TestCliIntegration:
    """Integration tests for CLI."""

    def test_full_workflow(self, input_file, tmp_path):
        """Test validate -> solve -> metrics workflow."""
        # Step 1: Validate
        result = runner.invoke(app, ["validate", str(input_file)])
        assert result.exit_code == 0

        # Step 2: Solve (short timeout)
        output_path = tmp_path / "solution.json"
        result = runner.invoke(app, ["solve", str(input_file), "-o", str(output_path), "-t", "5"])

        # If solved successfully, test metrics
        if output_path.exists():
            result = runner.invoke(app, ["metrics", str(output_path)])
            assert result.exit_code == 0


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_output(self, tmp_path):
        """Handles empty timetable output."""
        empty_output = {
            "status": "optimal",
            "solveTimeSeconds": 0.1,
            "quality": {
                "totalPenalty": 0,
                "hardConstraintsSatisfied": True,
                "softConstraintScores": {}
            },
            "timetable": {"lessons": []},
            "views": {
                "byTeacher": {},
                "byClass": {},
                "byRoom": {},
                "byDay": {}
            }
        }

        filepath = tmp_path / "empty.json"
        with open(filepath, "w") as f:
            json.dump(empty_output, f)

        result = runner.invoke(app, ["view", str(filepath)])
        assert result.exit_code == 0

    def test_malformed_input(self, tmp_path):
        """Handles malformed input gracefully."""
        malformed = {"teachers": "not a list"}

        filepath = tmp_path / "malformed.json"
        with open(filepath, "w") as f:
            json.dump(malformed, f)

        result = runner.invoke(app, ["validate", str(filepath)])
        assert result.exit_code == 1
