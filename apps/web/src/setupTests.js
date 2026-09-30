import '@testing-library/jest-dom';

// jsdom has no ResizeObserver; recharts' ResponsiveContainer needs one
if (typeof window !== 'undefined' && !window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
