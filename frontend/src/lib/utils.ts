import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export const money = (n: number | null | undefined) =>
  `$${(n ?? 0).toFixed(6)}`;
export const latency = (n: number | null | undefined) =>
  n == null
    ? "—"
    : n >= 1000
      ? `${(n / 1000).toFixed(2)}s`
      : `${Math.round(n)}ms`;
export const tokens = (n: number | null | undefined) =>
  n == null ? "—" : n.toLocaleString();
