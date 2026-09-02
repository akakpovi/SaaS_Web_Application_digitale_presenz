import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import axios from 'axios';
import { PublicScanResult } from '../PublicScanResult';

vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

describe('🧪 Page PublicScanResult — Paywall de Remédiation', () => {
  it('affiche le nouveau message de remédiation et le CTA avec cadenas', async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: {
        scan_id: '123',
        domain: 'example.com',
        score: 65,
        status: 'completed',
        summary: { critical: 2, warnings: 1, passed: 4 },
        checks: {
          ssl: { status: 'healthy', score: 20, message: 'SSL valide' },
          email_security: { status: 'critical', score: 0, message: 'SPF manquant' },
        },
      },
    });

    render(
      <MemoryRouter initialEntries={['/scan/123']}>
        <Routes>
          <Route path="/scan/:scanId" element={<PublicScanResult />} />
        </Routes>
      </MemoryRouter>
    );

    // Attendre la fin du chargement
    await waitFor(() => {
      expect(screen.getByText('Rapport de présence — example.com')).toBeInTheDocument();
    });

    // Vérifier le message de valeur de la Phase 2
    expect(
      screen.getByText(/Débloquez le diagnostic détaillé et les instructions pas-à-pas pour corriger ces vulnérabilités\./i)
    ).toBeInTheDocument();

    // Vérifier la présence du bouton de conversion
    expect(
      screen.getByRole('button', { name: /créer mon compte gratuit/i })
    ).toBeInTheDocument();
  });
});
