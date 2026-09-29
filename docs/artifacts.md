# Model artifacts

Trained models and the legal vector store (33 files, 143 MB) live in `apps/api/artifacts/`
(`ESTATEMIND_ARTIFACTS_DIR` overrides the location). They are gitignored. What *should* be there is
recorded in the tracked `apps/api/artifacts.lock.json`: each file's path, size and sha256.

```bash
cd apps/api
python scripts/artifacts.py verify               # does disk match the lock? (--strict: see below)
python scripts/artifacts.py lock                 # record the current files (after retraining)
python scripts/artifacts.py pack bundle.tar.gz   # bundle them for upload
python scripts/artifacts.py fetch <https-url>    # download a bundle, verify, install
```

`fetch` verifies every file against the lock *before* installing anything. A bundle that doesn't
match is rejected, and nothing is written. The API container runs `verify` at start, and runs
`fetch` when `ESTATEMIND_ARTIFACTS_URL` is set and files are missing.

The legal vector store (`chroma/`) is runtime-mutable: Chroma rewrites its files when it is used.
It is locked and shipped like the rest, but `verify` only requires those files to be present, so
using the legal assistant doesn't make the next container start re-download the bundle.
`verify --strict`, `pack` and `fetch` compare every file. To pack after the store has been used,
run `lock` first.

## Workflow after retraining

1. Train. This writes into `artifacts/`.
2. `python scripts/artifacts.py lock`, then commit `artifacts.lock.json` with the code change.
3. `pack` and upload the bundle.
4. Point `ESTATEMIND_ARTIFACTS_URL` (deployments, and the CI secret) at the new bundle.

## Where to store the bundle: GitHub Releases (decided)

One GitHub Release per locked bundle, tagged `artifacts-YYYYMMDD`, with the `.tar.gz` as its
asset. Nothing is published yet: the repository has no remote. Once it does:

```bash
python scripts/artifacts.py pack estatemind-artifacts-YYYYMMDD.tar.gz
gh release create artifacts-YYYYMMDD estatemind-artifacts-YYYYMMDD.tar.gz --notes "lock: <commit>"
```

Then set `ESTATEMIND_ARTIFACTS_URL` to the asset's download URL. For a private repository the
download needs authentication, e.g. a pre-signed or token-bearing URL; `fetch` only accepts
`https://`.

The other options, if the needs change:

| Option | Fits when | Notes |
| --- | --- | --- |
| GitHub Release asset | The repo is on GitHub | Simplest. Private repos need a token in the URL or an authenticated download |
| Object storage (S3, R2, GCS) with pre-signed URLs | There is a cloud account | Versioned buckets make rollbacks easy |
| Hugging Face Hub (private model repo) | Models may be shared later | Built for large binaries; bundles can also be split per model |
| Git LFS | Everything should stay in git | Bandwidth quotas; every clone pulls large files |

Move to object storage if bundles become frequent or large.

## What is in the bundle

- `valuation/models/models_estateprocessor/`: the serving champions (CatBoost, plus ExtraTrees
  challengers for houses and land).
- `valuation/models/estate_v2_20260927/`: v2 challengers at 0% traffic, with `priors.json`.
- `valuation/models/fallback_tabular/`: fallback models and the location price priors.
- `valuation/models/image_property_type_fallback.pt`: the image classifier (not useful; see ml.md).
- `valuation/models/tfidf_char_sentiment.joblib`: description sentiment (display only).
- `valuation/valuation_model.joblib`, `forecast/forecast_model.joblib`: legacy models.
- `chroma/legal/`: the legal vector store. The active collection is `legal_tunisia_all_v1`; older
  collections are kept for rollback.

Hugging Face models (the sentence encoder, the NLI model, the chatbot intent encoder) are *not*
in the bundle. They download on first use into `HF_HOME`, which is a named volume in
docker-compose.
