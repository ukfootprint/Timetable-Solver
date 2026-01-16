"""Solution output formatting."""

from .formatter import format_solution, format_timetable_grid
from .schema import (
    OutputStatus,
    LessonOutput,
    QualityMetrics,
    DaySchedule,
    EntitySchedule,
    TimetableViews,
    Timetable,
    TimetableOutput,
    create_timetable_output,
    solution_to_json,
    solution_to_dict,
)
from .extractor import (
    SolutionExtractor,
    extract_solution,
    extract_to_json,
    extract_to_dict,
    minutes_to_time_string,
    week_minutes_to_day_time,
    group_by_teacher,
    group_by_class,
    group_by_room,
    group_by_day,
    sort_lessons,
)
from .formatters import (
    # Formatter classes
    JSONFormatter,
    CSVFormatter,
    ConsoleFormatter,
    TeacherViewFormatter,
    ClassViewFormatter,
    WeekGridFormatter,
    # Convenience functions
    format_json,
    format_csv,
    format_console,
    print_console,
    format_teacher_view,
    format_all_teachers,
    format_class_view,
    format_all_classes,
    format_week_grid,
    # File utilities
    save_json,
    save_csv,
    save_teacher_views,
    save_class_views,
    # Constants
    DAY_NAMES,
    DAY_ABBREV,
    RICH_AVAILABLE,
)
from .metrics import (
    # Data classes
    GapMetrics,
    DistributionMetrics,
    BalanceMetrics,
    UtilizationMetrics,
    MetricsReport,
    # Calculator class
    QualityMetricsCalculator,
    # Convenience functions
    calculate_all_metrics,
    calculate_gap_score,
    calculate_distribution_score,
    calculate_daily_balance,
    generate_report,
)

__all__ = [
    # Formatter
    "format_solution",
    "format_timetable_grid",
    # Schema models
    "OutputStatus",
    "LessonOutput",
    "QualityMetrics",
    "DaySchedule",
    "EntitySchedule",
    "TimetableViews",
    "Timetable",
    "TimetableOutput",
    # Schema conversion functions
    "create_timetable_output",
    "solution_to_json",
    "solution_to_dict",
    # Extractor
    "SolutionExtractor",
    "extract_solution",
    "extract_to_json",
    "extract_to_dict",
    # Helper functions
    "minutes_to_time_string",
    "week_minutes_to_day_time",
    "group_by_teacher",
    "group_by_class",
    "group_by_room",
    "group_by_day",
    "sort_lessons",
    # Formatter classes
    "JSONFormatter",
    "CSVFormatter",
    "ConsoleFormatter",
    "TeacherViewFormatter",
    "ClassViewFormatter",
    "WeekGridFormatter",
    # Formatter convenience functions
    "format_json",
    "format_csv",
    "format_console",
    "print_console",
    "format_teacher_view",
    "format_all_teachers",
    "format_class_view",
    "format_all_classes",
    "format_week_grid",
    # File utilities
    "save_json",
    "save_csv",
    "save_teacher_views",
    "save_class_views",
    # Constants
    "DAY_NAMES",
    "DAY_ABBREV",
    "RICH_AVAILABLE",
    # Metrics data classes
    "GapMetrics",
    "DistributionMetrics",
    "BalanceMetrics",
    "UtilizationMetrics",
    "MetricsReport",
    # Metrics calculator
    "QualityMetricsCalculator",
    # Metrics convenience functions
    "calculate_all_metrics",
    "calculate_gap_score",
    "calculate_distribution_score",
    "calculate_daily_balance",
    "generate_report",
]
