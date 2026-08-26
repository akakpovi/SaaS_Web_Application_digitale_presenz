import React, {
  createContext, useContext, useState, useEffect,
  ReactNode,
} from "react";
import { Lang, getLang, translations } from "../i18n";

interface LangContextType {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string) => string;
}

const LangContext = createContext<LangContextType | null>(null);

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(getLang);

  useEffect(() => {
    const handler = () => setLangState(getLang());
    window.addEventListener("presence_lang_change", handler);
    return () => window.removeEventListener("presence_lang_change", handler);
  }, []);

  const setLang = (l: Lang) => {
    localStorage.setItem("presence_lang", l);
    setLangState(l);
    window.dispatchEvent(new Event("presence_lang_change"));
  };

  const t = (key: string): string =>
    translations[lang]?.[key] ?? translations["en"]?.[key] ?? key;

  return (
    <LangContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used within LangProvider");
  return ctx;
}
