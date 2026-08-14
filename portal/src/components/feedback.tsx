import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from 'react'
import { AlertIcon, CheckIcon, CloseIcon, InfoIcon, type IconProps } from './icons'

const TOAST_DURATION = 5000

type ToastKind = 'success' | 'error' | 'info' | 'warn'

interface ToastItem {
  id: number
  kind: ToastKind
  message: string
}

interface ConfirmOptions {
  title: string
  message?: ReactNode
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

interface FeedbackContextValue {
  toast: {
    success: (message: string) => void
    error: (message: string) => void
    info: (message: string) => void
    warn: (message: string) => void
  }
  confirm: (options: ConfirmOptions) => Promise<boolean>
}

const FeedbackContext = createContext<FeedbackContextValue | null>(null)

const TOAST_ICONS: Record<ToastKind, ComponentType<IconProps>> = {
  success: CheckIcon,
  error: AlertIcon,
  info: InfoIcon,
  warn: AlertIcon,
}

let toastSeq = 0

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const [confirmState, setConfirmState] = useState<ConfirmOptions | null>(null)
  const confirmResolve = useRef<((value: boolean) => void) | null>(null)
  const timers = useRef<Record<number, ReturnType<typeof setTimeout>>>({})

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timers.current[id]
    if (timer) {
      clearTimeout(timer)
      delete timers.current[id]
    }
  }, [])

  const pushToast = useCallback(
    (kind: ToastKind, message: string) => {
      const id = ++toastSeq
      setToasts((prev) => [...prev.slice(-3), { id, kind, message }])
      timers.current[id] = setTimeout(() => dismissToast(id), TOAST_DURATION)
    },
    [dismissToast],
  )

  useEffect(() => {
    const current = timers.current
    return () => {
      Object.values(current).forEach((t) => clearTimeout(t))
    }
  }, [])

  const confirm = useCallback(
    (options: ConfirmOptions) =>
      new Promise<boolean>((resolve) => {
        confirmResolve.current = resolve
        setConfirmState(options)
      }),
    [],
  )

  const closeConfirm = useCallback((value: boolean) => {
    confirmResolve.current?.(value)
    confirmResolve.current = null
    setConfirmState(null)
  }, [])

  useEffect(() => {
    if (!confirmState) return
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') closeConfirm(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [confirmState, closeConfirm])

  const value = useMemo<FeedbackContextValue>(
    () => ({
      toast: {
        success: (m) => pushToast('success', m),
        error: (m) => pushToast('error', m),
        info: (m) => pushToast('info', m),
        warn: (m) => pushToast('warn', m),
      },
      confirm,
    }),
    [pushToast, confirm],
  )

  return (
    <FeedbackContext.Provider value={value}>
      {children}

      {/* 右上角消息通知：5s 进度条 + 自动消失 */}
      <div className="toast-wrap" role="status" aria-live="polite">
        {toasts.map((t) => {
          const Icon = TOAST_ICONS[t.kind]
          return (
            <div key={t.id} className={`toast-item toast-${t.kind}`}>
              <span className="toast-icon">
                <Icon size={16} />
              </span>
              <span className="toast-message">{t.message}</span>
              <button type="button" className="icon-btn toast-close" aria-label="关闭" onClick={() => dismissToast(t.id)}>
                <CloseIcon size={13} />
              </button>
              <span className="toast-progress" />
            </div>
          )
        })}
      </div>

      {/* 居中确认弹窗：所有交互确认统一走这里 */}
      {confirmState ? (
        <div className="modal-overlay" onClick={() => closeConfirm(false)}>
          <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <div className={`modal-icon${confirmState.danger ? ' danger' : ''}`}>
              {confirmState.danger ? <AlertIcon size={20} /> : <InfoIcon size={20} />}
            </div>
            <div className="modal-title">{confirmState.title}</div>
            {confirmState.message ? <div className="modal-message">{confirmState.message}</div> : null}
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => closeConfirm(false)}>
                {confirmState.cancelText ?? '取消'}
              </button>
              <button
                type="button"
                className={confirmState.danger ? 'btn btn-danger-solid' : 'btn'}
                autoFocus
                onClick={() => closeConfirm(true)}
              >
                {confirmState.confirmText ?? '确认'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </FeedbackContext.Provider>
  )
}

export function useFeedback(): FeedbackContextValue {
  const ctx = useContext(FeedbackContext)
  if (!ctx) throw new Error('useFeedback 必须在 FeedbackProvider 内使用')
  return ctx
}
