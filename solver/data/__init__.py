"""Data loading utilities."""

from .loader import load_school_data, validate_school_data
from .generator import (
    GeneratorConfig,
    generate_sample_school,
    generate_small_school,
    generate_medium_school,
    generate_large_school,
    save_generated_school,
    get_generation_stats,
)

__all__ = [
    # Loader
    "load_school_data",
    "validate_school_data",
    # Generator
    "GeneratorConfig",
    "generate_sample_school",
    "generate_small_school",
    "generate_medium_school",
    "generate_large_school",
    "save_generated_school",
    "get_generation_stats",
]
