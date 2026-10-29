"use client";

import { useEffect, type ReactNode } from "react";
import { AlertTriangle, Info, XCircle } from "./icons";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  variant?: "danger" | "info";
}

export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  variant = "info",
}: ModalProps) {
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    window.addEventListener("keydown", handleKeyDown);
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = originalOverflow;
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-dialog-title"
      aria-describedby={description ? "modal-dialog-description" : undefined}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg rounded-2xl border border-gray-700/60 bg-[rgba(17,24,39,0.95)] backdrop-blur-2xl p-6 shadow-2xl shadow-black/80 focus:outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-100 p-1 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00FF9D] transition-colors cursor-pointer"
          aria-label="Close dialog"
        >
          <XCircle className="w-5 h-5" />
        </button>

        <div className="flex items-start gap-4">
          {variant === "danger" ? (
            <div className="p-3 rounded-xl bg-red-500/15 border border-red-500/40 text-[#EF4444] shrink-0">
              <AlertTriangle className="w-6 h-6" />
            </div>
          ) : (
            <div className="p-3 rounded-xl bg-[rgba(0,255,157,0.12)] border border-[#00FF9D]/40 text-[#00FF9D] shrink-0">
              <Info className="w-6 h-6" />
            </div>
          )}

          <div>
            <h3 id="modal-dialog-title" className="text-lg font-semibold text-gray-100 font-mono">
              {title}
            </h3>
            {description && (
              <p id="modal-dialog-description" className="mt-1 text-xs text-gray-400 font-mono">
                {description}
              </p>
            )}
          </div>
        </div>

        <div className="mt-6">{children}</div>
      </div>
    </div>
  );
}
