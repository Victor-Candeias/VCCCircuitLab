import { afterEach, describe, expect, test } from 'vitest';
import { demoCircuit } from '../editor/demoCircuit';
import { emptyCircuit } from './circuitJson';
import { clearAutosave, loadAutosave, saveAutosave } from './persistence';

afterEach(async () => {
  await clearAutosave();
});

describe('persistence', () => {
  test('sem gravação prévia, não há nada para recuperar', async () => {
    expect(await loadAutosave()).toBeUndefined();
  });

  test('grava e recupera o último documento', async () => {
    await saveAutosave(demoCircuit);
    const snapshot = await loadAutosave();
    expect(snapshot?.circuit).toEqual(demoCircuit);
    expect(snapshot?.savedAt).toBeTypeOf('number');
  });

  test('uma nova gravação substitui a anterior', async () => {
    await saveAutosave(demoCircuit);
    await saveAutosave(emptyCircuit());
    const snapshot = await loadAutosave();
    expect(snapshot?.circuit.components).toEqual([]);
  });
});
