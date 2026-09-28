# Valuation training data: how 10,055 listings become 5,513

This describes `apps/api/ml/shared/listings_dataset.py`, which builds the data for the v2
valuation challengers (`estate_v2_20260927`). v2 is not promoted. It stays at 0% traffic
until this has been reviewed.

Source: `apps/api/estatemind/intelligence/valuation/data/listings.csv`. It holds 10,055 scraped
listings, and its sha256 is recorded in each model's data card.

## What gets dropped, in order

| # | Rule | Rows removed | Why |
| --- | --- | ---: | --- |
| 1 | Keep sale listings only | 2,621 | These are rentals. A monthly rent is a different target from a sale price. All 10,055 rows are apartment, house or land, so no other property types are dropped. |
| 2 | Price between 20,000 and 5,000,000 TND | 1,551 | 1,355 are under 20k: their median is 1,500 TND, and 1,244 of them price at 3–60 TND/m², which is what monthly rents look like. So these are almost certainly rentals labelled as sales. 196 are over 5M, with a median of 39M and a maximum of 236M TND: these are data errors, probably prices entered in millimes. |
| 3 | Plausible surface for the type | 73 | Apartments must be 20–600 m² (48 were larger, 2 smaller). Houses must be at least 40 m² (1 was smaller). Land must be 50–100,000 m² (22 were smaller). |
| 4 | Plausible price per m² | 180 | Apartments and houses must be 200–15,000 TND/m², land 5–8,000 TND/m². 102 land plots were above 8,000 TND/m², and 34 houses were below 200. Most of these are a surface or price typo. |
| 5 | Duplicates | 117 | Same type, price, surface, city, coordinates, room and bedroom counts: one row is kept. These are re-posted listings. Removing them first means the same property can't appear in both training and test data (checked: 0 overlap). 111 of the 117 are apartments. |
| | **Kept** | **5,513** | 2,930 apartments, 1,836 houses, 747 land plots |

The thresholds in rules 2–4 are judgement calls, not measured values. They are the numbers most
worth challenging. A lower price floor of about 10k would keep a few more real sales, but it would also
let rentals back in.

## What is changed (not dropped)

- **Descriptions are ignored.** Every description in the file is auto-generated from the listing
  title ("Informations déduites automatiquement..."), and 3,293 rows share one identical text.
- **Room count is derived from bedrooms (bedrooms + 1; land: bedrooms), not taken from the listing.**
  The live API never receives a room count: it takes bedrooms and derives rooms the same way. So
  training on the listed count would teach the model something it never sees when serving. The cost
  is that the listed room count differs from bedrooms + 1 in 84% of rows (4,604 of 5,513). It is
  kept in the data as `rooms_listed` but not used.
- **Location names are normalized.** Accents, case and spelling variants are unified, and a
  governorate is inferred when the columns disagree. This uses the same function the live API
  applies, so training and serving see the same values.
- **Local price levels ("priors").** For each property type, the model is given the median
  price per m² by town, by governorate, and nationally. A town or governorate needs at least 3
  listings to get its own figure. These medians are computed from the training 80% only, so the
  test set stays unseen.
- **Split:** 80% training, 20% test, within each property type, with a fixed seed. That gives
  4,411 training and 1,102 test rows.

## Issue found while writing this: the town information is mostly lost

In `listings.csv`, the `governorate` and `city` columns are swapped for most rows. `governorate`
holds the town (Hammamet 254, La Marsa 174, La Soukra 151, "Autres villes" 571; 289 distinct
values). `city` holds the governorate (Sousse, Tunis, Grand Tunis, Nabeul...; 140 distinct values).

The normalizer recovers the right governorate, so 3,602 rows get their governorate corrected. But
the pipeline then builds the model's `city` feature from the `city` column. As a result, in
4,003 of 5,513 rows (73%), the model's "city" is just the governorate name again. The most common
town keys are `tunis__tunis`, `sousse__sousse` and `nabeul__nabeul`. The model never learns that
La Marsa is priced differently from other parts of Tunis. The live API does send the real town
(for example `city=La Marsa`), and the model has mostly never seen those values in training.

The current champion models were trained on the same file, so they very likely share this issue.
v2's advantage over the champions is measured with this issue present in both.

**Proposed fix (not applied; it needs your OK):** when the `governorate` column holds a town
rather than a governorate name, use it as the town. Treat "Autres villes" ("other towns") as an
unknown town. Then retrain v2 and compare it again with the champions on the same test set. I expect
this to be the largest single accuracy improvement available from this data, but that is untested.

## Issue found while writing tests: some values look generated, not scraped

- **920 of the 5,513 kept rows (17%) have a surface with decimals**: 603 apartments, 315 land plots
  and 2 houses. Scraped surfaces are normally whole numbers. Examples include a 2-room apartment
  at 217.4 m² (713 TND/m², far below its area) and an apartment at 76.233109 m².
- **8 rows in 8 different towns have exactly the same price and surface** (1,361,916.03 TND and
  232.870099 m²), in Le Kram, La Manouba, Grombalia, Radès and others. That looks like a filled-in
  average, not 8 real listings.
- The current scraper does fill in missing prices, surfaces and bedroom counts with fixed benchmark
  values, and it doesn't flag them as filled in. But few rows in this file match those benchmarks
  exactly (18 kept rows on both price and surface). So the decimals above probably come from an
  earlier process that is no longer in the code.

These rows are kept by the current rules. **Proposed (not applied):** drop groups where the same
price and surface appear in more than one town, then measure how the models change with and without
the non-integer-surface rows before deciding on them. Separately, the scraper should mark
filled-in values so that future training data can exclude them.

## Other things to know

- `location_raw` holds numbers ("100", "550", "999"), not locations, so it is not used.
- 4 kept rows have no recognizable governorate ("unknown"). 24 governorates are represented.
- The test set comes from the same scrape as the training data. Its errors describe listing prices
  on this site, not transaction prices.

## Questions for your review

1. Are the price floor (20k TND) and ceiling (5M TND) acceptable?
2. Are the surface and price-per-m² ranges in rules 3–4 acceptable?
3. Should rooms be derived from bedrooms (it matches the API), or should the API be extended to accept a room count?
4. Should the town-column fix be applied before any promotion decision? I recommend yes.
5. Should cross-town duplicate values be dropped, and should the non-integer-surface rows be tested
   for exclusion? I recommend yes to both, with the effect measured before anything is promoted.

## Update: fixes applied and compared (not promoted)

The fixes above are now options in `ml/shared/listings_dataset.py` (`Options`). The defaults still
rebuild the v2 data exactly. Each change is counted in the data card. To reproduce the comparison,
run `python -m ml.valuation.compare_data_fixes`.

### The town/governorate columns: decided per row, not swapped wholesale

The swap turned out not to be systematic. Rows were grouped by which column holds a governorate
name:

| Pattern (all 10,055 rows) | Rows | Rule |
| --- | ---: | --- |
| Swapped: governorate column holds the town | 5,703 | Town from the governorate column ("Borj Louzir à La Soukra" becomes La Soukra); "Autres villes" (1,069) means no town |
| Correct orientation | 2,278 | Town from the city column |
| Both columns name the same governorate, or "Grand Tunis" | 1,754 | No town given |
| Two different governorates, e.g. "Tunis" + "Mahdia" | 244 | Governorate from the city column: the listing text names it in 236 of 236 kept rows (the governorate column in 3) |
| Neither column is a governorate name (encoding damage, e.g. "Gabs") | 76 | Town from the city column |

When no town is given, the governorate name stands in, as it does when a user types the
governorate as the city. In the 5,513 cleaned rows, the share with a real town rose from 27%
(1,510) to 66% (3,616). Apartments with a town-level price prior rose from 66 towns to 110.

### Coordinates: a train/serve mismatch

- 23% of all rows have coordinates at the geographic centre of Tunisia (33.844, 9.400), the scraper's
  "not geocoded" default.
- The valuation API never receives coordinates, so in production every model sees them as missing.
  The models were all trained with coordinates on every row.
- So every model is scored twice below: with coordinates (as in training) and without (as served).
  **The served numbers are the ones that matter.** The current champion also loses accuracy when
  served: its house error goes from 31% with coordinates to 38% without.

### Results (served, no coordinates)

Held-out set: the 1,102 listings in the previous v2's test set, minus those removed by the new
cleaning, leaving 833. No model was trained on them, except that the current champions' training data
is unknown and may include them. Intervals are 95% bootstrap intervals on the difference in median
error; a negative difference means E is better.

| Median error | Champion | Previous v2 | A: location fix | B: +cross-town dups dropped | C: +decimal surfaces dropped | D: +centroid coords missing | E: +no coords |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Apartment (n=398) | 25.5% | 26.4% | 23.6% | 23.9% | 23.7% | 23.3% | **22.5%** |
| House (n=350) | 37.8% | 39.8% | 33.8% | 32.4% | 33.3% | 33.0% | **31.5%** |
| Land (n=85) | 36.0% | 43.5% | 36.4% | 38.9% | 38.1% | 38.1% | **35.5%** |

- **E vs previous v2**: apartment −3.9 points [−6.5, −0.9], house −8.3 [−12.7, −3.1], land −8.0
  [−12.8, +1.5].
- **E vs champion**: apartment −3.1 [−7.0, +0.7], house −6.3 [−11.3, −1.8], land −0.5 [−24.5,
  +11.0]. Land has too few held-out rows to tell.
- **Price bias** (median predicted ÷ actual) for E: 0.99 / 1.01 / 0.94. For the champion: 1.01 /
  0.96 / 1.31. For the previous v2: 1.04 / 1.20 / 1.17.
- **Most of the gain comes from the location fix (A) and from training without coordinates (E).**
  Dropping the 516 cross-town duplicates and the 785 decimal surfaces does not clearly change
  accuracy on this held-out set. Keep or drop them on principle (they look generated), not for
  accuracy.
- **The town feature now carries signal.** The importance of town, town+governorate and the local
  price prior for apartments rose from 6.7 (previous v2) to 20.6 (E). Error on rows with a known town
  is 19.9% for E, against 24.8% for v2 and 21.4% for the champion.
- **By town, the results are mixed.** Apartments, E vs v2: La Soukra 25% → 14%, Menzah 29% → 16%,
  Hammamet 42% → 33%, Sousse Jawhara 22% → 16%; but Sousse 38% → 45%, Ariana 28% → 37% and La Marsa
  27% → 32%. "Sousse", "Ariana" and similar here are mostly rows with no town given.

Nothing was written to the artifacts or the registry. Variant E is the candidate if you want a
challenger. Training it for real (`train_catboost_bundle.py` with these options) would be the next
step, still at 0% traffic.
