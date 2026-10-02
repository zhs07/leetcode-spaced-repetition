import { useEffect, useRef } from 'react'

export default function useModalDialog() {
  const dialog = useRef<HTMLDialogElement>(null)
  // Capture the trigger before React mounts any auto-focused form fields.
  const trigger = useRef(document.activeElement)
  useEffect(() => {
    const element = dialog.current!
    const opener = trigger.current
    element.showModal()
    return () => {
      element.close()
      queueMicrotask(() => {
        // StrictMode immediately reopens the dialog when replaying effects.
        if (!element.open && opener instanceof HTMLElement && opener.isConnected) opener.focus()
      })
    }
  }, [])
  return dialog
}
