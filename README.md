# Timetable Solver

A constraint-based school timetabling solver using Google OR-Tools CP-SAT.

## Overview

This project provides automated timetable generation for schools using constraint programming. Given a set of lessons, teachers, rooms, and constraints, the solver finds a valid timetable assignment that satisfies hard constraints and optimizes soft constraints.

## Features

- **CP-SAT Solver**: Uses Google OR-Tools' CP-SAT solver with parallel search and LP relaxation
- **Hard Constraints** (always satisfied):
  - No teacher double-booking
  - No class double-booking
  - No room double-booking
  - Specialist room requirements (Science needs lab, PE needs gym)
  - Lessons within school hours
- **Soft Constraints** (optimized with weights):
  - Minimize teacher gaps (idle periods between lessons)
  - Balance daily workload across teachers
  - Respect teacher max periods per day/week preferences
  - Spread lessons across the week
- **Continuous Time Model**: Periods defined with start/end times (minutes from midnight)
- **JSON Schema Validation**: Strict input validation with Pydantic models
- **Quality Metrics**: Gap scores, distribution scores, balance metrics
- **Multiple Views**: Teacher, class, room, and day-based schedule views

## Installation

### Prerequisites

- Python 3.9+
- pip

### Setup

```bash
# Clone the repository
cd ai-timetabler-poc

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Verify Installation

```bash
# Run tests
pytest tests/ -v

# Check CLI
python -m solver.cli --help
```

## CLI Usage

The solver provides a command-line interface with four commands:

### solve - Generate a timetable

```bash
# Basic usage
python -m solver.cli solve input.json

# Save output to file
python -m solver.cli solve input.json -o output.json

# Set timeout (default: 60 seconds)
python -m solver.cli solve input.json -t 120

# Verbose output
python -m solver.cli solve input.json -v
```

### validate - Check input data

```bash
# Validate input file
python -m solver.cli validate input.json

# Verbose validation
python -m solver.cli validate input.json -v
```

Validates:
- Valid JSON structure
- Schema compliance
- Reference integrity (teacher IDs, room IDs, etc.)
- Logical consistency (no overloaded teachers, specialist rooms exist)

### view - Display schedule views

```bash
# View specific teacher's schedule
python -m solver.cli view output.json --teacher T001

# View specific class schedule
python -m solver.cli view output.json --class 7A

# View specific room usage
python -m solver.cli view output.json --room LAB1

# View specific day
python -m solver.cli view output.json --day monday

# View all teachers
python -m solver.cli view output.json --all-teachers

# View all classes
python -m solver.cli view output.json --all-classes
```

### metrics - Analyze solution quality

```bash
# Basic metrics table
python -m solver.cli metrics output.json

# Detailed report with input data
python -m solver.cli metrics output.json --input input.json --format report

# JSON format for programmatic use
python -m solver.cli metrics output.json --format json
```

## Return to virtual environment

```bash
# Navigate to the directory containing your virtual environment and run:

# Win Powershell
\venv\Scripts\Activate.ps1

#MacOS/Linux 	bash/zsh
source venv/bin/activate
```

## Input Schema

Input data is provided as JSON. The schema uses Pydantic models with automatic validation.

### Complete Input Structure

```json
{
  "config": {
    "schoolName": "Example School",
    "academicYear": "2024-2025",
    "numDays": 5,
    "defaultLessonDuration": 60,
    "dayStartMinutes": 540,
    "dayEndMinutes": 960
  },
  "teachers": [...],
  "classes": [...],
  "subjects": [...],
  "rooms": [...],
  "lessons": [...],
  "periods": [...],
  "constraints": {...}
}
```

### Entity Definitions

#### Teacher

```json
{
  "id": "T001",
  "name": "Sarah Mitchell",
  "code": "SMI",
  "email": "s.mitchell@school.edu",
  "subjects": ["eng", "dra"],
  "maxPeriodsPerDay": 5,
  "maxPeriodsPerWeek": 22,
  "availability": [
    {
      "day": 0,
      "startMinutes": 540,
      "endMinutes": 600,
      "available": false,
      "reason": "Staff meeting"
    }
  ],
  "preferredRooms": ["R101"]
}
```

#### Class (StudentClass)

```json
{
  "id": "7A",
  "name": "Year 7A",
  "yearGroup": 7,
  "studentCount": 28,
  "homeRoom": "R101"
}
```

#### Subject

```json
{
  "id": "sci",
  "name": "Science",
  "code": "SCI",
  "color": "#4CAF50",
  "requiresSpecialistRoom": true,
  "requiredRoomType": "science_lab",
  "department": "Science"
}
```

#### Room

```json
{
  "id": "LAB1",
  "name": "Science Lab 1",
  "type": "science_lab",
  "capacity": 30,
  "building": "Main",
  "floor": 1,
  "equipment": ["bunsen_burners", "fume_hood"],
  "accessible": true
}
```

Room types: `classroom`, `science_lab`, `computer_lab`, `gym`, `sports_hall`, `art_room`, `music_room`, `workshop`, `library`, `auditorium`, `other`

#### Lesson

```json
{
  "id": "L001",
  "teacherId": "T001",
  "classId": "7A",
  "subjectId": "eng",
  "durationMinutes": 60,
  "lessonsPerWeek": 5,
  "splitAllowed": true,
  "consecutivePreferred": false,
  "roomRequirement": {
    "roomType": "classroom",
    "minCapacity": 25,
    "preferredRooms": ["R101", "R102"],
    "excludedRooms": ["R999"]
  },
  "fixedSlots": [
    {"day": 0, "periodId": "P1"}
  ]
}
```

#### Period

```json
{
  "id": "MON_P1",
  "name": "Period 1",
  "day": 0,
  "startMinutes": 540,
  "endMinutes": 600,
  "isBreak": false,
  "isLunch": false
}
```

Time is represented as minutes from midnight (0-1439):
- 9:00 AM = 540
- 12:30 PM = 750
- 3:15 PM = 915

Days are 0-4 (Monday-Friday).

### Constraints (Optional)

```json
{
  "constraints": {
    "teacherMaxPeriods": [
      {"teacherId": "T001", "maxPerDay": 5, "maxPerWeek": 22}
    ],
    "roomType": [
      {"subjectId": "sci", "roomType": "science_lab"}
    ],
    "consecutiveLessons": [
      {"lessonId": "L001", "maxConsecutive": 2}
    ],
    "lessonSpread": [
      {"lessonId": "L001", "minDaysBetween": 1}
    ]
  }
}
```

## Output Format

The solver outputs a JSON structure with the solution and metadata.

### Complete Output Structure

```json
{
  "status": "OPTIMAL",
  "solveTimeSeconds": 12.5,
  "quality": {
    "totalPenalty": 42,
    "hardConstraintsSatisfied": true,
    "softConstraintScores": {
      "teacher_gap_T001_day0": 1,
      "workload_imbalance_T002_day1": 2
    }
  },
  "timetable": {
    "lessons": [...]
  },
  "views": {
    "byTeacher": {...},
    "byClass": {...},
    "byRoom": {...},
    "byDay": {...}
  }
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `OPTIMAL` | Best possible solution found |
| `FEASIBLE` | Valid solution found, may not be optimal |
| `INFEASIBLE` | No valid solution exists |
| `TIMEOUT` | Time limit reached without solution |
| `UNKNOWN` | Solver status unknown |

### Lesson Assignment

```json
{
  "lessonId": "L001",
  "day": 0,
  "dayName": "Monday",
  "periodId": "MON_P1",
  "startTime": "09:00",
  "endTime": "10:00",
  "roomId": "R101",
  "teacherId": "T001",
  "classId": "7A",
  "subjectId": "eng"
}
```

### Views

The output includes pre-computed views for easy display:

- **byTeacher**: Lessons grouped by teacher ID
- **byClass**: Lessons grouped by class ID
- **byRoom**: Lessons grouped by room ID
- **byDay**: Lessons grouped by day (0-4)

## Sample Data Generation

Generate sample school data for testing:

```python
from solver.data.generator import (
    generate_small_school,
    generate_medium_school,
    generate_large_school,
    GeneratorConfig,
    get_generation_stats,
)

# Generate small school (10 teachers, 8 classes)
school = generate_small_school(seed=42)

# Generate with custom config
config = GeneratorConfig(
    num_teachers=20,
    num_classes=15,
    num_rooms=15,
    lessons_per_class_per_week=18,
    seed=42,
)
school = generate_sample_school(config)

# Check feasibility
stats = get_generation_stats(school)
print(f"Utilization: {stats['utilization_percent']}%")
print(f"Feasible: {stats['is_feasible']}")
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_solver.py -v

# Run with coverage
pytest tests/ --cov=solver --cov-report=term-missing

# Run only fast tests (skip slow solver tests)
pytest tests/ -v -m "not slow"
```

## Project Structure

```
ai-timetabler-poc/
├── solver/
│   ├── cli.py              # Command-line interface
│   ├── model.py            # Simple solver model
│   ├── model_builder.py    # Full-featured model builder
│   ├── constraints/        # Constraint implementations
│   │   ├── __init__.py     # Constraint manager
│   │   ├── core.py         # Core hard constraints
│   │   ├── room.py         # Room constraints
│   │   ├── availability.py # Availability constraints
│   │   ├── daily_limits.py # Workload constraints
│   │   └── spreading.py    # Lesson spreading
│   ├── data/
│   │   ├── models.py       # Pydantic data models
│   │   └── generator.py    # Sample data generator
│   └── output/
│       ├── schema.py       # Output models
│       └── metrics.py      # Quality metrics
├── schema/
│   └── types.ts            # TypeScript type definitions
├── data/
│   └── sample-timetable.json
├── tests/
│   ├── test_models.py      # Data model tests
│   ├── test_generator.py   # Generator tests
│   ├── test_solver.py      # Solver tests
│   └── ...
├── requirements.txt
└── README.md
```

## Constraints Reference

### Hard Constraints (Always Enforced)

| Constraint | Description |
|------------|-------------|
| Teacher No Overlap | A teacher cannot teach two lessons at the same time |
| Class No Overlap | A class cannot have two lessons at the same time |
| Room No Overlap | A room cannot host two lessons at the same time |
| Room Type Match | Lessons requiring specialist rooms get appropriate rooms |
| School Hours | All lessons scheduled within defined school hours |
| Teacher Capacity | No teacher assigned more lessons than available periods |

### Soft Constraints (Optimized)

| Constraint | Weight | Description |
|------------|--------|-------------|
| Teacher Gaps | 10 | Minimize idle periods between lessons |
| Daily Balance | 5 | Even distribution of lessons across days |
| Max Periods/Day | 50 | Respect teacher's max periods per day preference |
| Max Periods/Week | 50 | Respect teacher's max periods per week preference |
| Lesson Spread | 20 | Spread same-subject lessons across days |

## License

MIT
