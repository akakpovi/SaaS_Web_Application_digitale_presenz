import React, { useState, useEffect, useCallback } from "react";

type ConsentType = "essential" | "all" | "custom" | null;

export const useCookieConsent = () => {
  const [consent, setConsentState] = useState<ConsentType>(null);
  const [isResolved, setIsResolved] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("cookie_consent") as ConsentType;
    if (stored) {
      setConsentState(stored);
      setIsResolved(true);
    }
  }, []);

  const setConsent = useCallback((type: ConsentType) => {
    if (type) {
      localStorage.setItem("cookie_consent", type);
    }
    setConsentState(type);
    setIsResolved(true);
  }, []);

  return { consent, isResolved, setConsent };
};
