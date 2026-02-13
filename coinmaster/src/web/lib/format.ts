export function formatMoney(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2
  }).format(value);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2
  }).format(value);
}

export function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}

export function formatPercent(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${formatNumber(value)}%`;
}

export function formatMoneyWithPercent(value: number, pct: number): string {
  return `${formatMoney(value)} (${formatPercent(pct)})`;
}
