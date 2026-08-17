import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

jest.mock('react-force-graph-2d', () => {
  return function MockForceGraph2D() {
    return <div data-testid="mock-force-graph">ForceGraph2D</div>;
  };
});

test('renders KubePulse dashboard header', () => {
  render(<App />);
  const brandElement = screen.getByText(/KubePulse/i);
  expect(brandElement).toBeInTheDocument();
});

