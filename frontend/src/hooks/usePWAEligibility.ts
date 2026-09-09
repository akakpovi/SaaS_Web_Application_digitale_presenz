import React, { useEffect, useState, useCallback } from 'react';

const DISMISS_KEY = 'pwa_dismissed_at';
const DISMISS_DAYS = 7;

interface UsePWAEligibilityResult {
  showPWAToast: boolean;
  dismissPWA: () => void;
  installPWA: () => void;
  isIOS: boolean;
}

export function usePWAEligibility(
  scanCompleted: boolean,
  cookieConsentResolved: boolean = true
): UsePWAEligibilityResult {
  const [showPWAToast, setShowPWAToast] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);

  useEffect(() => {
    // 1. Ne pas afficher si déjà en mode PWA installée (standalone)
    const isStandalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as any).standalone === true;
    if (isStandalone) return;

    // 2. Détection iOS Safari
    const ua = navigator.userAgent;
    const isIosDevice = /iPad|iPhone|iPod/.test(ua) && !(window as any).MSStream;
    setIsIOS(isIosDevice);

    // 3. Ne pas afficher si l'utilisateur a cliqué sur "Plus tard" récemment
    const dismissedAt = localStorage.getItem(DISMISS_KEY);
    if (dismissedAt) {
      const daysSince = (Date.now() - parseInt(dismissedAt, 10)) / (1000 * 60 * 60 * 24);
      if (daysSince < DISMISS_DAYS) return;
    }

    // 4. Capturer l'événement natif Chrome/Android beforeinstallprompt
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
      // Dès que le navigateur est prêt, stocker l'event
      (window as any).__pwaInstallEvent = e;
    };
    window.addEventListener('beforeinstallprompt', handler);

    // 5. Déclenchement rapide après 3 secondes (au lieu de 30s) dès que le scan est prêt
    let timer: ReturnType<typeof setTimeout> | null = null;
    if (scanCompleted) {
      timer = setTimeout(() => {
        setShowPWAToast(true);
      }, 3000); // 3 secondes pour un affichage visible en test et fluide en UX
    }

    return () => {
      if (timer) clearTimeout(timer);
      window.removeEventListener('beforeinstallprompt', handler);
    };
  }, [scanCompleted]);

  const dismissPWA = useCallback(() => {
    setShowPWAToast(false);
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  }, []);

  const installPWA = useCallback(() => {
    const promptEvent = deferredPrompt || (window as any).__pwaInstallEvent;
    if (promptEvent) {
      promptEvent.prompt();
      promptEvent.userChoice.then((choice: { outcome: string }) => {
        if (choice.outcome === 'accepted') {
          localStorage.setItem('pwa_installed', 'true');
        }
      });
    } else if (isIOS) {
      alert("Sur iOS : appuyez sur le bouton de partage en bas de Safari, puis sur 'Sur l'écran d'accueil'.");
    } else {
      alert("Pour installer : cliquez sur l'icône d'installation dans la barre d'adresse de votre navigateur.");
    }
    setShowPWAToast(false);
  }, [deferredPrompt, isIOS]);

  return { showPWAToast, dismissPWA, installPWA, isIOS };
}

export default usePWAEligibility;
