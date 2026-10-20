import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { generateCircuit, generateFromText, toApiError } from '../api/client';
import type { CircuitIssue, GenerateTextResult } from '../api/types';
import { useEditorStore } from '../store/editorStore';
import { CircuitPreview } from './CircuitPreview';
import { toCanonical } from './circuitJson';
import {
  defaultGenerateValues,
  GENERATE_TEMPLATES,
  parseGenerateParameters,
  type GenerateFormValues,
} from './generateTemplates';
import './project.css';

interface GenerateError {
  title: string;
  issues: readonly CircuitIssue[];
}

type GenerateMode = 'template' | 'text';

/** Tamanho máximo da descrição em texto livre (igual ao limite da API). */
const MAX_TEXT_CHARS = 1000;

const TEXT_PLACEHOLDER =
  'Ex.: circuito em série com fonte de 12 V e resistências de 100, 220 e 330 Ω';

/**
 * Diálogo "Gerar": escolhe um template, preenche os parâmetros e pede à API o circuito
 * (`POST /api/v1/circuits/generate`). O resultado substitui o circuito atual, tal como abrir
 * um ficheiro ou um exemplo (com confirmação, se o circuito atual não estiver vazio). Erros de
 * parâmetros da API (`invalid-parameters`) são mostrados com o apontador (`pointer`) de cada
 * campo inválido.
 *
 * No modo "Texto livre" (F2-06) a descrição é interpretada pela API
 * (`POST /api/v1/circuits/generate/text`): o diálogo mostra o resumo, os valores assumidos e uma
 * pré-visualização do circuito, que só é aberto no editor depois de o utilizador confirmar.
 */
const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function GenerateDialog({ onClose }: { onClose: () => void }) {
  const titleId = useId();
  const formRef = useRef<HTMLFormElement>(null);
  const [templateId, setTemplateId] = useState(GENERATE_TEMPLATES[0].id);
  const template = GENERATE_TEMPLATES.find((t) => t.id === templateId) ?? GENERATE_TEMPLATES[0];
  const [values, setValues] = useState<GenerateFormValues>(() => defaultGenerateValues(template));
  const [mode, setMode] = useState<GenerateMode>('template');
  const [text, setText] = useState('');
  const [interpretation, setInterpretation] = useState<GenerateTextResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<GenerateError | null>(null);

  // Foca o primeiro campo ao abrir, para quem navega só por teclado.
  useEffect(() => {
    formRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)?.focus();
  }, []);

  // Esc fecha o diálogo; Tab/Shift+Tab ficam contidos nos seus campos (foco preso).
  const onDialogKeyDown = (event: KeyboardEvent<HTMLFormElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(
      formRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [],
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const onTemplateChange = (id: string) => {
    const next = GENERATE_TEMPLATES.find((t) => t.id === id) ?? GENERATE_TEMPLATES[0];
    setTemplateId(next.id);
    setValues(defaultGenerateValues(next));
    setError(null);
  };

  const onModeChange = (next: GenerateMode) => {
    setMode(next);
    setError(null);
  };

  const onTextChange = (value: string) => {
    setText(value);
    // A pré-visualização tem de corresponder ao texto: outra descrição exige nova interpretação.
    setInterpretation(null);
    setError(null);
  };

  /** Substitui o circuito atual (com confirmação, se não estiver vazio) e fecha o diálogo. */
  const openInEditor = (generated: CircuitDocument) => {
    const circuit = toCanonical(generated);
    const { circuit: current, loadCircuit } = useEditorStore.getState();
    const hasContent = current.components.length > 0 || current.wires.length > 0;
    if (hasContent && !window.confirm('Descartar o circuito atual e abrir o circuito gerado?')) {
      return;
    }
    loadCircuit(circuit);
    onClose();
  };

  const request = async (run: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await run();
    } catch (cause) {
      const apiError = toApiError(cause);
      setError({
        title: apiError.problem?.title ?? apiError.message,
        issues: apiError.problem?.errors ?? [],
      });
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (mode === 'text') {
      if (interpretation) {
        openInEditor(interpretation.circuit);
        return;
      }
      const description = text.trim();
      if (!description) {
        setError({ title: 'Descreva o circuito que pretende gerar.', issues: [] });
        return;
      }
      await request(async () => setInterpretation(await generateFromText(description)));
      return;
    }

    const parsed = parseGenerateParameters(template, values);
    if (!parsed.ok) {
      setError({ title: parsed.error, issues: [] });
      return;
    }
    await request(async () => openInEditor(await generateCircuit(template.id, parsed.parameters)));
  };

  const submitLabel =
    mode === 'template'
      ? busy
        ? 'A gerar…'
        : 'Gerar'
      : busy
        ? 'A interpretar…'
        : interpretation
          ? 'Abrir no editor'
          : 'Interpretar';

  return (
    <div className="generate-dialog__overlay" onClick={onClose}>
      <form
        ref={formRef}
        className="generate-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => void onSubmit(event)}
        onKeyDown={onDialogKeyDown}
      >
        <h2 id={titleId}>Gerar circuito</h2>

        <fieldset className="generate-dialog__modes">
          <legend>Modo</legend>
          <label>
            <input
              type="radio"
              name="generate-mode"
              checked={mode === 'template'}
              onChange={() => onModeChange('template')}
            />
            Por template
          </label>
          <label>
            <input
              type="radio"
              name="generate-mode"
              checked={mode === 'text'}
              onChange={() => onModeChange('text')}
            />
            Texto livre
          </label>
        </fieldset>

        {mode === 'template' && (
          <label className="generate-dialog__field">
            Template
            <select value={templateId} onChange={(event) => onTemplateChange(event.target.value)}>
              {GENERATE_TEMPLATES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
        )}

        {mode === 'text' && (
          <>
            <label className="generate-dialog__field">
              Descrição do circuito
              <textarea
                rows={3}
                maxLength={MAX_TEXT_CHARS}
                placeholder={TEXT_PLACEHOLDER}
                value={text}
                onChange={(event) => onTextChange(event.target.value)}
              />
            </label>
            {interpretation && (
              <section className="generate-dialog__interpretation" aria-label="Interpretação">
                <p>
                  <strong>{interpretation.summary}</strong>
                </p>
                {interpretation.assumptions.length > 0 && (
                  <>
                    <p>Valores assumidos (confirme antes de abrir):</p>
                    <ul>
                      {interpretation.assumptions.map((assumption) => (
                        <li key={assumption}>{assumption}</li>
                      ))}
                    </ul>
                  </>
                )}
                {interpretation.warnings.length > 0 && (
                  <ul>
                    {interpretation.warnings.map((warning, index) => (
                      <li key={index}>{warning.message}</li>
                    ))}
                  </ul>
                )}
                <CircuitPreview
                  circuit={interpretation.circuit}
                  label={`Pré-visualização: ${interpretation.summary}`}
                />
              </section>
            )}
          </>
        )}

        {mode === 'template' &&
          template.fields.map((field) =>
            field.type === 'boolean' ? (
              <label key={field.key} className="generate-dialog__field generate-dialog__checkbox">
                <input
                  type="checkbox"
                  checked={values[field.key] === 'true'}
                  onChange={(event) =>
                    setValues((v) => ({ ...v, [field.key]: String(event.target.checked) }))
                  }
                />
                {field.label}
              </label>
            ) : (
              <label key={field.key} className="generate-dialog__field">
                {field.label}
                <input
                  value={values[field.key] ?? ''}
                  onChange={(event) =>
                    setValues((v) => ({ ...v, [field.key]: event.target.value }))
                  }
                />
              </label>
            ),
          )}

        {error && (
          <div className="generate-dialog__error" role="alert">
            <strong>{error.title}</strong>
            {error.issues.length > 0 && (
              <ul>
                {error.issues.map((issue, index) => (
                  <li key={index}>
                    {issue.pointer && <code>{issue.pointer}</code>} {issue.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="generate-dialog__actions">
          <button type="button" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" disabled={busy}>
            {submitLabel}
          </button>
        </div>
      </form>
    </div>
  );
}
