import { changeColor, signedPct } from '../format';

describe('signedPct', () => {
  it('shows the sign of the change', () => {
    expect(signedPct(3.66)).toBe('+3.7%');
    expect(signedPct(-8)).toBe('−8.0%');
    expect(signedPct(0)).toBe('0.0%');
  });

  it('returns null when there is no value', () => {
    expect(signedPct(null)).toBeNull();
    expect(signedPct(undefined)).toBeNull();
  });
});

describe('changeColor', () => {
  it('colours rises, falls and missing values', () => {
    expect(changeColor(2)).toBe('#22c55e');
    expect(changeColor(-2)).toBe('#ef4444');
    expect(changeColor(null)).toBe('#9ca3af');
  });
});
