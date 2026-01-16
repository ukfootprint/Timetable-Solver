"""CP-SAT model builder for timetabling (legacy dict-based API).

NOTE: This is the old dict-based implementation. For the new interval-based
implementation using Pydantic models, see model_builder.py.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from ortools.sat.python import cp_model

from .constraints.core import (
    add_one_slot_per_lesson,
    add_teacher_no_overlap,
    add_room_no_overlap,
    add_group_no_overlap,
)
from .constraints.room_types import add_room_type_requirements


@dataclass
class SolverSolution:
    """Result from the CP-SAT solver."""
    status: str
    assignments: list[dict]
    solve_time_ms: int
    objective_value: Optional[int] = None


class TimetableModel:
    """
    Builds and solves a CP-SAT model for school timetabling.

    The model uses boolean variables to represent lesson-slot-room assignments:
        x[lesson_id, day, period, room_id] = 1 if lesson is assigned to that slot/room
    """

    def __init__(self, school_data: dict):
        """
        Initialize the model with school data.

        Args:
            school_data: Dictionary containing lessons, teachers, rooms, groups, etc.
        """
        self.data = school_data
        self.model = cp_model.CpModel()
        self.variables: dict[tuple, cp_model.IntVar] = {}
        self._built = False

    def build(self) -> None:
        """Build the CP-SAT model with all variables and constraints."""
        if self._built:
            return

        self._create_variables()
        self._add_constraints()
        self._built = True

    def _create_variables(self) -> None:
        """Create boolean variables for lesson-slot-room assignments."""
        lessons = self.data["lessons"]
        rooms = self.data["rooms"]
        num_days = self.data.get("num_days", 5)
        num_periods = self.data.get("num_periods", 6)

        for lesson in lessons:
            lesson_id = lesson["id"]
            for day in range(num_days):
                for period in range(1, num_periods + 1):
                    for room in rooms:
                        room_id = room["id"]
                        var_name = f"x_{lesson_id}_{day}_{period}_{room_id}"
                        self.variables[(lesson_id, day, period, room_id)] = \
                            self.model.NewBoolVar(var_name)

    def _add_constraints(self) -> None:
        """Add all constraints to the model."""
        # Core constraints (required for valid timetable)
        add_one_slot_per_lesson(self.model, self.variables, self.data)
        add_teacher_no_overlap(self.model, self.variables, self.data)
        add_room_no_overlap(self.model, self.variables, self.data)
        add_group_no_overlap(self.model, self.variables, self.data)

        # Optional constraints (based on data availability)
        if any(r.get("type") for r in self.data["rooms"]):
            add_room_type_requirements(self.model, self.variables, self.data)

    def solve(self, time_limit: int = 60) -> SolverSolution:
        """
        Solve the model and return the solution.

        Args:
            time_limit: Maximum solving time in seconds

        Returns:
            SolverSolution with status and assignments
        """
        if not self._built:
            self.build()

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_search_workers = 0  # Use all available cores
        solver.parameters.linearization_level = 2  # Maximum LP relaxation for better bounds

        status = solver.Solve(self.model)

        status_name = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
            cp_model.UNKNOWN: "UNKNOWN",
        }.get(status, "UNKNOWN")

        assignments = []
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            assignments = self._extract_assignments(solver)

        return SolverSolution(
            status=status_name,
            assignments=assignments,
            solve_time_ms=int(solver.WallTime() * 1000),
            objective_value=int(solver.ObjectiveValue()) if status == cp_model.OPTIMAL else None,
        )

    def _extract_assignments(self, solver: cp_model.CpSolver) -> list[dict]:
        """Extract lesson assignments from the solved model."""
        assignments = []
        lessons_map = {l["id"]: l for l in self.data["lessons"]}
        rooms_map = {r["id"]: r for r in self.data["rooms"]}

        for (lesson_id, day, period, room_id), var in self.variables.items():
            if solver.Value(var) == 1:
                lesson = lessons_map[lesson_id]
                room = rooms_map[room_id]
                assignments.append({
                    "lesson_id": lesson_id,
                    "day": day,
                    "period": period,
                    "room_id": room_id,
                    "room_name": room["name"],
                    "teacher_id": lesson["teacher_id"],
                    "group_id": lesson["group_id"],
                    "subject_id": lesson["subject_id"],
                })

        return assignments
