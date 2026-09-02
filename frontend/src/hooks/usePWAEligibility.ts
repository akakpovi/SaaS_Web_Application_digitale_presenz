import { useState, useEffect, useCallback } from "react";

export const usePWAEligibility = () => {
  const [isEligible, setIsEligible] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);

  useEffect(() => {
    const checkInstalled = () => {
      const standalone = window.matchMedia("(display-mode: standalone)").matches
        || (window.navigator as any).standalone === true
        || localStorage.getItem("presence_pwa_installed") === "true";
      setIsInstalled(standalone);
    };

    checkInstalled();

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener("beforeinstallprompt", handler);
    window.addEventListener("appinstalled", () => {
      localStorage.setItem("presence_pwa_installed", "true");
      setIsInstalled(true);
      setIsEligible(false);
    });

    // Vérifier les conditions toutes les 5 secondes
    const interval = setInterval(() => {
      const cookieDone = localStorage.getItem("cookie_consent") !== null;
      const hasScanned = sessionStorage.getItem("has_scanned") === "true";
      const dismissedAt = localStorage.getItem("pwa_dismissed_at");
      const dismissedRecently = dismissedAt && (Date.now() - Number(dismissedAt)) < 7 * 24 * 60 * 60 * 1000;

      if (cookieDone && hasScanned && !dismissedRecently && !isInstalled) {
        setIsEligible(true);
      }
    }, 5000);

    return () => {
      window.removeEventListener("beforeinstallprompt", handler);
      clearInterval(interval);
    };
  }, [isInstalled]);

  const dismiss = useCallback(() => {
    localStorage.setItem("pwa_dismissed_at", Date.now().toString());
    setIsEligible(false);
  }, []);

  const install = useCallback(async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === "accepted") {
        localStorage.setItem("presence_pwa_installed", "true");
        setIsInstalled(true);
        setIsEligible(false);
      }
      setDeferredPrompt(null);
    }
  }, [deferredPrompt]);

  return { isEligible, isInstalled, dismiss, install };
};
