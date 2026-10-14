import { beforeEach, describe, expect, test } from 'vitest';
import { demoCircuit } from '../editor/demoCircuit';
import { useEditorStore } from './editorStore';

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
