import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';

interface RateLimitConversionModalProps {
  isOpen: boolean;
  onClose: () => void;
  scannedUrl?: string;
}

export function RateLimitConversionModal({
  isOpen,
  onClose,
  scannedUrl,
}: RateLimitConversionModalProps) {
  const navigate = useNavigate();

  // Verrouiller le scroll de l'arrière-plan lorsque la modale est active
  useEffect(() => {
    if (!isOpen) return;
    const originalStyle = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = originalStyle;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleRegisterRedirect = () => {
    const params = new URLSearchParams();
    params.set('source', 'rate_limit');
    if (scannedUrl) {
      params.set('url', scannedUrl);
    }
    onClose();
    navigate(`/register?${params.toString()}`);
  };

  const modalJSX = (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="rate-limit-title"
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ zIndex: 2147483647 }} // z-index maximal pour bypasser les bannières cookies/PWA
    >
      {/* Overlay flouté */}
      <div
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Conteneur de la modale */}
      <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl transition-all scale-100">
        <div className="mb-4 flex justify-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
            <svg className="h-6 w-6 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
        </div>

        <h3 id="rate-limit-title" className="text-center text-lg font-bold text-gray-900">
          Limite de scans atteinte
        </h3>
        
        <p className="mt-2 text-center text-sm text-gray-500">
          Vous avez atteint la limite publique. Créez un compte gratuit instantanément pour lancer des scans illimités.
        </p>

        <div className="mt-6 flex flex-col gap-2">
          <button
            type="button"
            onClick={handleRegisterRedirect}
            className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            Créer un compte gratuit
          </button>
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-lg bg-white px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 border border-gray-300"
          >
            Plus tard
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(modalJSX, document.body);
}
