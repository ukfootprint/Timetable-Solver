/**
 * TypeScript types for the AI Timetabler
 * These types mirror the JSON schemas for type-safe data handling
 */

// Room types that require specialized facilities
export type RoomType =
  | 'standard'
  | 'science_lab'
  | 'computer_room'
  | 'sports_hall'
  | 'art_room'
  | 'music_room';

// Solver status codes
export type SolverStatus =
  | 'OPTIMAL'
  | 'FEASIBLE'
  | 'INFEASIBLE'
  | 'MODEL_INVALID'
  | 'UNKNOWN';

// A specific time slot in the week
export interface TimeSlot {
  day: number;      // 0-4 for Mon-Fri
  period: number;   // 1-based period number
}

// Teacher information
export interface Teacher {
  id: string;
  name: string;
  code?: string;
}

// Room information
export interface Room {
  id: string;
  name: string;
  type?: RoomType;
  capacity?: number;
}

// Student group/class
export interface StudentGroup {
  id: string;
  name: string;
  year_group?: number;
  size?: number;
}

// Subject/course
export interface Subject {
  id: string;
  name: string;
  required_room_type?: RoomType;
}

// A lesson that needs to be scheduled
export interface Lesson {
  id: string;
  teacher_id: string;
  group_id: string;
  subject_id: string;
  duration?: number;  // Number of consecutive periods (default: 1)
}

// Complete school data input
export interface SchoolData {
  num_days?: number;
  num_periods?: number;
  teachers: Teacher[];
  rooms: Room[];
  groups: StudentGroup[];
  subjects: Subject[];
  lessons: Lesson[];
  teacher_availability?: Record<string, TimeSlot[]>;
}

// A single lesson assignment in the solution
export interface Assignment {
  lesson_id: string;
  day: number;
  period: number;
  room_id: string;
  room_name?: string;
  teacher_id?: string;
  teacher_name?: string;
  group_id?: string;
  group_name?: string;
  subject_id?: string;
  subject_name?: string;
}

// Solution summary statistics
export interface SolutionSummary {
  total_lessons: number;
  assigned_lessons: number;
  teachers: number;
  rooms: number;
  groups: number;
}

// Complete solver output
export interface Solution {
  status: SolverStatus;
  solve_time_ms: number;
  objective_value?: number | null;
  assignments: Assignment[];
  summary?: SolutionSummary;
  generated_at?: string;
}

// Timetable grid for a specific view
export interface TimetableGrid {
  view_type: 'teacher' | 'room' | 'group';
  view_id: string;
  grid: Record<string, Record<number, Assignment | null>>;
}
