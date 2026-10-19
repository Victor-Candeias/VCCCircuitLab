import { zodResolver } from '@hookform/resolvers/zod';
import type { ComponentProperties } from '@vcccircuitlab/circuit-schema';
import { useEffect, useMemo } from 'react';
import { useForm, type Resolver } from 'react-hook-form';
import { z } from 'zod';
import { useEditorStore } from '../store/editorStore';
import { getComponentDefinition } from './catalog';
import './properties.css';

/** Mensagem do limite violado, no mesmo tom das mensagens do backend (`app/circuit/catalog.py`). */
function numberConstraint(
  spec: { minimum?: number; maximum?: number; exclusiveMinimum?: number; exclusiveMaximum?: number },
  schema: z.ZodNumber,
): z.ZodNumber {
  let s = schema.finite({ message: 'tem de ser um número finito' });
  if (spec.exclusiveMinimum !== undefined) {
    s = s.gt(spec.exclusiveMinimum, { message: `tem de ser > ${spec.exclusiveMinimum}` });
  }
  if (spec.minimum !== undefined) {
    s = s.min(spec.minimum, { message: `tem de ser ≥ ${spec.minimum}` });
  }
  if (spec.exclusiveMaximum !== undefined) {
    s = s.lt(spec.exclusiveMaximum, { message: `tem de ser < ${spec.exclusiveMaximum}` });
  }
  if (spec.maximum !== undefined) {
    s = s.max(spec.maximum, { message: `tem de ser ≤ ${spec.maximum}` });
  }
  return s;
}

/** Schema Zod construído a partir das propriedades do catálogo (E1-05: validação imediata). */
function buildSchema(properties: Record<string, { type: 'number' | 'boolean' } & Record<string, unknown>>) {
  const shape: Record<string, z.ZodTypeAny> = {};
  for (const [name, spec] of Object.entries(properties)) {
    shape[name] =
      spec.type === 'boolean'
        ? z.boolean()
        : numberConstraint(spec as never, z.number({ message: 'tem de ser um número' }));
  }
  return z.object(shape);
}

type FormValues = Record<string, unknown>;

/**
 * Painel lateral de propriedades do componente selecionado: um campo por propriedade do
 * catálogo, validado imediatamente (React Hook Form + Zod) a partir dos limites do catálogo
 * carregado da API (`GET /api/v1/components`). Alterações válidas atualizam o documento de
 * imediato; inválidas ficam assinaladas sem tocar no circuito.
 */
export function PropertiesPanel() {
  const selectedIds = useEditorStore((s) => s.selectedIds);
  const component = useEditorStore((s) =>
    s.selectedIds.length === 1
      ? s.circuit.components.find((c) => c.id === s.selectedIds[0])
      : undefined,
  );
  const definition = component && getComponentDefinition(component.type);
  const schema = useMemo(
    () => buildSchema((definition?.properties ?? {}) as never),
    [definition],
  );

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isValid },
  } = useForm<FormValues>({
    resolver: zodResolver(schema) as Resolver<FormValues>,
    mode: 'onChange',
    values: (component?.properties as FormValues) ?? {},
  });

  // Ao trocar de seleção, recomeça com os valores do novo componente (e limpa erros antigos).
  useEffect(() => {
    reset((component?.properties as FormValues) ?? {});
  }, [component?.id, component?.properties, reset]);

  if (selectedIds.length === 0) {
    return (
      <aside className="properties" aria-label="Propriedades">
        <h2>Propriedades</h2>
        <p className="properties__hint">Selecione um componente para editar as propriedades.</p>
      </aside>
    );
  }
  if (!component || !definition) {
    return (
      <aside className="properties" aria-label="Propriedades">
        <h2>Propriedades</h2>
        <p className="properties__hint">
          {selectedIds.length > 1
            ? 'Selecione um único componente para editar as propriedades.'
            : 'Este elemento não tem propriedades editáveis.'}
        </p>
      </aside>
    );
  }

  const apply = (values: FormValues) => {
    // Preserva o tipo declarado no catálogo (boolean/number), mesmo que o form devolva strings.
    const next: ComponentProperties = {};
    for (const [name, spec] of Object.entries(definition.properties)) {
      const raw = values[name];
      next[name] = spec.type === 'boolean' ? Boolean(raw) : Number(raw);
    }
    useEditorStore.getState().setComponentProperties(component.id, next);
  };

  return (
    <aside className="properties" aria-label="Propriedades">
      <h2 className="properties__title">
        Propriedades de {definition.label} ({component.id})
      </h2>
      <form className="properties__form" onChange={handleSubmit(apply)} onSubmit={(e) => e.preventDefault()}>
        {Object.entries(definition.properties).map(([name, spec]) => {
          const error = errors[name]?.message as string | undefined;
          const inputId = `property-${component.id}-${name}`;
          return (
            <div className="properties__field" key={name}>
              <label htmlFor={inputId}>
                {spec.title}
                {spec.type === 'number' && spec.unit ? ` (${spec.unit})` : ''}
              </label>
              {spec.type === 'boolean' ? (
                <input
                  id={inputId}
                  type="checkbox"
                  aria-invalid={error ? 'true' : undefined}
                  aria-describedby={error ? `${inputId}-error` : undefined}
                  {...register(name)}
                />
              ) : (
                <input
                  id={inputId}
                  type="number"
                  step="any"
                  aria-invalid={error ? 'true' : undefined}
                  aria-describedby={error ? `${inputId}-error` : undefined}
                  {...register(name, { valueAsNumber: true })}
                />
              )}
              {error && (
                <p id={`${inputId}-error`} className="properties__error" role="alert">
                  {error}
                </p>
              )}
            </div>
          );
        })}
        {Object.keys(definition.properties).length === 0 && (
          <p className="properties__hint">{definition.label} não tem propriedades.</p>
        )}
        <p className="properties__status" aria-live="polite">
          {isValid ? '' : 'Corrija os campos assinalados: as alterações não são aplicadas.'}
        </p>
      </form>
    </aside>
  );
}
