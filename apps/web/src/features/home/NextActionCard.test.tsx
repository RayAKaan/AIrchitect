import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import NextActionCard from './NextActionCard';

describe('NextActionCard', () => {
  it('prioritizes the source brief when none exists', async () => {
    const user = userEvent.setup(); const onNavigate = vi.fn();
    render(<NextActionCard mode="Brief" snapshot={null} status="DRAFT" onNavigate={onNavigate} />);
    expect(screen.getByRole('heading', { name: 'Write the project brief' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Open brief/ }));
    expect(onNavigate).toHaveBeenCalledWith('Brief');
  });

  it('moves a complete brief toward concept exploration', () => {
    render(<NextActionCard mode="Brief" snapshot={{ brief: { raw_text: 'A retail building' }, requirements: [{ id: 'r1' }] }} status="DRAFT" onNavigate={() => {}} />);
    expect(screen.getByRole('heading', { name: 'Explore concepts' })).toBeInTheDocument();
  });
});
