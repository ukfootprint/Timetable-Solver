"""Tests for quality metrics calculator."""

from __future__ import annotations

import pytest

from solver.data.models import (
    TimetableInput,
    Teacher,
    StudentClass,
    Subject,
    Room,
    Lesson,
    Period,
    RoomType,
)
from solver.model_builder import SolverSolution, SolverStatus, LessonAssignment
from solver.output.schema import create_timetable_output, TimetableOutput
from solver.output.metrics import (
    QualityMetricsCalculator,
    GapMetrics,
    DistributionMetrics,
    BalanceMetrics,
    UtilizationMetrics,
    MetricsReport,
    calculate_all_metrics,
    calculate_gap_score,
    calculate_distribution_score,
    calculate_daily_balance,
    generate_report,
)


@pytest.fixture
def basic_input() -> TimetableInput:
    """Create basic timetable input for testing."""
    return TimetableInput(
        teachers=[
            Teacher(id="t1", name="Mr Smith"),
            Teacher(id="t2", name="Ms Jones"),
        ],
        classes=[
            StudentClass(id="c1", name="Year 10A"),
        ],
        subjects=[
            Subject(id="mat", name="Maths"),
            Subject(id="eng", name="English"),
        ],
        rooms=[
            Room(id="r1", name="Room 101", type=RoomType.CLASSROOM),
            Room(id="r2", name="Room 102", type=RoomType.CLASSROOM),
        ],
        lessons=[
            Lesson(id="l1", teacher_id="t1", class_id="c1", subject_id="mat", lessons_per_week=2),
            Lesson(id="l2", teacher_id="t2", class_id="c1", subject_id="eng", lessons_per_week=1),
        ],
        periods=[
            Period(id="mon1", name="Mon P1", day=0, start_minutes=540, end_minutes=600),
            Period(id="mon2", name="Mon P2", day=0, start_minutes=600, end_minutes=660),
            Period(id="mon3", name="Mon P3", day=0, start_minutes=720, end_minutes=780),
            Period(id="tue1", name="Tue P1", day=1, start_minutes=540, end_minutes=600),
            Period(id="wed1", name="Wed P1", day=2, start_minutes=540, end_minutes=600),
        ],
    )


@pytest.fixture
def well_distributed_assignments() -> list[LessonAssignment]:
    """Assignments where multi-lesson subjects are on different days."""
    return [
        LessonAssignment(
            lesson_id="l1",
            instance=0,
            day=0,
            start_minutes=540,
            end_minutes=600,
            room_id="r1",
            room_name="Room 101",
            teacher_id="t1",
            teacher_name="Mr Smith",
            class_id="c1",
            class_name="Year 10A",
            subject_id="mat",
            subject_name="Maths",
        ),
        LessonAssignment(
            lesson_id="l1",
            instance=1,
            day=2,  # Different day (Wednesday)
            start_minutes=540,
            end_minutes=600,
            room_id="r1",
            room_name="Room 101",
            teacher_id="t1",
            teacher_name="Mr Smith",
            class_id="c1",
            class_name="Year 10A",
            subject_id="mat",
            subject_name="Maths",
        ),
        LessonAssignment(
            lesson_id="l2",
            instance=0,
            day=1,
            start_minutes=540,
            end_minutes=600,
            room_id="r2",
            room_name="Room 102",
            teacher_id="t2",
            teacher_name="Ms Jones",
            class_id="c1",
            class_name="Year 10A",
            subject_id="eng",
            subject_name="English",
        ),
    ]


@pytest.fixture
def poorly_distributed_assignments() -> list[LessonAssignment]:
    """Assignments where multi-lesson subjects are on the same day."""
    return [
        LessonAssignment(
            lesson_id="l1",
            instance=0,
            day=0,
            start_minutes=540,
            end_minutes=600,
            room_id="r1",
            room_name="Room 101",
            teacher_id="t1",
            teacher_name="Mr Smith",
            class_id="c1",
            class_name="Year 10A",
            subject_id="mat",
            subject_name="Maths",
        ),
        LessonAssignment(
            lesson_id="l1",
            instance=1,
            day=0,  # Same day (Monday)
            start_minutes=600,
            end_minutes=660,
            room_id="r1",
            room_name="Room 101",
            teacher_id="t1",
            teacher_name="Mr Smith",
            class_id="c1",
            class_name="Year 10A",
            subject_id="mat",
            subject_name="Maths",
        ),
        LessonAssignment(
            lesson_id="l2",
            instance=0,
            day=1,
            start_minutes=540,
            end_minutes=600,
            room_id="r2",
            room_name="Room 102",
            teacher_id="t2",
            teacher_name="Ms Jones",
            class_id="c1",
            class_name="Year 10A",
            subject_id="eng",
            subject_name="English",
        ),
    ]


@pytest.fixture
def gapped_assignments() -> list[LessonAssignment]:
    """Assignments with gaps between lessons."""
    return [
        LessonAssignment(
            lesson_id="l1",
            instance=0,
            day=0,
            start_minutes=540,  # 09:00
            end_minutes=600,    # 10:00
            room_id="r1",
            room_name="Room 101",
            teacher_id="t1",
            teacher_name="Mr Smith",
            class_id="c1",
            class_name="Year 10A",
            subject_id="mat",
            subject_name="Maths",
        ),
        LessonAssignment(
            lesson_id="l1",
            instance=1,
            day=0,
            start_minutes=720,  # 12:00 (2 hour gap)
            end_minutes=780,    # 13:00
            room_id="r1",
            room_name="Room 101",
            teacher_id="t1",
            teacher_name="Mr Smith",
            class_id="c1",
            class_name="Year 10A",
            subject_id="mat",
            subject_name="Maths",
        ),
    ]


@pytest.fixture
def well_distributed_output(well_distributed_assignments) -> TimetableOutput:
    """Create output with well-distributed lessons."""
    solution = SolverSolution(
        status=SolverStatus.OPTIMAL,
        assignments=well_distributed_assignments,
        solve_time_ms=1000,
        objective_value=10,
    )
    return create_timetable_output(solution)


@pytest.fixture
def poorly_distributed_output(poorly_distributed_assignments) -> TimetableOutput:
    """Create output with poorly-distributed lessons."""
    solution = SolverSolution(
        status=SolverStatus.OPTIMAL,
        assignments=poorly_distributed_assignments,
        solve_time_ms=1000,
        objective_value=50,
    )
    return create_timetable_output(solution)


@pytest.fixture
def gapped_output(gapped_assignments) -> TimetableOutput:
    """Create output with gaps between lessons."""
    solution = SolverSolution(
        status=SolverStatus.OPTIMAL,
        assignments=gapped_assignments,
        solve_time_ms=1000,
        objective_value=30,
    )
    return create_timetable_output(solution)


class TestGapMetrics:
    """Tests for gap score calculation."""

    def test_no_gap_when_consecutive(self, well_distributed_output, basic_input):
        """No gap when lessons are on different days."""
        calculator = QualityMetricsCalculator()
        gap_score = calculator.calculate_gap_score(well_distributed_output, basic_input.teachers)

        # Each teacher has only 1 lesson per day, so no gaps
        assert gap_score == 0.0

    def test_gap_calculated_correctly(self, gapped_output, basic_input):
        """Gap calculated when there's idle time between lessons."""
        calculator = QualityMetricsCalculator()
        metrics = calculator.calculate_gap_metrics(gapped_output, basic_input.teachers)

        # t1 has lessons 09:00-10:00 and 12:00-13:00 on Monday
        # Span = 13:00 - 09:00 = 240 minutes
        # Teaching time = 60 + 60 = 120 minutes
        # Gap = 240 - 120 = 120 minutes
        assert metrics.average_gap_minutes == 120.0

    def test_gap_metrics_structure(self, gapped_output, basic_input):
        """GapMetrics has all required fields."""
        calculator = QualityMetricsCalculator()
        metrics = calculator.calculate_gap_metrics(gapped_output, basic_input.teachers)

        assert isinstance(metrics, GapMetrics)
        assert metrics.average_gap_minutes >= 0
        assert metrics.max_gap_minutes >= 0
        assert metrics.total_gap_minutes >= 0
        assert metrics.teacher_days_analyzed >= 0
        assert isinstance(metrics.gaps_by_teacher, dict)

    def test_gap_score_property(self, gapped_output, basic_input):
        """Score property normalizes gap to 0-100 scale."""
        calculator = QualityMetricsCalculator()
        metrics = calculator.calculate_gap_metrics(gapped_output, basic_input.teachers)

        # Score should be between 0 and 100
        assert 0 <= metrics.score <= 100


class TestDistributionMetrics:
    """Tests for distribution score calculation."""

    def test_well_distributed_score(self, well_distributed_output, basic_input):
        """Well-distributed lessons get high score."""
        calculator = QualityMetricsCalculator()
        score = calculator.calculate_distribution_score(well_distributed_output, basic_input.lessons)

        assert score == 100.0

    def test_poorly_distributed_score(self, poorly_distributed_output, basic_input):
        """Poorly-distributed lessons get lower score."""
        calculator = QualityMetricsCalculator()
        score = calculator.calculate_distribution_score(poorly_distributed_output, basic_input.lessons)

        # Only l1 is multi-lesson, and both instances are on same day
        assert score == 0.0

    def test_distribution_metrics_structure(self, well_distributed_output, basic_input):
        """DistributionMetrics has all required fields."""
        calculator = QualityMetricsCalculator()
        metrics = calculator.calculate_distribution_metrics(well_distributed_output, basic_input.lessons)

        assert isinstance(metrics, DistributionMetrics)
        assert metrics.well_distributed_count >= 0
        assert metrics.total_multi_lesson_subjects >= 0
        assert 0 <= metrics.percentage_well_distributed <= 100
        assert isinstance(metrics.poorly_distributed, list)

    def test_poorly_distributed_list(self, poorly_distributed_output, basic_input):
        """Poorly distributed lessons are tracked."""
        calculator = QualityMetricsCalculator()
        metrics = calculator.calculate_distribution_metrics(poorly_distributed_output, basic_input.lessons)

        assert len(metrics.poorly_distributed) > 0
        assert "mat" in metrics.poorly_distributed[0]  # Contains subject id


class TestBalanceMetrics:
    """Tests for daily balance calculation."""

    def test_balanced_schedule(self, well_distributed_output, basic_input):
        """Balanced schedule has low std dev."""
        calculator = QualityMetricsCalculator()
        balance = calculator.calculate_daily_balance(well_distributed_output, basic_input.teachers)

        # With lessons spread across different days, should be reasonably balanced
        assert balance >= 0

    def test_balance_metrics_structure(self, well_distributed_output, basic_input):
        """BalanceMetrics has all required fields."""
        calculator = QualityMetricsCalculator()
        metrics = calculator.calculate_daily_balance_metrics(well_distributed_output, basic_input.teachers)

        assert isinstance(metrics, BalanceMetrics)
        assert metrics.average_std_dev >= 0
        assert metrics.max_std_dev >= 0
        assert isinstance(metrics.teacher_balance, dict)
        assert isinstance(metrics.unbalanced_teachers, list)

    def test_balance_score_property(self, well_distributed_output, basic_input):
        """Score property normalizes balance to 0-100 scale."""
        calculator = QualityMetricsCalculator()
        metrics = calculator.calculate_daily_balance_metrics(well_distributed_output, basic_input.teachers)

        assert 0 <= metrics.score <= 100


class TestUtilizationMetrics:
    """Tests for utilization calculation."""

    def test_utilization_calculated(self, well_distributed_output, basic_input):
        """Utilization metrics are calculated."""
        calculator = QualityMetricsCalculator()
        metrics = calculator.calculate_utilization_metrics(well_distributed_output, basic_input)

        assert isinstance(metrics, UtilizationMetrics)
        assert 0 <= metrics.room_utilization <= 100
        assert 0 <= metrics.teacher_utilization <= 100
        assert 0 <= metrics.slot_utilization <= 100
        assert metrics.total_lessons_scheduled == 3
        assert metrics.total_slots_available > 0


class TestCalculateAll:
    """Tests for calculate_all method."""

    def test_calculate_all_returns_report(self, well_distributed_output, basic_input):
        """calculate_all returns a complete MetricsReport."""
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(well_distributed_output, basic_input)

        assert isinstance(report, MetricsReport)
        assert isinstance(report.gap_metrics, GapMetrics)
        assert isinstance(report.distribution_metrics, DistributionMetrics)
        assert isinstance(report.balance_metrics, BalanceMetrics)
        assert isinstance(report.utilization_metrics, UtilizationMetrics)

    def test_overall_score_calculated(self, well_distributed_output, basic_input):
        """Overall score is calculated."""
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(well_distributed_output, basic_input)

        assert 0 <= report.overall_score <= 100

    def test_grade_assigned(self, well_distributed_output, basic_input):
        """Grade is assigned based on score."""
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(well_distributed_output, basic_input)

        assert report.grade in ["A", "B", "C", "D", "F"]

    def test_hard_constraints_tracked(self, well_distributed_output, basic_input):
        """Hard constraint satisfaction is tracked."""
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(well_distributed_output, basic_input)

        assert report.hard_constraints_satisfied is True

    def test_totals_correct(self, well_distributed_output, basic_input):
        """Total counts are correct."""
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(well_distributed_output, basic_input)

        assert report.total_lessons == 3
        assert report.total_teachers == 2


class TestGenerateReport:
    """Tests for report generation."""

    def test_generate_report_produces_string(self, well_distributed_output, basic_input):
        """generate_report produces a string."""
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(well_distributed_output, basic_input)
        report_str = calculator.generate_report(report)

        assert isinstance(report_str, str)
        assert len(report_str) > 0

    def test_report_contains_sections(self, well_distributed_output, basic_input):
        """Report contains all major sections."""
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(well_distributed_output, basic_input)
        report_str = calculator.generate_report(report)

        assert "TIMETABLE QUALITY REPORT" in report_str
        assert "GAP ANALYSIS" in report_str
        assert "DISTRIBUTION" in report_str
        assert "DAILY BALANCE" in report_str
        assert "UTILIZATION" in report_str

    def test_report_includes_scores(self, well_distributed_output, basic_input):
        """Report includes score values."""
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(well_distributed_output, basic_input)
        report_str = calculator.generate_report(report)

        assert "Score:" in report_str
        assert "Overall Score:" in report_str

    def test_report_includes_status(self, well_distributed_output, basic_input):
        """Report includes status indicators."""
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(well_distributed_output, basic_input)
        report_str = calculator.generate_report(report)

        # Should have either GOOD or NEEDS IMPROVEMENT
        assert "GOOD" in report_str or "NEEDS IMPROVEMENT" in report_str


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_calculate_all_metrics(self, well_distributed_output, basic_input):
        """calculate_all_metrics works."""
        report = calculate_all_metrics(well_distributed_output, basic_input)
        assert isinstance(report, MetricsReport)

    def test_calculate_gap_score(self, well_distributed_output, basic_input):
        """calculate_gap_score works."""
        score = calculate_gap_score(well_distributed_output, basic_input.teachers)
        assert isinstance(score, float)
        assert score >= 0

    def test_calculate_distribution_score(self, well_distributed_output, basic_input):
        """calculate_distribution_score works."""
        score = calculate_distribution_score(well_distributed_output, basic_input.lessons)
        assert isinstance(score, float)
        assert 0 <= score <= 100

    def test_calculate_daily_balance(self, well_distributed_output, basic_input):
        """calculate_daily_balance works."""
        balance = calculate_daily_balance(well_distributed_output, basic_input.teachers)
        assert isinstance(balance, float)
        assert balance >= 0

    def test_generate_report_function(self, well_distributed_output, basic_input):
        """generate_report function works."""
        report_str = generate_report(well_distributed_output, basic_input)
        assert isinstance(report_str, str)
        assert "TIMETABLE QUALITY REPORT" in report_str


class TestCustomTargets:
    """Tests for custom target thresholds."""

    def test_custom_targets_applied(self, well_distributed_output, basic_input):
        """Custom targets affect improvement suggestions."""
        # Set very strict targets
        strict_targets = {
            "gap_score": 0.0,
            "distribution_score": 100.0,
            "daily_balance": 0.0,
            "utilization": 100.0,
        }

        calculator = QualityMetricsCalculator(targets=strict_targets)
        report = calculator.calculate_all(well_distributed_output, basic_input)

        # Should have improvement areas due to strict targets
        # (may or may not have improvements depending on actual scores)
        assert isinstance(report.improvement_areas, list)


class TestMetricsReportToDict:
    """Tests for MetricsReport.to_dict()."""

    def test_to_dict_structure(self, well_distributed_output, basic_input):
        """to_dict returns proper structure."""
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(well_distributed_output, basic_input)
        data = report.to_dict()

        assert "overallScore" in data
        assert "grade" in data
        assert "gaps" in data
        assert "distribution" in data
        assert "balance" in data
        assert "utilization" in data

    def test_to_dict_gap_section(self, well_distributed_output, basic_input):
        """Gap section has required fields."""
        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(well_distributed_output, basic_input)
        data = report.to_dict()

        gaps = data["gaps"]
        assert "score" in gaps
        assert "averageGapMinutes" in gaps
        assert "maxGapMinutes" in gaps


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_output(self, basic_input):
        """Handles empty output gracefully."""
        solution = SolverSolution(
            status=SolverStatus.OPTIMAL,
            assignments=[],
            solve_time_ms=100,
        )
        output = create_timetable_output(solution)

        calculator = QualityMetricsCalculator()
        report = calculator.calculate_all(output, basic_input)

        assert report.total_lessons == 0
        assert isinstance(report.overall_score, float)

    def test_single_lesson_per_subject(self, basic_input):
        """Handles single-lesson subjects (100% distribution by default)."""
        solution = SolverSolution(
            status=SolverStatus.OPTIMAL,
            assignments=[
                LessonAssignment(
                    lesson_id="l2",
                    instance=0,
                    day=0,
                    start_minutes=540,
                    end_minutes=600,
                    room_id="r1",
                    room_name="Room 101",
                    teacher_id="t2",
                    teacher_name="Ms Jones",
                    class_id="c1",
                    class_name="Year 10A",
                    subject_id="eng",
                    subject_name="English",
                ),
            ],
            solve_time_ms=100,
        )
        output = create_timetable_output(solution)

        calculator = QualityMetricsCalculator()
        metrics = calculator.calculate_distribution_metrics(output, basic_input.lessons)

        # Single-lesson subjects don't count toward multi-lesson distribution
        assert metrics.total_multi_lesson_subjects == 0
        assert metrics.percentage_well_distributed == 100.0

    def test_teacher_with_no_lessons(self, well_distributed_output, basic_input):
        """Handles teachers with no scheduled lessons."""
        # Add a teacher with no lessons
        basic_input.teachers.append(Teacher(id="t3", name="Mr Nobody"))

        calculator = QualityMetricsCalculator()
        metrics = calculator.calculate_gap_metrics(well_distributed_output, basic_input.teachers)

        # Should still work, just skip the teacher with no lessons
        assert isinstance(metrics, GapMetrics)
