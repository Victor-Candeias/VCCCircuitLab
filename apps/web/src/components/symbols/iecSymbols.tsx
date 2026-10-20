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

/** Ponta de seta cheia em `to`, no sentido `from` → `to`. */
function ArrowHead({ from, to, size = 6 }: { from: Point; to: Point; size?: number }) {
  const length = Math.hypot(to.x - from.x, to.y - from.y);
  const ux = (to.x - from.x) / length;
  const uy = (to.y - from.y) / length;
  const bx = to.x - ux * size;
  const by = to.y - uy * size;
  const w = size / 2;
  const points = [
    [to.x, to.y],
    [bx - uy * w, by + ux * w],
    [bx + uy * w, by - ux * w],
  ];
  return <polygon className="symbol__fill" points={points.map((p) => p.join(',')).join(' ')} />;
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

/** Fonte de tensão alternada (IEC 60617-02-06-01 + 02-02-04): círculo com uma sinusoide. */
function AcVoltageSourceSymbol() {
  const r = SOURCE_RADIUS;
  return (
    <>
      <Lead from={{ x: 0, y: -40 }} to={{ x: 0, y: -r }} />
      <Lead from={{ x: 0, y: r }} to={{ x: 0, y: 40 }} />
      <circle r={r} />
      <path d="M -9 0 q 4.5 -10 9 0 t 9 0" />
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

/**
 * Comutador de lustre/escada (IEC 60617-07-02-03): a lâmina liga o comum (esquerda) a `l1`
 * (cima) ou, com `toL2`, a `l2` (baixo).
 */
function SwitchSpdtSymbol({ properties }: Pick<SymbolProps, 'properties'>) {
  const toL2 = properties.toL2 === true;
  return (
    <g data-state={toL2 ? 'l2' : 'l1'}>
      <Lead from={{ x: -40, y: 0 }} to={{ x: -16, y: 0 }} />
      <Lead from={{ x: 16, y: -12 }} to={{ x: 30, y: -12 }} />
      <Lead from={{ x: 30, y: -12 }} to={{ x: 40, y: -20 }} />
      <Lead from={{ x: 16, y: 12 }} to={{ x: 30, y: 12 }} />
      <Lead from={{ x: 30, y: 12 }} to={{ x: 40, y: 20 }} />
      <Line from={{ x: -16, y: 0 }} to={{ x: 16, y: toL2 ? 12 : -12 }} />
      <circle className="symbol__contact" cx={-16} cy={0} r={3} />
      <circle className="symbol__contact" cx={16} cy={-12} r={3} />
      <circle className="symbol__contact" cx={16} cy={12} r={3} />
    </g>
  );
}

/**
 * Relé (IEC 60617-07-15-01 + 07-02-01): bobina (retângulo, à esquerda) e contacto de fecho
 * (à direita) ligados por um traço tracejado. Só símbolo: o solver ainda não o simula.
 */
function RelaySymbol() {
  return (
    <>
      <Lead from={{ x: -40, y: -20 }} to={{ x: -28, y: -20 }} />
      <Lead from={{ x: -28, y: -20 }} to={{ x: -28, y: -10 }} />
      <Lead from={{ x: -40, y: 20 }} to={{ x: -28, y: 20 }} />
      <Lead from={{ x: -28, y: 20 }} to={{ x: -28, y: 10 }} />
      <rect x={-36} y={-10} width={16} height={20} />
      <Line from={{ x: -20, y: 0 }} to={{ x: 10, y: 0 }} />
      <Lead from={{ x: 24, y: -20 }} to={{ x: 40, y: -20 }} />
      <Lead from={{ x: 24, y: 20 }} to={{ x: 40, y: 20 }} />
      <Lead from={{ x: 24, y: -20 }} to={{ x: 24, y: -10 }} />
      <Line from={{ x: 24, y: 20 }} to={{ x: 12, y: -8 }} />
      <circle className="symbol__contact" cx={24} cy={-10} r={2.5} />
      <line className="symbol__link" x1={-20} y1={0} x2={18} y2={6} />
    </>
  );
}

/**
 * Disjuntor (IEC 60617-07-13-05): contacto de fecho com uma cruz no contacto fixo; desenha o
 * estado `closed` (armado) ou disparado/aberto.
 */
function CircuitBreakerSymbol({ properties }: Pick<SymbolProps, 'properties'>) {
  const closed = properties.closed !== false;
  return (
    <g data-state={closed ? 'closed' : 'open'}>
      <Lead from={{ x: -40, y: 0 }} to={{ x: -16, y: 0 }} />
      <Lead from={{ x: 16, y: 0 }} to={{ x: 40, y: 0 }} />
      <Line from={{ x: -16, y: 0 }} to={closed ? { x: 16, y: 0 } : { x: 14, y: -16 }} />
      <Line from={{ x: 12, y: -4 }} to={{ x: 20, y: 4 }} />
      <Line from={{ x: 12, y: 4 }} to={{ x: 20, y: -4 }} />
      <circle className="symbol__contact" cx={-16} cy={0} r={3} />
    </g>
  );
}

/**
 * Interruptor diferencial (IEC 60617-07-13-05 + 07-20-02): dois polos (fase em cima, neutro em
 * baixo) manobrados em conjunto e um toro de deteção da corrente residual.
 */
function RcdSymbol({ properties }: Pick<SymbolProps, 'properties'>) {
  const closed = properties.closed !== false;
  const blade = (y: number) => (
    <Line from={{ x: 4, y }} to={closed ? { x: 22, y } : { x: 20, y: y - 12 }} />
  );
  return (
    <g data-state={closed ? 'closed' : 'open'}>
      <Lead from={{ x: -40, y: -20 }} to={{ x: 4, y: -20 }} />
      <Lead from={{ x: -40, y: 20 }} to={{ x: 4, y: 20 }} />
      <Lead from={{ x: 22, y: -20 }} to={{ x: 40, y: -20 }} />
      <Lead from={{ x: 22, y: 20 }} to={{ x: 40, y: 20 }} />
      {blade(-20)}
      {blade(20)}
      <ellipse cx={-18} cy={0} rx={6} ry={26} />
      <line className="symbol__link" x1={12} y1={-24} x2={12} y2={16} />
      <circle className="symbol__contact" cx={4} cy={-20} r={2.5} />
      <circle className="symbol__contact" cx={4} cy={20} r={2.5} />
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

/** Díodo (IEC 60617-05-03-01): triângulo no sentido ânodo (esquerda) → cátodo (barra). */
function DiodeSymbol({ light = false }: { light?: boolean }) {
  return (
    <>
      <Lead from={{ x: -40, y: 0 }} to={{ x: -10, y: 0 }} />
      <Lead from={{ x: 10, y: 0 }} to={{ x: 40, y: 0 }} />
      <polygon className="symbol__fill" points="-10,-11 -10,11 10,0" />
      <Line from={{ x: 10, y: -11 }} to={{ x: 10, y: 11 }} />
      {light && (
        <g data-testid="led-arrows">
          <Line from={{ x: -2, y: -14 }} to={{ x: 6, y: -24 }} />
          <ArrowHead from={{ x: -2, y: -14 }} to={{ x: 6, y: -24 }} size={5} />
          <Line from={{ x: 6, y: -12 }} to={{ x: 14, y: -22 }} />
          <ArrowHead from={{ x: 6, y: -12 }} to={{ x: 14, y: -22 }} size={5} />
        </g>
      )}
    </>
  );
}

/**
 * Transístor bipolar (IEC 60617-05-05-01/02): base à esquerda, coletor e emissor à direita.
 * A seta no emissor aponta para fora (NPN) ou para a base (PNP); no PNP o emissor fica em cima.
 */
function BjtSymbol({ type }: { type: 'npn' | 'pnp' }) {
  const emitterY = type === 'npn' ? 1 : -1;
  const collector = { x: 20, y: -22 * emitterY };
  const emitter = { x: 20, y: 22 * emitterY };
  const emitterBase = { x: -6, y: 7 * emitterY };
  const along = (t: number) => ({
    x: emitterBase.x + t * (emitter.x - emitterBase.x),
    y: emitterBase.y + t * (emitter.y - emitterBase.y),
  });
  return (
    <>
      <circle cx={4} cy={0} r={26} />
      <Lead from={{ x: -40, y: 0 }} to={{ x: -6, y: 0 }} />
      <Lead from={collector} to={{ x: 20, y: -40 * emitterY }} />
      <Lead from={emitter} to={{ x: 20, y: 40 * emitterY }} />
      <Line from={{ x: -6, y: -14 }} to={{ x: -6, y: 14 }} />
      <Line from={{ x: -6, y: -7 * emitterY }} to={collector} />
      <Line from={emitterBase} to={emitter} />
      {type === 'npn' ? (
        <ArrowHead from={emitterBase} to={along(0.75)} />
      ) : (
        <ArrowHead from={emitter} to={along(0.3)} />
      )}
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
    case 'ac_voltage_source_iec':
      return <AcVoltageSourceSymbol />;
    case 'resistor_iec':
      return <ResistorSymbol />;
    case 'capacitor_iec':
      return <CapacitorSymbol />;
    case 'inductor_iec':
      return <InductorSymbol />;
    case 'switch_spst_iec':
      return <SwitchSpstSymbol properties={properties} />;
    case 'switch_spdt_iec':
      return <SwitchSpdtSymbol properties={properties} />;
    case 'relay_iec':
      return <RelaySymbol />;
    case 'circuit_breaker_iec':
      return <CircuitBreakerSymbol properties={properties} />;
    case 'rcd_iec':
      return <RcdSymbol properties={properties} />;
    case 'lamp_iec':
      return <LampSymbol />;
    case 'voltmeter_iec':
      return <MeterSymbol letter="V" rotation={rotation} />;
    case 'ammeter_iec':
      return <MeterSymbol letter="A" rotation={rotation} />;
    case 'oscilloscope_iec':
      return <OscilloscopeSymbol />;
    case 'diode_iec':
      return <DiodeSymbol />;
    case 'led_iec':
      return <DiodeSymbol light />;
    case 'npn_iec':
      return <BjtSymbol type="npn" />;
    case 'pnp_iec':
      return <BjtSymbol type="pnp" />;
    case 'ground_iec':
      return <GroundSymbol />;
  }
}
