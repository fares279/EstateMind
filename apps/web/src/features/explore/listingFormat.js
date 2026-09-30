// Shared display rules for listing cards and the listing detail modal.

// Assessment computed by the API (map/listings): the listing's price per m² against the
// median of real listings of the same type and transaction in its delegation.
export const DEAL_META = {
  good:  { icon: '🟢', label: 'Below Market', desc: 'Price per m² more than 15% under the local median' },
  fair:  { icon: '🟡', label: 'In Line With Market', desc: 'Price per m² within 15% of the local median' },
  above: { icon: '🔴', label: 'Above Market', desc: 'Price per m² more than 15% over the local median' },
  none:  { icon: '⚪', label: 'Not Assessed', desc: 'Too few comparable listings in this area to judge the price' },
};

export function dealMeta(deal) {
  return DEAL_META[deal] || DEAL_META.none;
}

// 320K TND / 1.25M TND, or 900 TND/month for rentals
export function priceLabel(price, transactionType) {
  const n = Number(price || 0);
  if (transactionType === 'rent') return `${Math.round(n).toLocaleString('en-US')} TND/month`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2).replace(/\.?0+$/, '')}M TND`;
  return `${Math.round(n / 1000)}K TND`;
}

export function priceCaption(transactionType) {
  return transactionType === 'rent' ? 'Monthly Rent' : 'Asking Price';
}

const SOURCES = {
  listings_csv: 'Classified listings dataset',
  synthetic: 'EstateMind sample (not a real listing)',
  tunisie_annonce: 'Tunisie Annonce', mubawab: 'Mubawab', tayara: 'Tayara', afariat: 'Afariat',
};

export function sourceLabel(source) {
  if (!source) return null;
  return SOURCES[String(source).toLowerCase()]
    || String(source).split(/[_\s]+/).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}
