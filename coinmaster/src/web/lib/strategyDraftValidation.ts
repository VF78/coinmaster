export function parseFiniteNumberFields(fields: string[]): number[] | null {
  const trimmed = fields.map((field) => field.trim());
  if (trimmed.length === 0 || trimmed.some((field) => field === '')) return null;
  const values = trimmed.map(Number);
  return values.every(Number.isFinite) ? values : null;
}
