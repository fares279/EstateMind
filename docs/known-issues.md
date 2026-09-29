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

- **Hard ceiling: the corpus has 23 passages, covering registration duties and mortgage law
  only.** Questions about other property law (sales, leases, co-ownership, inheritance, zoning)
  have nothing to retrieve, however good the model is.
- Answer quality with a real LLM is unmeasured. The default endpoint only resolves on the ESPRIT
  network. `evaluate_legal_assistant` measures it once an endpoint is reachable.
- The routing threshold was tuned on the evaluation set, so 42/43 is optimistic.

## Valuation data

See [ml/valuation-training-data.md](ml/valuation-training-data.md):

- In `listings.csv`, the governorate and town columns are swapped for most rows. The model's town
  feature is the governorate name in 73% of rows.
- 17% of kept surfaces have decimals, and 8 rows in different towns share an identical price and
  surface. These values look generated.
- v2 challengers stay at 0% traffic until that review.

## Scraper

- Prices in "MD" are not scaled. In classifieds "MD" usually means thousands of dinars, but it
  is ambiguous. Such prices are then rejected as too low and replaced by a benchmark.
- Missing prices, surfaces and bedroom counts are filled with benchmark values, and nothing marks
  them as filled in.

## Climate (domain review needed; code unchanged)

- The composite rises toward the north (correlation with latitude +0.36). Tozeur, with heat 0.72,
  comes out VERY_LOW.
- The flood factor is mocked: it takes two fixed values, set only by `is_coastal`.
- Djerba is marked as not coastal.
- Climate does not change served valuations: the CatBoost models have no climate input, and
  `climate_adjusted_price` is never set. The page shows climate as context only.
- The `ClimateRisk` table is empty (the ClimaTN CSVs are not in the repo), so the climate layer
  on the Explore map is empty. `seed_demo_data` fills the delegation-level scores only.
- Coastal flags come from a governorate-level rule, and Hammamet has no coordinates in the source
  geography.
- Weights: flood 0.30, heat 0.25, coastal erosion 0.20, wildfire 0.10, infrastructure resilience
  −0.15.

## Investor

- Scores come from fixed rules (labelled); the 7 designed models don't exist, and there is no
  transaction or return history to train them on.
- The forward IRR assumes the 12-month forecast growth continues for the 10-year holding period
  (stated on the page). The forecast band it uses for the low and high cases is illustrative, not
  measured.
- `investor/data/zone_market_stats.csv` still feeds the (absent) models' features; its demand,
  vacancy and days-on-market columns are one constant for every delegation and are no longer shown.

## Valuation serving

- The house and land champions were trained with coordinates and on the swapped location
  columns, but the API sends no coordinates and a correct governorate and town. Served error on
  that input: houses 49.6%, land 59.2%. Variant E (31.5%, 35.5%) is registered at 0% traffic;
  the stability gate blocks it (see [ml/valuation-training-data.md](ml/valuation-training-data.md)).
  Apartments are served by E since 2026-09-29.

## Forecast

- There is no price history, so forecast levels can't be backtested. Current forecasts sit at
  0.63× listing prices; the archived set is at 0.32×.
- The scraper assigns catch-all "X Ville" delegations.
- Conformal intervals under-cover after regime changes.

## Simulator

- Runs execute in a thread inside the web process, not in Celery. A burst of runs competes with
  web requests. Moving them to Celery is a separate project.
- RL backtesting and calibration are `not_implemented`.

## Platform

- Rate limits exist (see settings `DEFAULT_THROTTLE_RATES`). They need `CACHE_URL` (shared Redis)
  to hold across several processes, and `NUM_PROXIES` behind a proxy.
- `checkout.session.completed` webhooks handle subscriptions, but checkout creates one-off
  PaymentIntents. Real upgrades go through `confirm-payment`, and renewals aren't automatic.
- Frontend test coverage is thin (see frontend.md).
- The dev database starts empty by design; run `migrate` then `seed_demo_data`. Only about half
  of the real listings match a delegation; listing coordinates are delegation centroids.
- API Keys is parked: `pages/AccountApiKeysPage.jsx` is a mock-up with no backend. It is kept but
  not routed or linked, pending a decision on a real API-key feature.
- Property Alerts has no backend; the page says "Coming soon" instead of showing sample alerts.
- Valuation scenarios (renovation, extra bedroom, ...) are rules of thumb, labelled as such.
