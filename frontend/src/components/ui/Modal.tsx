"use client";

import { useEffect, type ReactNode } from "react";
import { AlertTriangle, XCircle } from "./icons";

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
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "auto";
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-lg rounded-2xl border border-cyan-500/20 bg-[#0a1628] p-6 shadow-2xl shadow-cyan-950/40">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-sky-300/60 hover:text-sky-200 transition-colors cursor-pointer"
          aria-label="Close dialog"
        >
          <XCircle className="w-5 h-5" />
        </button>

        <div className="flex items-start gap-4">
          {variant === "danger" ? (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400">
              <AlertTriangle className="w-6 h-6" />
            </div>
          ) : (
            <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <AlertTriangle className="w-6 h-6" />
            </div>
          )}

          <div>
            <h3 className="text-lg font-semibold text-cyan-50">{title}</h3>
            {description && (
              <p className="mt-1 text-sm text-sky-200/70">{description}</p>
            )}
          </div>
        </div>

        <div className="mt-6">{children}</div>
      </div>
    </div>
  );
}

