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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-lg rounded-2xl border border-[rgba(75,85,99,0.4)] bg-[rgba(31,41,55,0.85)] backdrop-blur-2xl p-6 shadow-2xl shadow-black/80">
        <button
          suppressHydrationWarning
          onClick={onClose}
          className="absolute top-4 right-4 text-[#9CA3AF] hover:text-[#F3F4F6] transition-colors cursor-pointer"
          aria-label="Close dialog"
        >
          <XCircle className="w-5 h-5" />
        </button>

        <div className="flex items-start gap-4">
          {variant === "danger" ? (
            <div className="p-3 rounded-xl bg-[rgba(239,68,68,0.15)] border border-red-500/40 text-[#EF4444]">
              <AlertTriangle className="w-6 h-6" />
            </div>
          ) : (
            <div className="p-3 rounded-xl bg-[rgba(0,255,157,0.12)] border border-[#00FF9D]/40 text-[#00FF9D]">
              <AlertTriangle className="w-6 h-6" />
            </div>
          )}

          <div>
            <h3 className="text-lg font-semibold text-gray-100">{title}</h3>
            {description && (
              <p className="mt-1 text-xs text-[#9CA3AF] font-mono">{description}</p>
            )}
          </div>
        </div>

        <div className="mt-6">{children}</div>
      </div>
    </div>
  );
}
