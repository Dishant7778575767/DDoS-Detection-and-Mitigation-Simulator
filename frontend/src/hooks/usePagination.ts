"use client";

import { useMemo, useState } from "react";

export interface UsePaginationOptions {
  initialPage?: number;
  initialPageSize?: number;
}

export interface UsePaginationResult<T> {
  currentPage: number;
  pageSize: number;
  totalPages: number;
  totalItems: number;
  paginatedItems: T[];
  setCurrentPage: (page: number) => void;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  goToNextPage: () => void;
  goToPreviousPage: () => void;
  canNextPage: boolean;
  canPreviousPage: boolean;
}

export function usePagination<T>(
  items: T[],
  initialPageSize: number = 10,
  initialPage: number = 1
): UsePaginationResult<T> {
  const [currentPage, setCurrentPageState] = useState<number>(initialPage);
  const [pageSize, setPageSizeState] = useState<number>(initialPageSize);

  const totalItems = items.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));

  // Reset to valid range if items change
  const validCurrentPage = Math.min(Math.max(1, currentPage), totalPages);

  const setCurrentPage = (page: number) => {
    setCurrentPageState(Math.min(Math.max(1, page), totalPages));
  };

  const setPageSize = (size: number) => {
    setPageSizeState(size);
    setCurrentPageState(1);
  };

  const paginatedItems = useMemo(() => {
    const startIndex = (validCurrentPage - 1) * pageSize;
    return items.slice(startIndex, startIndex + pageSize);
  }, [items, validCurrentPage, pageSize]);

  return {
    currentPage: validCurrentPage,
    pageSize,
    totalPages,
    totalItems,
    paginatedItems,
    setCurrentPage,
    setPage: setCurrentPage,
    setPageSize,
    goToNextPage: () => setCurrentPage(validCurrentPage + 1),
    goToPreviousPage: () => setCurrentPage(validCurrentPage - 1),
    canNextPage: validCurrentPage < totalPages,
    canPreviousPage: validCurrentPage > 1,
  };
}
