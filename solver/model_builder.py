"""
CP-SAT Model Builder for Timetabling.

This module provides a sophisticated model builder that creates a CP-SAT model
for school timetabling using interval variables.

Time representation:
- Week is represented as continuous minutes: 0 to (num_days * 1440 - 1)
- Day 0 (Monday) = minutes 0-1439
- Day 1 (Tuesday) = minutes 1440-2879
- Day 2 (Wednesday) = minutes 2880-4319
- Day 3 (Thursday) = minutes 4320-5759
- Day 4 (Friday) = minutes 5760-7199
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ortools.sat.python import cp_model

from .data.models import (
    TimetableInput,
    Lesson,
    Period,
    Room,
    Teacher,
    StudentClass,
    Subject,
    RoomType,
)


# =============================================================================
# Constants
# =============================================================================

MINUTES_PER_DAY = 1440
MINUTES_PER_HOUR = 60


# =============================================================================
# Time Conversion Helpers
# =============================================================================

def minutes_to_week_time(week_minutes: int) -> tuple[int, int, int]:
    """
    Convert week minutes to (day, hour, minute).

    Args:
        week_minutes: Minutes from start of week (0 = Monday 00:00)

    Returns:
        Tuple of (day, hour, minute) where day is 0-4

    Example:
        >>> minutes_to_week_time(570)  # Monday 9:30
        (0, 9, 30)
        >>> minutes_to_week_time(1980)  # Tuesday 9:00
        (1, 9, 0)
    """
    day = week_minutes // MINUTES_PER_DAY
    day_minutes = week_minutes % MINUTES_PER_DAY
    hour = day_minutes // MINUTES_PER_HOUR
    minute = day_minutes % MINUTES_PER_HOUR
    return (day, hour, minute)


def week_time_to_minutes(day: int, hour: int, minute: int) -> int:
    """
    Convert (day, hour, minute) to week minutes.

    Args:
        day: Day of week (0=Monday, 4=Friday)
        hour: Hour (0-23)
        minute: Minute (0-59)

    Returns:
        Minutes from start of week

    Example:
        >>> week_time_to_minutes(0, 9, 30)  # Monday 9:30
        570
        >>> week_time_to_minutes(1, 9, 0)  # Tuesday 9:00
        1980
    """
    return day * MINUTES_PER_DAY + hour * MINUTES_PER_HOUR + minute


def day_minutes_to_week_minutes(day: int, day_minutes: int) -> int:
    """
    Convert day index and minutes-from-midnight to week minutes.

    Args:
        day: Day of week (0-4)
        day_minutes: Minutes from midnight on that day

    Returns:
        Minutes from start of week
    """
    return day * MINUTES_PER_DAY + day_minutes


def format_week_time(week_minutes: int) -> str:
    """Format week minutes as 'DayName HH:MM'."""
    day, hour, minute = minutes_to_week_time(week_minutes)
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_name = day_names[day] if day < len(day_names) else f"Day{day}"
    return f"{day_name} {hour:02d}:{minute:02d}"


# =============================================================================
# Data Classes for Variables and Solutions
# =============================================================================

@dataclass
class LessonInstanceVars:
    """Variables for a single instance of a lesson."""
    lesson_id: str
    instance: int  # Which instance (0, 1, 2, ... for lessonsPerWeek)

    # Time variables
    start_var: cp_model.IntVar  # Start time in week minutes
    end_var: cp_model.IntVar    # End time in week minutes
    duration: int               # Fixed duration in minutes

    # Interval variable for no-overlap constraints
    interval_var: cp_model.IntervalVar

    # Day variable (0-4 for Mon-Fri)
    day_var: cp_model.IntVar

    # Room assignment variable (index into rooms list)
    room_var: cp_model.IntVar

    # Optional: period assignment (if using fixed periods)
    period_var: Optional[cp_model.IntVar] = None


@dataclass
class PenaltyVar:
    """A soft constraint penalty variable."""
    name: str
    var: cp_model.IntVar
    weight: int
    description: str


class SolverStatus(str, Enum):
    """Solver result status."""
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    MODEL_INVALID = "MODEL_INVALID"
    UNKNOWN = "UNKNOWN"


@dataclass
class LessonAssignment:
    """A single lesson assignment in the solution."""
    lesson_id: str
    instance: int
    day: int
    start_minutes: int  # Minutes from midnight on that day
    end_minutes: int
    room_id: str
    room_name: str
    teacher_id: str
    teacher_name: str
    class_id: str
    class_name: str
    subject_id: str
    subject_name: str
    period_id: Optional[str] = None
    period_name: Optional[str] = None


@dataclass
class SolverSolution:
    """Complete solver solution."""
    status: SolverStatus
    assignments: list[LessonAssignment]
    solve_time_ms: int
    objective_value: Optional[int] = None
    num_conflicts: int = 0
    penalties: dict[str, int] = field(default_factory=dict)

    @property
    def is_feasible(self) -> bool:
        return self.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)


# =============================================================================
# Main Model Builder
# =============================================================================

class TimetableModelBuilder:
    """
    Builds and solves a CP-SAT model for school timetabling.

    This builder creates interval variables for each lesson instance,
    allowing the solver to find optimal time slots and room assignments.

    Usage:
        builder = TimetableModelBuilder(timetable_input)
        builder.create_variables()
        builder.add_constraints()
        builder.set_objective()
        solution = builder.solve(time_limit_seconds=60)
    """

    def __init__(self, input_data: TimetableInput):
        """
        Initialize the model builder.

        Args:
            input_data: Validated TimetableInput with all school data
        """
        self.input = input_data
        self.model = cp_model.CpModel()

        # Configuration
        self.num_days = input_data.config.num_days
        self.week_minutes = self.num_days * MINUTES_PER_DAY

        # Variable storage
        self.lesson_vars: dict[str, list[LessonInstanceVars]] = {}
        self.penalty_vars: list[PenaltyVar] = []

        # Indexed data for quick lookup
        self._room_indices: dict[str, int] = {
            room.id: idx for idx, room in enumerate(input_data.rooms)
        }
        self._period_indices: dict[str, int] = {
            period.id: idx for idx, period in enumerate(input_data.periods)
        }

        # Build period time slots for each day
        self._period_slots: dict[int, list[tuple[int, int, str]]] = {}
        for period in input_data.get_schedulable_periods():
            day = period.day
            if day not in self._period_slots:
                self._period_slots[day] = []
            self._period_slots[day].append(
                (period.start_minutes, period.end_minutes, period.id)
            )

        # Sort slots by start time
        for day in self._period_slots:
            self._period_slots[day].sort(key=lambda x: x[0])

        # State tracking
        self._variables_created = False
        self._constraints_added = False
        self._objective_set = False

    # -------------------------------------------------------------------------
    # Variable Creation
    # -------------------------------------------------------------------------

    def create_variables(self) -> None:
        """
        Create all CP-SAT variables for the timetabling problem.

        For each lesson, creates variables for each weekly instance:
        - start_var: Start time in week minutes
        - end_var: End time in week minutes
        - interval_var: Interval for no-overlap constraints
        - day_var: Which day (0-4)
        - room_var: Which room (index into rooms list)
        """
        if self._variables_created:
            return

        for lesson in self.input.lessons:
            self._create_lesson_variables(lesson)

        self._variables_created = True

    def _create_lesson_variables(self, lesson: Lesson) -> None:
        """Create variables for all instances of a lesson."""
        lesson_id = lesson.id
        duration = lesson.duration_minutes
        num_instances = lesson.lessons_per_week
        num_rooms = len(self.input.rooms)

        self.lesson_vars[lesson_id] = []

        for instance in range(num_instances):
            var_prefix = f"L{lesson_id}_I{instance}"

            # Start time variable (0 to end of week minus duration)
            start_var = self.model.NewIntVar(
                0, self.week_minutes - duration,
                f"{var_prefix}_start"
            )

            # End time variable
            end_var = self.model.NewIntVar(
                duration, self.week_minutes,
                f"{var_prefix}_end"
            )

            # End = Start + Duration
            self.model.Add(end_var == start_var + duration)

            # Interval variable for no-overlap constraints
            interval_var = self.model.NewIntervalVar(
                start_var, duration, end_var,
                f"{var_prefix}_interval"
            )

            # Day variable (derived from start time)
            day_var = self.model.NewIntVar(0, self.num_days - 1, f"{var_prefix}_day")

            # Link day_var to start_var: day = start // MINUTES_PER_DAY
            self.model.AddDivisionEquality(day_var, start_var, MINUTES_PER_DAY)

            # Room assignment variable
            room_var = self.model.NewIntVar(0, num_rooms - 1, f"{var_prefix}_room")

            # Store the variables
            instance_vars = LessonInstanceVars(
                lesson_id=lesson_id,
                instance=instance,
                start_var=start_var,
                end_var=end_var,
                duration=duration,
                interval_var=interval_var,
                day_var=day_var,
                room_var=room_var,
            )

            self.lesson_vars[lesson_id].append(instance_vars)

    # -------------------------------------------------------------------------
    # Variable Access Helpers
    # -------------------------------------------------------------------------

    def get_lesson_vars(self, lesson_id: str) -> list[LessonInstanceVars]:
        """Get all instance variables for a lesson."""
        return self.lesson_vars.get(lesson_id, [])

    def get_all_intervals(self) -> list[cp_model.IntervalVar]:
        """Get all interval variables."""
        intervals = []
        for instances in self.lesson_vars.values():
            for inst in instances:
                intervals.append(inst.interval_var)
        return intervals

    def get_teacher_intervals(self, teacher_id: str) -> list[cp_model.IntervalVar]:
        """Get all interval variables for lessons taught by a teacher."""
        intervals = []
        for lesson in self.input.lessons:
            if lesson.teacher_id == teacher_id:
                for inst in self.lesson_vars.get(lesson.id, []):
                    intervals.append(inst.interval_var)
        return intervals

    def get_class_intervals(self, class_id: str) -> list[cp_model.IntervalVar]:
        """Get all interval variables for lessons of a class."""
        intervals = []
        for lesson in self.input.lessons:
            if lesson.class_id == class_id:
                for inst in self.lesson_vars.get(lesson.id, []):
                    intervals.append(inst.interval_var)
        return intervals

    # -------------------------------------------------------------------------
    # Constraint Addition
    # -------------------------------------------------------------------------

    def add_constraints(self) -> None:
        """Add all constraints to the model."""
        if not self._variables_created:
            raise RuntimeError("Must call create_variables() before add_constraints()")

        if self._constraints_added:
            return

        # Hard constraints (must be satisfied)
        self._add_valid_time_slots_constraint()
        self._add_teacher_no_overlap_constraint()
        self._add_class_no_overlap_constraint()
        self._add_room_no_overlap_constraint()
        self._add_room_type_constraints()
        self._add_teacher_availability_constraints()

        # Soft constraints (add penalties)
        self._add_lesson_spread_soft_constraint()
        self._add_teacher_max_periods_soft_constraint()

        self._constraints_added = True

    def _add_valid_time_slots_constraint(self) -> None:
        """
        Constrain lessons to valid time slots (during school hours).

        Lessons must start and end within schedulable periods.
        """
        schedulable_periods = self.input.get_schedulable_periods()

        for lesson_id, instances in self.lesson_vars.items():
            for inst in instances:
                # Build allowed (start, end) pairs for this lesson
                allowed_starts = []

                for period in schedulable_periods:
                    day = period.day
                    week_start = day_minutes_to_week_minutes(day, period.start_minutes)
                    week_end = day_minutes_to_week_minutes(day, period.end_minutes)

                    # Check if lesson fits in this period
                    if week_end - week_start >= inst.duration:
                        allowed_starts.append(week_start)

                # Constrain start to allowed values
                if allowed_starts:
                    self.model.AddAllowedAssignments(
                        [inst.start_var],
                        [[s] for s in allowed_starts]
                    )
                else:
                    # No valid slots - this will make model infeasible
                    self.model.Add(inst.start_var == -1)  # Impossible

    def _add_teacher_no_overlap_constraint(self) -> None:
        """Teachers cannot teach two lessons at the same time."""
        for teacher in self.input.teachers:
            intervals = self.get_teacher_intervals(teacher.id)
            if len(intervals) > 1:
                self.model.AddNoOverlap(intervals)

    def _add_class_no_overlap_constraint(self) -> None:
        """Classes cannot have two lessons at the same time."""
        for cls in self.input.classes:
            intervals = self.get_class_intervals(cls.id)
            if len(intervals) > 1:
                self.model.AddNoOverlap(intervals)

    def _add_room_no_overlap_constraint(self) -> None:
        """
        Rooms cannot host two lessons at the same time.

        Uses optional intervals that are active only when a lesson
        is assigned to that room.
        """
        num_rooms = len(self.input.rooms)

        for room_idx, room in enumerate(self.input.rooms):
            # Create optional intervals for lessons that could use this room
            room_intervals = []

            for lesson_id, instances in self.lesson_vars.items():
                lesson = self.input.get_lesson(lesson_id)
                if not lesson:
                    continue

                # Check if this room is valid for this lesson
                if not self._is_room_valid_for_lesson(room, lesson):
                    continue

                for inst in instances:
                    # Create a boolean: is this lesson in this room?
                    is_in_room = self.model.NewBoolVar(
                        f"L{lesson_id}_I{inst.instance}_in_R{room.id}"
                    )

                    # Link to room_var
                    self.model.Add(inst.room_var == room_idx).OnlyEnforceIf(is_in_room)
                    self.model.Add(inst.room_var != room_idx).OnlyEnforceIf(is_in_room.Not())

                    # Create optional interval
                    optional_interval = self.model.NewOptionalIntervalVar(
                        inst.start_var,
                        inst.duration,
                        inst.end_var,
                        is_in_room,
                        f"L{lesson_id}_I{inst.instance}_R{room.id}_interval"
                    )
                    room_intervals.append(optional_interval)

            # No overlap for this room
            if len(room_intervals) > 1:
                self.model.AddNoOverlap(room_intervals)

    def _add_room_type_constraints(self) -> None:
        """Constrain lessons to rooms of the required type."""
        for lesson in self.input.lessons:
            # Determine required room type
            required_type = None

            # Check lesson's room requirement
            if lesson.room_requirement and lesson.room_requirement.room_type:
                required_type = lesson.room_requirement.room_type

            # Check subject's room requirement
            if not required_type:
                subject = self.input.get_subject(lesson.subject_id)
                if subject and subject.requires_specialist_room:
                    required_type = subject.required_room_type

            if not required_type:
                continue

            # Get valid room indices
            valid_room_indices = [
                idx for idx, room in enumerate(self.input.rooms)
                if room.type == required_type
            ]

            if not valid_room_indices:
                # No valid rooms - will cause infeasibility
                continue

            # Constrain room_var for all instances
            for inst in self.lesson_vars.get(lesson.id, []):
                self.model.AddAllowedAssignments(
                    [inst.room_var],
                    [[idx] for idx in valid_room_indices]
                )

    def _add_teacher_availability_constraints(self) -> None:
        """Teachers can only teach when available."""
        for teacher in self.input.teachers:
            if not teacher.availability:
                continue

            # Build list of unavailable week-minute ranges
            unavailable_ranges: list[tuple[int, int]] = []
            for avail in teacher.availability:
                if not avail.available:
                    week_start = day_minutes_to_week_minutes(avail.day, avail.start_minutes)
                    week_end = day_minutes_to_week_minutes(avail.day, avail.end_minutes)
                    unavailable_ranges.append((week_start, week_end))

            if not unavailable_ranges:
                continue

            # For each lesson of this teacher, forbid unavailable times
            for lesson in self.input.lessons:
                if lesson.teacher_id != teacher.id:
                    continue

                for inst in self.lesson_vars.get(lesson.id, []):
                    for unavail_start, unavail_end in unavailable_ranges:
                        # Lesson must not overlap with unavailable time
                        # Either lesson ends before unavailable starts,
                        # or lesson starts after unavailable ends

                        # Create boolean for "overlaps with unavailable"
                        overlaps = self.model.NewBoolVar(
                            f"L{lesson.id}_I{inst.instance}_overlaps_unavail_{unavail_start}"
                        )

                        # overlaps = (start < unavail_end) AND (end > unavail_start)
                        before_end = self.model.NewBoolVar(f"temp_be_{lesson.id}_{inst.instance}_{unavail_start}")
                        after_start = self.model.NewBoolVar(f"temp_as_{lesson.id}_{inst.instance}_{unavail_start}")

                        self.model.Add(inst.start_var < unavail_end).OnlyEnforceIf(before_end)
                        self.model.Add(inst.start_var >= unavail_end).OnlyEnforceIf(before_end.Not())

                        self.model.Add(inst.end_var > unavail_start).OnlyEnforceIf(after_start)
                        self.model.Add(inst.end_var <= unavail_start).OnlyEnforceIf(after_start.Not())

                        # overlaps = before_end AND after_start
                        self.model.AddBoolAnd([before_end, after_start]).OnlyEnforceIf(overlaps)
                        self.model.AddBoolOr([before_end.Not(), after_start.Not()]).OnlyEnforceIf(overlaps.Not())

                        # Forbid overlapping
                        self.model.Add(overlaps == 0)

    def _add_lesson_spread_soft_constraint(self) -> None:
        """
        Soft constraint: spread lesson instances across different days.

        Penalize having multiple instances of the same lesson on the same day.
        """
        for lesson in self.input.lessons:
            instances = self.lesson_vars.get(lesson.id, [])
            if len(instances) <= 1:
                continue

            # For each pair of instances, penalize same day
            for i, inst1 in enumerate(instances):
                for inst2 in instances[i + 1:]:
                    # same_day = (day_var1 == day_var2)
                    same_day = self.model.NewBoolVar(
                        f"L{lesson.id}_I{inst1.instance}_I{inst2.instance}_same_day"
                    )
                    self.model.Add(inst1.day_var == inst2.day_var).OnlyEnforceIf(same_day)
                    self.model.Add(inst1.day_var != inst2.day_var).OnlyEnforceIf(same_day.Not())

                    # Add penalty for same day
                    self.penalty_vars.append(PenaltyVar(
                        name=f"same_day_{lesson.id}_{inst1.instance}_{inst2.instance}",
                        var=same_day,
                        weight=10,  # Soft constraint weight
                        description=f"Lesson {lesson.id} instances on same day"
                    ))

    def _add_teacher_max_periods_soft_constraint(self) -> None:
        """
        Soft constraint: respect teacher's max periods per day preference.
        """
        for teacher in self.input.teachers:
            if not teacher.max_periods_per_day:
                continue

            max_per_day = teacher.max_periods_per_day
            teacher_lessons = self.input.get_teacher_lessons(teacher.id)

            for day in range(self.num_days):
                # Count lessons on this day
                day_indicators = []

                for lesson in teacher_lessons:
                    for inst in self.lesson_vars.get(lesson.id, []):
                        is_on_day = self.model.NewBoolVar(
                            f"T{teacher.id}_L{lesson.id}_I{inst.instance}_day{day}"
                        )
                        self.model.Add(inst.day_var == day).OnlyEnforceIf(is_on_day)
                        self.model.Add(inst.day_var != day).OnlyEnforceIf(is_on_day.Not())
                        day_indicators.append(is_on_day)

                if not day_indicators:
                    continue

                # Sum of lessons on this day
                day_count = self.model.NewIntVar(0, len(day_indicators), f"T{teacher.id}_day{day}_count")
                self.model.Add(day_count == sum(day_indicators))

                # Excess over max
                max_excess = max(0, len(day_indicators) - max_per_day)
                if max_excess > 0:
                    excess = self.model.NewIntVar(0, max_excess, f"T{teacher.id}_day{day}_excess")
                    self.model.AddMaxEquality(excess, [day_count - max_per_day, 0])

                    self.penalty_vars.append(PenaltyVar(
                        name=f"teacher_overload_{teacher.id}_day{day}",
                        var=excess,
                        weight=20,
                        description=f"Teacher {teacher.name} overloaded on day {day}"
                    ))

    def _is_room_valid_for_lesson(self, room: Room, lesson: Lesson) -> bool:
        """Check if a room is valid for a lesson based on type requirements."""
        # Check excluded rooms
        if lesson.room_requirement and room.id in lesson.room_requirement.excluded_rooms:
            return False

        # Check room type requirement
        required_type = None
        if lesson.room_requirement and lesson.room_requirement.room_type:
            required_type = lesson.room_requirement.room_type
        else:
            subject = self.input.get_subject(lesson.subject_id)
            if subject and subject.requires_specialist_room:
                required_type = subject.required_room_type

        if required_type and room.type != required_type:
            return False

        return True

    # -------------------------------------------------------------------------
    # Objective Function
    # -------------------------------------------------------------------------

    def set_objective(self) -> None:
        """
        Set the optimization objective.

        Minimizes the weighted sum of all penalty variables.
        """
        if not self._constraints_added:
            raise RuntimeError("Must call add_constraints() before set_objective()")

        if self._objective_set:
            return

        if self.penalty_vars:
            total_penalty = sum(p.var * p.weight for p in self.penalty_vars)
            self.model.Minimize(total_penalty)

        self._objective_set = True

    # -------------------------------------------------------------------------
    # Solving
    # -------------------------------------------------------------------------

    def solve(self, time_limit_seconds: int = 60) -> SolverSolution:
        """
        Solve the timetabling problem.

        Args:
            time_limit_seconds: Maximum time to spend solving

        Returns:
            SolverSolution with status and assignments
        """
        if not self._variables_created:
            self.create_variables()
        if not self._constraints_added:
            self.add_constraints()
        if not self._objective_set:
            self.set_objective()

        # Configure solver
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_seconds
        solver.parameters.num_search_workers = 0  # Use all available cores
        solver.parameters.linearization_level = 2  # Maximum LP relaxation for better bounds
        solver.parameters.log_search_progress = False

        # Solve
        status_code = solver.Solve(self.model)

        # Map status
        status_map = {
            cp_model.OPTIMAL: SolverStatus.OPTIMAL,
            cp_model.FEASIBLE: SolverStatus.FEASIBLE,
            cp_model.INFEASIBLE: SolverStatus.INFEASIBLE,
            cp_model.MODEL_INVALID: SolverStatus.MODEL_INVALID,
            cp_model.UNKNOWN: SolverStatus.UNKNOWN,
        }
        status = status_map.get(status_code, SolverStatus.UNKNOWN)

        # Extract solution if feasible
        assignments: list[LessonAssignment] = []
        penalties: dict[str, int] = {}

        if status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            assignments = self._extract_assignments(solver)
            penalties = self._extract_penalties(solver)

        return SolverSolution(
            status=status,
            assignments=assignments,
            solve_time_ms=int(solver.WallTime() * 1000),
            objective_value=int(solver.ObjectiveValue()) if status == SolverStatus.OPTIMAL else None,
            penalties=penalties,
        )

    def _extract_assignments(self, solver: cp_model.CpSolver) -> list[LessonAssignment]:
        """Extract lesson assignments from solved model."""
        assignments = []

        for lesson_id, instances in self.lesson_vars.items():
            lesson = self.input.get_lesson(lesson_id)
            if not lesson:
                continue

            teacher = self.input.get_teacher(lesson.teacher_id)
            cls = self.input.get_class(lesson.class_id)
            subject = self.input.get_subject(lesson.subject_id)

            for inst in instances:
                week_start = solver.Value(inst.start_var)
                week_end = solver.Value(inst.end_var)
                room_idx = solver.Value(inst.room_var)
                day = solver.Value(inst.day_var)

                room = self.input.rooms[room_idx]

                # Convert week minutes to day minutes
                day_start_minutes = week_start % MINUTES_PER_DAY
                day_end_minutes = week_end % MINUTES_PER_DAY

                # Find matching period if any
                period_id = None
                period_name = None
                for period in self.input.periods:
                    if (period.day == day and
                        period.start_minutes == day_start_minutes):
                        period_id = period.id
                        period_name = period.name
                        break

                assignments.append(LessonAssignment(
                    lesson_id=lesson_id,
                    instance=inst.instance,
                    day=day,
                    start_minutes=day_start_minutes,
                    end_minutes=day_end_minutes,
                    room_id=room.id,
                    room_name=room.name,
                    teacher_id=lesson.teacher_id,
                    teacher_name=teacher.name if teacher else "Unknown",
                    class_id=lesson.class_id,
                    class_name=cls.name if cls else "Unknown",
                    subject_id=lesson.subject_id,
                    subject_name=subject.name if subject else "Unknown",
                    period_id=period_id,
                    period_name=period_name,
                ))

        # Sort by day, then start time
        assignments.sort(key=lambda a: (a.day, a.start_minutes))

        return assignments

    def _extract_penalties(self, solver: cp_model.CpSolver) -> dict[str, int]:
        """Extract penalty values from solved model."""
        penalties = {}
        for penalty in self.penalty_vars:
            value = solver.Value(penalty.var)
            if value > 0:
                penalties[penalty.name] = value * penalty.weight
        return penalties

    # -------------------------------------------------------------------------
    # Diagnostics
    # -------------------------------------------------------------------------

    def get_statistics(self) -> dict[str, Any]:
        """Get model statistics."""
        total_instances = sum(len(insts) for insts in self.lesson_vars.values())
        return {
            "num_lessons": len(self.input.lessons),
            "num_lesson_instances": total_instances,
            "num_teachers": len(self.input.teachers),
            "num_classes": len(self.input.classes),
            "num_rooms": len(self.input.rooms),
            "num_periods": len(self.input.periods),
            "num_schedulable_periods": len(self.input.get_schedulable_periods()),
            "num_days": self.num_days,
            "week_minutes": self.week_minutes,
            "num_penalty_vars": len(self.penalty_vars),
            "variables_created": self._variables_created,
            "constraints_added": self._constraints_added,
            "objective_set": self._objective_set,
        }
