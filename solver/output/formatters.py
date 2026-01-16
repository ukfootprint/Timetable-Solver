"""
Output formatters for timetable solutions.

This module provides formatters for different output formats:
- JSON: Complete solution with all views
- CSV: Flat format for spreadsheets
- Console: Pretty-printed for CLI
- Teacher/Class views: Individual timetables
"""

from __future__ import annotations

import csv
import json
import sys
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from .schema import TimetableOutput, LessonOutput

# Try to import rich for colored console output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# =============================================================================
# Constants
# =============================================================================

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBREV = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# =============================================================================
# JSON Formatter
# =============================================================================

class JSONFormatter:
    """Formats timetable output as JSON."""

    def __init__(self, indent: int = 2, ensure_ascii: bool = False):
        """
        Initialize JSON formatter.

        Args:
            indent: JSON indentation level
            ensure_ascii: If True, escape non-ASCII characters
        """
        self.indent = indent
        self.ensure_ascii = ensure_ascii

    def format(self, output: TimetableOutput) -> str:
        """
        Format output as JSON string.

        Args:
            output: TimetableOutput to format

        Returns:
            JSON string
        """
        return output.to_json(indent=self.indent)

    def format_compact(self, output: TimetableOutput) -> str:
        """Format as compact single-line JSON."""
        data = output.to_dict()
        return json.dumps(data, ensure_ascii=self.ensure_ascii, separators=(',', ':'))

    def format_lessons_only(self, output: TimetableOutput) -> str:
        """Format only the lessons array as JSON."""
        lessons_data = [
            lesson.model_dump(by_alias=True)
            for lesson in output.timetable.lessons
        ]
        return json.dumps(lessons_data, indent=self.indent, ensure_ascii=self.ensure_ascii)


def format_json(output: TimetableOutput, indent: int = 2) -> str:
    """Convenience function for JSON formatting."""
    return JSONFormatter(indent=indent).format(output)


# =============================================================================
# CSV Formatter
# =============================================================================

class CSVFormatter:
    """Formats timetable output as CSV."""

    # Default column order
    DEFAULT_COLUMNS = [
        'lesson_id', 'instance', 'day', 'day_name', 'start_time', 'end_time',
        'teacher_id', 'teacher_name', 'class_id', 'class_name',
        'subject_id', 'subject_name', 'room_id', 'room_name',
        'period_id', 'period_name'
    ]

    # Minimal columns for simpler output
    MINIMAL_COLUMNS = [
        'lesson_id', 'day', 'start_time', 'end_time',
        'teacher_name', 'class_name', 'subject_name', 'room_name'
    ]

    def __init__(
        self,
        columns: list[str] | None = None,
        include_header: bool = True,
        delimiter: str = ',',
    ):
        """
        Initialize CSV formatter.

        Args:
            columns: List of columns to include (None = all)
            include_header: Whether to include header row
            delimiter: Field delimiter
        """
        self.columns = columns or self.DEFAULT_COLUMNS
        self.include_header = include_header
        self.delimiter = delimiter

    def format(self, output: TimetableOutput) -> str:
        """
        Format output as CSV string.

        Args:
            output: TimetableOutput to format

        Returns:
            CSV string
        """
        buffer = StringIO()
        self.write(output, buffer)
        return buffer.getvalue()

    def write(self, output: TimetableOutput, file: TextIO) -> None:
        """
        Write CSV to file-like object.

        Args:
            output: TimetableOutput to format
            file: File-like object to write to
        """
        writer = csv.writer(file, delimiter=self.delimiter)

        if self.include_header:
            writer.writerow(self.columns)

        for lesson in output.timetable.lessons:
            row = self._lesson_to_row(lesson)
            writer.writerow(row)

    def _lesson_to_row(self, lesson: LessonOutput) -> list[str]:
        """Convert lesson to CSV row."""
        day_name = DAY_NAMES[lesson.day] if lesson.day < len(DAY_NAMES) else f"Day {lesson.day}"

        field_map = {
            'lesson_id': lesson.lesson_id,
            'instance': str(lesson.instance),
            'day': str(lesson.day),
            'day_name': day_name,
            'start_time': lesson.start_time,
            'end_time': lesson.end_time,
            'teacher_id': lesson.teacher_id,
            'teacher_name': lesson.teacher_name or '',
            'class_id': lesson.class_id,
            'class_name': lesson.class_name or '',
            'subject_id': lesson.subject_id,
            'subject_name': lesson.subject_name or '',
            'room_id': lesson.room_id,
            'room_name': lesson.room_name or '',
            'period_id': lesson.period_id or '',
            'period_name': lesson.period_name or '',
        }

        return [field_map.get(col, '') for col in self.columns]


def format_csv(
    output: TimetableOutput,
    columns: list[str] | None = None,
    minimal: bool = False,
) -> str:
    """
    Convenience function for CSV formatting.

    Args:
        output: TimetableOutput to format
        columns: Columns to include
        minimal: Use minimal column set

    Returns:
        CSV string
    """
    if minimal:
        columns = CSVFormatter.MINIMAL_COLUMNS
    return CSVFormatter(columns=columns).format(output)


# =============================================================================
# Console Formatter
# =============================================================================

class ConsoleFormatter:
    """Formats timetable output for console display."""

    def __init__(
        self,
        use_colors: bool = True,
        width: int | None = None,
    ):
        """
        Initialize console formatter.

        Args:
            use_colors: Use colored output (requires rich)
            width: Console width (None = auto-detect)
        """
        self.use_colors = use_colors and RICH_AVAILABLE
        self.width = width

    def format(self, output: TimetableOutput) -> str:
        """
        Format output as console string.

        Args:
            output: TimetableOutput to format

        Returns:
            Formatted string for console
        """
        if self.use_colors:
            return self._format_rich(output)
        else:
            return self._format_plain(output)

    def print(self, output: TimetableOutput, file: TextIO = None) -> None:
        """
        Print output to console.

        Args:
            output: TimetableOutput to print
            file: Output stream (default: stdout)
        """
        if file is None:
            file = sys.stdout

        if self.use_colors:
            console = Console(file=file, width=self.width)
            self._print_rich(output, console)
        else:
            file.write(self._format_plain(output))
            file.write('\n')

    def _format_plain(self, output: TimetableOutput) -> str:
        """Format without colors."""
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append(f"TIMETABLE SOLUTION - Status: {output.status.value.upper()}")
        lines.append("=" * 60)
        lines.append("")

        # Summary
        lines.append(f"Solve time: {output.solve_time_seconds:.2f}s")
        lines.append(f"Total penalty: {output.quality.total_penalty}")
        lines.append(f"Lessons scheduled: {len(output.timetable.lessons)}")
        lines.append("")

        # Lessons by day
        for day in sorted(output.views.by_day.keys()):
            day_schedule = output.views.by_day[day]
            lines.append(f"--- {day_schedule.day_name} ---")

            for lesson in day_schedule.lessons:
                lines.append(
                    f"  {lesson.start_time}-{lesson.end_time}: "
                    f"{lesson.subject_name or lesson.subject_id} | "
                    f"{lesson.class_name or lesson.class_id} | "
                    f"{lesson.teacher_name or lesson.teacher_id} | "
                    f"Room: {lesson.room_name or lesson.room_id}"
                )

            lines.append("")

        return '\n'.join(lines)

    def _format_rich(self, output: TimetableOutput) -> str:
        """Format with rich colors (returns string via capture)."""
        console = Console(record=True, width=self.width or 100)
        self._print_rich(output, console)
        return console.export_text()

    def _print_rich(self, output: TimetableOutput, console: Console) -> None:
        """Print with rich library."""
        # Status panel
        status_color = "green" if output.status.value in ("optimal", "feasible") else "red"
        status_text = Text(output.status.value.upper(), style=f"bold {status_color}")

        console.print(Panel(
            status_text,
            title="Timetable Solution",
            subtitle=f"Solved in {output.solve_time_seconds:.2f}s"
        ))

        # Summary
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Total penalty: {output.quality.total_penalty}")
        console.print(f"  Lessons: {len(output.timetable.lessons)}")

        # Create grid table
        table = Table(title="Weekly Schedule", show_header=True, header_style="bold cyan")
        table.add_column("Time", style="dim")

        # Add day columns
        days_in_schedule = sorted(output.views.by_day.keys())
        for day in days_in_schedule:
            day_name = DAY_ABBREV[day] if day < len(DAY_ABBREV) else f"D{day}"
            table.add_column(day_name, justify="center")

        # Collect all time slots
        time_slots = set()
        for lesson in output.timetable.lessons:
            time_slots.add(lesson.start_time)

        # Build rows
        for time_slot in sorted(time_slots):
            row = [time_slot]
            for day in days_in_schedule:
                day_lessons = output.views.by_day.get(day)
                if day_lessons:
                    matching = [l for l in day_lessons.lessons if l.start_time == time_slot]
                    if matching:
                        lesson = matching[0]
                        cell = f"{lesson.subject_name or lesson.subject_id}\n{lesson.class_name or lesson.class_id}"
                        row.append(cell)
                    else:
                        row.append("-")
                else:
                    row.append("-")
            table.add_row(*row)

        console.print(table)


def format_console(output: TimetableOutput, use_colors: bool = True) -> str:
    """Convenience function for console formatting."""
    return ConsoleFormatter(use_colors=use_colors).format(output)


def print_console(output: TimetableOutput, use_colors: bool = True) -> None:
    """Print timetable to console."""
    ConsoleFormatter(use_colors=use_colors).print(output)


# =============================================================================
# Teacher View Formatter
# =============================================================================

class TeacherViewFormatter:
    """Formats individual teacher timetables."""

    def __init__(self, use_colors: bool = True):
        """
        Initialize teacher view formatter.

        Args:
            use_colors: Use colored output
        """
        self.use_colors = use_colors and RICH_AVAILABLE

    def format(self, output: TimetableOutput, teacher_id: str) -> str:
        """
        Format timetable for a specific teacher.

        Args:
            output: TimetableOutput
            teacher_id: Teacher ID to format

        Returns:
            Formatted string
        """
        teacher_schedule = output.views.by_teacher.get(teacher_id)
        if not teacher_schedule:
            return f"No schedule found for teacher: {teacher_id}"

        if self.use_colors:
            return self._format_rich(teacher_schedule)
        else:
            return self._format_plain(teacher_schedule)

    def format_all(self, output: TimetableOutput) -> str:
        """Format timetables for all teachers."""
        lines = []
        for teacher_id in sorted(output.views.by_teacher.keys()):
            lines.append(self.format(output, teacher_id))
            lines.append("")
        return '\n'.join(lines)

    def _format_plain(self, schedule) -> str:
        """Format without colors."""
        lines = []
        lines.append(f"{'=' * 50}")
        lines.append(f"TEACHER: {schedule.name} ({schedule.id})")
        lines.append(f"{'=' * 50}")

        for day in sorted(schedule.by_day.keys()):
            day_name = DAY_NAMES[day] if day < len(DAY_NAMES) else f"Day {day}"
            lines.append(f"\n{day_name}:")

            for lesson in schedule.by_day[day]:
                lines.append(
                    f"  {lesson.start_time}-{lesson.end_time}: "
                    f"{lesson.subject_name or lesson.subject_id} "
                    f"({lesson.class_name or lesson.class_id}) "
                    f"@ {lesson.room_name or lesson.room_id}"
                )

        return '\n'.join(lines)

    def _format_rich(self, schedule) -> str:
        """Format with rich colors."""
        console = Console(record=True, width=100)

        console.print(Panel(
            f"[bold]{schedule.name}[/bold] ({schedule.id})",
            title="Teacher Schedule"
        ))

        table = Table(show_header=True, header_style="bold")
        table.add_column("Day", style="cyan")
        table.add_column("Time")
        table.add_column("Subject")
        table.add_column("Class")
        table.add_column("Room")

        for day in sorted(schedule.by_day.keys()):
            day_name = DAY_NAMES[day] if day < len(DAY_NAMES) else f"Day {day}"
            for lesson in schedule.by_day[day]:
                table.add_row(
                    day_name,
                    f"{lesson.start_time}-{lesson.end_time}",
                    lesson.subject_name or lesson.subject_id,
                    lesson.class_name or lesson.class_id,
                    lesson.room_name or lesson.room_id,
                )

        console.print(table)
        return console.export_text()


def format_teacher_view(output: TimetableOutput, teacher_id: str) -> str:
    """Format timetable for a specific teacher."""
    return TeacherViewFormatter().format(output, teacher_id)


def format_all_teachers(output: TimetableOutput) -> str:
    """Format timetables for all teachers."""
    return TeacherViewFormatter().format_all(output)


# =============================================================================
# Class View Formatter
# =============================================================================

class ClassViewFormatter:
    """Formats individual class timetables."""

    def __init__(self, use_colors: bool = True):
        """
        Initialize class view formatter.

        Args:
            use_colors: Use colored output
        """
        self.use_colors = use_colors and RICH_AVAILABLE

    def format(self, output: TimetableOutput, class_id: str) -> str:
        """
        Format timetable for a specific class.

        Args:
            output: TimetableOutput
            class_id: Class ID to format

        Returns:
            Formatted string
        """
        class_schedule = output.views.by_class.get(class_id)
        if not class_schedule:
            return f"No schedule found for class: {class_id}"

        if self.use_colors:
            return self._format_rich(class_schedule)
        else:
            return self._format_plain(class_schedule)

    def format_all(self, output: TimetableOutput) -> str:
        """Format timetables for all classes."""
        lines = []
        for class_id in sorted(output.views.by_class.keys()):
            lines.append(self.format(output, class_id))
            lines.append("")
        return '\n'.join(lines)

    def _format_plain(self, schedule) -> str:
        """Format without colors."""
        lines = []
        lines.append(f"{'=' * 50}")
        lines.append(f"CLASS: {schedule.name} ({schedule.id})")
        lines.append(f"{'=' * 50}")

        for day in sorted(schedule.by_day.keys()):
            day_name = DAY_NAMES[day] if day < len(DAY_NAMES) else f"Day {day}"
            lines.append(f"\n{day_name}:")

            for lesson in schedule.by_day[day]:
                lines.append(
                    f"  {lesson.start_time}-{lesson.end_time}: "
                    f"{lesson.subject_name or lesson.subject_id} "
                    f"({lesson.teacher_name or lesson.teacher_id}) "
                    f"@ {lesson.room_name or lesson.room_id}"
                )

        return '\n'.join(lines)

    def _format_rich(self, schedule) -> str:
        """Format with rich colors."""
        console = Console(record=True, width=100)

        console.print(Panel(
            f"[bold]{schedule.name}[/bold] ({schedule.id})",
            title="Class Schedule"
        ))

        table = Table(show_header=True, header_style="bold")
        table.add_column("Day", style="cyan")
        table.add_column("Time")
        table.add_column("Subject")
        table.add_column("Teacher")
        table.add_column("Room")

        for day in sorted(schedule.by_day.keys()):
            day_name = DAY_NAMES[day] if day < len(DAY_NAMES) else f"Day {day}"
            for lesson in schedule.by_day[day]:
                table.add_row(
                    day_name,
                    f"{lesson.start_time}-{lesson.end_time}",
                    lesson.subject_name or lesson.subject_id,
                    lesson.teacher_name or lesson.teacher_id,
                    lesson.room_name or lesson.room_id,
                )

        console.print(table)
        return console.export_text()


def format_class_view(output: TimetableOutput, class_id: str) -> str:
    """Format timetable for a specific class."""
    return ClassViewFormatter().format(output, class_id)


def format_all_classes(output: TimetableOutput) -> str:
    """Format timetables for all classes."""
    return ClassViewFormatter().format_all(output)


# =============================================================================
# Week Grid Formatter
# =============================================================================

class WeekGridFormatter:
    """Formats timetable as a week grid."""

    def __init__(
        self,
        time_slots: list[str] | None = None,
        use_colors: bool = True,
    ):
        """
        Initialize week grid formatter.

        Args:
            time_slots: List of time slots to show (None = auto-detect)
            use_colors: Use colored output
        """
        self.time_slots = time_slots
        self.use_colors = use_colors and RICH_AVAILABLE

    def format(self, output: TimetableOutput, view_type: str = "overview") -> str:
        """
        Format as week grid.

        Args:
            output: TimetableOutput
            view_type: "overview", "by_room", etc.

        Returns:
            Formatted grid string
        """
        if self.use_colors:
            return self._format_rich(output)
        else:
            return self._format_plain(output)

    def _format_plain(self, output: TimetableOutput) -> str:
        """Format as plain text grid."""
        lines = []

        # Get time slots
        time_slots = self.time_slots
        if not time_slots:
            time_slots = sorted(set(l.start_time for l in output.timetable.lessons))

        # Get days
        days = sorted(output.views.by_day.keys())

        # Header
        day_width = 20
        header = "Time".ljust(8)
        for day in days:
            day_name = DAY_ABBREV[day] if day < len(DAY_ABBREV) else f"D{day}"
            header += day_name.center(day_width)
        lines.append(header)
        lines.append("-" * (8 + len(days) * day_width))

        # Rows
        for time_slot in time_slots:
            row = time_slot.ljust(8)
            for day in days:
                day_lessons = output.views.by_day.get(day)
                cell = ""
                if day_lessons:
                    matching = [l for l in day_lessons.lessons if l.start_time == time_slot]
                    if matching:
                        lesson = matching[0]
                        cell = f"{lesson.subject_id}"[:day_width-2]
                row += cell.center(day_width)
            lines.append(row)

        return '\n'.join(lines)

    def _format_rich(self, output: TimetableOutput) -> str:
        """Format with rich table."""
        console = Console(record=True, width=120)

        table = Table(title="Week Grid", show_header=True, header_style="bold cyan")
        table.add_column("Time", style="dim")

        # Get days
        days = sorted(output.views.by_day.keys())
        for day in days:
            day_name = DAY_ABBREV[day] if day < len(DAY_ABBREV) else f"D{day}"
            table.add_column(day_name, justify="center")

        # Get time slots
        time_slots = self.time_slots
        if not time_slots:
            time_slots = sorted(set(l.start_time for l in output.timetable.lessons))

        # Build rows
        for time_slot in time_slots:
            row = [time_slot]
            for day in days:
                day_lessons = output.views.by_day.get(day)
                if day_lessons:
                    matching = [l for l in day_lessons.lessons if l.start_time == time_slot]
                    if matching:
                        lesson = matching[0]
                        cell = f"[bold]{lesson.subject_name or lesson.subject_id}[/bold]\n{lesson.class_name or lesson.class_id}"
                        row.append(cell)
                    else:
                        row.append("[dim]-[/dim]")
                else:
                    row.append("[dim]-[/dim]")
            table.add_row(*row)

        console.print(table)
        return console.export_text()


def format_week_grid(output: TimetableOutput) -> str:
    """Format as week grid."""
    return WeekGridFormatter().format(output)


# =============================================================================
# File Writing Utilities
# =============================================================================

def save_json(output: TimetableOutput, filepath: str | Path, indent: int = 2) -> None:
    """
    Save output as JSON file.

    Args:
        output: TimetableOutput to save
        filepath: Path to save to
        indent: JSON indentation
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    json_str = JSONFormatter(indent=indent).format(output)
    filepath.write_text(json_str, encoding='utf-8')


def save_csv(
    output: TimetableOutput,
    filepath: str | Path,
    columns: list[str] | None = None,
    minimal: bool = False,
) -> None:
    """
    Save output as CSV file.

    Args:
        output: TimetableOutput to save
        filepath: Path to save to
        columns: Columns to include
        minimal: Use minimal column set
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if minimal:
        columns = CSVFormatter.MINIMAL_COLUMNS

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        CSVFormatter(columns=columns).write(output, f)


def save_teacher_views(
    output: TimetableOutput,
    output_dir: str | Path,
    format: str = "txt",
) -> list[Path]:
    """
    Save individual teacher timetables to files.

    Args:
        output: TimetableOutput
        output_dir: Directory to save files
        format: Output format ("txt" or "csv")

    Returns:
        List of created file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    created_files = []
    formatter = TeacherViewFormatter(use_colors=False)

    for teacher_id in output.views.by_teacher:
        if format == "txt":
            filepath = output_dir / f"teacher_{teacher_id}.txt"
            content = formatter.format(output, teacher_id)
            filepath.write_text(content, encoding='utf-8')
        elif format == "csv":
            filepath = output_dir / f"teacher_{teacher_id}.csv"
            teacher_lessons = output.views.by_teacher[teacher_id].lessons
            # Create mini output with just this teacher's lessons
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['day', 'start_time', 'end_time', 'subject', 'class', 'room'])
                for lesson in teacher_lessons:
                    day_name = DAY_NAMES[lesson.day] if lesson.day < len(DAY_NAMES) else f"Day {lesson.day}"
                    writer.writerow([
                        day_name,
                        lesson.start_time,
                        lesson.end_time,
                        lesson.subject_name or lesson.subject_id,
                        lesson.class_name or lesson.class_id,
                        lesson.room_name or lesson.room_id,
                    ])

        created_files.append(filepath)

    return created_files


def save_class_views(
    output: TimetableOutput,
    output_dir: str | Path,
    format: str = "txt",
) -> list[Path]:
    """
    Save individual class timetables to files.

    Args:
        output: TimetableOutput
        output_dir: Directory to save files
        format: Output format ("txt" or "csv")

    Returns:
        List of created file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    created_files = []
    formatter = ClassViewFormatter(use_colors=False)

    for class_id in output.views.by_class:
        if format == "txt":
            filepath = output_dir / f"class_{class_id}.txt"
            content = formatter.format(output, class_id)
            filepath.write_text(content, encoding='utf-8')
        elif format == "csv":
            filepath = output_dir / f"class_{class_id}.csv"
            class_lessons = output.views.by_class[class_id].lessons
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['day', 'start_time', 'end_time', 'subject', 'teacher', 'room'])
                for lesson in class_lessons:
                    day_name = DAY_NAMES[lesson.day] if lesson.day < len(DAY_NAMES) else f"Day {lesson.day}"
                    writer.writerow([
                        day_name,
                        lesson.start_time,
                        lesson.end_time,
                        lesson.subject_name or lesson.subject_id,
                        lesson.teacher_name or lesson.teacher_id,
                        lesson.room_name or lesson.room_id,
                    ])

        created_files.append(filepath)

    return created_files
