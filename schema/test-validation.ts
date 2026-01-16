/**
 * Test script to validate sample data using Zod schemas.
 */

import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import {
  validateTimetable,
  parseTimetableData,
} from './timetable.zod.js';
import type { TimetableData } from './timetable.zod.js';
import { formatTime, getDayName } from './timetable.types.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

function printHeader(title: string): void {
  console.log('\n' + '='.repeat(60));
  console.log(title);
  console.log('='.repeat(60));
}

function printSuccess(message: string): void {
  console.log(`✓ ${message}`);
}

function printError(message: string): void {
  console.log(`✗ ${message}`);
}

function printInfo(message: string): void {
  console.log(`  ${message}`);
}

// Load sample data
const dataPath = join(__dirname, '..', 'data', 'sample-timetable.json');
console.log(`Loading data from: ${dataPath}`);

let rawData: unknown;
try {
  const content = readFileSync(dataPath, 'utf-8');
  rawData = JSON.parse(content);
  printSuccess('JSON parsed successfully');
} catch (err) {
  printError(`Failed to load/parse JSON: ${err}`);
  process.exit(1);
}

// Validate with Zod
printHeader('Schema Validation');

const result = validateTimetable(rawData);

if (!result.success) {
  printError('Validation failed!');

  if (result.schemaErrors) {
    console.log('\nSchema Errors:');
    for (const issue of result.schemaErrors) {
      console.log(`  - Path: ${issue.path.join('.')}`);
      console.log(`    Error: ${issue.message}`);
    }
  }

  if (result.referenceErrors) {
    console.log('\nReference Errors:');
    for (const error of result.referenceErrors) {
      console.log(`  - ${error}`);
    }
  }

  process.exit(1);
}

printSuccess('Schema validation passed');
printSuccess('Reference validation passed');

// Print summary
const data: TimetableData = result.data!;

printHeader('Data Summary');

if (data.schoolName) {
  printInfo(`School: ${data.schoolName}`);
}
if (data.academicYear) {
  printInfo(`Academic Year: ${data.academicYear}`);
}

console.log('');
printInfo(`Teachers: ${data.teachers.length}`);
printInfo(`Classes: ${data.classes.length}`);
printInfo(`Subjects: ${data.subjects.length}`);
printInfo(`Rooms: ${data.rooms.length}`);
printInfo(`Lessons: ${data.lessons.length}`);
printInfo(`Periods: ${data.periods.length}`);

// Calculate total lessons per week
const totalLessonsPerWeek = data.lessons.reduce((sum, l) => sum + l.lessonsPerWeek, 0);
printInfo(`Total lesson instances per week: ${totalLessonsPerWeek}`);

// Count schedulable periods
const schedulablePeriods = data.periods.filter(p => !p.isBreak && !p.isLunch);
printInfo(`Schedulable periods per week: ${schedulablePeriods.length}`);

// Print period structure for one day
printHeader('Period Structure (Monday)');

const mondayPeriods = data.periods
  .filter(p => p.day === 0)
  .sort((a, b) => a.startMinutes - b.startMinutes);

for (const period of mondayPeriods) {
  const start = formatTime(period.startMinutes);
  const end = formatTime(period.endMinutes);
  const type = period.isBreak ? ' [Break]' : period.isLunch ? ' [Lunch]' : '';
  console.log(`  ${start} - ${end}  ${period.name}${type}`);
}

// Print teacher workload
printHeader('Teacher Workloads');

for (const teacher of data.teachers) {
  const teacherLessons = data.lessons.filter(l => l.teacherId === teacher.id);
  const periodsPerWeek = teacherLessons.reduce((sum, l) => sum + l.lessonsPerWeek, 0);
  const maxDisplay = teacher.maxPeriodsPerWeek ? `/${teacher.maxPeriodsPerWeek}` : '';
  console.log(`  ${teacher.name} (${teacher.code}): ${periodsPerWeek}${maxDisplay} periods/week`);
}

// Print specialist room requirements
printHeader('Specialist Room Requirements');

const specialistSubjects = data.subjects.filter(s => s.requiresSpecialistRoom);
for (const subject of specialistSubjects) {
  const rooms = data.rooms.filter(r => r.type === subject.requiredRoomType);
  console.log(`  ${subject.name} → ${subject.requiredRoomType} (${rooms.length} available)`);
}

// Check for potential issues
printHeader('Potential Issues');

let issueCount = 0;

// Check if any teacher exceeds their max periods
for (const teacher of data.teachers) {
  if (!teacher.maxPeriodsPerWeek) continue;
  const teacherLessons = data.lessons.filter(l => l.teacherId === teacher.id);
  const periodsPerWeek = teacherLessons.reduce((sum, l) => sum + l.lessonsPerWeek, 0);
  if (periodsPerWeek > teacher.maxPeriodsPerWeek) {
    printError(`${teacher.name} has ${periodsPerWeek} periods but max is ${teacher.maxPeriodsPerWeek}`);
    issueCount++;
  }
}

// Check if there are enough specialist rooms
for (const subject of specialistSubjects) {
  const subjectLessons = data.lessons.filter(l => l.subjectId === subject.id);
  const periodsNeeded = subjectLessons.reduce((sum, l) => sum + l.lessonsPerWeek, 0);
  const rooms = data.rooms.filter(r => r.type === subject.requiredRoomType);
  const slotsAvailable = rooms.length * schedulablePeriods.length;

  if (periodsNeeded > slotsAvailable) {
    printError(`${subject.name} needs ${periodsNeeded} slots but only ${slotsAvailable} available`);
    issueCount++;
  }
}

// Check total capacity
if (totalLessonsPerWeek > schedulablePeriods.length * data.rooms.length) {
  printError(`More lessons (${totalLessonsPerWeek}) than room-slots available (${schedulablePeriods.length * data.rooms.length})`);
  issueCount++;
}

if (issueCount === 0) {
  printSuccess('No potential issues detected');
}

printHeader('Validation Complete');
console.log('');
