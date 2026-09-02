import { useModalQueue } from "../context/ModalQueueContext";

export function PWAInstallToast() {
  const { activeModal, dismissModal } = useModalQueue();

  if (activeModal !== "pwa_install") return null;

  const handleInstall = () => {
    const event = (window as any).__pwaInstallEvent;
    if (event) {
      event.prompt();
      event.userChoice.then((choice: { outcome: string }) => {
        if (choice.outcome === "accepted") {
          sessionStorage.setItem("pwa_installed", "true");
        }
      });
    }
    dismissModal();
  };

  const handleDismiss = () => {
    sessionStorage.setItem("pwa_dismissed", "true");
    dismissModal();
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 overflow-hidden rounded-xl border border-blue-200 bg-white shadow-xl">
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2.5 flex items-center gap-2">
        <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        <span className="text-sm font-semibold text-white">Alertes instantanées</span>
      </div>

      <div className="p-4">
        <p className="text-sm text-slate-600 leading-relaxed">
          Installez l'application pour recevoir une notification push immédiate si votre site devient inaccessible.
        </p>

        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={handleInstall}
            className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-blue-700"
          >
            Installer
          </button>
          <button
            type="button"
            onClick={handleDismiss}
            className="rounded-lg px-3 py-2 text-xs font-medium text-slate-500 hover:bg-slate-100"
          >
            Plus tard
          </button>
        </div>
      </div>
    </div>
  );
}
