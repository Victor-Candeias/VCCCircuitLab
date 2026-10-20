/**
 * Ficheiro gerado a partir de schema/catalog.schema.json — não editar à mão.
 * Regenerar com: pnpm --filter @vcccircuitlab/circuit-schema generate
 */

/**
 * Categoria usada para agrupar a paleta.
 *
 * This interface was referenced by `ComponentCatalog`'s JSON-Schema
 * via the `definition` "ComponentCategory".
 */
export type ComponentCategory = 'source' | 'passive' | 'switch' | 'load' | 'instrument' | 'reference';
/**
 * Natureza elétrica do pino: `passive` (sem polaridade), `positive`/`negative` (polaridade de fontes) ou `reference` (terra).
 *
 * This interface was referenced by `ComponentCatalog`'s JSON-Schema
 * via the `definition` "PinKind".
 */
export type PinKind = 'passive' | 'positive' | 'negative' | 'reference';
/**
 * This interface was referenced by `ComponentCatalog`'s JSON-Schema
 * via the `definition` "PropertyDefinition".
 */
export type PropertyDefinition = NumberPropertyDefinition | BooleanPropertyDefinition;
/**
 * Modelo elétrico usado pelo solver. `null` indica `não suportado pelo solver` (o componente pode ser desenhado mas não simulado).
 *
 * This interface was referenced by `ComponentCatalog`'s JSON-Schema
 * via the `definition` "SimulationModel".
 */
export type SimulationModel =
  | 'dc_voltage_source'
  | 'dc_current_source'
  | 'resistor'
  | 'ideal_switch'
  | 'resistive_lamp'
  | 'capacitor'
  | 'inductor'
  | 'voltmeter'
  | 'ammeter'
  | 'oscilloscope'
  | 'ground'
  | null;

/**
 * Catálogo de componentes do VCCCircuitLab. Separa símbolo, terminais, validação de propriedades e modelo elétrico.
 */
export interface ComponentCatalog {
  /**
   * Versão do formato do catálogo.
   */
  catalogVersion: '1.0';
  /**
   * Passo da grelha do editor em unidades de canvas. As posições dos pinos são múltiplos deste valor.
   */
  gridSize: number;
  /**
   * @minItems 1
   */
  components: [ComponentDefinition, ...ComponentDefinition[]];
}
/**
 * This interface was referenced by `ComponentCatalog`'s JSON-Schema
 * via the `definition` "ComponentDefinition".
 */
export interface ComponentDefinition {
  /**
   * Tipo usado em `Component.type` no documento de circuito.
   */
  type: string;
  /**
   * Nome apresentado na paleta.
   */
  label: string;
  description?: string;
  category: ComponentCategory;
  /**
   * Prefixo dos IDs gerados para novas instâncias (ex.: `R` → `R1`, `R2`).
   */
  idPrefix: string;
  /**
   * Identificador do símbolo SVG (simbologia IEC).
   */
  symbol: string;
  size: Size;
  /**
   * @minItems 1
   */
  pins: [PinDefinition, ...PinDefinition[]];
  /**
   * Propriedades por nome (camelCase com sufixo da unidade SI).
   */
  properties: {
    [k: string]: PropertyDefinition;
  };
  simulationModel: SimulationModel;
}
/**
 * Caixa envolvente do símbolo com rotação 0, centrada em `position`.
 *
 * This interface was referenced by `ComponentCatalog`'s JSON-Schema
 * via the `definition` "Size".
 */
export interface Size {
  width: number;
  height: number;
}
/**
 * This interface was referenced by `ComponentCatalog`'s JSON-Schema
 * via the `definition` "PinDefinition".
 */
export interface PinDefinition {
  id: string;
  kind: PinKind;
  position: RelativePoint;
}
/**
 * Posição do pino relativa a `position` do componente, com rotação 0, em unidades de canvas.
 */
export interface RelativePoint {
  x: number;
  y: number;
}
/**
 * Propriedade numérica. Os campos de validação seguem as palavras-chave do JSON Schema.
 *
 * This interface was referenced by `ComponentCatalog`'s JSON-Schema
 * via the `definition` "NumberPropertyDefinition".
 */
export interface NumberPropertyDefinition {
  type: 'number';
  title: string;
  description?: string;
  /**
   * Símbolo da unidade SI apresentado na interface (ex.: `V`, `A`, `Ω`, `W`).
   */
  unit: string;
  default: number;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
}
/**
 * Propriedade booleana (estado).
 *
 * This interface was referenced by `ComponentCatalog`'s JSON-Schema
 * via the `definition` "BooleanPropertyDefinition".
 */
export interface BooleanPropertyDefinition {
  type: 'boolean';
  title: string;
  description?: string;
  default: boolean;
}
/**
 * This interface was referenced by `ComponentCatalog`'s JSON-Schema
 * via the `definition` "RelativePoint".
 */
export interface RelativePoint1 {
  x: number;
  y: number;
}
