/**
 * Ficheiro gerado a partir de schema/circuit.schema.json — não editar à mão.
 * Regenerar com: pnpm --filter @vcccircuitlab/circuit-schema generate
 */

/**
 * Identificador do documento.
 *
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "DocumentId".
 */
export type DocumentId = string;
/**
 * Identificador estável de componente, junção, fio ou rede. Sensível a maiúsculas, único em todo o documento e sem '.', que é reservado como separador `Componente.pino`.
 *
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "ElementId".
 */
export type ElementId = string;
/**
 * Tipo do componente no catálogo (snake_case, ex.: `resistor`, `dc_voltage_source`).
 *
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "ComponentType".
 */
export type ComponentType = string;
/**
 * Rotação em graus, no sentido horário, em torno de `position`.
 *
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "Rotation".
 */
export type Rotation = 0 | 90 | 180 | 270;
/**
 * Identificador de pino, único dentro do componente.
 *
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "PinId".
 */
export type PinId = string;
/**
 * Extremidade de um fio: um terminal (`Componente.pino`) ou o ElementId de uma junção (sem '.').
 *
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "WireEndpoint".
 */
export type WireEndpoint = string;
/**
 * Referência a um terminal no formato `<ElementId do componente>.<PinId>` (ex.: `R1.a`).
 *
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "TerminalRef".
 */
export type TerminalRef = string;

/**
 * Documento canónico de circuito do VCCCircuitLab (schemaVersion 1.0). A conectividade elétrica é definida por `wires` e `junctions`; `nets` é derivado e opcional.
 */
export interface CircuitDocument {
  /**
   * Versão do schema do documento. Alterações incompatíveis exigem nova versão e migração.
   */
  schemaVersion: '1.0';
  id: DocumentId;
  /**
   * Nome do circuito apresentado ao utilizador.
   */
  name: string;
  description?: string;
  /**
   * Sistema de unidades das propriedades (SI). As unidades são explícitas no sufixo do nome da propriedade.
   */
  units: 'SI';
  components: Component[];
  /**
   * Junções explícitas fio-a-fio. Fios cruzados sem junção (ou terminal) comum não ficam ligados.
   */
  junctions?: Junction[];
  /**
   * Ligações entre extremidades (terminais ou junções). Fonte de verdade da conectividade e da geometria dos fios.
   */
  wires: Wire[];
  /**
   * Redes elétricas derivadas pelo normalizador a partir de `wires` e `junctions`. Opcional; nunca é aceite como fonte de verdade se for inconsistente com os fios.
   */
  nets?: Net[];
}
/**
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "Component".
 */
export interface Component {
  id: ElementId;
  type: ComponentType;
  /**
   * Etiqueta opcional apresentada no esquema.
   */
  label?: string;
  position: Point;
  rotation: Rotation;
  properties: ComponentProperties;
  /**
   * @minItems 1
   */
  pins: [PinId, ...PinId[]];
}
/**
 * Coordenadas no canvas, em unidades de canvas (px a zoom 1), com o eixo y para baixo.
 *
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "Point".
 */
export interface Point {
  x: number;
  y: number;
}
/**
 * Propriedades tipadas do componente. Nomes em camelCase com sufixo de unidade SI (ex.: `voltageV`, `resistanceOhm`, `currentA`, `powerW`); booleanos para estados (ex.: `closed`).
 *
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "ComponentProperties".
 */
export interface ComponentProperties {
  [k: string]: number | boolean;
}
/**
 * Ponto de ligação explícito entre fios.
 *
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "Junction".
 */
export interface Junction {
  id: ElementId;
  position: Point;
}
/**
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "Wire".
 */
export interface Wire {
  id: ElementId;
  from: WireEndpoint;
  to: WireEndpoint;
  /**
   * Pontos intermédios do traçado (fios ortogonais), excluindo as extremidades.
   */
  waypoints: Point[];
}
/**
 * Rede elétrica: conjunto de terminais ao mesmo potencial.
 *
 * This interface was referenced by `CircuitDocument`'s JSON-Schema
 * via the `definition` "Net".
 */
export interface Net {
  id: ElementId;
  /**
   * @minItems 1
   */
  terminals: [TerminalRef, ...TerminalRef[]];
}
