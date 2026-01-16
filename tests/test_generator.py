"""Tests for sample data generator."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from solver.data.generator import (
    GeneratorConfig,
    generate_sample_school,
    generate_small_school,
    generate_medium_school,
    generate_large_school,
    save_generated_school,
    get_generation_stats,
)
from solver.data.models import (
    TimetableInput,
    RoomType,
)


class TestGeneratorConfig:
    """Tests for GeneratorConfig."""

    def test_default_config(self):
        """Default config has expected values."""
        config = GeneratorConfig()

        assert config.num_teachers == 20
        assert config.num_classes == 15
        assert config.num_rooms == 15  # Updated for feasibility
        assert config.lessons_per_class_per_week == 18  # Updated for feasibility

    def test_custom_config(self):
        """Custom config values are applied."""
        config = GeneratorConfig(
            num_teachers=50,
            num_classes=40,
            num_rooms=20,
        )

        assert config.num_teachers == 50
        assert config.num_classes == 40
        assert config.num_rooms == 20

    def test_seed_makes_reproducible(self):
        """Same seed produces same data."""
        config1 = GeneratorConfig(seed=42, num_teachers=5)
        config2 = GeneratorConfig(seed=42, num_teachers=5)

        school1 = generate_sample_school(config1)
        school2 = generate_sample_school(config2)

        # Same seed should produce same teacher names
        assert school1.teachers[0].name == school2.teachers[0].name
        assert school1.teachers[0].subjects == school2.teachers[0].subjects


class TestGenerateSampleSchool:
    """Tests for generate_sample_school function."""

    def test_generates_valid_timetable_input(self):
        """Generated data is valid TimetableInput."""
        school = generate_sample_school(GeneratorConfig(seed=42))

        assert isinstance(school, TimetableInput)
        # Should pass Pydantic validation

    def test_generates_teachers(self):
        """Generates correct number of teachers."""
        config = GeneratorConfig(num_teachers=10, seed=42)
        school = generate_sample_school(config)

        assert len(school.teachers) == 10

    def test_teachers_have_subjects(self):
        """All teachers have assigned subjects."""
        config = GeneratorConfig(num_teachers=10, seed=42)
        school = generate_sample_school(config)

        for teacher in school.teachers:
            assert len(teacher.subjects) >= config.teacher_min_subjects
            assert len(teacher.subjects) <= config.teacher_max_subjects

    def test_teachers_have_unique_ids(self):
        """All teachers have unique IDs."""
        school = generate_sample_school(GeneratorConfig(seed=42))
        ids = [t.id for t in school.teachers]
        assert len(ids) == len(set(ids))

    def test_generates_classes(self):
        """Generates correct number of classes."""
        config = GeneratorConfig(num_classes=8, seed=42)
        school = generate_sample_school(config)

        assert len(school.classes) == 8

    def test_classes_have_year_groups(self):
        """Classes are distributed across year groups."""
        config = GeneratorConfig(num_classes=10, year_groups=[7, 8, 9, 10], seed=42)
        school = generate_sample_school(config)

        year_groups = set(c.year_group for c in school.classes)
        assert len(year_groups) > 1  # Multiple year groups represented

    def test_generates_rooms(self):
        """Generates correct number of rooms."""
        config = GeneratorConfig(num_rooms=12, seed=42)
        school = generate_sample_school(config)

        assert len(school.rooms) == 12

    def test_includes_specialist_rooms(self):
        """Includes specialist rooms when subjects require them."""
        config = GeneratorConfig(include_specialist_subjects=True, seed=42)
        school = generate_sample_school(config)

        room_types = set(r.type for r in school.rooms)
        assert RoomType.CLASSROOM in room_types
        # Should have at least some specialist rooms
        assert len(room_types) > 1

    def test_generates_lessons(self):
        """Generates lessons for all classes."""
        config = GeneratorConfig(num_classes=5, seed=42)
        school = generate_sample_school(config)

        assert len(school.lessons) > 0

        # Each class should have lessons
        class_ids_with_lessons = set(l.class_id for l in school.lessons)
        assert len(class_ids_with_lessons) == len(school.classes)

    def test_lessons_reference_valid_teachers(self):
        """All lessons reference existing teachers."""
        school = generate_sample_school(GeneratorConfig(seed=42))

        teacher_ids = set(t.id for t in school.teachers)
        for lesson in school.lessons:
            assert lesson.teacher_id in teacher_ids

    def test_lessons_reference_valid_subjects(self):
        """All lessons reference existing subjects."""
        school = generate_sample_school(GeneratorConfig(seed=42))

        subject_ids = set(s.id for s in school.subjects)
        for lesson in school.lessons:
            assert lesson.subject_id in subject_ids

    def test_generates_periods(self):
        """Generates period structure."""
        config = GeneratorConfig(num_days=5, periods_per_day=6, seed=42)
        school = generate_sample_school(config)

        assert len(school.periods) == 5 * 6

    def test_periods_cover_all_days(self):
        """Periods exist for all days."""
        config = GeneratorConfig(num_days=5, seed=42)
        school = generate_sample_school(config)

        days = set(p.day for p in school.periods)
        assert days == {0, 1, 2, 3, 4}

    def test_school_config_set(self):
        """School config is properly set."""
        school = generate_sample_school(GeneratorConfig(seed=42))

        assert school.config.school_name == "Generated Test School"
        assert school.config.academic_year == "2024-2025"


class TestGenerateSmallSchool:
    """Tests for generate_small_school function."""

    def test_generates_small_school(self):
        """Generates a small school for testing."""
        school = generate_small_school(seed=42)

        assert len(school.teachers) == 10
        assert len(school.classes) == 8
        # Rooms may exceed config.num_rooms if specialist rooms are required
        assert len(school.rooms) >= 6

    def test_small_school_is_valid(self):
        """Small school passes validation."""
        school = generate_small_school(seed=42)

        # Should not raise validation errors
        assert isinstance(school, TimetableInput)

    def test_small_school_has_reasonable_lesson_count(self):
        """Small school has manageable lesson count."""
        school = generate_small_school(seed=42)

        total_instances = sum(l.lessons_per_week for l in school.lessons)
        # Should be under 300 for quick solving
        assert total_instances < 300


class TestGenerateMediumSchool:
    """Tests for generate_medium_school function."""

    def test_generates_medium_school(self):
        """Generates a medium school."""
        school = generate_medium_school(seed=42)

        assert len(school.teachers) == 25
        assert len(school.classes) == 20
        assert len(school.rooms) >= 18  # Updated for feasibility

    def test_medium_school_is_valid(self):
        """Medium school passes validation."""
        school = generate_medium_school(seed=42)

        assert isinstance(school, TimetableInput)


class TestGenerateLargeSchool:
    """Tests for generate_large_school function."""

    def test_generates_large_school(self):
        """Generates a large school for stress testing."""
        school = generate_large_school(seed=42)

        assert len(school.teachers) == 80
        assert len(school.classes) == 60
        assert len(school.rooms) >= 60  # Updated for feasibility

    def test_large_school_is_valid(self):
        """Large school passes validation."""
        school = generate_large_school(seed=42)

        assert isinstance(school, TimetableInput)

    def test_large_school_has_many_lessons(self):
        """Large school has many lesson instances."""
        school = generate_large_school(seed=42)

        total_instances = sum(l.lessons_per_week for l in school.lessons)
        # Should be 1000+ for stress testing
        assert total_instances > 1000


class TestSaveGeneratedSchool:
    """Tests for save_generated_school function."""

    def test_saves_valid_json(self):
        """Saves valid JSON file."""
        school = generate_small_school(seed=42)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_school.json"
            save_generated_school(school, str(filepath))

            assert filepath.exists()

            with open(filepath) as f:
                data = json.load(f)

            assert "teachers" in data
            assert "classes" in data
            assert "subjects" in data
            assert "rooms" in data
            assert "lessons" in data
            assert "periods" in data

    def test_saved_file_has_correct_counts(self):
        """Saved file has correct entity counts."""
        school = generate_small_school(seed=42)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_school.json"
            save_generated_school(school, str(filepath))

            with open(filepath) as f:
                data = json.load(f)

            assert len(data["teachers"]) == len(school.teachers)
            assert len(data["classes"]) == len(school.classes)
            assert len(data["rooms"]) == len(school.rooms)

    def test_creates_parent_directories(self):
        """Creates parent directories if needed."""
        school = generate_small_school(seed=42)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "subdir" / "test_school.json"
            save_generated_school(school, str(filepath))

            assert filepath.exists()


class TestGetGenerationStats:
    """Tests for get_generation_stats function."""

    def test_returns_stats_dict(self):
        """Returns dictionary with stats."""
        school = generate_small_school(seed=42)
        stats = get_generation_stats(school)

        assert isinstance(stats, dict)
        assert "teachers" in stats
        assert "classes" in stats
        assert "subjects" in stats
        assert "rooms" in stats
        assert "lessons" in stats
        assert "lesson_instances" in stats

    def test_stats_match_school(self):
        """Stats match actual school data."""
        school = generate_small_school(seed=42)
        stats = get_generation_stats(school)

        assert stats["teachers"] == len(school.teachers)
        assert stats["classes"] == len(school.classes)
        assert stats["subjects"] == len(school.subjects)
        assert stats["rooms"] == len(school.rooms)
        assert stats["lessons"] == len(school.lessons)

    def test_calculates_utilization(self):
        """Calculates utilization percentage."""
        school = generate_small_school(seed=42)
        stats = get_generation_stats(school)

        assert "utilization_percent" in stats
        assert 0 <= stats["utilization_percent"] <= 100


class TestDataRealism:
    """Tests for realistic data generation."""

    def test_teacher_names_are_realistic(self):
        """Teacher names look realistic."""
        school = generate_sample_school(GeneratorConfig(num_teachers=10, seed=42))

        for teacher in school.teachers:
            # Name should have first and last name
            parts = teacher.name.split()
            assert len(parts) >= 2

    def test_subjects_have_colors(self):
        """Subjects have color codes."""
        school = generate_sample_school(GeneratorConfig(seed=42))

        for subject in school.subjects:
            assert subject.color is not None
            assert subject.color.startswith("#")

    def test_science_requires_lab(self):
        """Science subject requires science lab."""
        school = generate_sample_school(GeneratorConfig(seed=42))

        science = next((s for s in school.subjects if s.id == "sci"), None)
        if science:
            assert science.requires_specialist_room
            assert science.required_room_type == RoomType.SCIENCE_LAB

    def test_pe_requires_gym(self):
        """PE subject requires gym."""
        school = generate_sample_school(GeneratorConfig(include_specialist_subjects=True, seed=42))

        pe = next((s for s in school.subjects if s.id == "pe"), None)
        if pe:
            assert pe.requires_specialist_room
            assert pe.required_room_type == RoomType.GYM

    def test_class_names_follow_pattern(self):
        """Class names follow Year X pattern."""
        school = generate_sample_school(GeneratorConfig(seed=42))

        for cls in school.classes:
            assert "Year" in cls.name

    def test_rooms_have_capacity(self):
        """All rooms have capacity set."""
        school = generate_sample_school(GeneratorConfig(seed=42))

        for room in school.rooms:
            assert room.capacity is not None
            assert room.capacity > 0


class TestEdgeCases:
    """Tests for edge cases."""

    def test_minimal_config(self):
        """Can generate with minimal config."""
        config = GeneratorConfig(
            num_teachers=2,
            num_classes=2,
            num_rooms=2,
            lessons_per_class_per_week=5,
            include_specialist_subjects=False,  # Avoid specialist room requirements
            seed=42,
        )
        school = generate_sample_school(config)

        assert len(school.teachers) == 2
        assert len(school.classes) == 2

    def test_no_specialist_subjects(self):
        """Can generate without specialist subjects."""
        config = GeneratorConfig(
            include_specialist_subjects=False,
            seed=42,
        )
        school = generate_sample_school(config)

        # Should only have core subjects
        assert len(school.subjects) == 5  # 5 core subjects

    def test_single_year_group(self):
        """Can generate with single year group."""
        config = GeneratorConfig(
            year_groups=[7],
            num_classes=4,
            seed=42,
        )
        school = generate_sample_school(config)

        year_groups = set(c.year_group for c in school.classes)
        assert year_groups == {7}

    def test_different_seeds_produce_different_data(self):
        """Different seeds produce different data."""
        config1 = GeneratorConfig(num_teachers=5, seed=1)
        config2 = GeneratorConfig(num_teachers=5, seed=2)

        school1 = generate_sample_school(config1)
        school2 = generate_sample_school(config2)

        # Names should be different with different seeds
        names1 = [t.name for t in school1.teachers]
        names2 = [t.name for t in school2.teachers]
        assert names1 != names2


class TestGeneratedDataCanBeSolved:
    """Tests that generated data produces solvable problems."""

    def test_small_school_has_enough_slots(self):
        """Small school has enough room-period slots for lessons."""
        school = generate_small_school(seed=42)
        stats = get_generation_stats(school)

        # Utilization should be reasonable (not over 100%)
        assert stats["utilization_percent"] < 100

    def test_teachers_can_cover_subjects(self):
        """All subjects have at least one teacher."""
        school = generate_sample_school(GeneratorConfig(seed=42))

        subject_ids = set(s.id for s in school.subjects)
        covered_subjects = set()
        for teacher in school.teachers:
            covered_subjects.update(teacher.subjects)

        # All subjects used in lessons should be covered
        lesson_subjects = set(l.subject_id for l in school.lessons)
        assert lesson_subjects.issubset(covered_subjects)

    def test_specialist_rooms_exist_for_requirements(self):
        """Specialist rooms exist for all required room types."""
        school = generate_sample_school(GeneratorConfig(seed=42))

        # Get required room types from subjects
        required_types = set()
        for subject in school.subjects:
            if subject.required_room_type:
                required_types.add(subject.required_room_type)

        # Get available room types
        available_types = set(r.type for r in school.rooms)

        # All required types should be available
        assert required_types.issubset(available_types)
