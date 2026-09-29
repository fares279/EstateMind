// A percentage change with its sign: +3.7%, −8.0%, 0.0%. null/undefined -> null.
export function signedPct(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return null;
  const n = Number(value);
  const text = Math.abs(n).toFixed(digits);
  if (n > 0) return `+${text}%`;
  if (n < 0) return `−${text}%`;
  return `${text}%`;
}

// Green for a rise, red for a fall, grey for flat or missing.
export function changeColor(value) {
  if (value == null || Number(value) === 0) return '#9ca3af';
  return Number(value) > 0 ? '#22c55e' : '#ef4444';
}
