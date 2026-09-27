# Valuation training data: how 10,055 listings become 5,513

This describes `apps/api/ml/shared/listings_dataset.py`, which builds the data for the v2
valuation challengers (`estate_v2_20260927`). v2 is not promoted. It stays at 0% traffic
until this has been reviewed.

Source: `apps/api/estatemind/intelligence/valuation/data/listings.csv`. It holds 10,055 scraped
listings, and its sha256 is recorded in each model's data card.

## What gets dropped, in order

| # | Rule | Rows removed | Why |
|---|------|-------------:|-----|
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
