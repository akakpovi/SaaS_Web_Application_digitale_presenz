import React, { createContext, useContext, useState, useCallback } from "react"
import { useT } from "../i18n"

interface Toast {
  id: number
  message: string
  type: "success" | "error" | "info"
}

interface ToastContextValue {
  toasts: Toast[]
  showToast: (message: string, type: Toast["type"]) => void
  dismissToast: (id: number) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const t = useT()
  const [toasts, setToasts] = useState<Toast[]>([])

  const showToast = useCallback((message: string, type: Toast["type"]) => {
    const id = Date.now()
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 5000)
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, showToast, dismissToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg max-w-sm animate-slide-in ${
              toast.type === "success"
                ? "bg-emerald-600 text-white"
                : toast.type === "error"
                  ? "bg-red-600 text-white"
                  : "bg-indigo-600 text-white"
            }`}
          >
            <span className="flex-1 text-sm">{toast.message}</span>
            <button
              onClick={() => dismissToast(toast.id)}
              className="flex-shrink-0 text-white/80 hover:text-white text-lg leading-none"
              aria-label={t("common.dismiss")}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider")
  }
  return context
}
