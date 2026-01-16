"""AI Timetabler Solver - CP-SAT based school timetabling."""

from .model import TimetableModel
from .main import solve_timetable
from .model_builder import TimetableModelBuilder, SolverSolution, SolverStatus
from .cli import app as cli_app

__all__ = [
    # Legacy API
    "TimetableModel",
    "solve_timetable",
    # Modern API
    "TimetableModelBuilder",
    "SolverSolution",
    "SolverStatus",
    # CLI
    "cli_app",
]
