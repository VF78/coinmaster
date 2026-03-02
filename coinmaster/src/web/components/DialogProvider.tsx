import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react';
import { Button } from './Button';

type DialogType = 'confirm' | 'alert';

interface DialogOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
}

interface DialogRequest extends DialogOptions {
  id: number;
  type: DialogType;
  resolve: (value: boolean) => void;
}

interface DialogContextValue {
  confirm: (options: DialogOptions | string) => Promise<boolean>;
  alert: (options: DialogOptions | string) => Promise<void>;
}

const DialogContext = createContext<DialogContextValue | null>(null);

function normalizeOptions(options: DialogOptions | string): DialogOptions {
  return typeof options === 'string' ? { message: options } : options;
}

export function DialogProvider({ children }: PropsWithChildren) {
  const [active, setActive] = useState<DialogRequest | null>(null);
  const queueRef = useRef<DialogRequest[]>([]);
  const idRef = useRef(1);

  const processNext = useCallback(() => {
    if (active) return;
    const next = queueRef.current.shift() ?? null;
    if (next) setActive(next);
  }, [active]);

  useEffect(() => {
    processNext();
  }, [active, processNext]);

  const enqueue = useCallback((type: DialogType, options: DialogOptions | string) => {
    const normalized = normalizeOptions(options);
    return new Promise<boolean>((resolve) => {
      const req: DialogRequest = {
        id: idRef.current++,
        type,
        resolve,
        ...normalized,
      };
      queueRef.current.push(req);
      processNext();
    });
  }, [processNext]);

  const close = useCallback((value: boolean) => {
    if (!active) return;
    active.resolve(value);
    setActive(null);
  }, [active]);

  useEffect(() => {
    if (!active) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        close(active.type === 'alert' ? true : false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [active, close]);

  const ctx = useMemo<DialogContextValue>(() => ({
    confirm: async (options) => enqueue('confirm', options),
    alert: async (options) => {
      await enqueue('alert', options);
    },
  }), [enqueue]);

  return (
    <DialogContext.Provider value={ctx}>
      {children}

      {active ? (
        <div className="oc-dialog-overlay" role="dialog" aria-modal="true" aria-label={active.title || 'Dialog'}>
          <div className="oc-dialog-card">
            {active.title ? <h3 className="oc-dialog-title">{active.title}</h3> : null}
            <p className="oc-dialog-message">{active.message}</p>

            <div className="oc-dialog-actions">
              {active.type === 'confirm' ? (
                <Button variant="secondary" onClick={() => close(false)}>
                  {active.cancelText || 'Cancel'}
                </Button>
              ) : null}
              <Button variant="primary" onClick={() => close(true)}>
                {active.confirmText || 'OK'}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </DialogContext.Provider>
  );
}

export function useDialog(): DialogContextValue {
  const ctx = useContext(DialogContext);
  if (!ctx) {
    throw new Error('useDialog must be used within DialogProvider');
  }
  return ctx;
}
