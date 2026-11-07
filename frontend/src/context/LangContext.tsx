import React, { ReactNode, createContext, useContext } from 'react';
// Wrapper de compatibilité — utilise i18next directement
// Conservé pour les imports existants, mais useTranslation() est préférable
import { useTranslation } from "react-i18next";
import type { Lang } from "../i18n";

interface LangContextType {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string) => string;
}

const LangContext = createContext<LangContextType | null>(null);

export function LangProvider({ children }: { children: ReactNode }) {
  const { t, i18n } = useTranslation();
  const setLang = (l: Lang) => i18n.changeLanguage(l);
  return (
    <LangContext.Provider value={{
      lang: (i18n.language?.slice(0, 2) as Lang) ?? "de",
      setLang,
      t: (key: string) => t(key),
    }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used within LangProvider");
  return ctx;
}
