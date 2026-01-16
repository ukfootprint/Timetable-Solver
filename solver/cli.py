"""
Command-line interface for the timetable solver.

Usage:
    python -m solver solve input.json -o output.json --timeout 60
    python -m solver validate input.json
    python -m solver view output.json --teacher T001
    python -m solver metrics output.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from .data.models import TimetableInput, load_timetable_from_json
from .model_builder import TimetableModelBuilder, SolverStatus
from .constraints import ConstraintManager
from .output.schema import create_timetable_output, TimetableOutput
from .output.extractor import extract_solution
from .output.metrics import (
    QualityMetricsCalculator,
    calculate_all_metrics,
    generate_report,
)

# Create Typer app
app = typer.Typer(
    name="solver",
    help="School timetable solver using CP-SAT constraint programming.",
    add_completion=False,
)

# Rich console for pretty output
console = Console()

# Day name mappings
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_MAP = {name.lower(): i for i, name in enumerate(DAY_NAMES)}


# =============================================================================
# Helper Functions
# =============================================================================

def load_input(input_path: Path) -> TimetableInput:
    """Load and validate input data."""
    if not input_path.exists():
        console.print(f"[red]Error:[/red] Input file not found: {input_path}")
        raise typer.Exit(code=1)

    try:
        return load_timetable_from_json(str(input_path))
    except Exception as e:
        console.print(f"[red]Error loading input:[/red] {e}")
        raise typer.Exit(code=1)


def load_output(output_path: Path) -> TimetableOutput:
    """Load output JSON file."""
    if not output_path.exists():
        console.print(f"[red]Error:[/red] Output file not found: {output_path}")
        raise typer.Exit(code=1)

    try:
        with open(output_path) as f:
            data = json.load(f)
        return TimetableOutput.model_validate(data)
    except Exception as e:
        console.print(f"[red]Error loading output:[/red] {e}")
        raise typer.Exit(code=1)


def print_summary(output: TimetableOutput) -> None:
    """Print solution summary to console."""
    # Status panel
    status_color = "green" if output.status.value in ("optimal", "feasible") else "red"
    status_text = Text(output.status.value.upper(), style=f"bold {status_color}")

    console.print(Panel(
        status_text,
        title="Solution Status",
        subtitle=f"Solved in {output.solve_time_seconds:.2f}s"
    ))

    # Summary table
    table = Table(title="Summary", show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Total Lessons", str(len(output.timetable.lessons)))
    table.add_row("Teachers", str(len(output.views.by_teacher)))
    table.add_row("Classes", str(len(output.views.by_class)))
    table.add_row("Rooms Used", str(len(output.views.by_room)))
    table.add_row("Days", str(len(output.views.by_day)))
    table.add_row("Total Penalty", str(output.quality.total_penalty))

    console.print(table)


# =============================================================================
# Commands
# =============================================================================

@app.command()
def solve(
    input_file: Path = typer.Argument(
        ...,
        help="Path to input JSON file with timetable data",
        exists=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Path to write output JSON file",
    ),
    timeout: int = typer.Option(
        60,
        "--timeout", "-t",
        help="Maximum solving time in seconds",
        min=1,
        max=3600,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose output",
    ),
) -> None:
    """
    Solve a timetabling problem.

    Loads the input data, runs the CP-SAT solver, and outputs the solution.

    Example:
        python -m solver solve input.json -o output.json --timeout 60
    """
    console.print(f"\n[bold]Loading input from:[/bold] {input_file}")

    # Load input
    input_data = load_input(input_file)

    console.print(f"[green]Loaded:[/green] {len(input_data.lessons)} lessons, "
                  f"{len(input_data.teachers)} teachers, {len(input_data.rooms)} rooms")

    # Build model
    console.print("\n[bold]Building model...[/bold]")
    builder = TimetableModelBuilder(input_data)
    builder.create_variables()

    if verbose:
        console.print(f"  Created {len(builder.lesson_vars)} lesson variable sets")

    # Apply constraints
    manager = ConstraintManager()
    stats = manager.apply_all_constraints(builder)

    if verbose:
        console.print(f"  Applied {stats.hard_constraint_count} hard constraints")
        console.print(f"  Applied {stats.soft_constraint_count} soft constraints")

    # Set objective
    builder.set_objective()

    # Solve with progress
    console.print(f"\n[bold]Solving (timeout: {timeout}s)...[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Searching for optimal solution...", total=None)
        solution = builder.solve(time_limit_seconds=timeout)

    # Create output
    timetable_output = create_timetable_output(solution)

    # Print summary
    console.print()
    print_summary(timetable_output)

    # Check status
    if solution.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        console.print(f"\n[red]No solution found.[/red]")
        raise typer.Exit(code=1)

    # Save output if requested
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            f.write(timetable_output.to_json())
        console.print(f"\n[green]Solution saved to:[/green] {output}")

    console.print()


@app.command()
def validate(
    input_file: Path = typer.Argument(
        ...,
        help="Path to input JSON file to validate",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show detailed validation results",
    ),
) -> None:
    """
    Validate input data against the schema.

    Checks for:
    - Valid JSON structure
    - Schema compliance
    - Reference integrity (teacher IDs, room IDs, etc.)
    - Logical consistency

    Example:
        python -m solver validate input.json
    """
    console.print(f"\n[bold]Validating:[/bold] {input_file}\n")

    if not input_file.exists():
        console.print(f"[red]Error:[/red] File not found: {input_file}")
        raise typer.Exit(code=1)

    # Step 1: JSON parsing
    console.print("[cyan]1. Checking JSON syntax...[/cyan]")
    try:
        with open(input_file) as f:
            raw_data = json.load(f)
        console.print("   [green]JSON syntax is valid[/green]")
    except json.JSONDecodeError as e:
        console.print(f"   [red]Invalid JSON:[/red] {e}")
        raise typer.Exit(code=1)

    # Step 2: Schema validation
    console.print("[cyan]2. Validating against schema...[/cyan]")
    try:
        input_data = load_timetable_from_json(str(input_file))
        console.print("   [green]Schema validation passed[/green]")
    except Exception as e:
        console.print(f"   [red]Schema validation failed:[/red]")
        for line in str(e).split("\n"):
            console.print(f"   {line}")
        raise typer.Exit(code=1)

    # Step 3: Logical consistency
    console.print("[cyan]3. Checking logical consistency...[/cyan]")
    warnings = []

    # Check teacher workload
    for teacher in input_data.teachers:
        teacher_lessons = input_data.get_teacher_lessons(teacher.id)
        total_periods = sum(l.lessons_per_week for l in teacher_lessons)
        if teacher.max_periods_per_week and total_periods > teacher.max_periods_per_week:
            warnings.append(
                f"Teacher '{teacher.name}' has {total_periods} periods "
                f"but max is {teacher.max_periods_per_week}"
            )

    # Check slot capacity
    schedulable_periods = len(input_data.get_schedulable_periods())
    total_lessons = input_data.total_lessons_per_week
    total_slots = schedulable_periods * len(input_data.rooms)

    if total_lessons > total_slots:
        warnings.append(
            f"Total lessons ({total_lessons}) exceeds available slots ({total_slots})"
        )

    if warnings:
        console.print("   [yellow]Warnings found:[/yellow]")
        for w in warnings:
            console.print(f"   - {w}")
    else:
        console.print("   [green]No logical consistency issues[/green]")

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    table = Table(show_header=False, box=None)
    table.add_column("Entity", style="cyan")
    table.add_column("Count", style="white")

    table.add_row("Teachers", str(len(input_data.teachers)))
    table.add_row("Classes", str(len(input_data.classes)))
    table.add_row("Subjects", str(len(input_data.subjects)))
    table.add_row("Rooms", str(len(input_data.rooms)))
    table.add_row("Lessons", str(len(input_data.lessons)))
    table.add_row("Periods", str(len(input_data.periods)))
    table.add_row("Total lesson instances", str(total_lessons))
    table.add_row("Available slots", str(total_slots))

    console.print(table)

    if verbose:
        console.print("\n[bold]Detailed breakdown:[/bold]")
        console.print(f"  Schedulable periods per day: {schedulable_periods // 5 if input_data.config.num_days == 5 else schedulable_periods // input_data.config.num_days}")
        console.print(f"  Days per week: {input_data.config.num_days}")

    console.print("\n[green]Validation complete.[/green]\n")


@app.command()
def view(
    output_file: Path = typer.Argument(
        ...,
        help="Path to output JSON file",
        exists=True,
    ),
    teacher: Optional[str] = typer.Option(
        None,
        "--teacher", "-T",
        help="Show schedule for specific teacher ID",
    ),
    class_id: Optional[str] = typer.Option(
        None,
        "--class", "-C",
        help="Show schedule for specific class ID",
    ),
    room: Optional[str] = typer.Option(
        None,
        "--room", "-R",
        help="Show schedule for specific room ID",
    ),
    day: Optional[str] = typer.Option(
        None,
        "--day", "-D",
        help="Show schedule for specific day (monday, tuesday, etc.)",
    ),
    all_teachers: bool = typer.Option(
        False,
        "--all-teachers",
        help="Show schedules for all teachers",
    ),
    all_classes: bool = typer.Option(
        False,
        "--all-classes",
        help="Show schedules for all classes",
    ),
) -> None:
    """
    Display specific views of a timetable solution.

    Examples:
        python -m solver view output.json --teacher T001
        python -m solver view output.json --class C001
        python -m solver view output.json --day monday
        python -m solver view output.json --all-teachers
    """
    output = load_output(output_file)

    # Determine what to show
    if teacher:
        _show_teacher_view(output, teacher)
    elif class_id:
        _show_class_view(output, class_id)
    elif room:
        _show_room_view(output, room)
    elif day:
        _show_day_view(output, day)
    elif all_teachers:
        _show_all_teachers(output)
    elif all_classes:
        _show_all_classes(output)
    else:
        # Default: show overview
        _show_overview(output)


def _show_teacher_view(output: TimetableOutput, teacher_id: str) -> None:
    """Show schedule for a specific teacher."""
    schedule = output.views.by_teacher.get(teacher_id)
    if not schedule:
        console.print(f"[red]Error:[/red] Teacher '{teacher_id}' not found")
        console.print(f"Available teachers: {', '.join(output.views.by_teacher.keys())}")
        raise typer.Exit(code=1)

    console.print(Panel(
        f"[bold]{schedule.name}[/bold] ({schedule.id})",
        title="Teacher Schedule"
    ))

    _print_entity_schedule(schedule)


def _show_class_view(output: TimetableOutput, class_id: str) -> None:
    """Show schedule for a specific class."""
    schedule = output.views.by_class.get(class_id)
    if not schedule:
        console.print(f"[red]Error:[/red] Class '{class_id}' not found")
        console.print(f"Available classes: {', '.join(output.views.by_class.keys())}")
        raise typer.Exit(code=1)

    console.print(Panel(
        f"[bold]{schedule.name}[/bold] ({schedule.id})",
        title="Class Schedule"
    ))

    _print_entity_schedule(schedule, show_teacher=True)


def _show_room_view(output: TimetableOutput, room_id: str) -> None:
    """Show schedule for a specific room."""
    schedule = output.views.by_room.get(room_id)
    if not schedule:
        console.print(f"[red]Error:[/red] Room '{room_id}' not found")
        console.print(f"Available rooms: {', '.join(output.views.by_room.keys())}")
        raise typer.Exit(code=1)

    console.print(Panel(
        f"[bold]{schedule.name}[/bold] ({schedule.id})",
        title="Room Schedule"
    ))

    _print_entity_schedule(schedule, show_teacher=True, show_class=True)


def _show_day_view(output: TimetableOutput, day_name: str) -> None:
    """Show schedule for a specific day."""
    day_lower = day_name.lower()
    if day_lower not in DAY_MAP:
        console.print(f"[red]Error:[/red] Invalid day '{day_name}'")
        console.print(f"Valid days: {', '.join(DAY_MAP.keys())}")
        raise typer.Exit(code=1)

    day_idx = DAY_MAP[day_lower]
    day_schedule = output.views.by_day.get(day_idx)

    if not day_schedule:
        console.print(f"[yellow]No lessons scheduled for {DAY_NAMES[day_idx]}[/yellow]")
        return

    console.print(Panel(
        f"[bold]{day_schedule.day_name}[/bold]",
        title="Daily Schedule"
    ))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Time")
    table.add_column("Subject")
    table.add_column("Teacher")
    table.add_column("Class")
    table.add_column("Room")

    for lesson in sorted(day_schedule.lessons, key=lambda l: l.start_time):
        table.add_row(
            f"{lesson.start_time}-{lesson.end_time}",
            lesson.subject_name or lesson.subject_id,
            lesson.teacher_name or lesson.teacher_id,
            lesson.class_name or lesson.class_id,
            lesson.room_name or lesson.room_id,
        )

    console.print(table)


def _show_all_teachers(output: TimetableOutput) -> None:
    """Show schedules for all teachers."""
    for teacher_id in sorted(output.views.by_teacher.keys()):
        _show_teacher_view(output, teacher_id)
        console.print()


def _show_all_classes(output: TimetableOutput) -> None:
    """Show schedules for all classes."""
    for class_id in sorted(output.views.by_class.keys()):
        _show_class_view(output, class_id)
        console.print()


def _show_overview(output: TimetableOutput) -> None:
    """Show overview of the timetable."""
    print_summary(output)

    # Week grid
    console.print("\n[bold]Weekly Overview:[/bold]")

    # Get all time slots
    time_slots = sorted(set(l.start_time for l in output.timetable.lessons))
    days = sorted(output.views.by_day.keys())

    if not time_slots or not days:
        console.print("[yellow]No lessons scheduled[/yellow]")
        return

    table = Table(title="Week Grid", show_header=True, header_style="bold cyan")
    table.add_column("Time", style="dim")

    for day in days:
        day_name = DAY_NAMES[day] if day < len(DAY_NAMES) else f"Day {day}"
        table.add_column(day_name[:3], justify="center")

    for time_slot in time_slots:
        row = [time_slot]
        for day in days:
            day_schedule = output.views.by_day.get(day)
            if day_schedule:
                matching = [l for l in day_schedule.lessons if l.start_time == time_slot]
                if matching:
                    cell = f"{len(matching)}"
                else:
                    cell = "-"
            else:
                cell = "-"
            row.append(cell)
        table.add_row(*row)

    console.print(table)


def _print_entity_schedule(schedule, show_teacher: bool = False, show_class: bool = False) -> None:
    """Print an entity's schedule as a table."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("Day", style="cyan")
    table.add_column("Time")
    table.add_column("Subject")

    if show_teacher:
        table.add_column("Teacher")
    if show_class:
        table.add_column("Class")

    table.add_column("Room")

    for day in sorted(schedule.by_day.keys()):
        day_name = DAY_NAMES[day] if day < len(DAY_NAMES) else f"Day {day}"
        for lesson in schedule.by_day[day]:
            row = [
                day_name,
                f"{lesson.start_time}-{lesson.end_time}",
                lesson.subject_name or lesson.subject_id,
            ]
            if show_teacher:
                row.append(lesson.teacher_name or lesson.teacher_id)
            if show_class:
                row.append(lesson.class_name or lesson.class_id)
            row.append(lesson.room_name or lesson.room_id)
            table.add_row(*row)

    console.print(table)


@app.command()
def metrics(
    output_file: Path = typer.Argument(
        ...,
        help="Path to output JSON file",
        exists=True,
    ),
    input_file: Optional[Path] = typer.Option(
        None,
        "--input", "-i",
        help="Path to input JSON file (for detailed metrics)",
    ),
    format: str = typer.Option(
        "table",
        "--format", "-f",
        help="Output format: table, report, or json",
    ),
) -> None:
    """
    Calculate and display quality metrics for a timetable solution.

    Analyzes:
    - Gap score (teacher idle time)
    - Distribution score (lesson spread)
    - Daily balance (workload evenness)
    - Utilization (resource usage)

    Examples:
        python -m solver metrics output.json
        python -m solver metrics output.json --input input.json --format report
    """
    output = load_output(output_file)

    # Load input if provided for detailed metrics
    input_data = None
    if input_file:
        input_data = load_input(input_file)

    if format == "json":
        _show_metrics_json(output, input_data)
    elif format == "report" and input_data:
        _show_metrics_report(output, input_data)
    else:
        _show_metrics_table(output, input_data)


def _show_metrics_table(output: TimetableOutput, input_data: Optional[TimetableInput]) -> None:
    """Show metrics as a table."""
    console.print(Panel("[bold]Timetable Quality Metrics[/bold]"))

    # Basic metrics from output
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_column("Status")

    # Solution status
    status_color = "green" if output.status.value in ("optimal", "feasible") else "red"
    table.add_row(
        "Solution Status",
        output.status.value.upper(),
        f"[{status_color}]{'PASS' if status_color == 'green' else 'FAIL'}[/{status_color}]"
    )

    # Hard constraints
    hc_color = "green" if output.quality.hard_constraints_satisfied else "red"
    table.add_row(
        "Hard Constraints",
        "Satisfied" if output.quality.hard_constraints_satisfied else "Violated",
        f"[{hc_color}]{'PASS' if output.quality.hard_constraints_satisfied else 'FAIL'}[/{hc_color}]"
    )

    # Total penalty
    penalty = output.quality.total_penalty
    penalty_status = "green" if penalty < 50 else "yellow" if penalty < 200 else "red"
    table.add_row(
        "Total Penalty",
        str(penalty),
        f"[{penalty_status}]{'LOW' if penalty < 50 else 'MEDIUM' if penalty < 200 else 'HIGH'}[/{penalty_status}]"
    )

    # Lessons
    table.add_row(
        "Lessons Scheduled",
        str(len(output.timetable.lessons)),
        "[green]OK[/green]"
    )

    console.print(table)

    # Detailed metrics if input is provided
    if input_data:
        console.print("\n[bold]Detailed Analysis:[/bold]")

        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(output, input_data)

        detail_table = Table(show_header=True, header_style="bold cyan")
        detail_table.add_column("Metric")
        detail_table.add_column("Score")
        detail_table.add_column("Details")

        # Gap score
        gap = report.gap_metrics
        gap_color = "green" if gap.score >= 80 else "yellow" if gap.score >= 60 else "red"
        detail_table.add_row(
            "Gap Score",
            f"[{gap_color}]{gap.score}/100[/{gap_color}]",
            f"Avg gap: {gap.average_gap_minutes:.0f} min"
        )

        # Distribution score
        dist = report.distribution_metrics
        dist_color = "green" if dist.score >= 80 else "yellow" if dist.score >= 60 else "red"
        detail_table.add_row(
            "Distribution",
            f"[{dist_color}]{dist.score}/100[/{dist_color}]",
            f"{dist.well_distributed_count}/{dist.total_multi_lesson_subjects} well-distributed"
        )

        # Balance score
        balance = report.balance_metrics
        balance_color = "green" if balance.score >= 80 else "yellow" if balance.score >= 60 else "red"
        detail_table.add_row(
            "Daily Balance",
            f"[{balance_color}]{balance.score}/100[/{balance_color}]",
            f"Avg std dev: {balance.average_std_dev:.2f}"
        )

        # Overall
        overall_color = "green" if report.overall_score >= 80 else "yellow" if report.overall_score >= 60 else "red"
        detail_table.add_row(
            "[bold]Overall Score[/bold]",
            f"[bold {overall_color}]{report.overall_score}/100 ({report.grade})[/bold {overall_color}]",
            ""
        )

        console.print(detail_table)

        # Improvement areas
        if report.improvement_areas:
            console.print("\n[bold yellow]Areas for Improvement:[/bold yellow]")
            for area in report.improvement_areas:
                console.print(f"  [yellow]*[/yellow] {area}")
    else:
        console.print("\n[dim]Provide --input for detailed analysis[/dim]")


def _show_metrics_report(output: TimetableOutput, input_data: TimetableInput) -> None:
    """Show full metrics report."""
    report_str = generate_report(output, input_data)
    console.print(report_str)


def _show_metrics_json(output: TimetableOutput, input_data: Optional[TimetableInput]) -> None:
    """Show metrics as JSON."""
    if input_data:
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(output, input_data)
        data = report.to_dict()
    else:
        data = {
            "status": output.status.value,
            "hardConstraintsSatisfied": output.quality.hard_constraints_satisfied,
            "totalPenalty": output.quality.total_penalty,
            "lessonsScheduled": len(output.timetable.lessons),
            "softConstraintScores": output.quality.soft_constraint_scores,
        }

    console.print_json(json.dumps(data, indent=2))


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
