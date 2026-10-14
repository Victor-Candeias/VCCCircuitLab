import type { ComponentProperties, Rotation, Size } from '@vcccircuitlab/circuit-schema';
import { IecSymbol } from './iecSymbols';
import { isSymbolId } from './symbolIds';
import './symbols.css';

export interface ComponentSymbolProps {
  /** Identificador do símbolo (`ComponentDefinition.symbol`). */
  symbol: string;
  /** Tamanho do catálogo, com rotação 0. */
  size: Size;
  rotation?: Rotation;
  properties?: ComponentProperties;
  className?: string;
}

const NO_PROPERTIES: ComponentProperties = {};

/**
 * Desenha um símbolo do catálogo numa caixa com o tamanho já rodado. O `viewBox` é centrado
 * na âncora do componente e a rotação horária (eixo y para baixo) é a mesma de `rotateOffset`,
 * para que as extremidades dos condutores coincidam com os pinos.
 */
export function ComponentSymbol({
  symbol,
  size,
  rotation = 0,
  properties = NO_PROPERTIES,
  className,
}: ComponentSymbolProps) {
  const swap = rotation === 90 || rotation === 270;
  const width = swap ? size.height : size.width;
  const height = swap ? size.width : size.height;

  return (
    <svg
      className={['component-symbol', className].filter(Boolean).join(' ')}
      width={width}
      height={height}
      viewBox={`${-width / 2} ${-height / 2} ${width} ${height}`}
      overflow="visible"
      aria-hidden="true"
      data-symbol={symbol}
    >
      <g transform={rotation ? `rotate(${rotation})` : undefined}>
        {isSymbolId(symbol) ? (
          <IecSymbol symbol={symbol} properties={properties} rotation={rotation} />
        ) : (
          <rect
            className="component-symbol__missing"
            x={-size.width / 2}
            y={-size.height / 2}
            width={size.width}
            height={size.height}
          />
        )}
      </g>
    </svg>
  );
}
