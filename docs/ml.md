# ML models

The table below shows what each model is, and how far it has been checked against real data.
"Validated" means measured on held-out data or ground truth. It doesn't mean "trained".

| Component | What it is | Status |
| --- | --- | --- |
| Valuation | CatBoost per property type + global, chosen by the model registry | Serving. v2 challengers trained, at 0% traffic, awaiting data review |
| Description sentiment | TF-IDF classifier on listing text | Shown to users, **not** applied to price (no accuracy gain) |
| Image classifier | ResNet50, property type from a photo | Loads, but is not useful: predicts "appartement" for anything. Not retrained (no labelled photos). Price effect off |
| Forecast | Linear / N-BEATS per delegation, split-conformal intervals | Intervals cover less than their nominal level; no price history to backtest levels |
| Investor scoring | Fixed rules on zone market averages | Rule-based, labelled as such. The 7 ML models it was designed for do not exist |
| Investor IRR | Cash-flow IRR with pessimistic / base / optimistic growth | The growth input is a 0% placeholder in portfolio analysis, so the three scenarios are identical (labelled) |
| Climate risk | Weighted 5-factor composite, kriging between delegations | Formula only. The flood factor is mocked (set by the coastal flag); weights need domain review |
| Simulator | Mesa agent-based market model | Runs. RL backtesting and calibration are `not_implemented` |
| Chatbot | Sentence-embedding intent classifier + SQL-grounded answers | Works offline; known misclassifications (see known-issues) |
| Legal assistant | Multilingual retrieval over 23 law passages + NLI grounding gate + LLM | Retrieval and grounding measured; answer quality unmeasured until an LLM is reachable |

## Valuation

- **Data**: `ml/shared/listings_dataset.py` builds a train/test split from
  `estatemind/intelligence/valuation/data/listings.csv`. The rules and the open questions are in
  [ml/valuation-training-data.md](ml/valuation-training-data.md). Read that before promoting
  anything: the town column is mostly lost, and about 17% of the surfaces look generated.
- **Train**: `python ml/valuation/train_catboost_bundle.py [--register] [--version NAME]`. This
  writes `artifacts/valuation/models/<version>/` with a `priors.json`, and prints a comparison with
  the current champions on the same test set. `--register` adds the models as challengers at 0%
  traffic.
- **Promote**: `python manage.py promote_model --version-id <pk> --to challenger --traffic 10`,
  then `--to champion` once the A/B numbers hold up. Each registry scope has one champion.
- **Checks**: `tests/intelligence/valuation/test_training_pipeline.py` asserts that training and
  serving produce identical features (100% consistency on the v2 test set).
- **Measured** (300 clean listings, the models' own training data, so optimistic): the median
  error is 34.5%, and 30% of estimates are within 20% of the listed price.

## Forecast

- `python manage.py train_forecast_model`, then `generate_forecasts`.
- Intervals are split-conformal and sized per forecast horizon
  (`services/conformal_predictor.py`, tested in `tests/intelligence/forecast/test_conformal.py`).
  In a synthetic backtest at 90% nominal coverage, the linear model reached 81% overall and 70% at
  month 12. Intervals under-cover after regime changes; adaptive conformal is future work.
- There is no historical price series, so forecast *levels* cannot be backtested. The current
  forecasts sit at about 0.63× listing prices, and the archived set at 0.32× (a likely scaling
  error).

## Chatbot

- `python manage.py retrain_intent_classifier` (labelled intents: `export_labeled_intents`).
- It answers from SQL lookups, not a vector index, so there is nothing to re-embed.

## Legal assistant

- Index the corpus with `python manage.py index_legal_data`. This builds a new Chroma collection
  and activates it unless `--no-activate` is given.
- Evaluate with `python manage.py evaluate_legal_assistant [--json report.json]`, using the 43
  questions in `data/eval_questions.json`.
- Retrieval recall@3 is 0.96 and routing is 42/43. The routing threshold was tuned on this same
  set, so that figure is optimistic. The grounding gate caught 10/10 unsupported claims and kept
  10/12 supported ones.
- **Corpus ceiling**: 23 passages, covering registration duties and mortgage law only. Questions
  outside them cannot be answered well, whatever the model.
- LLM: `LEGAL_LLM_*` configures the primary endpoint (default tokenfactory, which only resolves on
  the ESPRIT network). `LEGAL_LLM_FALLBACK_*` sets an OpenAI-compatible or Claude fallback. Answer
  quality stays unmeasured until one of them is reachable.

## Signals kept out of the price

Both of these were re-validated in Phase 4 and are off by default:

- `VALUATION_SENTIMENT_PRICE_ADJUSTMENT` (0.9–1.15×). It raised prices by about 4–10% with no
  accuracy gain against listing prices. Every description in the data is auto-generated.
- `VALUATION_CV_PRICE_ADJUSTMENT` (1.0–1.2×). It is driven by image pixel variance, not by the
  classifier: a map scored +5%.

## Future projects

- Real investor models (the 7 the scorer was designed for), and real forecast growth for IRR
  scenarios.
- Simulator RL backtesting and calibration.
- Adaptive conformal intervals for the forecast.
- A labelled photo set, needed before the image classifier can be retrained or used.
- A larger legal corpus. It must be sourced with approval: no scraping of outside sites.
