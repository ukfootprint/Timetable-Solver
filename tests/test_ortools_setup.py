"""Simple test to verify OR-Tools CP-SAT is working correctly."""

from ortools.sat.python import cp_model


def test_cpsat_simple_constraint():
    """
    Verify OR-Tools CP-SAT works by solving a trivial constraint problem.

    Problem: Find values for x, y, z where:
    - x, y, z are in range [0, 10]
    - x + y + z = 15
    - x < y < z
    """
    model = cp_model.CpModel()

    # Create variables
    x = model.NewIntVar(0, 10, 'x')
    y = model.NewIntVar(0, 10, 'y')
    z = model.NewIntVar(0, 10, 'z')

    # Add constraints
    model.Add(x + y + z == 15)
    model.Add(x < y)
    model.Add(y < z)

    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # Verify solution found
    assert status == cp_model.OPTIMAL or status == cp_model.FEASIBLE

    # Verify constraints are satisfied
    x_val = solver.Value(x)
    y_val = solver.Value(y)
    z_val = solver.Value(z)

    assert x_val + y_val + z_val == 15, "Sum should equal 15"
    assert x_val < y_val < z_val, "Values should be strictly increasing"
    assert 0 <= x_val <= 10, "x should be in range"
    assert 0 <= y_val <= 10, "y should be in range"
    assert 0 <= z_val <= 10, "z should be in range"

    print(f"Solution found: x={x_val}, y={y_val}, z={z_val}")


def test_cpsat_boolean_satisfiability():
    """
    Verify boolean variable handling works.

    Problem: Schedule 3 tasks to 2 slots where each task
    must be assigned to exactly one slot.
    """
    model = cp_model.CpModel()

    # task_slot[t][s] = 1 if task t is in slot s
    tasks = 3
    slots = 2
    task_slot = {}

    for t in range(tasks):
        for s in range(slots):
            task_slot[(t, s)] = model.NewBoolVar(f'task{t}_slot{s}')

    # Each task assigned to exactly one slot
    for t in range(tasks):
        model.AddExactlyOne([task_slot[(t, s)] for s in range(slots)])

    # Slot 0 can have at most 1 task
    model.Add(sum(task_slot[(t, 0)] for t in range(tasks)) <= 1)

    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    assert status == cp_model.OPTIMAL or status == cp_model.FEASIBLE

    # Count assignments per slot
    slot_counts = [0, 0]
    for t in range(tasks):
        for s in range(slots):
            if solver.Value(task_slot[(t, s)]):
                slot_counts[s] += 1

    assert slot_counts[0] <= 1, "Slot 0 should have at most 1 task"
    assert sum(slot_counts) == tasks, "All tasks should be assigned"

    print(f"Slot assignments: slot0={slot_counts[0]}, slot1={slot_counts[1]}")


if __name__ == "__main__":
    print("Running OR-Tools CP-SAT verification tests...\n")

    print("Test 1: Simple integer constraint")
    test_cpsat_simple_constraint()
    print("✓ Passed\n")

    print("Test 2: Boolean satisfiability")
    test_cpsat_boolean_satisfiability()
    print("✓ Passed\n")

    print("All verification tests passed! OR-Tools is working correctly.")
