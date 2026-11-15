"use client";

import React, { useRef } from "react";

export function formatPagoMovilAmount(value: number): string {
  const safe = Number.isFinite(value) && value >= 0 ? value : 0;
  const cents = Math.round(safe * 100);
  const integerPart = Math.floor(cents / 100);
  const decimalPart = String(cents % 100).padStart(2, "0");
  const intFormatted = integerPart
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${intFormatted},${decimalPart}`;
}

interface BankAmountInputProps {
  value: number;
  onChange: (nextValue: number) => void;
  className?: string;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  autoFocus?: boolean;
  id?: string;
  ariaLabel?: string;
}

/**
 * Entrada numérica estilo Banca Venezolana / Pago Móvil (sin botones spin, con decimales ",00"
 * y desplazamiento de derecha a izquierda: 0,00 -> 0,05 -> 0,50 -> 5,00 -> 50,00).
 */
export function BankAmountInput({
  value,
  onChange,
  className = "",
  placeholder = "0,00",
  disabled = false,
  required = false,
  autoFocus = false,
  id,
  ariaLabel,
}: BankAmountInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const justFocusedRef = useRef<boolean>(false);

  const formattedValue = formatPagoMovilAmount(value);

  function moveCaretToEnd(el: HTMLInputElement | null) {
    if (!el) return;
    requestAnimationFrame(() => {
      try {
        const len = el.value.length;
        el.setSelectionRange(len, len);
      } catch {
        // Ignorar si el navegador no soporta setSelectionRange en el elemento
      }
    });
  }

  function handleFocus(e: React.FocusEvent<HTMLInputElement>) {
    justFocusedRef.current = true;
    moveCaretToEnd(e.currentTarget);
  }

  function handleClick(e: React.MouseEvent<HTMLInputElement>) {
    moveCaretToEnd(e.currentTarget);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (disabled) return;

    // Permitir atajos del sistema (Ctrl+C, Ctrl+V, Ctrl+A, Alt+N, Tab, Enter, Escape)
    if (e.ctrlKey || e.metaKey || e.altKey) {
      return;
    }

    if (/^[0-9]$/.test(e.key)) {
      e.preventDefault();
      const digit = Number(e.key);
      const currentCents = justFocusedRef.current
        ? 0
        : Math.round((Number.isFinite(value) ? value : 0) * 100);
      justFocusedRef.current = false;

      const nextCents = Math.min(999999999999, currentCents * 10 + digit);
      onChange(nextCents / 100);
      moveCaretToEnd(inputRef.current);
      return;
    }

    if (e.key === "Backspace") {
      e.preventDefault();
      justFocusedRef.current = false;
      const currentCents = Math.round((Number.isFinite(value) ? value : 0) * 100);
      const nextCents = Math.floor(currentCents / 10);
      onChange(nextCents / 100);
      moveCaretToEnd(inputRef.current);
      return;
    }

    if (e.key === "Delete") {
      e.preventDefault();
      justFocusedRef.current = false;
      onChange(0);
      moveCaretToEnd(inputRef.current);
      return;
    }

    // Ignorar letras o símbolos de puntuación manuales para mantener formato ,00 estricto
    if (e.key.length === 1) {
      e.preventDefault();
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (disabled) return;
    justFocusedRef.current = false;
    const rawDigits = e.target.value.replace(/\D/g, "").slice(0, 12);
    const cents = rawDigits ? parseInt(rawDigits, 10) : 0;
    onChange(cents / 100);
    moveCaretToEnd(e.currentTarget);
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    if (disabled) return;
    e.preventDefault();
    justFocusedRef.current = false;
    const pasted = e.clipboardData.getData("text").trim();
    if (!pasted) return;

    // Si pega un número con separador decimal explícito (ej. "4500,50" o "4500.50")
    const normalized = pasted
      .replace(/\s/g, "")
      .replace(/\.(?=\d{3}(?:[.,]|$))/g, "")
      .replace(",", ".");
    const parsedFloat = Number(normalized);
    if (Number.isFinite(parsedFloat) && parsedFloat >= 0) {
      onChange(Math.round(parsedFloat * 100) / 100);
      moveCaretToEnd(inputRef.current);
      return;
    }

    const digits = pasted.replace(/\D/g, "").slice(0, 12);
    if (digits) {
      onChange(parseInt(digits, 10) / 100);
      moveCaretToEnd(inputRef.current);
    }
  }

  return (
    <input
      ref={inputRef}
      id={id}
      type="text"
      inputMode="numeric"
      autoComplete="off"
      required={required}
      autoFocus={autoFocus}
      disabled={disabled}
      aria-label={ariaLabel}
      placeholder={placeholder}
      value={formattedValue}
      onFocus={handleFocus}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      onChange={handleChange}
      onPaste={handlePaste}
      className={className}
    />
  );
}
