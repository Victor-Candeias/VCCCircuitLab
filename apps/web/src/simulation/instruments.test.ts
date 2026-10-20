import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import medicoesJson from '@vcccircuitlab/circuit-schema/examples/medicoes-rc.json';
import { describe, expect, test } from 'vitest';
import type { SimulationResult, TransientResult } from '../api/types';
import { formatReading, instrumentModel, instrumentReadings, scopeChannels } from './instruments';
import { plotOf } from './transient';

const circuit = medicoesJson as unknown as CircuitDocument;
const component = (id: string) => circuit.components.find((c) => c.id === id)!;

// Resposta real da API (motor interno) para medicoes-rc, 2 ms com passo de 1 ms.
const transient: TransientResult = {
  analysis: 'transient',
  status: 'success',
  timeS: [0, 1e-3, 2e-3],
  nodeVoltagesV: {
    N1: [5, 5, 5],
    N2: [0, 0, 0],
    N3: [5, 5, 5],
    N4: [0, 3.1606020272657336, 4.323323527427427],
  },
  components: {
    AM1: { voltageV: [0, 0, 0], currentA: [5e-3, 1.8394e-3, 6.7668e-4], powerW: [0, 0, 0] },
    VM1: { voltageV: [0, 3.1606, 4.323323527427427], currentA: [0, 0, 0], powerW: [0, 0, 0] },
  },
  warnings: [],
};

describe('instrumentos virtuais', () => {
  test('instrumentModel reconhece os instrumentos pelo modelo de simulação', () => {
    expect(instrumentModel('voltmeter')).toBe('voltmeter');
    expect(instrumentModel('ammeter')).toBe('ammeter');
    expect(instrumentModel('oscilloscope')).toBe('oscilloscope');
    expect(instrumentModel('resistor')).toBeNull();
    expect(instrumentModel('desconhecido')).toBeNull();
  });

  test('scopeChannels liga cada canal à rede do seu pino (IDs da API)', () => {
    expect(scopeChannels(circuit, component('OSC1'))).toEqual([
      { pin: 'ch1', label: 'CH1', netId: 'N1' },
      { pin: 'ch2', label: 'CH2', netId: 'N4' },
    ]);
  });

  test('leituras DC: tensão do voltímetro, corrente do amperímetro, tensões dos canais', () => {
    const dc: SimulationResult = {
      analysis: 'dc_operating_point',
      status: 'success',
      nodeVoltagesV: { N1: 5, N2: 0, N3: 5, N4: 5 },
      components: {
        AM1: { voltageV: 0, currentA: 0, powerW: 0 },
        VM1: { voltageV: 5, currentA: 0, powerW: 0 },
      },
      warnings: [],
    };
    const readings = instrumentReadings(circuit, dc);
    expect(readings.map((r) => [r.component.id, r.model, r.values.map(formatReading)])).toEqual([
      ['AM1', 'ammeter', ['0 A']],
      ['VM1', 'voltmeter', ['5 V']],
      ['OSC1', 'oscilloscope', ['5 V', '5 V']],
    ]);
  });

  test('na transitória as leituras são os valores finais', () => {
    const readings = instrumentReadings(circuit, transient);
    expect(readings.map((r) => r.values.map(formatReading))).toEqual([
      ['677 µA'],
      ['4,32 V'],
      ['5 V', '4,32 V'],
    ]);
  });

  test('pontas desligadas (sem tensão definida) não têm leitura', () => {
    const unplugged: CircuitDocument = {
      ...circuit,
      wires: circuit.wires.filter((w) => !w.from.startsWith('OSC1') && !w.from.startsWith('VM1')),
    };
    const result = { ...transient, components: { AM1: transient.components.AM1 } };
    const readings = instrumentReadings(unplugged, result);
    expect(readings.map((r) => r.values.map(formatReading))).toEqual([
      ['677 µA'],
      ['—'],
      ['—', '—'],
    ]);
  });

  test('plotOf com um osciloscópio desenha os canais ligados', () => {
    expect(plotOf(transient, 'scope:OSC1', circuit)).toEqual({
      unit: 'V',
      series: [
        { key: 'CH1', label: 'CH1 (N1)', values: [5, 5, 5] },
        { key: 'CH2', label: 'CH2 (N4)', values: transient.nodeVoltagesV.N4 },
      ],
    });
    expect(plotOf(transient, 'scope:OSC9', circuit).series).toEqual([]);
  });
});
