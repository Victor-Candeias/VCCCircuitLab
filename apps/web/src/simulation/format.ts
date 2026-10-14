/** Prefixos SI usados nos resultados (de giga a pico). */
const PREFIXES: readonly [number, string][] = [
  [1e9, 'G'],
  [1e6, 'M'],
  [1e3, 'k'],
  [1, ''],
  [1e-3, 'm'],
  [1e-6, 'µ'],
  [1e-9, 'n'],
  [1e-12, 'p'],
];

/** Abaixo disto o valor é ruído numérico do solver e mostra-se como zero. */
const ZERO_THRESHOLD = 1e-12;

const decimal = new Intl.NumberFormat('pt-PT', { maximumSignificantDigits: 3 });

/** Valor com prefixo SI e 3 algarismos significativos: `0.0409, 'A'` → `40,9 mA`. */
export function formatQuantity(value: number, unit: string): string {
  if (!Number.isFinite(value)) return '—';
  const abs = Math.abs(value);
  if (abs < ZERO_THRESHOLD) return `0 ${unit}`;
  let index = PREFIXES.findIndex(([factor]) => abs >= factor);
  if (index === -1) index = PREFIXES.length - 1;
  // Arredondar pode passar a 1000 (999,96 mA → 1 A): sobe um prefixo.
  if (index > 0 && Math.abs(Number((value / PREFIXES[index][0]).toPrecision(3))) >= 1000) {
    index -= 1;
  }
  const [factor, prefix] = PREFIXES[index];
  return `${decimal.format(value / factor)} ${prefix}${unit}`;
}
