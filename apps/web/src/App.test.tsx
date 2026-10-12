import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import App from './App';

describe('App', () => {
  test('mostra o título e o canvas do editor', () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1, name: 'VCCCircuitLab' })).toBeInTheDocument();
    expect(screen.getByText('R1')).toBeInTheDocument();
  });
});
