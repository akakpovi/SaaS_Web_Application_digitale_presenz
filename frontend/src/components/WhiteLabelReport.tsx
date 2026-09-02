import { useState, useRef } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

interface WhiteLabelReportProps {
  scanId: string;
  domain: string;
}

export function WhiteLabelReport({ scanId, domain }: WhiteLabelReportProps) {
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      setError('Le logo doit faire moins de 2 Mo.');
      return;
    }

    setLogoFile(file);
    setError(null);

    const reader = new FileReader();
    reader.onloadend = () => setLogoPreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  const handleGeneratePDF = async () => {
    setGenerating(true);
    setError(null);

    try {
      let logoUrl = '';
      if (logoFile) {
        const formData = new FormData();
        formData.append('file', logoFile);
        // Note : en production, uploader vers un endpoint dédié (ex: S3, Cloudinary)
        // et récupérer l'URL. Pour la démo, on utilise le DataURL.
        logoUrl = logoPreview || '';
      }

      const token = localStorage.getItem('access_token');
      const response = await axios.get(
        `${API_BASE}/reports/pdf/${scanId}/`,
        {
          params: { logo_url: logoUrl, lang: 'fr' },
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob',
        }
      );

      // Téléchargement du PDF
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `rapport-presence-${domain}-${scanId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setError(
        err.response?.status === 403
          ? 'Accès refusé. Ce rapport nécessite un plan Pro ou Business.'
          : 'Erreur lors de la génération du PDF.'
      );
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h3 className="text-lg font-bold text-slate-900">
        Rapport PDF Marque Blanche
      </h3>
      <p className="mt-1 text-sm text-slate-500">
        Générez un rapport professionnel personnalisé avec votre logo d'agence.
      </p>

      {/* Upload Logo */}
      <div className="mt-4">
        <label className="block text-sm font-medium text-slate-700">
          Logo personnalisé (optionnel)
        </label>
        <div className="mt-2 flex items-center gap-4">
          {logoPreview ? (
            <img
              src={logoPreview}
              alt="Logo"
              className="h-12 w-auto rounded border border-slate-200 object-contain p-1"
            />
          ) : (
            <div className="flex h-12 w-12 items-center justify-center rounded border-2 border-dashed border-slate-300 text-slate-400">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
          )}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Choisir un fichier
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/svg+xml"
            onChange={handleLogoUpload}
            className="hidden"
          />
        </div>
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-600">{error}</p>
      )}

      {/* Bouton Générer */}
      <button
        type="button"
        onClick={handleGeneratePDF}
        disabled={generating}
        className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-50"
      >
        {generating ? (
          <>
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            Génération en cours...
          </>
        ) : (
          <>
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Générer le rapport PDF
          </>
        )}
      </button>
    </div>
  );
}

export default WhiteLabelReport;
