/**
 * TypeScript types for the AI Timetabler data model.
 *
 * Time conventions:
 * - Time is represented as minutes from midnight (0-1439)
 * - Days are 0-4 (Monday-Friday)
 *
 * Example times:
 * - 9:00 AM = 540
 * - 12:30 PM = 750
 * - 3:15 PM = 915
 */

// =============================================================================
// Primitive Types
// =============================================================================

/** Day of week: 0=Monday through 4=Friday */
export type Day = 0 | 1 | 2 | 3 | 4;

/** Minutes from midnight (0-1439) */
export type MinutesFromMidnight = number;

/** Room types for specialist facilities */
export type RoomType =
  | 'classroom'
  | 'science_lab'
  | 'computer_lab'
  | 'gym'
  | 'sports_hall'
  | 'art_room'
  | 'music_room'
  | 'workshop'
  | 'library'
  | 'auditorium'
  | 'other';

// =============================================================================
// Core Entity Types
// =============================================================================

/**
 * Availability window for a teacher, class, or room.
 * Represents a time range on a specific day.
 */
export interface Availability {
  /** Day of week (0-4) */
  day: Day;
  /** Start time in minutes from midnight */
  startMinutes: MinutesFromMidnight;
  /** End time in minutes from midnight */
  endMinutes: MinutesFromMidnight;
  /** Whether available during this window */
  available: boolean;
  /** Optional reason for unavailability */
  reason?: string;
}

/**
 * Teacher entity.
 */
export interface Teacher {
  /** Unique identifier */
  id: string;
  /** Full name */
  name: string;
  /** Short code (e.g., initials) */
  code?: string;
  /** Email address */
  email?: string;
  /** Subject IDs this teacher can teach */
  subjects?: string[];
  /** Availability windows */
  availability?: Availability[];
  /** Maximum teaching periods per day */
  maxPeriodsPerDay?: number;
  /** Maximum teaching periods per week */
  maxPeriodsPerWeek?: number;
  /** Preferred room IDs */
  preferredRooms?: string[];
}

/**
 * Student class/group.
 */
export interface Class {
  /** Unique identifier */
  id: string;
  /** Class name (e.g., 'Year 7A') */
  name: string;
  /** Year/grade level (1-13) */
  yearGroup?: number;
  /** Number of students */
  studentCount?: number;
  /** Class-specific availability */
  availability?: Availability[];
  /** Home room ID */
  homeRoom?: string;
}

/**
 * Subject/course.
 */
export interface Subject {
  /** Unique identifier */
  id: string;
  /** Subject name */
  name: string;
  /** Short code */
  code?: string;
  /** Display color (hex format) */
  color?: string;
  /** Whether this needs a specialist room */
  requiresSpecialistRoom?: boolean;
  /** Required room type if specialist room needed */
  requiredRoomType?: RoomType;
  /** Academic department */
  department?: string;
}

/**
 * Room/facility.
 */
export interface Room {
  /** Unique identifier */
  id: string;
  /** Room name/number */
  name: string;
  /** Type of room */
  type: RoomType;
  /** Maximum student capacity */
  capacity?: number;
  /** Building name/identifier */
  building?: string;
  /** Floor number */
  floor?: number;
  /** Room availability windows */
  availability?: Availability[];
  /** Available equipment */
  equipment?: string[];
  /** Whether wheelchair accessible */
  accessible?: boolean;
}

/**
 * Room requirements for a lesson.
 */
export interface RoomRequirement {
  /** Required room type */
  roomType?: RoomType;
  /** Minimum room capacity */
  minCapacity?: number;
  /** Preferred room IDs */
  preferredRooms?: string[];
  /** Excluded room IDs */
  excludedRooms?: string[];
  /** Required equipment */
  requiresEquipment?: string[];
}

/**
 * Fixed time slot assignment.
 */
export interface FixedSlot {
  /** Day of week */
  day: Day;
  /** Period ID */
  periodId: string;
}

/**
 * Lesson to be scheduled.
 */
export interface Lesson {
  /** Unique identifier */
  id: string;
  /** Teacher ID */
  teacherId: string;
  /** Class/student group ID */
  classId: string;
  /** Subject ID */
  subjectId: string;
  /** Duration in minutes (default: 60) */
  durationMinutes?: number;
  /** Number of occurrences per week */
  lessonsPerWeek: number;
  /** Room requirements */
  roomRequirement?: RoomRequirement;
  /** Can lessons be split across days */
  splitAllowed?: boolean;
  /** Prefer consecutive periods (double lessons) */
  consecutivePreferred?: boolean;
  /** Pre-fixed time slots */
  fixedSlots?: FixedSlot[];
}

/**
 * Period in the school day schedule.
 */
export interface Period {
  /** Unique identifier */
  id: string;
  /** Display name (e.g., 'Period 1') */
  name: string;
  /** Start time in minutes from midnight */
  startMinutes: MinutesFromMidnight;
  /** End time in minutes from midnight */
  endMinutes: MinutesFromMidnight;
  /** Day of week */
  day: Day;
  /** Whether this is a break period */
  isBreak?: boolean;
  /** Whether this is a lunch period */
  isLunch?: boolean;
}

// =============================================================================
// Complete Data Model
// =============================================================================

/**
 * Complete timetable data model.
 */
export interface TimetableData {
  /** School name */
  schoolName?: string;
  /** Academic year */
  academicYear?: string;
  /** List of teachers */
  teachers: Teacher[];
  /** List of classes */
  classes: Class[];
  /** List of subjects */
  subjects: Subject[];
  /** List of rooms */
  rooms: Room[];
  /** List of lessons to schedule */
  lessons: Lesson[];
  /** Period structure */
  periods: Period[];
}

// =============================================================================
// Utility Types
// =============================================================================

/** Map of entity ID to entity */
export type EntityMap<T extends { id: string }> = Map<string, T>;

/** Lookup maps for all entities */
export interface EntityMaps {
  teachers: EntityMap<Teacher>;
  classes: EntityMap<Class>;
  subjects: EntityMap<Subject>;
  rooms: EntityMap<Room>;
  lessons: EntityMap<Lesson>;
  periods: EntityMap<Period>;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Convert hours and minutes to minutes from midnight.
 * @example minutesFromTime(9, 30) // returns 570
 */
export function minutesFromTime(hours: number, minutes: number): MinutesFromMidnight {
  return hours * 60 + minutes;
}

/**
 * Convert minutes from midnight to time string.
 * @example formatTime(570) // returns "09:30"
 */
export function formatTime(minutes: MinutesFromMidnight): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

/**
 * Get day name from day number.
 */
export function getDayName(day: Day): string {
  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
  return days[day];
}

/**
 * Build entity lookup maps from timetable data.
 */
export function buildEntityMaps(data: TimetableData): EntityMaps {
  return {
    teachers: new Map(data.teachers.map(t => [t.id, t])),
    classes: new Map(data.classes.map(c => [c.id, c])),
    subjects: new Map(data.subjects.map(s => [s.id, s])),
    rooms: new Map(data.rooms.map(r => [r.id, r])),
    lessons: new Map(data.lessons.map(l => [l.id, l])),
    periods: new Map(data.periods.map(p => [p.id, p])),
  };
}
