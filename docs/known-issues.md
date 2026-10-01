# Known issues

These are found and not fixed: either a decision is needed, or the fix belongs in its own
project. Fixed issues are in the git history.

## Chatbot

- Intent accuracy on the hand-labelled held-out set (`data/chatbot_intents.json`, 31 questions) is
  77% (24/31), below the 92% target. Adding labelled examples did not change it (the method was
  chosen by cross-validation on the examples: 78% there); the embedding model seems to be the
  limit. Portfolio and forecast questions are the weakest. Explicit words decide which national
  ranking is shown, so rankings don't depend on the classifier.

## Legal assistant

- **The corpus is small: 51 passages** (registration duties, mortgage law, collective investment,
  debt recovery, and the Ministry of Justice's land-registration guide). Questions on sales,
  leases, co-ownership, inheritance or zoning have little to retrieve. The Code des droits réels
  and the COC are listed on justice.gov.tn, which has not answered from this machine since
  2026-09-30; `python -m ml.legal.fetch_official_texts` retries the fixed list. Copies exist on
  FAOLEX (fao.org), Droit-Afrique and bna.tn; they are outside sites, so not fetched without
  approval (legal-corpus-sources.md).
- The registry judge's guide (justice.gov.tn id 326) extracts as glyph names and needs OCR; it is
  skipped.
- Without a reachable LLM, answers quote the most relevant sentences of the retrieved texts
  (grounded by construction). Answer quality with an LLM is unmeasured: the default endpoint only
  resolves on the ESPRIT network. `evaluate_legal_assistant` measures it once one is reachable.

## Valuation data

See [ml/valuation-training-data.md](ml/valuation-training-data.md):

- `listings.csv` (source data, kept as is) has the governorate and town columns swapped in most
  rows, and generated-looking rows. The training pipeline fixes the location per row and drops
  those rows (variants E and E2, which all three types now use).
- `listings.csv` has no listing dates, so no price history can be built from it.
- The previous v2 models remain registered at 0% traffic.

## Scraper

- "MD" is read as thousands of dinars ("350 MD" = 350,000), except a value under 10 with decimals
  ("1,2 MD"), read as millions. The notation is ambiguous; listings that fit neither reading are
  rejected as before.

## Climate (domain review or data needed)

- Scores come from curated governorate climate normals (`data/climate_governorate_normals.csv`:
  rainfall, days above 35 °C, documented flood exposure, forest cover), not a hazard map.
  Delegations of one governorate differ only through the coastal flag, a short list of named
  erosion hotspots, and population.
  Weights: flood 0.25, heat 0.25, water stress 0.20, coastal erosion 0.15, wildfire 0.10,
  infrastructure resilience −0.05. Changing them is a domain decision.
- Coastal flags come from the distance to a simplified coastline (5 km, plus a list of known
  coastal delegations): accurate to a few kilometres.
- Climate does not change served valuations: the models have no climate input. The valuation page
  shows climate as context only.
- The governorate-level `ClimateRisk` table is empty (the ClimaTN CSVs are not in the repo). The
  Explore map's climate layer shows the delegation scores instead.

## Investor

- Scores come from fixed rules (labelled); the 7 designed models don't exist, and there is no
  transaction or return history to label them with (undervaluation outcomes, IRRs, buy/wait
  results).
- Rent: a CatBoost rent-per-m² model trained on the 572 real rental listings beat the medians on
  average (median error 26.7% vs 32.3%) but lost one of five splits, so under the rule set before
  training (`ml/investor/train_rent_model.py`) it is not adopted; yields use the delegation or
  governorate median rent. The serving path is in place if a retrain with more listings passes.
- The forward IRR assumes the 12-month outlook growth continues for the 10-year holding period
  (stated on the page). Its low and high cases use the outlook's 90% interval, measured on the
  national INS index only.
- `investor/data/zone_market_stats.csv` still feeds the (absent) models' features; its demand,
  vacancy and days-on-market columns are one constant for every delegation and are no longer shown.

## Valuation serving

- All three property types are served by models trained on the cleaned data without
  coordinates: apartments and land by variant E, houses by E2 (E without the redundant
  surface x local price feature; it passed the stability gate at 0.91 where E failed at 0.72).
  Served median error: apartments 22.5%, houses 31.2%, land 35.5%.

## Forecast

- The outlook's growth rate is national: the INS index (`data/ins_property_price_index.csv`, 2000
  Q1 - 2025 Q4) has no delegation or governorate series. Its backtest error (12-month growth,
  2005-2025: apartments 5.6 points, houses 5.7, land 3.7) is national; local accuracy is not
  measured. Delegations differ only by their benchmark trend's deviation from the type's median.
- Price levels are the benchmark averages of `delegations.csv` (asking prices, undated); they sit
  well above listing medians for houses (see the simulator calibration report).
- The INS series ends at the last release (2025 Q4, published 2026-08-11); update the CSV when a
  new release appears.
- The scraper assigns catch-all "X Ville" delegations.
- The adaptive-conformal path still under-covers on synthetic series (73-80% at a 90% target) and
  is not calibrated for served outlooks; they use the INS backtest interval.

## Simulator

- Starting price levels are calibrated to real sale listings (`calibrate_simulator`): median
  error against listings drops from 34% to 16% for apartments and 68% to 19% for houses
  (leave-one-out). Land keeps its benchmark: the correction did not help there (59% vs 79%).
- Agent behaviour (reward weights) is not calibrated: that needs observed transactions, and only
  asking prices exist. The strategy backtest (buy now vs wait) reports simulated outcomes under
  each scenario's assumptions, not forecasts.

## Platform

- Automatic renewal works in the Stripe sandbox (Pro $50, Investor $100 a month). A live
  deployment needs live-mode Prices in `STRIPE_PRICE_PRO` / `STRIPE_PRICE_INVESTOR`; without them,
  a payment gives 30 days of the plan.
- 54% of the real listings (2,875 of 5,306) match a delegation. Of the sale listings, 1,554 name
  no town, and about 700 name neighbourhoods missing from the scraper's town table; those stay at
  governorate level. Listing coordinates are delegation centroids.
- API Keys is parked: `pages/AccountApiKeysPage.jsx` is a mock-up with no backend. It is kept but
  not routed or linked, pending a decision on a real API-key feature.
- Property Alerts has no backend; the page says "Coming soon" instead of showing sample alerts.
- Valuation scenarios (renovation, extra bedroom, ...) are rules of thumb, labelled as such.
