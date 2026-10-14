import { describe, expect, it } from 'vitest';
import { groupClassesByGrade, parseClassName } from './class-list';

describe('parseClassName', () => {
  it('splits a grade and a Cyrillic letter', () => {
    expect(parseClassName('5А')).toEqual({ grade: '5', letter: 'А' });
    expect(parseClassName('5 А')).toEqual({ grade: '5', letter: 'А' });
    expect(parseClassName('10Б')).toEqual({ grade: '10', letter: 'Б' });
  });
  it('keeps a grade without a letter', () => {
    expect(parseClassName('5')).toEqual({ grade: '5', letter: '' });
  });
  it('returns null for non-class names', () => {
    expect(parseClassName('Спортзал')).toBeNull();
    expect(parseClassName('')).toBeNull();
  });
});

describe('groupClassesByGrade', () => {
  it('groups by grade in numeric order and drops non-class names', () => {
    expect(
      groupClassesByGrade(['10Б', '5А', '5Б', 'Спортзал', '2В']),
    ).toEqual([
      { grade: '2', classes: ['2В'] },
      { grade: '5', classes: ['5А', '5Б'] },
      { grade: '10', classes: ['10Б'] },
    ]);
  });
});
