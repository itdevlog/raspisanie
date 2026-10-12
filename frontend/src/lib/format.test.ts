import { describe, expect, it } from 'vitest';
import { formatDuration } from './format';

describe('formatDuration', () => {
  it('shows plain minutes below an hour', () => {
    expect(formatDuration(0)).toBe('0 мин');
    expect(formatDuration(5)).toBe('5 мин');
    expect(formatDuration(45)).toBe('45 мин');
    expect(formatDuration(59)).toBe('59 мин');
  });

  it('shows whole hours without minutes', () => {
    expect(formatDuration(60)).toBe('1 ч');
    expect(formatDuration(120)).toBe('2 ч');
  });

  it('shows hours and minutes', () => {
    expect(formatDuration(61)).toBe('1 ч 1 мин');
    expect(formatDuration(90)).toBe('1 ч 30 мин');
    expect(formatDuration(123)).toBe('2 ч 3 мин');
  });

  it('clamps negatives to zero', () => {
    expect(formatDuration(-10)).toBe('0 мин');
  });
});
