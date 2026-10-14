import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import App from './App';

describe('App', () => {
  test('mostra o título e o canvas do editor', () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1, name: 'VCCCircuitLab' })).toBeInTheDocument();
    expect(screen.getByText('R1')).toBeInTheDocument();
  });

  test('"Criar conta" abre o diálogo de registo e Esc fecha-o', () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Criar conta' }));
    const dialog = screen.getByRole('dialog', { name: 'Criar conta' });
    expect(dialog).toBeInTheDocument();

    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
