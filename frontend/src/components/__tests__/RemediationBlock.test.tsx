import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RemediationBlock } from '../RemediationBlock';
import { REMEDIATION_GUIDES } from '../../types/remediation';

describe('🧪 Composant RemediationBlock', () => {
  beforeEach(() => {
    // Mock de navigator.clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockImplementation(() => Promise.resolve()),
      },
    });
  });

  it('affiche correctement le guide SPF manquant', () => {
    render(<RemediationBlock guide={REMEDIATION_GUIDES.spf_missing} />);

    // Titre et badge
    expect(screen.getByText('Enregistrement SPF manquant')).toBeInTheDocument();
    expect(screen.getByText('Critique')).toBeInTheDocument();

    // Bloc de code copiable
    expect(screen.getByText(/v=spf1 include:_spf\.example\.com ~all/)).toBeInTheDocument();
  });

  it('permet de copier le code technique au clic sur le bouton Copier', async () => {
    render(<RemediationBlock guide={REMEDIATION_GUIDES.spf_missing} />);

    const copyBtn = screen.getByRole('button', { name: /copier/i });
    expect(copyBtn).toBeInTheDocument();

    fireEvent.click(copyBtn);

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('v=spf1 include:_spf.example.com ~all');

    // Feedback visuel de copie
    await waitFor(() => {
      expect(screen.getByText(/copié/i)).toBeInTheDocument();
    });
  });
});
