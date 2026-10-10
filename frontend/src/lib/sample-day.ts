// frontend/src/lib/sample-day.ts
//
// A realistic, built-in day payload used by the `/variants` comparison screen
// when no school/entity is selected (or its day cannot be loaded). It mirrors a
// real export closely enough to exercise every visual state the variants must
// handle:
//
//   * 6–7 lessons with filled teachers and rooms;
//   * one subject split into two groups (lesson 2);
//   * one substitution / exchange (lesson 3);
//   * one cancelled lesson (lesson 4);
//   * one method hour («Метод. час», lesson 6);
//   * a teaching period and the first shift.
//
// Kept framework-free so it can be imported by screens and tests alike.

import type { DaySchedule } from './api/types';

/** A hand-built day used as the `/variants` fallback (see file header). */
export const SAMPLE_DAY: DaySchedule = {
  date: '05.10.2026',
  day_name: 'Понедельник',
  kind: 'class',
  entity: '6А',
  lessons: [
    {
      num: 1,
      start: '08:00',
      end: '08:45',
      items: [
        {
          subject: 'Русский язык',
          teacher: 'Смирнова Е. П.',
          room: '204',
          class_name: '6А',
          groups: null,
          is_method_hour: false,
        },
      ],
      has_exchange: false,
      is_cancelled: false,
    },
    {
      num: 2,
      start: '08:55',
      end: '09:40',
      items: [
        {
          subject: 'Математика',
          teacher: 'Иванова Н. С.',
          room: '118',
          class_name: '6А',
          groups: 'Группа 1',
          is_method_hour: false,
        },
        {
          subject: 'Английский язык',
          teacher: 'Петрова А. В.',
          room: '301',
          class_name: '6А',
          groups: 'Группа 2',
          is_method_hour: false,
        },
      ],
      has_exchange: false,
      is_cancelled: false,
    },
    {
      num: 3,
      start: '09:50',
      end: '10:35',
      items: [
        {
          subject: 'История',
          teacher: 'Кузнецов Д. М.',
          room: '207',
          class_name: '6А',
          groups: null,
          is_method_hour: false,
        },
      ],
      has_exchange: true,
      is_cancelled: false,
    },
    {
      num: 4,
      start: '10:50',
      end: '11:35',
      items: [
        {
          subject: 'Физическая культура',
          teacher: 'Орлов В. В.',
          room: 'Спортзал',
          class_name: '6А',
          groups: null,
          is_method_hour: false,
        },
      ],
      has_exchange: false,
      is_cancelled: true,
    },
    {
      num: 5,
      start: '11:50',
      end: '12:35',
      items: [
        {
          subject: 'Биология',
          teacher: 'Петрова А. В.',
          room: '212',
          class_name: '6А',
          groups: null,
          is_method_hour: false,
        },
      ],
      has_exchange: false,
      is_cancelled: false,
    },
    {
      num: 6,
      start: '12:45',
      end: '13:30',
      items: [
        {
          subject: 'M',
          teacher: 'Кузнецов Д. М.',
          room: '207',
          class_name: '6А',
          groups: null,
          is_method_hour: true,
        },
      ],
      has_exchange: false,
      is_cancelled: false,
    },
    {
      num: 7,
      start: '13:40',
      end: '14:25',
      items: [
        {
          subject: 'Технология',
          teacher: 'Соколов П. А.',
          room: 'Мастерская',
          class_name: '6А',
          groups: null,
          is_method_hour: false,
        },
      ],
      has_exchange: false,
      is_cancelled: false,
    },
  ],
  vacation: false,
  weekend: false,
  no_period: false,
  period: { b: '01.09.2026', e: '31.05.2027', name: '01.09.2026 - 31.05.2027' },
  shift: null,
};
