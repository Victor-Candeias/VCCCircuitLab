import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { useRef, useState, type ChangeEvent } from 'react';
import { exportSpice, importSpice, toApiError } from '../api/client';
import type { CircuitIssue } from '../api/types';
import { useEditorStore } from '../store/editorStore';
import {
  circuitFileName,
  circuitSlug,
  emptyCircuit,
  parseCircuit,
  readCircuitFile,
  serializeCircuit,
} from './circuitJson';
import { CIRCUIT_EXAMPLES } from './examples';
import { GenerateDialog } from './GenerateDialog';
import { useAutosave } from './useAutosave';
import './project.css';

type Notice = { kind: 'error' | 'info'; title: string; details: string[] };

/** Tamanho máximo de uma netlist SPICE (o mesmo limite da API). */
const MAX_SPICE_BYTES = 256 * 1024;

/** Descarrega `text` como ficheiro (sem servidor: Blob + ligação temporária). */
function downloadText(text: string, fileName: string, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

const issueMessages = (issues: CircuitIssue[]) => issues.map((issue) => issue.message);

/**
 * Projeto: novo circuito, abrir um ficheiro JSON canónico (validado antes de substituir o
 * circuito atual), guardar o circuito atual em JSON canónico e importar/exportar netlists SPICE
 * (traduzidas pela API).
 */
export function ProjectMenu() {
  const name = useEditorStore((s) => s.circuit.name);
  const inputRef = useRef<HTMLInputElement>(null);
  const spiceInputRef = useRef<HTMLInputElement>(null);
  const [spiceBusy, setSpiceBusy] = useState(false);
  const generateButtonRef = useRef<HTMLButtonElement>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [showGenerate, setShowGenerate] = useState(false);
  useAutosave((savedAt) => {
    const when = new Date(savedAt).toLocaleTimeString('pt-PT');
    setNotice({
      kind: 'info',
      title: 'Projeto recuperado automaticamente.',
      details: [`Última gravação automática: ${when}.`],
    });
  });

  /** Substitui o circuito atual, pedindo confirmação se este não estiver vazio. */
  const replaceCircuit = (next: CircuitDocument, question: string) => {
    const { circuit, loadCircuit } = useEditorStore.getState();
    const hasContent = circuit.components.length > 0 || circuit.wires.length > 0;
    if (hasContent && !window.confirm(question)) return;
    loadCircuit(next);
    setNotice(null);
  };

  const onNew = () =>
    replaceCircuit(emptyCircuit(), 'Descartar o circuito atual e começar um novo?');

  const onExample = (event: ChangeEvent<HTMLSelectElement>) => {
    const example = CIRCUIT_EXAMPLES.find((e) => e.id === event.target.value);
    event.target.value = '';
    if (example) {
      replaceCircuit(example.circuit, `Descartar o circuito atual e abrir "${example.label}"?`);
    }
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

  const onExportSpice = async () => {
    const { circuit } = useEditorStore.getState();
    setSpiceBusy(true);
    try {
      const netlist = await exportSpice(circuit);
      downloadText(netlist, `${circuitSlug(circuit)}.cir`, 'text/plain');
      setNotice(null);
    } catch (cause) {
      const apiError = toApiError(cause);
      const issues = issueMessages(apiError.problem?.errors ?? []);
      setNotice({
        kind: 'error',
        title: 'Não foi possível exportar a netlist SPICE:',
        details: issues.length > 0 ? issues : [apiError.problem?.title ?? apiError.message],
      });
    } finally {
      setSpiceBusy(false);
    }
  };

  const onSpiceFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    const failed = (details: string[]) =>
      setNotice({
        kind: 'error',
        title: `Não foi possível importar "${file.name}" (o circuito atual não foi alterado):`,
        details,
      });
    if (file.size > MAX_SPICE_BYTES) {
      failed([`Ficheiro demasiado grande (máximo ${MAX_SPICE_BYTES / 1024} KB).`]);
      return;
    }
    setSpiceBusy(true);
    try {
      const result = await importSpice(await file.text());
      const parsed = parseCircuit(JSON.stringify(result.circuit));
      if (!parsed.ok) {
        failed(parsed.errors);
        return;
      }
      useEditorStore.getState().loadCircuit(parsed.circuit);
      const details = [...issueMessages(result.warnings), ...issueMessages(result.issues)];
      setNotice(
        details.length > 0
          ? { kind: 'info', title: `Importado "${parsed.circuit.name}" (SPICE).`, details }
          : null,
      );
    } catch (cause) {
      const apiError = toApiError(cause);
      const issues = issueMessages(apiError.problem?.errors ?? []);
      failed(issues.length > 0 ? issues : [apiError.problem?.title ?? apiError.message]);
    } finally {
      setSpiceBusy(false);
    }
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
      <select aria-label="Abrir exemplo" defaultValue="" onChange={onExample}>
        <option value="" disabled>
          Exemplos…
        </option>
        {CIRCUIT_EXAMPLES.map((example) => (
          <option key={example.id} value={example.id}>
            {example.label}
          </option>
        ))}
      </select>
      <button type="button" onClick={onSave}>
        Guardar JSON
      </button>
      <button type="button" ref={generateButtonRef} onClick={() => setShowGenerate(true)}>
        Gerar…
      </button>
      <button type="button" onClick={() => void onExportSpice()} disabled={spiceBusy}>
        Exportar SPICE
      </button>
      <button type="button" onClick={() => spiceInputRef.current?.click()} disabled={spiceBusy}>
        Importar SPICE…
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        hidden
        aria-label="Ficheiro de circuito (JSON)"
        onChange={onFile}
      />
      <input
        ref={spiceInputRef}
        type="file"
        accept=".cir,.sp,.spice,.net,.txt,text/plain"
        hidden
        aria-label="Netlist SPICE"
        onChange={(event) => void onSpiceFile(event)}
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
      {showGenerate && (
        <GenerateDialog
          onClose={() => {
            setShowGenerate(false);
            generateButtonRef.current?.focus();
          }}
        />
      )}
    </div>
  );
}
