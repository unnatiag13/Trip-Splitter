export const EXPENSE_CATEGORIES = [
  'Food',
  'Accommodation',
  'Transport',
  'Shopping',
  'Activities',
  'Utilities',
  'Miscellaneous',
] as const;

export const ANALYTICS_PALETTE = [
  '#3D9A9B', // Soft teal
  '#8E7CC3', // Lavender
  '#E07A6B', // Coral
  '#E6A15C', // Pastel orange
  '#5B88B8', // Soft blue
  '#6F9E82', // Sage
  '#B9788B', // Dusty rose
];

export const CATEGORY_COLOR_MAP: Record<string, string> = {
  Food: '#E07A6B',
  Accommodation: '#8E7CC3',
  Transport: '#5B88B8',
  Shopping: '#E6A15C',
  Activities: '#3D9A9B',
  Utilities: '#6F9E82',
  Miscellaneous: '#B9788B',
};

export function formatINR(paise: number, showPlus = false): string {
  const sign = paise < 0 ? '-' : showPlus && paise > 0 ? '+' : '';
  const abs = Math.abs(Math.round(paise));
  const rupees = Math.floor(abs / 100);
  const cents = abs % 100;
  const formatted = rupees.toLocaleString('en-IN');
  return `${sign}₹${formatted}.${String(cents).padStart(2, '0')}`;
}

export function paiseToRupeeString(paise: number): string {
  return (paise / 100).toFixed(2);
}

export function rupeeStringToPaise(value: string): number {
  const num = Number.parseFloat(value);
  if (!Number.isFinite(num) || num < 0) return 0;
  return Math.round(num * 100);
}

export function formatDateShort(dateStr: string): string {
  if (!dateStr) return '';
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  const year = Number(parts[0]);
  const month = Number(parts[1]) - 1;
  const day = Number(parts[2]);
  const dt = new Date(year, month, day);
  return dt.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export function formatTimestamp(isoStr: string | null): string {
  if (!isoStr) return '';
  const dt = new Date(isoStr);
  if (Number.isNaN(dt.getTime())) return isoStr;
  return dt.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function splitMethodLabel(method: string): string {
  if (method === 'equal') return 'Equal';
  if (method === 'custom') return 'Custom';
  if (method === 'percentage') return 'Percentage';
  return method;
}
