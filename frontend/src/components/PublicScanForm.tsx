import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePublicScan } from '../hooks/usePublicScan';
import { RateLimitConversionModal } from './RateLimitConversionModal';

interface PublicScanFormProps {
  className?: string;
}

export function PublicScanForm({ className = '' }: PublicScanFormProps) {
  const [url, setUrl] = useState('');
  const navigate = useNavigate();
  const {
    loading,
    error,
    isRateLimited,
    scanResult,
    triggerScan,
    dismissRateLimitModal,
  } = usePublicScan();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    await triggerScan(url.trim());
  };

  if (scanResult?.scan_id) {
    navigate(`/scan/${scanResult.scan_id}`);
  }

  return (
    <div className={`w-full max-w-xl mx-auto ${className}`}>
      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Entrez votre nom de domaine (ex: monsite.com)"
          disabled={loading}
          className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-3 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:bg-blue-400"
        >
          {loading ? 'Analyse...' : 'Scanner'}
        </button>
      </form>

      {error && (
        <p className="mt-2 text-sm text-red-600 font-medium" role="alert">
          {error}
        </p>
      )}

      <RateLimitConversionModal
        isOpen={isRateLimited}
        onClose={dismissRateLimitModal}
        scannedUrl={url}
      />
    </div>
  );
}

export default PublicScanForm;
