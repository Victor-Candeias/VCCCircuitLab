import { useEffect, useRef } from 'react';
import { useEditorStore } from '../store/editorStore';
import { loadAutosave, saveAutosave } from './persistence';

/** Tempo de inatividade antes de gravar, para não escrever no IndexedDB a cada pixel arrastado. */
const DEBOUNCE_MS = 800;

/**
 * Ao arrancar, recupera o último projeto autogravado (se existir e for válido) substituindo o
 * circuito de exemplo por omissão e chamando `onRestored` com a hora da gravação (para a UI poder
 * informar o utilizador); a partir daí, grava automaticamente (com debounce) sempre que o
 * documento é alterado.
 */
export function useAutosave(onRestored?: (savedAt: number) => void): void {
  const restoring = useRef(true);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onRestoredRef = useRef(onRestored);
  useEffect(() => {
    onRestoredRef.current = onRestored;
  });

  useEffect(() => {
    let cancelled = false;
    loadAutosave().then((snapshot) => {
      if (cancelled) return;
      if (snapshot) {
        useEditorStore.getState().loadCircuit(snapshot.circuit);
        onRestoredRef.current?.(snapshot.savedAt);
      }
      restoring.current = false;
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(
    () =>
      useEditorStore.subscribe((state) => {
        if (restoring.current) return;
        const circuit = state.circuit;
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => {
          void saveAutosave(circuit);
        }, DEBOUNCE_MS);
      }),
    [],
  );
}
