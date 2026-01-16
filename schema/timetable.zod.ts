/**
 * Zod validation schemas for the AI Timetabler data model.
 *
 * These schemas provide runtime validation with detailed error messages.
 * Use these when loading data from external sources (files, APIs, etc.).
 */

import { z } from 'zod';

// =============================================================================
// Primitive Schemas
// =============================================================================

/** Day of week: 0=Monday through 4=Friday */
export const DaySchema = z.number().int().min(0).max(4).describe('Day of week (0=Monday, 4=Friday)');

/** Minutes from midnight (0-1439) */
export const MinutesFromMidnightSchema = z
  .number()
  .int()
  .min(0)
  .max(1439)
  .describe('Time as minutes from midnight (e.g., 9:00 AM = 540)');

/** Room types */
export const RoomTypeSchema = z.enum([
  'classroom',
  'science_lab',
  'computer_lab',
  'gym',
  'sports_hall',
  'art_room',
  'music_room',
  'workshop',
  'library',
  'auditorium',
  'other',
]).describe('Type of room/facility');

// =============================================================================
// Core Entity Schemas
// =============================================================================

/**
 * Availability window schema.
 */
export const AvailabilitySchema = z.object({
  day: DaySchema,
  startMinutes: MinutesFromMidnightSchema,
  endMinutes: MinutesFromMidnightSchema,
  available: z.boolean().describe('Whether available during this window'),
  reason: z.string().optional().describe('Reason for unavailability'),
}).refine(
  data => data.startMinutes < data.endMinutes,
  { message: 'startMinutes must be less than endMinutes' }
);

/**
 * Teacher schema.
 */
export const TeacherSchema = z.object({
  id: z.string().min(1).describe('Unique identifier'),
  name: z.string().min(1).describe('Full name'),
  code: z.string().max(5).optional().describe('Short code (e.g., initials)'),
  email: z.string().email().optional().describe('Email address'),
  subjects: z.array(z.string()).optional().describe('Subject IDs this teacher can teach'),
  availability: z.array(AvailabilitySchema).optional().describe('Availability windows'),
  maxPeriodsPerDay: z.number().int().min(1).max(12).optional().describe('Max periods per day'),
  maxPeriodsPerWeek: z.number().int().min(1).max(60).optional().describe('Max periods per week'),
  preferredRooms: z.array(z.string()).optional().describe('Preferred room IDs'),
}).strict();

/**
 * Class/student group schema.
 */
export const ClassSchema = z.object({
  id: z.string().min(1).describe('Unique identifier'),
  name: z.string().min(1).describe('Class name'),
  yearGroup: z.number().int().min(1).max(13).optional().describe('Year/grade level'),
  studentCount: z.number().int().min(1).optional().describe('Number of students'),
  availability: z.array(AvailabilitySchema).optional().describe('Class availability'),
  homeRoom: z.string().optional().describe('Home room ID'),
}).strict();

/**
 * Subject schema.
 */
export const SubjectSchema = z.object({
  id: z.string().min(1).describe('Unique identifier'),
  name: z.string().min(1).describe('Subject name'),
  code: z.string().max(10).optional().describe('Short code'),
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/).optional().describe('Hex color'),
  requiresSpecialistRoom: z.boolean().default(false).describe('Needs specialist room'),
  requiredRoomType: RoomTypeSchema.optional().describe('Required room type'),
  department: z.string().optional().describe('Academic department'),
}).strict();

/**
 * Room schema.
 */
export const RoomSchema = z.object({
  id: z.string().min(1).describe('Unique identifier'),
  name: z.string().min(1).describe('Room name/number'),
  type: RoomTypeSchema.describe('Type of room'),
  capacity: z.number().int().min(1).optional().describe('Max capacity'),
  building: z.string().optional().describe('Building name'),
  floor: z.number().int().optional().describe('Floor number'),
  availability: z.array(AvailabilitySchema).optional().describe('Room availability'),
  equipment: z.array(z.string()).optional().describe('Available equipment'),
  accessible: z.boolean().default(true).describe('Wheelchair accessible'),
}).strict();

/**
 * Room requirement schema.
 */
export const RoomRequirementSchema = z.object({
  roomType: RoomTypeSchema.optional().describe('Required room type'),
  minCapacity: z.number().int().min(1).optional().describe('Minimum capacity'),
  preferredRooms: z.array(z.string()).optional().describe('Preferred room IDs'),
  excludedRooms: z.array(z.string()).optional().describe('Excluded room IDs'),
  requiresEquipment: z.array(z.string()).optional().describe('Required equipment'),
}).strict();

/**
 * Fixed slot schema.
 */
export const FixedSlotSchema = z.object({
  day: DaySchema,
  periodId: z.string().describe('Period ID'),
}).strict();

/**
 * Lesson schema.
 */
export const LessonSchema = z.object({
  id: z.string().min(1).describe('Unique identifier'),
  teacherId: z.string().describe('Teacher ID'),
  classId: z.string().describe('Class ID'),
  subjectId: z.string().describe('Subject ID'),
  durationMinutes: z.number().int().min(15).max(240).default(60).describe('Duration in minutes'),
  lessonsPerWeek: z.number().int().min(1).max(20).describe('Occurrences per week'),
  roomRequirement: RoomRequirementSchema.optional().describe('Room requirements'),
  splitAllowed: z.boolean().default(true).describe('Can split across days'),
  consecutivePreferred: z.boolean().default(false).describe('Prefer double lessons'),
  fixedSlots: z.array(FixedSlotSchema).optional().describe('Pre-fixed slots'),
}).strict();

/**
 * Period schema.
 */
export const PeriodSchema = z.object({
  id: z.string().min(1).describe('Unique identifier'),
  name: z.string().describe('Display name'),
  startMinutes: MinutesFromMidnightSchema.describe('Start time'),
  endMinutes: MinutesFromMidnightSchema.describe('End time'),
  day: DaySchema.describe('Day of week'),
  isBreak: z.boolean().default(false).describe('Is break period'),
  isLunch: z.boolean().default(false).describe('Is lunch period'),
}).strict().refine(
  data => data.startMinutes < data.endMinutes,
  { message: 'startMinutes must be less than endMinutes' }
);

// =============================================================================
// Complete Data Model Schema
// =============================================================================

/**
 * Complete timetable data schema.
 */
export const TimetableDataSchema = z.object({
  schoolName: z.string().optional().describe('School name'),
  academicYear: z.string().optional().describe('Academic year'),
  teachers: z.array(TeacherSchema).min(1).describe('Teachers'),
  classes: z.array(ClassSchema).min(1).describe('Classes'),
  subjects: z.array(SubjectSchema).min(1).describe('Subjects'),
  rooms: z.array(RoomSchema).min(1).describe('Rooms'),
  lessons: z.array(LessonSchema).min(1).describe('Lessons'),
  periods: z.array(PeriodSchema).min(1).describe('Periods'),
}).strict();

// =============================================================================
// Type Inference
// =============================================================================

/** Inferred types from Zod schemas */
export type Day = z.infer<typeof DaySchema>;
export type MinutesFromMidnight = z.infer<typeof MinutesFromMidnightSchema>;
export type RoomType = z.infer<typeof RoomTypeSchema>;
export type Availability = z.infer<typeof AvailabilitySchema>;
export type Teacher = z.infer<typeof TeacherSchema>;
export type Class = z.infer<typeof ClassSchema>;
export type Subject = z.infer<typeof SubjectSchema>;
export type Room = z.infer<typeof RoomSchema>;
export type RoomRequirement = z.infer<typeof RoomRequirementSchema>;
export type FixedSlot = z.infer<typeof FixedSlotSchema>;
export type Lesson = z.infer<typeof LessonSchema>;
export type Period = z.infer<typeof PeriodSchema>;
export type TimetableData = z.infer<typeof TimetableDataSchema>;

// =============================================================================
// Validation Functions
// =============================================================================

/**
 * Parse and validate timetable data.
 * Throws ZodError if validation fails.
 */
export function parseTimetableData(data: unknown): TimetableData {
  return TimetableDataSchema.parse(data);
}

/**
 * Safely parse timetable data, returning success/error result.
 */
export function safeParseTimetableData(data: unknown): z.SafeParseReturnType<unknown, TimetableData> {
  return TimetableDataSchema.safeParse(data);
}

/**
 * Validate timetable data and return detailed errors.
 */
export function validateTimetableData(data: unknown): {
  success: boolean;
  data?: TimetableData;
  errors?: z.ZodIssue[];
} {
  const result = TimetableDataSchema.safeParse(data);
  if (result.success) {
    return { success: true, data: result.data };
  }
  return { success: false, errors: result.error.issues };
}

// =============================================================================
// Reference Validation
// =============================================================================

/**
 * Validate that all references between entities are valid.
 * Call this after schema validation to check referential integrity.
 */
export function validateReferences(data: TimetableData): string[] {
  const errors: string[] = [];

  const teacherIds = new Set(data.teachers.map(t => t.id));
  const classIds = new Set(data.classes.map(c => c.id));
  const subjectIds = new Set(data.subjects.map(s => s.id));
  const roomIds = new Set(data.rooms.map(r => r.id));
  const periodIds = new Set(data.periods.map(p => p.id));

  // Check lessons reference valid entities
  for (const lesson of data.lessons) {
    if (!teacherIds.has(lesson.teacherId)) {
      errors.push(`Lesson ${lesson.id}: unknown teacherId "${lesson.teacherId}"`);
    }
    if (!classIds.has(lesson.classId)) {
      errors.push(`Lesson ${lesson.id}: unknown classId "${lesson.classId}"`);
    }
    if (!subjectIds.has(lesson.subjectId)) {
      errors.push(`Lesson ${lesson.id}: unknown subjectId "${lesson.subjectId}"`);
    }
    if (lesson.roomRequirement?.preferredRooms) {
      for (const roomId of lesson.roomRequirement.preferredRooms) {
        if (!roomIds.has(roomId)) {
          errors.push(`Lesson ${lesson.id}: unknown preferredRoom "${roomId}"`);
        }
      }
    }
    if (lesson.fixedSlots) {
      for (const slot of lesson.fixedSlots) {
        if (!periodIds.has(slot.periodId)) {
          errors.push(`Lesson ${lesson.id}: unknown periodId "${slot.periodId}"`);
        }
      }
    }
  }

  // Check teacher subjects reference valid subjects
  for (const teacher of data.teachers) {
    if (teacher.subjects) {
      for (const subjectId of teacher.subjects) {
        if (!subjectIds.has(subjectId)) {
          errors.push(`Teacher ${teacher.id}: unknown subject "${subjectId}"`);
        }
      }
    }
    if (teacher.preferredRooms) {
      for (const roomId of teacher.preferredRooms) {
        if (!roomIds.has(roomId)) {
          errors.push(`Teacher ${teacher.id}: unknown preferredRoom "${roomId}"`);
        }
      }
    }
  }

  // Check class homeRoom references valid room
  for (const cls of data.classes) {
    if (cls.homeRoom && !roomIds.has(cls.homeRoom)) {
      errors.push(`Class ${cls.id}: unknown homeRoom "${cls.homeRoom}"`);
    }
  }

  return errors;
}

/**
 * Full validation including schema and references.
 */
export function validateTimetable(data: unknown): {
  success: boolean;
  data?: TimetableData;
  schemaErrors?: z.ZodIssue[];
  referenceErrors?: string[];
} {
  const schemaResult = TimetableDataSchema.safeParse(data);

  if (!schemaResult.success) {
    return {
      success: false,
      schemaErrors: schemaResult.error.issues,
    };
  }

  const referenceErrors = validateReferences(schemaResult.data);

  if (referenceErrors.length > 0) {
    return {
      success: false,
      data: schemaResult.data,
      referenceErrors,
    };
  }

  return {
    success: true,
    data: schemaResult.data,
  };
}
