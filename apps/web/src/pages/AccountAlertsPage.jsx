import React from 'react';
import { Link } from 'react-router-dom';
import { Bell } from 'lucide-react';

const CARD = 'rounded-2xl border border-white/10 bg-white/5 p-6';

// Property alerts have no backend yet. This page used to show sample alerts that
// were never saved or sent; it now says plainly that the feature is not available.
export default function AccountAlertsPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] px-4 pb-16 pt-24">
      <div className="mx-auto max-w-3xl space-y-6">
        <section className={`${CARD} text-center`}>
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-[#FF6B35]/30 bg-[#FF6B35]/10">
            <Bell className="h-6 w-6 text-[#FF6B35]" />
          </div>
          <span className="inline-block rounded-full border border-[#FF6B35]/30 bg-[#FF6B35]/10 px-3 py-1 text-xs font-semibold text-[#FF6B35]">
            Coming soon
          </span>
          <h1 className="mt-4 text-3xl font-black text-white">Property alerts</h1>
          <p className="mx-auto mt-3 max-w-xl text-sm text-gray-400">
            Alerts for price drops and new listings that match your criteria are not available yet.
            No alerts are saved or sent from this page.
          </p>
          <p className="mx-auto mt-3 max-w-xl text-sm text-gray-400">
            In the meantime, you can browse current listings or check a specific property.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link to="/explore" className="rounded-xl bg-[#FF6B35] px-4 py-2 text-sm font-semibold text-white hover:bg-[#ff7d4d]">
              Explore listings
            </Link>
            <Link to="/invest/scanner" className="rounded-xl border border-white/15 px-4 py-2 text-sm font-semibold text-gray-200 hover:bg-white/5">
              Scan a property
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
