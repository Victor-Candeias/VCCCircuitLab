import { useId, useState, type FormEvent } from 'react';
import { generateCircuit, toApiError } from '../api/client';
import type { CircuitIssue } from '../api/types';
import { useEditorStore } from '../store/editorStore';
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

/**
 * Diálogo "Gerar": escolhe um template, preenche os parâmetros e pede à API o circuito
 * (`POST /api/v1/circuits/generate`). O resultado substitui o circuito atual, tal como abrir
 * um ficheiro ou um exemplo (com confirmação, se o circuito atual não estiver vazio). Erros de
 * parâmetros da API (`invalid-parameters`) são mostrados com o apontador (`pointer`) de cada
 * campo inválido.
 */
export function GenerateDialog({ onClose }: { onClose: () => void }) {
  const titleId = useId();
  const [templateId, setTemplateId] = useState(GENERATE_TEMPLATES[0].id);
  const template = GENERATE_TEMPLATES.find((t) => t.id === templateId) ?? GENERATE_TEMPLATES[0];
  const [values, setValues] = useState<GenerateFormValues>(() => defaultGenerateValues(template));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<GenerateError | null>(null);

  const onTemplateChange = (id: string) => {
    const next = GENERATE_TEMPLATES.find((t) => t.id === id) ?? GENERATE_TEMPLATES[0];
    setTemplateId(next.id);
    setValues(defaultGenerateValues(next));
    setError(null);
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsed = parseGenerateParameters(template, values);
    if (!parsed.ok) {
      setError({ title: parsed.error, issues: [] });
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const circuit = toCanonical(await generateCircuit(template.id, parsed.parameters));
      const { circuit: current, loadCircuit } = useEditorStore.getState();
      const hasContent = current.components.length > 0 || current.wires.length > 0;
      if (hasContent && !window.confirm('Descartar o circuito atual e abrir o circuito gerado?')) {
        return;
      }
      loadCircuit(circuit);
      onClose();
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

  return (
    <div className="generate-dialog__overlay" onClick={onClose}>
      <form
        className="generate-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => void onSubmit(event)}
      >
        <h2 id={titleId}>Gerar circuito</h2>

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

        {template.fields.map((field) =>
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
                onChange={(event) => setValues((v) => ({ ...v, [field.key]: event.target.value }))}
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
            {busy ? 'A gerar…' : 'Gerar'}
          </button>
        </div>
      </form>
    </div>
  );
}
