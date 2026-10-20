/** Identificadores dos símbolos SVG desenhados (`ComponentDefinition.symbol` do catálogo). */
export const SYMBOL_IDS = [
  'dc_voltage_source_iec',
  'dc_current_source_iec',
  'resistor_iec',
  'capacitor_iec',
  'inductor_iec',
  'switch_spst_iec',
  'lamp_iec',
  'voltmeter_iec',
  'ammeter_iec',
  'oscilloscope_iec',
  'diode_iec',
  'led_iec',
  'npn_iec',
  'pnp_iec',
  'ground_iec',
] as const;

export type SymbolId = (typeof SYMBOL_IDS)[number];

export const isSymbolId = (symbol: string): symbol is SymbolId =>
  (SYMBOL_IDS as readonly string[]).includes(symbol);
