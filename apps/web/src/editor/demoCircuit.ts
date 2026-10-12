import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';

/** Circuito inicial do editor: fonte de 12 V, resistência e lâmpada em série, com terra. */
export const demoCircuit: CircuitDocument = {
  schemaVersion: '1.0',
  id: 'demo',
  name: 'Circuito de demonstração',
  units: 'SI',
  components: [
    {
      id: 'V1',
      type: 'dc_voltage_source',
      position: { x: 100, y: 200 },
      rotation: 0,
      properties: { voltageV: 12 },
      pins: ['positive', 'negative'],
    },
    {
      id: 'R1',
      type: 'resistor',
      position: { x: 240, y: 120 },
      rotation: 0,
      properties: { resistanceOhm: 100 },
      pins: ['a', 'b'],
    },
    {
      id: 'H1',
      type: 'lamp',
      position: { x: 360, y: 200 },
      rotation: 90,
      properties: { ratedVoltageV: 12, ratedPowerW: 5 },
      pins: ['a', 'b'],
    },
    {
      id: 'GND1',
      type: 'ground',
      position: { x: 100, y: 320 },
      rotation: 0,
      properties: {},
      pins: ['gnd'],
    },
  ],
  wires: [
    { id: 'W1', from: 'V1.positive', to: 'R1.a', waypoints: [{ x: 100, y: 120 }] },
    { id: 'W2', from: 'R1.b', to: 'H1.a', waypoints: [{ x: 360, y: 120 }] },
    {
      id: 'W3',
      from: 'H1.b',
      to: 'V1.negative',
      waypoints: [
        { x: 360, y: 260 },
        { x: 100, y: 260 },
      ],
    },
    { id: 'W4', from: 'GND1.gnd', to: 'V1.negative', waypoints: [] },
  ],
};
