import { beforeEach, describe, expect, test } from 'vitest';
import { demoCircuit } from '../editor/demoCircuit';
import { HISTORY_LIMIT, useEditorStore } from './editorStore';

const initialState = useEditorStore.getState();

beforeEach(() => {
  useEditorStore.setState(initialState, true);
});

const componentPosition = (id: string) =>
  useEditorStore.getState().circuit.components.find((c) => c.id === id)?.position;

describe('editorStore', () => {
  test('começa com o circuito de demonstração, sem seleção e sem fio em desenho', () => {
    const { circuit, selectedIds, wireDraft } = useEditorStore.getState();
    expect(circuit).toBe(demoCircuit);
    expect(selectedIds).toEqual([]);
    expect(wireDraft).toBeNull();
  });

  test('moveComponent aplica snap à grelha na âncora', () => {
    useEditorStore.getState().moveComponent('R1', { x: 251, y: 129 });
    expect(componentPosition('R1')).toEqual({ x: 260, y: 120 });
  });

  test('moveComponent não altera o documento quando a posição encaixada é a mesma', () => {
    const before = useEditorStore.getState().circuit;
    useEditorStore.getState().moveComponent('R1', { x: 245, y: 115 });
    expect(useEditorStore.getState().circuit).toBe(before);
  });

  test('moveComponent é imutável e ignora IDs desconhecidos', () => {
    useEditorStore.getState().moveComponent('R1', { x: 300, y: 300 });
    expect(demoCircuit.components.find((c) => c.id === 'R1')?.position).toEqual({
      x: 240,
      y: 120,
    });
    const before = useEditorStore.getState().circuit;
    useEditorStore.getState().moveComponent('X9', { x: 0, y: 0 });
    expect(useEditorStore.getState().circuit).toBe(before);
  });

  test('seleção é estado de vista: não altera o circuito', () => {
    const before = useEditorStore.getState().circuit;
    useEditorStore.getState().setSelection(['R1', 'V1', 'R1', 'desconhecido']);
    expect(useEditorStore.getState().selectedIds).toEqual(['R1', 'V1']);
    expect(useEditorStore.getState().circuit).toBe(before);
  });

  test('mover não altera a seleção', () => {
    useEditorStore.getState().setSelection(['R1']);
    useEditorStore.getState().moveComponent('R1', { x: 400, y: 400 });
    expect(useEditorStore.getState().selectedIds).toEqual(['R1']);
  });

  test('loadCircuit substitui o documento e limpa a seleção', () => {
    useEditorStore.getState().setSelection(['R1']);
    const other = { ...demoCircuit, id: 'outro', components: [], wires: [] };
    useEditorStore.getState().loadCircuit(other);
    expect(useEditorStore.getState().circuit).toBe(other);
    expect(useEditorStore.getState().selectedIds).toEqual([]);
  });

  test('loadCircuit cancela o fio em desenho', () => {
    useEditorStore.getState().startWire({ kind: 'terminal', ref: 'R1.a' });
    useEditorStore.getState().loadCircuit({ ...demoCircuit, id: 'outro' });
    expect(useEditorStore.getState().wireDraft).toBeNull();
  });
});

describe('editorStore — ferramenta de fio', () => {
  const store = () => useEditorStore.getState();
  const gnd = { kind: 'terminal', ref: 'GND1.gnd' } as const;

  test('começa um fio num terminal válido; ignora âncoras inexistentes', () => {
    store().startWire({ kind: 'terminal', ref: 'R1.z' });
    expect(store().wireDraft).toBeNull();
    store().startWire(gnd);
    expect(store().wireDraft).toEqual({ start: gnd, waypoints: [] });
  });

  test('waypoints são encaixados na grelha e ortogonais', () => {
    store().startWire(gnd); // (100, 300)
    store().addWireWaypoint({ x: 203, y: 337 });
    expect(store().wireDraft?.waypoints).toEqual([
      { x: 200, y: 300 },
      { x: 200, y: 340 },
    ]);
    store().addWireWaypoint({ x: 199, y: 401 });
    expect(store().wireDraft?.waypoints).toEqual([
      { x: 200, y: 300 },
      { x: 200, y: 400 },
    ]);
  });

  test('removeLastWireWaypoint e cancelWire', () => {
    store().startWire(gnd);
    store().addWireWaypoint({ x: 200, y: 300 });
    store().addWireWaypoint({ x: 200, y: 400 });
    store().removeLastWireWaypoint();
    expect(store().wireDraft?.waypoints).toEqual([{ x: 200, y: 300 }]);
    store().cancelWire();
    expect(store().wireDraft).toBeNull();
    expect(store().circuit).toBe(demoCircuit);
  });

  test('finishWire acrescenta o fio ao documento e sai do modo de desenho', () => {
    store().startWire(gnd);
    store().addWireWaypoint({ x: 280, y: 300 });
    expect(store().finishWire({ kind: 'terminal', ref: 'R1.b' })).toBe(true);
    expect(store().wireDraft).toBeNull();
    expect(store().circuit.wires.at(-1)).toEqual({
      id: 'W5',
      from: 'GND1.gnd',
      to: 'R1.b',
      waypoints: [{ x: 280, y: 300 }],
    });
  });

  test('finishWire inválido mantém o rascunho e o documento', () => {
    store().startWire(gnd);
    expect(store().finishWire(gnd)).toBe(false);
    expect(store().wireDraft).not.toBeNull();
    expect(store().circuit).toBe(demoCircuit);
  });

  test('clickWireAnchor começa e termina o fio; num fio cria uma junção', () => {
    store().clickWireAnchor(gnd);
    store().clickWireAnchor({ kind: 'wire', wireId: 'W2', point: { x: 320, y: 120 } });
    const { circuit, wireDraft } = store();
    expect(wireDraft).toBeNull();
    expect(circuit.junctions).toEqual([{ id: 'J1', position: { x: 320, y: 120 } }]);
    expect(circuit.wires.filter((w) => w.from === 'J1' || w.to === 'J1')).toHaveLength(3);
  });

  test('moveJunction aplica snap e as junções podem ser selecionadas', () => {
    store().clickWireAnchor(gnd);
    store().clickWireAnchor({ kind: 'wire', wireId: 'W2', point: { x: 320, y: 120 } });
    store().moveJunction('J1', { x: 331, y: 111 });
    expect(store().circuit.junctions).toEqual([{ id: 'J1', position: { x: 340, y: 120 } }]);
    const before = store().circuit;
    store().moveJunction('J1', { x: 345, y: 115 });
    store().moveJunction('J9', { x: 0, y: 0 });
    expect(store().circuit).toBe(before);

    store().setSelection(['J1', 'R1']);
    expect(store().selectedIds).toEqual(['J1', 'R1']);
  });
});

describe('editorStore — paleta e rotação', () => {
  const store = () => useEditorStore.getState();
  const component = (id: string) => store().circuit.components.find((c) => c.id === id);

  test('addComponent coloca o componente com snap e seleciona-o', () => {
    store().setSelection(['V1']);
    expect(store().addComponent('resistor', { x: 411, y: 289 })).toBe('R2');
    expect(component('R2')).toMatchObject({ position: { x: 420, y: 280 }, rotation: 0 });
    expect(store().selectedIds).toEqual(['R2']);
  });

  test('addComponent ignora tipos fora do catálogo', () => {
    expect(store().addComponent('motor', { x: 0, y: 0 })).toBeUndefined();
    expect(store().circuit).toBe(demoCircuit);
  });

  test('rotateSelection roda os componentes selecionados (horário e anti-horário)', () => {
    store().setSelection(['R1', 'H1']);
    store().rotateSelection();
    expect(component('R1')?.rotation).toBe(90);
    expect(component('H1')?.rotation).toBe(180);
    store().rotateSelection(-90);
    store().rotateSelection(-90);
    expect(component('R1')?.rotation).toBe(270);
    expect(component('V1')?.rotation).toBe(0);
  });

  test('rotateSelection sem componentes selecionados não altera o documento', () => {
    store().rotateSelection();
    expect(store().circuit).toBe(demoCircuit);
  });
});

describe('editorStore — histórico, apagar e copiar/colar', () => {
  const store = () => useEditorStore.getState();
  const ids = () => store().circuit.components.map((c) => c.id);
  const wireIds = () => store().circuit.wires.map((w) => w.id);

  test('undo/redo percorrem adicionar, mover, rodar, ligar e apagar', () => {
    store().addComponent('resistor', { x: 400, y: 300 });
    store().moveComponent('R2', { x: 500, y: 300 });
    store().rotateSelection();
    store().startWire({ kind: 'terminal', ref: 'R2.a' });
    store().finishWire({ kind: 'terminal', ref: 'H1.b' });
    store().setSelection(['R2']);
    store().deleteSelection();
    const final = store().circuit;
    expect(store().past).toHaveLength(5);
    expect(ids()).not.toContain('R2');

    store().undo();
    expect(ids()).toContain('R2');
    expect(wireIds()).toContain('W5');
    for (let i = 0; i < 4; i += 1) store().undo();
    expect(store().circuit).toBe(demoCircuit);
    expect(store().selectedIds).toEqual([]);
    store().undo();
    expect(store().circuit).toBe(demoCircuit);

    for (let i = 0; i < 5; i += 1) store().redo();
    expect(store().circuit).toBe(final);
    expect(store().future).toEqual([]);
  });

  test('uma alteração nova descarta o que tinha sido desfeito', () => {
    store().moveComponent('R1', { x: 300, y: 120 });
    store().undo();
    expect(store().future).toHaveLength(1);
    store().moveComponent('H1', { x: 400, y: 200 });
    expect(store().future).toEqual([]);
    store().redo();
    expect(store().circuit.components.find((c) => c.id === 'R1')?.position.x).toBe(240);
  });

  test(`o histórico guarda no máximo ${HISTORY_LIMIT} passos`, () => {
    for (let i = 1; i <= HISTORY_LIMIT + 5; i += 1) {
      store().moveComponent('R1', { x: 240 + i * 20, y: 120 });
    }
    expect(store().past).toHaveLength(HISTORY_LIMIT);
  });

  test('loadCircuit limpa o histórico', () => {
    store().moveComponent('R1', { x: 300, y: 120 });
    store().undo();
    store().loadCircuit(demoCircuit);
    expect(store().past).toEqual([]);
    expect(store().future).toEqual([]);
  });

  test('um gesto (arrastar) fica num só passo; sem alterações não regista nada', () => {
    store().beginHistoryGroup();
    store().moveComponent('R1', { x: 260, y: 120 });
    store().moveComponent('R1', { x: 280, y: 120 });
    store().moveComponent('R1', { x: 300, y: 140 });
    expect(store().past).toEqual([]);
    store().undo(); // ignorado durante o gesto
    store().endHistoryGroup();
    expect(store().past).toHaveLength(1);
    store().undo();
    expect(store().circuit).toBe(demoCircuit);

    store().beginHistoryGroup();
    store().endHistoryGroup();
    expect(store().past).toEqual([]);
    expect(store().historyGroup).toBeNull();
  });

  test('deleteSelection apaga componentes, fios selecionados e fios ligados', () => {
    store().setSelection(['W4']);
    expect(store().selectedIds).toEqual(['W4']);
    store().deleteSelection();
    expect(wireIds()).toEqual(['W1', 'W2', 'W3']);
    store().setSelection(['R1']);
    store().deleteSelection();
    expect(wireIds()).toEqual(['W3']);
    expect(store().selectedIds).toEqual([]);
    const before = store().circuit;
    store().deleteSelection();
    expect(store().circuit).toBe(before);
    expect(store().past).toHaveLength(2);
  });

  test('copiar e colar desloca cada colagem e seleciona os elementos colados', () => {
    store().setSelection(['R1']);
    store().paste(); // sem nada copiado
    expect(store().circuit).toBe(demoCircuit);
    store().copySelection();
    store().paste();
    expect(store().selectedIds).toEqual(['R2']);
    store().paste();
    expect(store().selectedIds).toEqual(['R3']);
    const position = (id: string) => store().circuit.components.find((c) => c.id === id)?.position;
    expect(position('R2')).toEqual({ x: 280, y: 160 });
    expect(position('R3')).toEqual({ x: 320, y: 200 });
    store().undo();
    expect(ids()).not.toContain('R3');
    expect(store().selectedIds).toEqual([]);
  });

  test('cortar apaga e a primeira colagem repõe no mesmo sítio (IDs livres reaproveitados)', () => {
    store().setSelection(['V1', 'GND1']);
    store().cutSelection();
    expect(ids()).toEqual(['R1', 'H1']);
    expect(wireIds()).toEqual(['W2']);
    store().paste();
    expect(store().circuit.components.slice(-2)).toMatchObject([
      { id: 'V1', position: { x: 100, y: 200 } },
      { id: 'GND1', position: { x: 100, y: 320 } },
    ]);
    expect(store().circuit.wires.at(-1)).toMatchObject({ from: 'GND1.gnd', to: 'V1.negative' });
    expect(store().past).toHaveLength(2);
  });
});
