import type {
  CircuitDocument,
  Component,
  Junction,
  Point,
  Wire,
} from '@vcccircuitlab/circuit-schema';
import circuitSchema from '@vcccircuitlab/circuit-schema/circuit.schema.json';
import Ajv2020, { type ErrorObject } from 'ajv/dist/2020';
import { getComponentDefinition } from '../editor/catalog';
import { parseTerminal } from '../editor/wiring';

/** Tamanho máximo aceite na importação (protege o browser de ficheiros enormes). */
export const MAX_IMPORT_BYTES = 5 * 1024 * 1024;

/** Número máximo de erros apresentados (os restantes são resumidos). */
const MAX_ERRORS = 20;

export type ImportResult =
  { ok: true; circuit: CircuitDocument; warnings: string[] } | { ok: false; errors: string[] };

const ajv = new Ajv2020({ allErrors: true, strict: true, allowUnionTypes: true });
const validateSchema = ajv.compile<CircuitDocument>(circuitSchema);

const point = ({ x, y }: Point): Point => ({ x, y });

const canonicalComponent = (c: Component): Component => ({
  id: c.id,
  type: c.type,
  ...(c.label !== undefined && { label: c.label }),
  position: point(c.position),
  rotation: c.rotation,
  properties: { ...c.properties },
  pins: [...c.pins],
});

const canonicalJunction = (j: Junction): Junction => ({ id: j.id, position: point(j.position) });

const canonicalWire = (w: Wire): Wire => ({
  id: w.id,
  from: w.from,
  to: w.to,
  waypoints: w.waypoints.map(point),
});

/**
 * Documento canónico pronto a gravar: chaves pela ordem do schema e sem `nets`, que é
 * derivado (o normalizador da API reconstrói-o a partir de `wires` e `junctions`).
 */
export function toCanonical(circuit: CircuitDocument): CircuitDocument {
  return {
    schemaVersion: circuit.schemaVersion,
    id: circuit.id,
    name: circuit.name,
    ...(circuit.description !== undefined && { description: circuit.description }),
    units: circuit.units,
    components: circuit.components.map(canonicalComponent),
    ...(circuit.junctions?.length && { junctions: circuit.junctions.map(canonicalJunction) }),
    wires: circuit.wires.map(canonicalWire),
  };
}

/** Circuito vazio para "Novo". */
export const emptyCircuit = (): CircuitDocument => ({
  schemaVersion: '1.0',
  id: `circuit-${Date.now().toString(36)}`,
  name: 'Novo circuito',
  units: 'SI',
  components: [],
  wires: [],
});

/** JSON do documento canónico (indentação de 2 espaços, terminado em nova linha). */
export const serializeCircuit = (circuit: CircuitDocument): string =>
  `${JSON.stringify(toCanonical(circuit), null, 2)}\n`;

/** Nome de ficheiro a partir do nome do circuito (`Circuito série` → `circuito-serie.json`). */
export function circuitFileName(circuit: CircuitDocument): string {
  const slug = circuit.name
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
  return `${slug || circuit.id}.json`;
}

function formatSchemaError(error: ErrorObject): string {
  const path = error.instancePath || '(raiz)';
  switch (error.keyword) {
    case 'additionalProperties':
      return `${path}: propriedade não permitida "${String(error.params.additionalProperty)}"`;
    case 'required':
      return `${path}: falta a propriedade obrigatória "${String(error.params.missingProperty)}"`;
    case 'const':
      return `${path}: valor inválido (esperado ${JSON.stringify(error.params.allowedValue)})`;
    case 'enum':
      return `${path}: valor inválido (permitidos: ${(error.params.allowedValues as unknown[])
        .map((v) => JSON.stringify(v))
        .join(', ')})`;
    default:
      return `${path}: ${error.message ?? 'inválido'}`;
  }
}

/**
 * Regras que o JSON Schema não exprime mas de que o editor depende: IDs únicos no documento,
 * tipos e pinos do catálogo, e extremidades de fios que existem.
 */
function integrityErrors(circuit: CircuitDocument): string[] {
  const errors: string[] = [];
  const seen = new Set<string>();
  const checkId = (id: string, where: string) => {
    if (seen.has(id))
      errors.push(`${where}: ID duplicado "${id}" (os IDs são únicos no documento)`);
    seen.add(id);
  };

  circuit.components.forEach((c, i) => {
    const where = `/components/${i}`;
    checkId(c.id, where);
    const definition = getComponentDefinition(c.type);
    if (!definition) {
      errors.push(`${where}: tipo de componente desconhecido "${c.type}"`);
      return;
    }
    const expected = definition.pins.map((p) => p.id);
    const unknown = c.pins.filter((p) => !expected.includes(p));
    const missing = expected.filter((p) => !c.pins.includes(p));
    if (unknown.length > 0) {
      errors.push(`${where}: pinos desconhecidos para ${c.type}: ${unknown.join(', ')}`);
    }
    if (missing.length > 0)
      errors.push(`${where}: faltam pinos de ${c.type}: ${missing.join(', ')}`);
    if (new Set(c.pins).size !== c.pins.length) errors.push(`${where}: pinos repetidos`);
  });
  (circuit.junctions ?? []).forEach((j, i) => checkId(j.id, `/junctions/${i}`));
  circuit.wires.forEach((w, i) => checkId(w.id, `/wires/${i}`));
  (circuit.nets ?? []).forEach((n, i) => checkId(n.id, `/nets/${i}`));

  const components = new Map(circuit.components.map((c) => [c.id, c]));
  const junctions = new Set((circuit.junctions ?? []).map((j) => j.id));
  const endpointError = (endpoint: string): string | undefined => {
    const terminal = parseTerminal(endpoint);
    if (!terminal) return junctions.has(endpoint) ? undefined : `junção inexistente "${endpoint}"`;
    const component = components.get(terminal.componentId);
    if (!component) return `componente inexistente em "${endpoint}"`;
    return component.pins.includes(terminal.pinId) ? undefined : `pino inexistente "${endpoint}"`;
  };
  circuit.wires.forEach((w, i) => {
    const where = `/wires/${i}`;
    for (const endpoint of [w.from, w.to]) {
      const error = endpointError(endpoint);
      if (error) errors.push(`${where}: ${error}`);
    }
    if (w.from === w.to) errors.push(`${where}: o fio liga "${w.from}" a si próprio`);
  });
  return errors;
}

const limitErrors = (errors: string[]): string[] =>
  errors.length > MAX_ERRORS
    ? [...errors.slice(0, MAX_ERRORS), `… e mais ${errors.length - MAX_ERRORS} erro(s).`]
    : errors;

/**
 * Lê um documento canónico (JSON Schema 1.0) e verifica a integridade necessária ao editor.
 * O `nets` importado é descartado (é derivado e nunca é aceite como fonte de verdade).
 */
export function parseCircuit(text: string): ImportResult {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (error) {
    return { ok: false, errors: [`JSON inválido: ${(error as Error).message}`] };
  }
  if (!validateSchema(data)) {
    return { ok: false, errors: limitErrors((validateSchema.errors ?? []).map(formatSchemaError)) };
  }
  const errors = integrityErrors(data);
  if (errors.length > 0) return { ok: false, errors: limitErrors(errors) };

  const warnings = data.nets
    ? ['As redes (nets) do ficheiro foram ignoradas: são recalculadas a partir dos fios.']
    : [];
  return { ok: true, circuit: toCanonical(data), warnings };
}

/** Lê um ficheiro escolhido pelo utilizador, com limite de tamanho. */
export async function readCircuitFile(file: Blob): Promise<ImportResult> {
  if (file.size > MAX_IMPORT_BYTES) {
    return {
      ok: false,
      errors: [`Ficheiro demasiado grande (máximo ${MAX_IMPORT_BYTES / 1024 / 1024} MB).`],
    };
  }
  return parseCircuit(await file.text());
}
