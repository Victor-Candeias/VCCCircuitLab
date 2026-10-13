import { Handle, Position, type NodeProps } from '@xyflow/react';
import { JUNCTION_HANDLE_ID, type JunctionNode } from './flowNodes';

/** Junção explícita: ponto cheio onde os fios ficam eletricamente ligados. */
export function JunctionNodeView({ data, selected }: NodeProps<JunctionNode>) {
  return (
    <div
      className={selected ? 'junction-node is-selected' : 'junction-node'}
      title={`Junção ${data.junction.id}`}
      aria-label={`Junção ${data.junction.id}`}
    >
      <Handle
        id={JUNCTION_HANDLE_ID}
        type="source"
        position={Position.Top}
        isConnectable={false}
        isConnectableStart={false}
        isConnectableEnd={false}
        className="junction-node__handle"
      />
    </div>
  );
}
