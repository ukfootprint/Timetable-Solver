"""Tests for constraint implementations."""

import pytest
from ortools.sat.python import cp_model

from solver.constraints.core import (
    add_one_slot_per_lesson,
    add_teacher_no_overlap,
    add_room_no_overlap,
    add_group_no_overlap,
)


@pytest.fixture
def simple_data():
    """Minimal school data for testing."""
    return {
        "num_days": 2,
        "num_periods": 2,
        "teachers": [
            {"id": "t1", "name": "Teacher 1"},
            {"id": "t2", "name": "Teacher 2"},
        ],
        "rooms": [
            {"id": "r1", "name": "Room 1"},
            {"id": "r2", "name": "Room 2"},
        ],
        "groups": [
            {"id": "g1", "name": "Group 1"},
        ],
        "subjects": [
            {"id": "s1", "name": "Subject 1"},
        ],
        "lessons": [
            {"id": "l1", "teacher_id": "t1", "group_id": "g1", "subject_id": "s1"},
            {"id": "l2", "teacher_id": "t1", "group_id": "g1", "subject_id": "s1"},
        ],
    }


def create_variables(data):
    """Create model variables for testing."""
    model = cp_model.CpModel()
    variables = {}

    for lesson in data["lessons"]:
        lesson_id = lesson["id"]
        for day in range(data["num_days"]):
            for period in range(1, data["num_periods"] + 1):
                for room in data["rooms"]:
                    room_id = room["id"]
                    var_name = f"x_{lesson_id}_{day}_{period}_{room_id}"
                    variables[(lesson_id, day, period, room_id)] = model.NewBoolVar(var_name)

    return model, variables


class TestOneLessonPerSlot:
    """Tests for the one-slot-per-lesson constraint."""

    def test_each_lesson_assigned_once(self, simple_data):
        """Each lesson should be assigned exactly once."""
        model, variables = create_variables(simple_data)
        add_one_slot_per_lesson(model, variables, simple_data)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Count assignments per lesson
        for lesson in simple_data["lessons"]:
            lesson_id = lesson["id"]
            count = sum(
                solver.Value(variables[(lesson_id, d, p, r["id"])])
                for d in range(simple_data["num_days"])
                for p in range(1, simple_data["num_periods"] + 1)
                for r in simple_data["rooms"]
            )
            assert count == 1, f"Lesson {lesson_id} should be assigned exactly once"


class TestTeacherNoOverlap:
    """Tests for the teacher no-overlap constraint."""

    def test_teacher_no_double_booking(self, simple_data):
        """Same teacher cannot teach two lessons at the same time."""
        model, variables = create_variables(simple_data)
        add_one_slot_per_lesson(model, variables, simple_data)
        add_teacher_no_overlap(model, variables, simple_data)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Check that teacher t1's lessons are in different slots
        l1_slot = None
        l2_slot = None

        for d in range(simple_data["num_days"]):
            for p in range(1, simple_data["num_periods"] + 1):
                for r in simple_data["rooms"]:
                    if solver.Value(variables[("l1", d, p, r["id"])]) == 1:
                        l1_slot = (d, p)
                    if solver.Value(variables[("l2", d, p, r["id"])]) == 1:
                        l2_slot = (d, p)

        assert l1_slot != l2_slot, "Same teacher's lessons should be in different slots"


class TestRoomNoOverlap:
    """Tests for the room no-overlap constraint."""

    def test_room_no_double_booking(self, simple_data):
        """Same room cannot host two lessons at the same time."""
        model, variables = create_variables(simple_data)
        add_one_slot_per_lesson(model, variables, simple_data)
        add_room_no_overlap(model, variables, simple_data)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Check each slot has at most one lesson per room
        for d in range(simple_data["num_days"]):
            for p in range(1, simple_data["num_periods"] + 1):
                for r in simple_data["rooms"]:
                    room_id = r["id"]
                    count = sum(
                        solver.Value(variables[(l["id"], d, p, room_id)])
                        for l in simple_data["lessons"]
                    )
                    assert count <= 1, f"Room {room_id} has multiple lessons at day {d}, period {p}"
