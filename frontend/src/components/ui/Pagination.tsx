"use client";

import { useMemo } from "react";
import { ChevronLeft, ChevronRight } from "@/components/ui/icons";

export interface PaginationProps {
  currentPage: number;
  totalItems: number;
  pageSize: number;
  totalPages?: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  pageSizeOptions?: number[];
  showPageSizeSelector?: boolean;
  className?: string;
}

export function Pagination({
  currentPage,
  totalItems,
  pageSize,
  totalPages: propTotalPages,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [5, 10, 25, 50],
  showPageSizeSelector = true,
  className = "",
}: PaginationProps) {
  const computedTotalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const totalPages = propTotalPages !== undefined ? propTotalPages : computedTotalPages;

  const startIndex = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endIndex = Math.min(currentPage * pageSize, totalItems);

  // Compute page numbers to display with ellipsis
  const pageNumbers = useMemo(() => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }

    const pages: (number | "ellipsis")[] = [];

    if (currentPage <= 4) {
      for (let i = 1; i <= 5; i++) pages.push(i);
      pages.push("ellipsis");
      pages.push(totalPages);
    } else if (currentPage >= totalPages - 3) {
      pages.push(1);
      pages.push("ellipsis");
      for (let i = totalPages - 4; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      pages.push("ellipsis");
      pages.push(currentPage - 1);
      pages.push(currentPage);
      pages.push(currentPage + 1);
      pages.push("ellipsis");
      pages.push(totalPages);
    }

    return pages;
  }, [currentPage, totalPages]);

  if (totalItems === 0) {
    return null;
  }

  return (
    <div
      className={`flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-gray-800 text-xs font-mono text-gray-400 ${className}`}
    >
      {/* Entries Counter & Page Size Selector */}
      <div className="flex flex-wrap items-center gap-2">
        <span>
          Showing <span className="text-gray-200 font-bold">{startIndex}</span> to{" "}
          <span className="text-gray-200 font-bold">{endIndex}</span> of{" "}
          <span className="text-[#00FF9D] font-bold">{totalItems}</span> entries
        </span>

        {showPageSizeSelector && onPageSizeChange && (
          <div className="flex items-center gap-1.5 ml-2 pl-2 border-l border-gray-800">
            <span className="text-[11px] text-gray-500">Per page:</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              aria-label="Items per page"
              className="bg-[#090D16] border border-gray-700/80 rounded px-1.5 py-0.5 text-xs text-gray-200 focus:outline-none focus:border-[#00FF9D]"
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Page Navigation Buttons */}
      <div className="flex items-center gap-1 shrink-0">
        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          aria-label="Previous page"
          className="p-1.5 rounded border border-gray-700/70 bg-[#090D16] text-gray-300 hover:text-white hover:border-[#00FF9D]/60 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>

        {pageNumbers.map((p, idx) => {
          if (p === "ellipsis") {
            return (
              <span key={`ellipsis-${idx}`} className="px-1 text-gray-500 select-none">
                …
              </span>
            );
          }

          const isActive = p === currentPage;
          return (
            <button
              key={p}
              type="button"
              onClick={() => onPageChange(p)}
              aria-current={isActive ? "page" : undefined}
              className={`min-w-6 h-6 px-1.5 rounded text-xs font-bold transition-all ${
                isActive
                  ? "bg-[#00FF9D]/20 text-[#00FF9D] border border-[#00FF9D]/60 shadow-[0_0_10px_rgba(0,255,157,0.2)]"
                  : "border border-transparent text-gray-400 hover:text-white hover:border-gray-700 bg-transparent"
              }`}
            >
              {p}
            </button>
          );
        })}

        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          aria-label="Next page"
          className="p-1.5 rounded border border-gray-700/70 bg-[#090D16] text-gray-300 hover:text-white hover:border-[#00FF9D]/60 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
