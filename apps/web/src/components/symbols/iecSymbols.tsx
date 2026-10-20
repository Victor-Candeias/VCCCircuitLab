import type { ComponentProperties, Point, Rotation } from '@vcccircuitlab/circuit-schema';
import type { SymbolId } from './symbolIds';

/**
 * Símbolos IEC 60617 desenhados em coordenadas locais: origem no centro do componente
 * (`Component.position`), rotação 0, mesmas unidades do catálogo. Cada condutor (`Lead`)
 * termina exatamente na posição do pino definida no catálogo.
 */
interface SymbolProps {
  properties: ComponentProperties;
  /** Rotação do componente, para manter texto e sinais na vertical. */
  rotation: Rotation;
}

const SOURCE_RADIUS = 14;
const LAMP_RADIUS = 14;
const METER_RADIUS = 14;

function Lead({ from, to }: { from: Point; to: Point }) {
  return <line className="symbol__lead" x1={from.x} y1={from.y} x2={to.x} y2={to.y} />;
}

function Line({ from, to }: { from: Point; to: Point }) {
  return <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} />;
}

/** Sinal de polaridade (`+` ou `−`) centrado em `at`, sempre na vertical. */
function PolarityMark({ at, sign, rotation }: { at: Point; sign: '+' | '-'; rotation: Rotation }) {
  const h = 3.5;
  return (
    <g
      className="symbol__mark"
      transform={rotation ? `rotate(${-rotation} ${at.x} ${at.y})` : undefined}
    >
      <Line from={{ x: at.x - h, y: at.y }} to={{ x: at.x + h, y: at.y }} />
      {sign === '+' && <Line from={{ x: at.x, y: at.y - h }} to={{ x: at.x, y: at.y + h }} />}
    </g>
  );
}

/** Fonte de tensão ideal (IEC 60617-02-06-01): círculo atravessado pelo condutor. */
function DcVoltageSourceSymbol({ rotation }: Pick<SymbolProps, 'rotation'>) {
  const r = SOURCE_RADIUS;
  return (
    <>
      <Lead from={{ x: 0, y: -40 }} to={{ x: 0, y: -r }} />
      <Lead from={{ x: 0, y: r }} to={{ x: 0, y: 40 }} />
      <circle r={r} />
      <Line from={{ x: 0, y: -r }} to={{ x: 0, y: r }} />
      <PolarityMark at={{ x: 12, y: -26 }} sign="+" rotation={rotation} />
      <PolarityMark at={{ x: 12, y: 26 }} sign="-" rotation={rotation} />
    </>
  );
}

/**
 * Fonte de corrente ideal (IEC 60617-02-06-02): círculo com um traço perpendicular ao condutor.
 * A seta indica o sentido da corrente: sai pelo terminal `positive` (topo).
 */
function DcCurrentSourceSymbol() {
  const r = SOURCE_RADIUS;
  return (
    <>
      <Lead from={{ x: 0, y: -40 }} to={{ x: 0, y: -r }} />
      <Lead from={{ x: 0, y: r }} to={{ x: 0, y: 40 }} />
      <circle r={r} />
      <Line from={{ x: -r, y: 0 }} to={{ x: r, y: 0 }} />
      <polygon className="symbol__fill" points="0,-32 -4,-23 4,-23" />
    </>
  );
}

/** Resistência (IEC 60617-04-01-01): retângulo. */
function ResistorSymbol() {
  return (
    <>
      <Lead from={{ x: -40, y: 0 }} to={{ x: -20, y: 0 }} />
      <Lead from={{ x: 20, y: 0 }} to={{ x: 40, y: 0 }} />
      <rect x={-20} y={-7} width={40} height={14} />
    </>
  );
}

/** Condensador (IEC 60617-04-02-01): duas armaduras paralelas. */
function CapacitorSymbol() {
  return (
    <>
      <Lead from={{ x: -40, y: 0 }} to={{ x: -5, y: 0 }} />
      <Lead from={{ x: 5, y: 0 }} to={{ x: 40, y: 0 }} />
      <Line from={{ x: -5, y: -14 }} to={{ x: -5, y: 14 }} />
      <Line from={{ x: 5, y: -14 }} to={{ x: 5, y: 14 }} />
    </>
  );
}

/** Bobina (IEC 60617-04-03-01): quatro semicírculos. */
function InductorSymbol() {
  return (
    <>
      <Lead from={{ x: -40, y: 0 }} to={{ x: -24, y: 0 }} />
      <Lead from={{ x: 24, y: 0 }} to={{ x: 40, y: 0 }} />
      <path d="M -24 0 a 6 6 0 0 1 12 0 a 6 6 0 0 1 12 0 a 6 6 0 0 1 12 0 a 6 6 0 0 1 12 0" />
    </>
  );
}

/**
 * Interruptor unipolar, contacto de fecho (IEC 60617-07-02-01); desenha o estado `closed`.
 * Os contactos (círculos ocos) distinguem o interruptor fechado de um fio.
 */
function SwitchSpstSymbol({ properties }: Pick<SymbolProps, 'properties'>) {
  const closed = properties.closed === true;
  return (
    <g data-state={closed ? 'closed' : 'open'}>
      <Lead from={{ x: -40, y: 0 }} to={{ x: -16, y: 0 }} />
      <Lead from={{ x: 16, y: 0 }} to={{ x: 40, y: 0 }} />
      <Line from={{ x: -16, y: 0 }} to={closed ? { x: 16, y: 0 } : { x: 14, y: -16 }} />
      <circle className="symbol__contact" cx={-16} cy={0} r={3} />
      <circle className="symbol__contact" cx={16} cy={0} r={3} />
    </g>
  );
}

/** Lâmpada (IEC 60617-08-10-01): círculo com cruz. */
function LampSymbol() {
  const r = LAMP_RADIUS;
  const d = r * Math.SQRT1_2;
  return (
    <>
      <Lead from={{ x: -40, y: 0 }} to={{ x: -r, y: 0 }} />
      <Lead from={{ x: r, y: 0 }} to={{ x: 40, y: 0 }} />
      <circle r={r} />
      <Line from={{ x: -d, y: -d }} to={{ x: d, y: d }} />
      <Line from={{ x: -d, y: d }} to={{ x: d, y: -d }} />
    </>
  );
}

/** Letra do instrumento (`V` ou `A`) desenhada com traços, centrada e sempre na vertical. */
function MeterLetter({ letter, rotation }: { letter: 'V' | 'A'; rotation: Rotation }) {
  return (
    <g
      className="symbol__mark"
      data-letter={letter}
      transform={rotation ? `rotate(${-rotation})` : undefined}
    >
      {letter === 'V' ? (
        <polyline points="-5,-6 0,6 5,-6" />
      ) : (
        <>
          <polyline points="-5,6 0,-6 5,6" />
          <Line from={{ x: -2.5, y: 1.5 }} to={{ x: 2.5, y: 1.5 }} />
        </>
      )}
    </g>
  );
}

/**
 * Instrumento de medida (IEC 60617-08-01-01): círculo com a letra da grandeza (`V` voltímetro,
 * `A` amperímetro); o terminal `positive` fica à esquerda.
 */
function MeterSymbol({ letter, rotation }: { letter: 'V' | 'A'; rotation: Rotation }) {
  const r = METER_RADIUS;
  return (
    <>
      <Lead from={{ x: -40, y: 0 }} to={{ x: -r, y: 0 }} />
      <Lead from={{ x: r, y: 0 }} to={{ x: 40, y: 0 }} />
      <circle r={r} />
      <MeterLetter letter={letter} rotation={rotation} />
      <PolarityMark at={{ x: -26, y: -9 }} sign="+" rotation={rotation} />
      <PolarityMark at={{ x: 26, y: -9 }} sign="-" rotation={rotation} />
    </>
  );
}

/** Osciloscópio: ecrã com uma onda e duas pontas de prova (CH1 em cima, CH2 em baixo). */
function OscilloscopeSymbol() {
  return (
    <>
      <Lead from={{ x: -40, y: -20 }} to={{ x: -24, y: -20 }} />
      <Lead from={{ x: -40, y: 20 }} to={{ x: -24, y: 20 }} />
      <rect x={-24} y={-30} width={58} height={60} rx={4} />
      <path d="M -18 0 q 6 -18 12 0 t 12 0 t 12 0 t 12 0" />
      <circle className="symbol__contact" cx={-24} cy={-20} r={2.5} />
      <circle className="symbol__contact" cx={-24} cy={20} r={2.5} />
    </>
  );
}

/** Terra (IEC 60617-02-15-01): três traços de comprimento decrescente. */
function GroundSymbol() {
  return (
    <>
      <Lead from={{ x: 0, y: -20 }} to={{ x: 0, y: 0 }} />
      <Line from={{ x: -14, y: 0 }} to={{ x: 14, y: 0 }} />
      <Line from={{ x: -9, y: 6 }} to={{ x: 9, y: 6 }} />
      <Line from={{ x: -4, y: 12 }} to={{ x: 4, y: 12 }} />
    </>
  );
}

/** Desenha o símbolo `symbol` (coordenadas locais, rotação 0). */
export function IecSymbol({ symbol, properties, rotation }: SymbolProps & { symbol: SymbolId }) {
  switch (symbol) {
    case 'dc_voltage_source_iec':
      return <DcVoltageSourceSymbol rotation={rotation} />;
    case 'dc_current_source_iec':
      return <DcCurrentSourceSymbol />;
    case 'resistor_iec':
      return <ResistorSymbol />;
    case 'capacitor_iec':
      return <CapacitorSymbol />;
    case 'inductor_iec':
      return <InductorSymbol />;
    case 'switch_spst_iec':
      return <SwitchSpstSymbol properties={properties} />;
    case 'lamp_iec':
      return <LampSymbol />;
    case 'voltmeter_iec':
      return <MeterSymbol letter="V" rotation={rotation} />;
    case 'ammeter_iec':
      return <MeterSymbol letter="A" rotation={rotation} />;
    case 'oscilloscope_iec':
      return <OscilloscopeSymbol />;
    case 'ground_iec':
      return <GroundSymbol />;
  }
}
