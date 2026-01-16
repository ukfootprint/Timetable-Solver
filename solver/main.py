"""Entry point for the timetable solver."""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .data.loader import load_school_data
from .model import TimetableModel
from .output.formatter import format_solution


def solve_timetable(data_path: str, output_path: Optional[str] = None, time_limit: int = 60) -> dict:
    """
    Solve a timetabling problem.

    Args:
        data_path: Path to the school data JSON file
        output_path: Optional path to write the solution
        time_limit: Maximum solving time in seconds

    Returns:
        Solution dictionary with assignments and metadata
    """
    # Load school data
    school_data = load_school_data(data_path)

    # Build and solve the model
    model = TimetableModel(school_data)
    model.build()
    solution = model.solve(time_limit=time_limit)

    # Format the solution
    result = format_solution(solution, school_data)

    # Write output if path provided
    if output_path:
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Solution written to {output_path}")

    return result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Solve school timetabling problems using CP-SAT"
    )
    parser.add_argument(
        "data",
        help="Path to school data JSON file"
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to write solution JSON"
    )
    parser.add_argument(
        "-t", "--time-limit",
        type=int,
        default=60,
        help="Maximum solving time in seconds (default: 60)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    if not Path(args.data).exists():
        print(f"Error: Data file not found: {args.data}", file=sys.stderr)
        sys.exit(1)

    try:
        result = solve_timetable(args.data, args.output, args.time_limit)

        if result["status"] == "OPTIMAL":
            print(f"✓ Optimal solution found")
        elif result["status"] == "FEASIBLE":
            print(f"✓ Feasible solution found (may not be optimal)")
        else:
            print(f"✗ No solution found: {result['status']}")
            sys.exit(1)

        print(f"  Assignments: {len(result['assignments'])}")
        print(f"  Solve time: {result['solve_time_ms']}ms")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
