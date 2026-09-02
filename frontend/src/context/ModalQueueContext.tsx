import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type ModalType =
  | 'cookie'
  | 'cookie_banner'
  | 'pwa_install'
  | 'pwa'
  | 'rate_limit_conversion'
  | 'email_capture'
  | 'push_tester';

export interface ModalQueueContextValue {
  activeModal: ModalType | null;
  requestModal: (type: ModalType) => void;
  registerModal: (type: ModalType) => void;
  dismissModal: (type?: ModalType | string) => void;
  triggerPWAPrompt: () => void;
}

const ModalQueueContext = createContext<ModalQueueContextValue | null>(null);

export function ModalQueueProvider({ children }: { children: ReactNode }) {
  const [activeModal, setActiveModal] = useState<ModalType | null>(null);
  const [queue, setQueue] = useState<ModalType[]>([]);

  const requestModal = useCallback((type: ModalType) => {
    setActiveModal((current) => {
      if (current === null) {
        return type;
      }
      setQueue((prev) => (prev.includes(type) ? prev : [...prev, type]));
      return current;
    });
  }, []);

  const registerModal = useCallback((type: ModalType) => {
    requestModal(type);
  }, [requestModal]);

  const dismissModal = useCallback((_type?: ModalType | string) => {
    setQueue((prev) => {
      if (prev.length > 0) {
        const [next, ...rest] = prev;
        setActiveModal(next);
        return rest;
      }
      setActiveModal(null);
      return [];
    });
  }, []);

  const triggerPWAPrompt = useCallback(() => {
    const isStandalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as any).standalone === true;

    if (isStandalone) return;
    if (sessionStorage.getItem('pwa_dismissed') === 'true') return;

    requestModal('pwa_install');
  }, [requestModal]);

  const value = useMemo(
    () => ({
      activeModal,
      requestModal,
      registerModal,
      dismissModal,
      triggerPWAPrompt,
    }),
    [activeModal, requestModal, registerModal, dismissModal, triggerPWAPrompt]
  );

  return (
    <ModalQueueContext.Provider value={value}>
      {children}
    </ModalQueueContext.Provider>
  );
}

export function useModalQueue(): ModalQueueContextValue {
  const context = useContext(ModalQueueContext);
  if (!context) {
    throw new Error('useModalQueue must be used within a ModalQueueProvider');
  }
  return context;
}
