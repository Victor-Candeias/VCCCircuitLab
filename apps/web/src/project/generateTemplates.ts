import type { GenerateParameters } from '../api/client';

/**
 * Metadados estáticos dos templates de geração (`POST /api/v1/circuits/generate`, E3-04). Têm
 * de corresponder aos templates do backend (`apps/api/app/generation/registry.py`); a API é a
 * autoridade final sobre os parâmetros válidos — isto só evita pedidos obviamente inválidos
 * (campos vazios, listas malformadas) antes de contactar o servidor.
 */

export type GenerateFieldType = 'number' | 'resistor-list' | 'boolean';

export interface GenerateField {
  key: string;
  label: string;
  type: GenerateFieldType;
  default: string;
}

export interface GenerateTemplate {
  id: string;
  label: string;
  fields: GenerateField[];
}

const voltageField: GenerateField = {
  key: 'voltageV',
  label: 'Tensão (V)',
  type: 'number',
  default: '12',
};

export const GENERATE_TEMPLATES: readonly GenerateTemplate[] = [
  {
    id: 'series_dc',
    label: 'Série (fonte e resistores)',
    fields: [
      voltageField,
      {
        key: 'resistorsOhm',
        label: 'Resistências (Ω, separadas por vírgula)',
        type: 'resistor-list',
        default: '100, 220',
      },
    ],
  },
  {
    id: 'parallel_dc',
    label: 'Paralelo (fonte e resistores)',
    fields: [
      voltageField,
      {
        key: 'resistorsOhm',
        label: 'Resistências (Ω, separadas por vírgula)',
        type: 'resistor-list',
        default: '100, 200',
      },
    ],
  },
  {
    id: 'voltage_divider',
    label: 'Divisor de tensão',
    fields: [
      voltageField,
      {
        key: 'resistorsOhm',
        label: 'Resistências (Ω, separadas por vírgula, mínimo 2)',
        type: 'resistor-list',
        default: '100, 100',
      },
    ],
  },
  {
    id: 'switch_circuit',
    label: 'Interruptor e carga',
    fields: [
      voltageField,
      { key: 'loadOhm', label: 'Carga (Ω)', type: 'number', default: '100' },
      { key: 'closed', label: 'Fechado', type: 'boolean', default: 'true' },
    ],
  },
] as const;

export type GenerateFormValues = Record<string, string>;

/** Valores por omissão de um template, prontos a editar no formulário. */
export const defaultGenerateValues = (template: GenerateTemplate): GenerateFormValues =>
  Object.fromEntries(template.fields.map((field) => [field.key, field.default]));

export type ParseGenerateResult =
  { ok: true; parameters: GenerateParameters } | { ok: false; error: string };

/** Converte os valores em texto do formulário nos parâmetros JSON esperados pela API. */
export function parseGenerateParameters(
  template: GenerateTemplate,
  values: GenerateFormValues,
): ParseGenerateResult {
  const parameters: GenerateParameters = {};
  for (const field of template.fields) {
    const raw = (values[field.key] ?? '').trim();
    if (field.type === 'boolean') {
      parameters[field.key] = raw === 'true';
      continue;
    }
    if (field.type === 'resistor-list') {
      const list = raw
        .split(',')
        .map((item) => item.trim())
        .filter((item) => item.length > 0)
        .map(Number);
      if (list.length === 0 || list.some((n) => !Number.isFinite(n))) {
        return { ok: false, error: `${field.label}: indique um ou mais números válidos.` };
      }
      parameters[field.key] = list;
      continue;
    }
    const n = Number(raw);
    if (raw === '' || !Number.isFinite(n)) {
      return { ok: false, error: `${field.label}: indique um número válido.` };
    }
    parameters[field.key] = n;
  }
  return { ok: true, parameters };
}
