/**
 * Qualidade da password, de 0 (muito fraca) a 4 (muito forte). Tem de dar os mesmos níveis que
 * `password_level` em `apps/api/app/security/passwords.py`:
 * - 0: menos de 8 caracteres ou uma password comum;
 * - caso contrário parte de 1 e soma 1 por cada: ≥ 12 caracteres, ≥ 16 caracteres,
 *   ≥ 3 classes de caracteres (minúsculas, maiúsculas, dígitos, símbolos).
 */
export type PasswordLevel = 0 | 1 | 2 | 3 | 4;

/** Nível mínimo aceite no registo (2 = razoável). */
export const MIN_PASSWORD_LEVEL: PasswordLevel = 2;

export const PASSWORD_LEVEL_LABELS = ['Muito fraca', 'Fraca', 'Razoável', 'Forte', 'Muito forte'];

/** Do vermelho (nível 0) ao verde (nível 4). */
export const PASSWORD_LEVEL_COLORS = ['#d92d20', '#f97316', '#eab308', '#84cc16', '#16a34a'];

const COMMON = new Set([
  '12345678',
  '123456789',
  '1234567890',
  'password',
  'password1',
  'qwertyui',
  'qwerty123',
  'abc12345',
  '11111111',
  'iloveyou',
  'senha123',
  'palavrapasse',
]);

const isLower = (c: string) => c !== c.toUpperCase();
const isUpper = (c: string) => c !== c.toLowerCase();
const isDigit = (c: string) => c >= '0' && c <= '9';

export function passwordLevel(password: string): PasswordLevel {
  const chars = Array.from(password);
  if (chars.length < 8 || COMMON.has(password.toLowerCase()) || new Set(chars).size === 1) {
    return 0;
  }
  const classes =
    Number(chars.some(isLower)) +
    Number(chars.some(isUpper)) +
    Number(chars.some(isDigit)) +
    Number(chars.some((c) => !isLower(c) && !isUpper(c) && !isDigit(c)));
  return (1 +
    Number(chars.length >= 12) +
    Number(chars.length >= 16) +
    Number(classes >= 3)) as PasswordLevel;
}
