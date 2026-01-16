"""
Entry point for running solver as a module.

Usage:
    python -m solver solve input.json -o output.json
    python -m solver validate input.json
    python -m solver view output.json --teacher T001
    python -m solver metrics output.json
"""

from solver.cli import main

if __name__ == "__main__":
    main()
