import { useRef, useState, type ChangeEvent } from 'react';
import { useEditorStore } from '../store/editorStore';
import { circuitFileName, emptyCircuit, readCircuitFile, serializeCircuit } from './circuitJson';
import './project.css';

type Notice = { kind: 'error' | 'info'; title: string; details: string[] };

/** Descarrega `text` como ficheiro (sem servidor: Blob + ligação temporária). */
function downloadText(text: string, fileName: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Projeto: novo circuito, abrir um ficheiro JSON canónico (validado antes de substituir o
 * circuito atual) e guardar o circuito atual em JSON canónico.
 */
export function ProjectMenu() {
  const name = useEditorStore((s) => s.circuit.name);
  const inputRef = useRef<HTMLInputElement>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const onNew = () => {
    const { circuit, loadCircuit } = useEditorStore.getState();
    const hasContent = circuit.components.length > 0 || circuit.wires.length > 0;
    if (hasContent && !window.confirm('Descartar o circuito atual e começar um novo?')) return;
    loadCircuit(emptyCircuit());
    setNotice(null);
  };

  const onSave = () => {
    const { circuit } = useEditorStore.getState();
    downloadText(serializeCircuit(circuit), circuitFileName(circuit));
  };

  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    const result = await readCircuitFile(file);
    if (!result.ok) {
      setNotice({
        kind: 'error',
        title: `Não foi possível abrir "${file.name}" (o circuito atual não foi alterado):`,
        details: result.errors,
      });
      return;
    }
    useEditorStore.getState().loadCircuit(result.circuit);
    setNotice(
      result.warnings.length > 0
        ? { kind: 'info', title: `Aberto "${result.circuit.name}".`, details: result.warnings }
        : null,
    );
  };

  return (
    <div className="project-menu">
      <span className="project-menu__name" title="Nome do circuito">
        {name}
      </span>
      <button type="button" onClick={onNew}>
        Novo
      </button>
      <button type="button" onClick={() => inputRef.current?.click()}>
        Abrir…
      </button>
      <button type="button" onClick={onSave}>
        Guardar JSON
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        hidden
        aria-label="Ficheiro de circuito (JSON)"
        onChange={onFile}
      />
      {notice && (
        <div
          className={`project-notice is-${notice.kind}`}
          role={notice.kind === 'error' ? 'alert' : 'status'}
        >
          <p className="project-notice__title">{notice.title}</p>
          <ul>
            {notice.details.map((detail, i) => (
              <li key={i}>{detail}</li>
            ))}
          </ul>
          <button
            type="button"
            className="project-notice__close"
            aria-label="Fechar mensagem"
            onClick={() => setNotice(null)}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
