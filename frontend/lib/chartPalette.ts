// Shared chart tokens for AskCFO tool-result visualizations. Values match the
// validated categorical/sequential palette (see dataviz skill references).
export const CHART_INK = "#0b0b0b";
export const CHART_INK_SECONDARY = "#52514e";
export const CHART_INK_MUTED = "#898781";
export const CHART_GRID = "#e1e0d9";
export const CHART_AXIS = "#c3c2b7";
export const CHART_SURFACE = "#fcfcfb";

export const CHART_BLUE = "#2a78d6"; // spending / money-in
export const CHART_BLUE_LIGHT = "#6da7ec"; // sequential: earlier period
export const CHART_BLUE_DARK = "#1c5cab"; // sequential: later period
export const CHART_AQUA = "#1baf7a"; // income
export const CHART_RED = "#e34948"; // money-out / expenses

export function formatCompactUsd(n: number): string {
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 10000) return `${sign}$${Math.round(abs / 1000)}k`;
  if (abs >= 1000) return `${sign}$${(abs / 1000).toFixed(1)}k`;
  return `${sign}$${Math.round(abs)}`;
}

export function formatUsd(n: number): string {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export function humanizeKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function monthLabel(ym: string): string {
  const [y, mo] = ym.split("-").map(Number);
  const name = new Date(y, mo - 1, 1).toLocaleString("en-US", { month: "short" });
  return `${name} '${String(y).slice(2)}`;
}
