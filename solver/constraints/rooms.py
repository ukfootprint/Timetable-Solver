"""
Room assignment and suitability constraints for timetabling.

This module provides constraints for:
- Filtering valid rooms based on type, capacity, and requirements
- Room assignment restrictions using AddAllowedAssignments
- Room no-overlap using optional intervals
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from solver.model_builder import TimetableModelBuilder, LessonInstanceVars
    from solver.data.models import Room, Lesson, RoomRequirement


# =============================================================================
# Statistics
# =============================================================================

@dataclass
class RoomConstraintStats:
    """Statistics about room constraints added."""
    lessons_with_room_type_requirement: int = 0
    lessons_with_capacity_requirement: int = 0
    lessons_with_specific_room: int = 0
    lessons_with_excluded_rooms: int = 0
    room_assignment_constraints: int = 0
    room_no_overlap_constraints: int = 0
    optional_intervals_created: int = 0


# =============================================================================
# Room Suitability
# =============================================================================

@dataclass
class RoomSuitability:
    """Suitability analysis for a room-lesson pair."""
    room_id: str
    room_index: int
    is_valid: bool
    reasons: list[str] = field(default_factory=list)


def get_valid_rooms_for_lesson(
    builder: TimetableModelBuilder,
    lesson: Lesson
) -> list[int]:
    """
    Get list of valid room indices for a lesson.

    Filters rooms based on:
    - Room type requirement (from lesson or subject)
    - Room capacity >= class size
    - Preferred rooms (if specified)
    - Excluded rooms

    Args:
        builder: The model builder with input data
        lesson: The lesson to find rooms for

    Returns:
        List of valid room indices
    """
    valid_indices = []

    # Get class size for capacity check
    student_class = builder.input.get_class(lesson.class_id)
    class_size = student_class.student_count if student_class else None

    # Get subject for room type requirement
    subject = builder.input.get_subject(lesson.subject_id)

    for idx, room in enumerate(builder.input.rooms):
        suitability = _evaluate_room_suitability(
            room, idx, lesson, class_size, subject, builder
        )
        if suitability.is_valid:
            valid_indices.append(idx)

    return valid_indices


def _evaluate_room_suitability(
    room: Room,
    room_index: int,
    lesson: Lesson,
    class_size: int | None,
    subject,
    builder: TimetableModelBuilder
) -> RoomSuitability:
    """
    Evaluate if a room is suitable for a lesson.

    Args:
        room: The room to evaluate
        room_index: Index of room in rooms list
        lesson: The lesson
        class_size: Number of students in the class
        subject: The subject being taught
        builder: The model builder

    Returns:
        RoomSuitability with validity and reasons
    """
    result = RoomSuitability(
        room_id=room.id,
        room_index=room_index,
        is_valid=True
    )

    req = lesson.room_requirement

    # Check excluded rooms
    if req and room.id in req.excluded_rooms:
        result.is_valid = False
        result.reasons.append(f"Room {room.id} is excluded for this lesson")
        return result

    # Check specific room requirement
    if req and req.preferred_rooms:
        # If specific rooms are required, only those are valid
        if room.id not in req.preferred_rooms:
            result.is_valid = False
            result.reasons.append(f"Lesson requires specific rooms: {req.preferred_rooms}")
            return result

    # Check room type requirement
    required_type = _get_required_room_type(lesson, subject)
    if required_type and room.type != required_type:
        result.is_valid = False
        result.reasons.append(f"Requires room type {required_type}, got {room.type}")
        return result

    # Check capacity requirement
    min_capacity = _get_min_capacity(lesson, class_size)
    if min_capacity and room.capacity and room.capacity < min_capacity:
        result.is_valid = False
        result.reasons.append(f"Room capacity {room.capacity} < required {min_capacity}")
        return result

    # Check equipment requirements
    if req and req.requires_equipment:
        room_equipment = set(room.equipment or [])
        required_equipment = set(req.requires_equipment)
        missing = required_equipment - room_equipment
        if missing:
            result.is_valid = False
            result.reasons.append(f"Missing equipment: {missing}")
            return result

    return result


def _get_required_room_type(lesson: Lesson, subject) -> str | None:
    """Get the required room type for a lesson."""
    # First check lesson's explicit requirement
    if lesson.room_requirement and lesson.room_requirement.room_type:
        return lesson.room_requirement.room_type

    # Then check subject's requirement
    if subject and subject.requires_specialist_room:
        return subject.required_room_type

    return None


def _get_min_capacity(lesson: Lesson, class_size: int | None) -> int | None:
    """Get minimum capacity requirement for a lesson."""
    # First check lesson's explicit requirement
    if lesson.room_requirement and lesson.room_requirement.min_capacity:
        return lesson.room_requirement.min_capacity

    # Use class size if available
    return class_size


# =============================================================================
# Room Assignment Constraints
# =============================================================================

def add_room_assignment_constraints(builder: TimetableModelBuilder) -> int:
    """
    Add constraints restricting room_var to valid rooms for each lesson.

    Uses AddAllowedAssignments to restrict room variables to only
    rooms that meet the lesson's requirements.

    Args:
        builder: The timetable model builder with created variables

    Returns:
        Number of constraints added
    """
    constraints_added = 0

    for lesson in builder.input.lessons:
        valid_room_indices = get_valid_rooms_for_lesson(builder, lesson)

        if not valid_room_indices:
            # No valid rooms - this will make the model infeasible
            # Add impossible constraint to signal this
            for inst in builder.lesson_vars.get(lesson.id, []):
                builder.model.Add(inst.room_var == -1)
            continue

        # If all rooms are valid, no need to add constraint
        if len(valid_room_indices) == len(builder.input.rooms):
            continue

        # Restrict room_var to valid rooms using AddAllowedAssignments
        for inst in builder.lesson_vars.get(lesson.id, []):
            builder.model.AddAllowedAssignments(
                [inst.room_var],
                [[idx] for idx in valid_room_indices]
            )
            constraints_added += 1

    return constraints_added


# =============================================================================
# Room No-Overlap with Optional Intervals
# =============================================================================

def add_room_no_overlap_with_optional_intervals(
    builder: TimetableModelBuilder
) -> tuple[int, int]:
    """
    Add room no-overlap constraints using optional intervals.

    For each room:
    1. Create optional intervals for lessons that could use that room
    2. Link the optional interval's presence to (room_var == room_index)
    3. Add NoOverlap on all optional intervals for that room

    Args:
        builder: The timetable model builder with created variables

    Returns:
        Tuple of (num_constraints_added, num_optional_intervals_created)
    """
    constraints_added = 0
    optional_intervals_created = 0

    for room_idx, room in enumerate(builder.input.rooms):
        optional_intervals = []

        for lesson_id, instances in builder.lesson_vars.items():
            lesson = builder.input.get_lesson(lesson_id)
            if not lesson:
                continue

            # Check if this room is valid for this lesson
            valid_rooms = get_valid_rooms_for_lesson(builder, lesson)
            if room_idx not in valid_rooms:
                continue

            for inst in instances:
                # Create boolean: is this lesson instance assigned to this room?
                is_in_room = builder.model.NewBoolVar(
                    f"L{lesson_id}_I{inst.instance}_in_R{room.id}_opt"
                )

                # Link boolean to room_var:
                # is_in_room == True  <=> room_var == room_idx
                builder.model.Add(
                    inst.room_var == room_idx
                ).OnlyEnforceIf(is_in_room)

                builder.model.Add(
                    inst.room_var != room_idx
                ).OnlyEnforceIf(is_in_room.Not())

                # Create optional interval that exists only when in this room
                optional_interval = builder.model.NewOptionalIntervalVar(
                    inst.start_var,
                    inst.duration,
                    inst.end_var,
                    is_in_room,
                    f"L{lesson_id}_I{inst.instance}_R{room.id}_interval"
                )

                optional_intervals.append(optional_interval)
                optional_intervals_created += 1

        # Add NoOverlap for this room's intervals
        if len(optional_intervals) > 1:
            builder.model.AddNoOverlap(optional_intervals)
            constraints_added += 1

    return constraints_added, optional_intervals_created


# =============================================================================
# Preferred Room Soft Constraints
# =============================================================================

def add_preferred_room_soft_constraint(
    builder: TimetableModelBuilder,
    weight: int = 5
) -> int:
    """
    Add soft constraints preferring certain rooms.

    This creates penalty variables when a lesson is not assigned
    to one of its preferred rooms.

    Args:
        builder: The timetable model builder with created variables
        weight: Penalty weight for not using preferred room

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0

    for lesson in builder.input.lessons:
        # Check if lesson has preferred rooms (not required, just preferred)
        if not lesson.room_requirement:
            continue

        teacher = builder.input.get_teacher(lesson.teacher_id)
        preferred_rooms = []

        # Get teacher's preferred rooms
        if teacher and teacher.preferred_rooms:
            preferred_rooms.extend(teacher.preferred_rooms)

        # This is for soft preference, not hard requirement
        # Hard requirements are handled by add_room_assignment_constraints
        if not preferred_rooms:
            continue

        # Get indices of preferred rooms
        preferred_indices = [
            idx for idx, r in enumerate(builder.input.rooms)
            if r.id in preferred_rooms
        ]

        if not preferred_indices:
            continue

        for inst in builder.lesson_vars.get(lesson.id, []):
            # Create boolean for "is in preferred room"
            in_preferred = builder.model.NewBoolVar(
                f"L{lesson.id}_I{inst.instance}_in_preferred"
            )

            # in_preferred = room_var in preferred_indices
            # We need to create boolean for each preferred room and OR them
            room_booleans = []
            for pref_idx in preferred_indices:
                is_this_room = builder.model.NewBoolVar(
                    f"L{lesson.id}_I{inst.instance}_is_R{pref_idx}"
                )
                builder.model.Add(inst.room_var == pref_idx).OnlyEnforceIf(is_this_room)
                builder.model.Add(inst.room_var != pref_idx).OnlyEnforceIf(is_this_room.Not())
                room_booleans.append(is_this_room)

            # in_preferred = OR(room_booleans)
            builder.model.AddBoolOr(room_booleans).OnlyEnforceIf(in_preferred)
            builder.model.AddBoolAnd([b.Not() for b in room_booleans]).OnlyEnforceIf(in_preferred.Not())

            # Penalty for NOT being in preferred room
            not_preferred = in_preferred.Not()

            builder.penalty_vars.append(PenaltyVar(
                name=f"not_preferred_room_{lesson.id}_{inst.instance}",
                var=not_preferred,
                weight=weight,
                description=f"Lesson {lesson.id} not in preferred room"
            ))
            penalties_added += 1

    return penalties_added


# =============================================================================
# Room Change Minimization (Soft Constraint)
# =============================================================================

def add_room_consistency_soft_constraint(
    builder: TimetableModelBuilder,
    weight: int = 3
) -> int:
    """
    Add soft constraint to minimize room changes for same lesson.

    Prefers keeping all instances of a lesson in the same room.

    Args:
        builder: The timetable model builder with created variables
        weight: Penalty weight for room changes

    Returns:
        Number of penalty variables added
    """
    from solver.model_builder import PenaltyVar

    penalties_added = 0

    for lesson in builder.input.lessons:
        instances = builder.lesson_vars.get(lesson.id, [])

        if len(instances) <= 1:
            continue

        # Compare each pair of instances
        for i, inst1 in enumerate(instances):
            for inst2 in instances[i + 1:]:
                # Create boolean for "different room"
                different_room = builder.model.NewBoolVar(
                    f"L{lesson.id}_I{inst1.instance}_I{inst2.instance}_diff_room"
                )

                builder.model.Add(
                    inst1.room_var != inst2.room_var
                ).OnlyEnforceIf(different_room)

                builder.model.Add(
                    inst1.room_var == inst2.room_var
                ).OnlyEnforceIf(different_room.Not())

                builder.penalty_vars.append(PenaltyVar(
                    name=f"room_change_{lesson.id}_{inst1.instance}_{inst2.instance}",
                    var=different_room,
                    weight=weight,
                    description=f"Lesson {lesson.id} room change between instances"
                ))
                penalties_added += 1

    return penalties_added


# =============================================================================
# Combined Function
# =============================================================================

def add_all_room_constraints(
    builder: TimetableModelBuilder,
    include_soft_constraints: bool = True
) -> RoomConstraintStats:
    """
    Add all room-related constraints.

    This includes:
    - Room assignment restrictions (hard constraint)
    - Room no-overlap with optional intervals (hard constraint)
    - Preferred room soft constraints (optional)
    - Room consistency soft constraints (optional)

    Args:
        builder: The timetable model builder with created variables
        include_soft_constraints: Whether to add soft constraints

    Returns:
        RoomConstraintStats with counts
    """
    stats = RoomConstraintStats()

    # Count lessons with various requirements
    for lesson in builder.input.lessons:
        subject = builder.input.get_subject(lesson.subject_id)
        req = lesson.room_requirement

        if _get_required_room_type(lesson, subject):
            stats.lessons_with_room_type_requirement += 1

        if req:
            if req.min_capacity:
                stats.lessons_with_capacity_requirement += 1
            if req.preferred_rooms:
                stats.lessons_with_specific_room += 1
            if req.excluded_rooms:
                stats.lessons_with_excluded_rooms += 1

    # Add hard constraints
    stats.room_assignment_constraints = add_room_assignment_constraints(builder)

    no_overlap_count, opt_interval_count = add_room_no_overlap_with_optional_intervals(builder)
    stats.room_no_overlap_constraints = no_overlap_count
    stats.optional_intervals_created = opt_interval_count

    # Add soft constraints if requested
    if include_soft_constraints:
        add_preferred_room_soft_constraint(builder)
        add_room_consistency_soft_constraint(builder)

    return stats


# =============================================================================
# Diagnostic Functions
# =============================================================================

def analyze_room_assignments(
    builder: TimetableModelBuilder
) -> dict[str, list[RoomSuitability]]:
    """
    Analyze room suitability for all lessons.

    Useful for debugging why certain lessons can't find rooms.

    Args:
        builder: The model builder

    Returns:
        Dict mapping lesson_id to list of RoomSuitability for each room
    """
    analysis = {}

    for lesson in builder.input.lessons:
        student_class = builder.input.get_class(lesson.class_id)
        class_size = student_class.student_count if student_class else None
        subject = builder.input.get_subject(lesson.subject_id)

        suitabilities = []
        for idx, room in enumerate(builder.input.rooms):
            suit = _evaluate_room_suitability(
                room, idx, lesson, class_size, subject, builder
            )
            suitabilities.append(suit)

        analysis[lesson.id] = suitabilities

    return analysis


def get_lessons_without_valid_rooms(
    builder: TimetableModelBuilder
) -> list[tuple[str, list[str]]]:
    """
    Find lessons that have no valid rooms.

    Args:
        builder: The model builder

    Returns:
        List of (lesson_id, reasons) for lessons without valid rooms
    """
    problematic = []

    for lesson in builder.input.lessons:
        valid_rooms = get_valid_rooms_for_lesson(builder, lesson)

        if not valid_rooms:
            # Collect all reasons why rooms were rejected
            student_class = builder.input.get_class(lesson.class_id)
            class_size = student_class.student_count if student_class else None
            subject = builder.input.get_subject(lesson.subject_id)

            reasons = []
            for idx, room in enumerate(builder.input.rooms):
                suit = _evaluate_room_suitability(
                    room, idx, lesson, class_size, subject, builder
                )
                if not suit.is_valid:
                    reasons.extend(suit.reasons)

            problematic.append((lesson.id, reasons))

    return problematic
