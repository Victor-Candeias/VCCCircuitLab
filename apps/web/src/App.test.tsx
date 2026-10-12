import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, test } from 'vitest';
import App from './App';

describe('App', () => {
  test('mostra o título', () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  test('incrementa o contador ao clicar', async () => {
    const user = userEvent.setup();
    render(<App />);
    const button = screen.getByRole('button', { name: /count is 0/i });
    await user.click(button);
    expect(button).toHaveTextContent('Count is 1');
  });
});
