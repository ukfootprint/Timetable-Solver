"""Tests for output formatters."""

from __future__ import annotations

import csv
import json
import tempfile
from io import StringIO
from pathlib import Path

import pytest

from solver.model_builder import SolverSolution, SolverStatus, LessonAssignment
from solver.output.schema import (
    OutputStatus,
    LessonOutput,
    QualityMetrics,
    DaySchedule,
    EntitySchedule,
    TimetableViews,
    Timetable,
    TimetableOutput,
    create_timetable_output,
)
from solver.output.formatters import (
    JSONFormatter,
    CSVFormatter,
    ConsoleFormatter,
    TeacherViewFormatter,
    ClassViewFormatter,
    WeekGridFormatter,
    format_json,
    format_csv,
    format_console,
    print_console,
    format_teacher_view,
    format_all_teachers,
    format_class_view,
    format_all_classes,
    format_week_grid,
    save_json,
    save_csv,
    save_teacher_views,
    save_class_views,
    DAY_NAMES,
    DAY_ABBREV,
)


@pytest.fixture
def sample_assignments() -> list[LessonAssignment]:
    """Create sample lesson assignments."""
    return [
        LessonAssignment(
            lesson_id="l1",
            instance=0,
            day=0,
            start_minutes=540,  # 09:00
            end_minutes=600,    # 10:00
            room_id="r1",
            room_name="Room 101",
            teacher_id="t1",
            teacher_name="Mr Smith",
            class_id="c1",
            class_name="Year 10A",
            subject_id="mat",
            subject_name="Maths",
            period_id="mon1",
            period_name="Monday Period 1",
        ),
        LessonAssignment(
            lesson_id="l1",
            instance=1,
            day=2,
            start_minutes=600,  # 10:00
            end_minutes=660,    # 11:00
            room_id="r1",
            room_name="Room 101",
            teacher_id="t1",
            teacher_name="Mr Smith",
            class_id="c1",
            class_name="Year 10A",
            subject_id="mat",
            subject_name="Maths",
            period_id="wed2",
            period_name="Wednesday Period 2",
        ),
        LessonAssignment(
            lesson_id="l2",
            instance=0,
            day=0,
            start_minutes=600,  # 10:00
            end_minutes=660,    # 11:00
            room_id="r2",
            room_name="Room 102",
            teacher_id="t2",
            teacher_name="Ms Jones",
            class_id="c1",
            class_name="Year 10A",
            subject_id="eng",
            subject_name="English",
            period_id="mon2",
            period_name="Monday Period 2",
        ),
    ]


@pytest.fixture
def sample_solution(sample_assignments) -> SolverSolution:
    """Create a sample solver solution."""
    return SolverSolution(
        status=SolverStatus.OPTIMAL,
        assignments=sample_assignments,
        solve_time_ms=1500,
        objective_value=25,
        penalties={"same_day_l1_0_1": 10, "teacher_gap_t1_day0": 15},
    )


@pytest.fixture
def sample_output(sample_solution) -> TimetableOutput:
    """Create sample TimetableOutput."""
    return create_timetable_output(sample_solution)


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_format_produces_valid_json(self, sample_output):
        """Format produces valid JSON string."""
        formatter = JSONFormatter()
        json_str = formatter.format(sample_output)

        data = json.loads(json_str)
        assert "status" in data
        assert "timetable" in data

    def test_format_with_indent(self, sample_output):
        """Respects indentation setting."""
        formatter = JSONFormatter(indent=4)
        json_str = formatter.format(sample_output)

        # Should have more indentation
        assert "    " in json_str

    def test_format_compact(self, sample_output):
        """Compact format has no whitespace."""
        formatter = JSONFormatter()
        compact = formatter.format_compact(sample_output)

        # Should be single line with no extra spaces
        assert "\n" not in compact
        assert ": " not in compact  # No space after colon

    def test_format_lessons_only(self, sample_output):
        """Lessons only format excludes metadata."""
        formatter = JSONFormatter()
        json_str = formatter.format_lessons_only(sample_output)

        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 3
        assert "lessonId" in data[0]


class TestCSVFormatter:
    """Tests for CSVFormatter class."""

    def test_format_produces_valid_csv(self, sample_output):
        """Format produces valid CSV."""
        formatter = CSVFormatter()
        csv_str = formatter.format(sample_output)

        reader = csv.reader(StringIO(csv_str))
        rows = list(reader)

        assert len(rows) == 4  # Header + 3 lessons
        assert rows[0][0] == "lesson_id"

    def test_format_with_custom_columns(self, sample_output):
        """Respects custom columns."""
        columns = ["lesson_id", "day", "start_time"]
        formatter = CSVFormatter(columns=columns)
        csv_str = formatter.format(sample_output)

        reader = csv.reader(StringIO(csv_str))
        rows = list(reader)

        assert len(rows[0]) == 3
        assert rows[0] == columns

    def test_format_without_header(self, sample_output):
        """Can exclude header."""
        formatter = CSVFormatter(include_header=False)
        csv_str = formatter.format(sample_output)

        reader = csv.reader(StringIO(csv_str))
        rows = list(reader)

        assert len(rows) == 3  # No header

    def test_format_with_delimiter(self, sample_output):
        """Respects custom delimiter."""
        formatter = CSVFormatter(delimiter=";")
        csv_str = formatter.format(sample_output)

        assert ";" in csv_str

    def test_write_to_file(self, sample_output):
        """Write method works with file-like objects."""
        formatter = CSVFormatter()
        buffer = StringIO()
        formatter.write(sample_output, buffer)

        buffer.seek(0)
        content = buffer.read()
        assert "lesson_id" in content

    def test_minimal_columns(self, sample_output):
        """Minimal columns work correctly."""
        formatter = CSVFormatter(columns=CSVFormatter.MINIMAL_COLUMNS)
        csv_str = formatter.format(sample_output)

        reader = csv.reader(StringIO(csv_str))
        header = next(reader)

        assert "lesson_id" in header
        assert "teacher_id" not in header  # Not in minimal


class TestConsoleFormatter:
    """Tests for ConsoleFormatter class."""

    def test_format_plain_text(self, sample_output):
        """Format produces plain text output."""
        formatter = ConsoleFormatter(use_colors=False)
        text = formatter.format(sample_output)

        assert "TIMETABLE SOLUTION" in text
        assert "OPTIMAL" in text
        assert "Monday" in text

    def test_format_includes_lessons(self, sample_output):
        """Output includes lesson details."""
        formatter = ConsoleFormatter(use_colors=False)
        text = formatter.format(sample_output)

        assert "09:00" in text
        assert "Maths" in text
        assert "Mr Smith" in text

    def test_print_to_stream(self, sample_output):
        """Print method writes to stream."""
        formatter = ConsoleFormatter(use_colors=False)
        buffer = StringIO()
        formatter.print(sample_output, buffer)

        content = buffer.getvalue()
        assert "TIMETABLE SOLUTION" in content


class TestTeacherViewFormatter:
    """Tests for TeacherViewFormatter class."""

    def test_format_single_teacher(self, sample_output):
        """Format produces output for single teacher."""
        formatter = TeacherViewFormatter(use_colors=False)
        text = formatter.format(sample_output, "t1")

        assert "Mr Smith" in text
        assert "t1" in text
        assert "Maths" in text

    def test_format_missing_teacher(self, sample_output):
        """Handles missing teacher gracefully."""
        formatter = TeacherViewFormatter(use_colors=False)
        text = formatter.format(sample_output, "nonexistent")

        assert "No schedule found" in text

    def test_format_all_teachers(self, sample_output):
        """Format all teachers includes both."""
        formatter = TeacherViewFormatter(use_colors=False)
        text = formatter.format_all(sample_output)

        assert "Mr Smith" in text
        assert "Ms Jones" in text

    def test_teacher_lessons_grouped_by_day(self, sample_output):
        """Teacher view groups lessons by day."""
        formatter = TeacherViewFormatter(use_colors=False)
        text = formatter.format(sample_output, "t1")

        assert "Monday" in text
        assert "Wednesday" in text


class TestClassViewFormatter:
    """Tests for ClassViewFormatter class."""

    def test_format_single_class(self, sample_output):
        """Format produces output for single class."""
        formatter = ClassViewFormatter(use_colors=False)
        text = formatter.format(sample_output, "c1")

        assert "Year 10A" in text
        assert "c1" in text

    def test_format_missing_class(self, sample_output):
        """Handles missing class gracefully."""
        formatter = ClassViewFormatter(use_colors=False)
        text = formatter.format(sample_output, "nonexistent")

        assert "No schedule found" in text

    def test_format_all_classes(self, sample_output):
        """Format all classes works."""
        formatter = ClassViewFormatter(use_colors=False)
        text = formatter.format_all(sample_output)

        assert "Year 10A" in text


class TestWeekGridFormatter:
    """Tests for WeekGridFormatter class."""

    def test_format_grid(self, sample_output):
        """Format produces grid output."""
        formatter = WeekGridFormatter(use_colors=False)
        text = formatter.format(sample_output)

        # Should have time slots and days
        assert "09:00" in text or "Time" in text

    def test_custom_time_slots(self, sample_output):
        """Respects custom time slots."""
        formatter = WeekGridFormatter(time_slots=["09:00", "10:00"], use_colors=False)
        text = formatter.format(sample_output)

        assert "09:00" in text


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_format_json(self, sample_output):
        """format_json convenience function works."""
        json_str = format_json(sample_output)
        data = json.loads(json_str)
        assert "status" in data

    def test_format_csv(self, sample_output):
        """format_csv convenience function works."""
        csv_str = format_csv(sample_output)
        assert "lesson_id" in csv_str

    def test_format_csv_minimal(self, sample_output):
        """format_csv with minimal flag works."""
        csv_str = format_csv(sample_output, minimal=True)
        reader = csv.reader(StringIO(csv_str))
        header = next(reader)
        assert "teacher_id" not in header

    def test_format_console(self, sample_output):
        """format_console convenience function works."""
        text = format_console(sample_output, use_colors=False)
        assert "TIMETABLE SOLUTION" in text

    def test_print_console(self, sample_output):
        """print_console convenience function works."""
        buffer = StringIO()
        # Redirect stdout to buffer
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer
        try:
            print_console(sample_output, use_colors=False)
        finally:
            sys.stdout = old_stdout

        content = buffer.getvalue()
        assert "TIMETABLE SOLUTION" in content

    def test_format_teacher_view(self, sample_output):
        """format_teacher_view convenience function works."""
        text = format_teacher_view(sample_output, "t1")
        assert "Mr Smith" in text or "t1" in text

    def test_format_all_teachers(self, sample_output):
        """format_all_teachers convenience function works."""
        text = format_all_teachers(sample_output)
        assert "t1" in text or "Mr Smith" in text

    def test_format_class_view(self, sample_output):
        """format_class_view convenience function works."""
        text = format_class_view(sample_output, "c1")
        assert "Year 10A" in text or "c1" in text

    def test_format_all_classes(self, sample_output):
        """format_all_classes convenience function works."""
        text = format_all_classes(sample_output)
        assert "c1" in text or "Year 10A" in text

    def test_format_week_grid(self, sample_output):
        """format_week_grid convenience function works."""
        text = format_week_grid(sample_output)
        assert len(text) > 0


class TestFileUtilities:
    """Tests for file writing utilities."""

    def test_save_json(self, sample_output):
        """save_json writes valid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "output.json"
            save_json(sample_output, filepath)

            assert filepath.exists()
            with open(filepath) as f:
                data = json.load(f)
            assert "status" in data

    def test_save_json_creates_directories(self, sample_output):
        """save_json creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "subdir" / "output.json"
            save_json(sample_output, filepath)

            assert filepath.exists()

    def test_save_csv(self, sample_output):
        """save_csv writes valid CSV file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "output.csv"
            save_csv(sample_output, filepath)

            assert filepath.exists()
            with open(filepath) as f:
                reader = csv.reader(f)
                rows = list(reader)
            assert len(rows) == 4  # Header + 3 lessons

    def test_save_csv_minimal(self, sample_output):
        """save_csv with minimal flag works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "output.csv"
            save_csv(sample_output, filepath, minimal=True)

            with open(filepath) as f:
                reader = csv.reader(f)
                header = next(reader)
            assert "teacher_id" not in header

    def test_save_teacher_views_txt(self, sample_output):
        """save_teacher_views creates text files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "teachers"
            files = save_teacher_views(sample_output, output_dir, format="txt")

            assert len(files) == 2  # t1 and t2
            assert all(f.suffix == ".txt" for f in files)
            assert all(f.exists() for f in files)

    def test_save_teacher_views_csv(self, sample_output):
        """save_teacher_views creates CSV files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "teachers"
            files = save_teacher_views(sample_output, output_dir, format="csv")

            assert len(files) == 2
            assert all(f.suffix == ".csv" for f in files)

            # Check content of one file
            with open(files[0]) as f:
                reader = csv.reader(f)
                header = next(reader)
            assert "day" in header
            assert "subject" in header

    def test_save_class_views_txt(self, sample_output):
        """save_class_views creates text files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "classes"
            files = save_class_views(sample_output, output_dir, format="txt")

            assert len(files) == 1  # Only c1
            assert files[0].suffix == ".txt"
            assert files[0].exists()

    def test_save_class_views_csv(self, sample_output):
        """save_class_views creates CSV files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "classes"
            files = save_class_views(sample_output, output_dir, format="csv")

            assert len(files) == 1
            assert files[0].suffix == ".csv"


class TestConstants:
    """Tests for module constants."""

    def test_day_names(self):
        """DAY_NAMES has correct values."""
        assert DAY_NAMES[0] == "Monday"
        assert DAY_NAMES[4] == "Friday"
        assert len(DAY_NAMES) == 7

    def test_day_abbrev(self):
        """DAY_ABBREV has correct values."""
        assert DAY_ABBREV[0] == "Mon"
        assert DAY_ABBREV[4] == "Fri"
        assert len(DAY_ABBREV) == 7


class TestEmptyOutput:
    """Tests for handling empty output."""

    @pytest.fixture
    def empty_output(self):
        """Create empty TimetableOutput."""
        solution = SolverSolution(
            status=SolverStatus.OPTIMAL,
            assignments=[],
            solve_time_ms=100,
        )
        return create_timetable_output(solution)

    def test_json_formatter_empty(self, empty_output):
        """JSONFormatter handles empty output."""
        formatter = JSONFormatter()
        json_str = formatter.format(empty_output)
        data = json.loads(json_str)
        assert data["timetable"]["lessons"] == []

    def test_csv_formatter_empty(self, empty_output):
        """CSVFormatter handles empty output."""
        formatter = CSVFormatter()
        csv_str = formatter.format(empty_output)
        reader = csv.reader(StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1  # Header only

    def test_console_formatter_empty(self, empty_output):
        """ConsoleFormatter handles empty output."""
        formatter = ConsoleFormatter(use_colors=False)
        text = formatter.format(empty_output)
        assert "TIMETABLE SOLUTION" in text
        assert "Lessons scheduled: 0" in text

    def test_teacher_view_empty(self, empty_output):
        """TeacherViewFormatter handles empty output."""
        formatter = TeacherViewFormatter(use_colors=False)
        text = formatter.format_all(empty_output)
        # Should produce empty or minimal output
        assert text is not None
