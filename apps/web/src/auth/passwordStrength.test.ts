import { describe, expect, test } from 'vitest';
import { MIN_PASSWORD_LEVEL, passwordLevel } from './passwordStrength';

// Os mesmos casos existem em apps/api/tests/test_security.py.
const LEVELS: [string, number][] = [
  ['', 0],
  ['abc', 0],
  ['1234567', 0],
  ['password', 0],
  ['aaaaaaaaaaaa', 0],
  ['abcdefgh', 1],
  ['abcdefg1', 1],
  ['Abcdefg1', 2],
  ['abcdefghijkl', 2],
  ['Abcdefghij1k', 3],
  ['abcdefghijklmnop', 3],
  ['Abcdefghijklmn1!', 4],
];

describe('passwordLevel', () => {
  test.each(LEVELS)('%j tem nível %i', (password, level) => {
    expect(passwordLevel(password)).toBe(level);
  });

  test('o nível mínimo exige 8 caracteres com 3 classes, ou 12 caracteres', () => {
    expect(passwordLevel('Abcdefg1')).toBeGreaterThanOrEqual(MIN_PASSWORD_LEVEL);
    expect(passwordLevel('abcdefg1')).toBeLessThan(MIN_PASSWORD_LEVEL);
  });
});
