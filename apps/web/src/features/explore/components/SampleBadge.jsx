// Marks a listing generated from price benchmarks (Property.source === 'synthetic').
export default function SampleBadge() {
  return (
    <span
      className="inline-block mt-1 px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide bg-amber-500/15 text-amber-300 border border-amber-500/30"
      title="Generated from EstateMind's price benchmarks where no real listing exists. Not a real listing."
    >
      Sample data
    </span>
  );
}
