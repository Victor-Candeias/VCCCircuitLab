import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import Dexie, { type EntityTable } from 'dexie';
import { parseCircuit } from './circuitJson';

/** Única entrada gravada: o último documento canónico, com a hora da gravação. */
interface AutosaveRecord {
  id: 'current';
  savedAt: number;
  circuit: CircuitDocument;
}

class VccCircuitLabDb extends Dexie {
  declare autosave: EntityTable<AutosaveRecord, 'id'>;

  constructor() {
    super('vcccircuitlab');
    this.version(1).stores({ autosave: 'id' });
  }
}

const db = new VccCircuitLabDb();

/** Grava o documento atual como autosave (substitui a entrada anterior). */
export async function saveAutosave(circuit: CircuitDocument): Promise<void> {
  await db.autosave.put({ id: 'current', savedAt: Date.now(), circuit });
}

export interface AutosaveSnapshot {
  circuit: CircuitDocument;
  savedAt: number;
}

/**
 * Lê o autosave, se existir e for válido (reutiliza as regras de integridade da importação
 * de ficheiros). Um autosave corrompido ou de um schema incompatível é ignorado em silêncio.
 */
export async function loadAutosave(): Promise<AutosaveSnapshot | undefined> {
  const record = await db.autosave.get('current');
  if (!record) return undefined;
  const result = parseCircuit(JSON.stringify(record.circuit));
  if (!result.ok) return undefined;
  return { circuit: result.circuit, savedAt: record.savedAt };
}

/** Apaga o autosave. Usado apenas nos testes, para repor o estado entre casos. */
export async function clearAutosave(): Promise<void> {
  await db.autosave.clear();
}
