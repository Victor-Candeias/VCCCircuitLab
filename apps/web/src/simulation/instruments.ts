import type { CircuitDocument, Component } from '@vcccircuitlab/circuit-schema';
import type { SimulationResult, TransientResult } from '../api/types';
import { getComponentDefinition } from '../editor/catalog';
import { formatQuantity } from './format';
import { circuitNets } from './nets';

/** Instrumentos virtuais ideais (F2-03), pelo `simulationModel` do catálogo. */
export type InstrumentModel = 'voltmeter' | 'ammeter' | 'oscilloscope';

const INSTRUMENT_MODELS: readonly string[] = ['voltmeter', 'ammeter', 'oscilloscope'];

export function instrumentModel(type: string): InstrumentModel | null {
  const model = getComponentDefinition(type)?.simulationModel;
  return model && INSTRUMENT_MODELS.includes(model) ? (model as InstrumentModel) : null;
}

/** Canal do osciloscópio (`CH1`, `CH2`…) e a rede a que o seu pino está ligado. */
export interface ScopeChannel {
  pin: string;
  label: string;
  netId: string;
}

/** Canais do osciloscópio `component`, pela ordem dos pinos (tensão em relação à terra). */
export function scopeChannels(circuit: CircuitDocument, component: Component): ScopeChannel[] {
  const nets = circuitNets(circuit);
  return component.pins.flatMap((pin, index) => {
    const net = nets.find((n) => n.terminals.includes(`${component.id}.${pin}`));
    return net ? [{ pin, label: `CH${index + 1}`, netId: net.id }] : [];
  });
}

/** Uma leitura: `value` é `null` quando o resultado não a define (ponta desligada). */
export interface InstrumentValue {
  label: string;
  value: number | null;
  unit: 'V' | 'A';
}

export interface InstrumentReading {
  component: Component;
  model: InstrumentModel;
  values: InstrumentValue[];
}

type Result = SimulationResult | TransientResult;

/** Valor DC, ou o último valor da série da transitória. */
const latest = (value: number | readonly number[] | undefined): number | null => {
  const last = Array.isArray(value) ? value[value.length - 1] : value;
  return typeof last === 'number' ? last : null;
};

/** Leitura do instrumento `component` (valores finais na transitória), ou `null` se não for um. */
export function instrumentReading(
  circuit: CircuitDocument,
  result: Result,
  component: Component,
): InstrumentReading | null {
  const model = instrumentModel(component.type);
  if (!model) return null;
  const own = result.components[component.id];
  let values: InstrumentValue[];
  if (model === 'voltmeter') {
    values = [{ label: 'V', value: latest(own?.voltageV), unit: 'V' }];
  } else if (model === 'ammeter') {
    values = [{ label: 'I', value: latest(own?.currentA), unit: 'A' }];
  } else {
    const byPin = new Map(scopeChannels(circuit, component).map((ch) => [ch.pin, ch]));
    values = component.pins.map((pin, index) => {
      const channel = byPin.get(pin);
      const voltage = channel ? result.nodeVoltagesV[channel.netId] : undefined;
      return { label: `CH${index + 1}`, value: latest(voltage), unit: 'V' };
    });
  }
  return { component, model, values };
}

/** Leituras de todos os instrumentos do circuito, pela ordem do documento. */
export function instrumentReadings(circuit: CircuitDocument, result: Result): InstrumentReading[] {
  return circuit.components.flatMap((component) => {
    const reading = instrumentReading(circuit, result, component);
    return reading ? [reading] : [];
  });
}

/** Texto curto de um valor (`8 V`, `40 mA`, `—` sem leitura). */
export const formatReading = ({ value, unit }: InstrumentValue): string =>
  value === null ? '—' : formatQuantity(value, unit);
