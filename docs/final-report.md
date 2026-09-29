# EstateMind migration: final report

Date: 2026-09-28. Scope: the original `backend/` and `frontend/`, moved into this monorepo
(`apps/api`, `apps/web`) and modernized over six phases. The originals are untouched, and remain
the rollback reference until sign-off.

## 1. State at handoff

| Check | Result |
| --- | --- |
| API tests | 241 passing on SQLite and on Postgres (in docker-compose). 7 skip cleanly when model artifacts are absent |
| Web tests and build | 12 tests passing; production build compiles |
| Migrations | Complete (`makemigrations --check`: no changes) |
| Full stack | docker-compose (Postgres, Redis, API, Celery worker, Celery beat, web) healthy; a Celery task ran end to end |
| Secret scan | gitleaks over the git history: no leaks |
| Originals | No file in `backend/` or `frontend/` changed since before the migration started |
| Git | 52 local commits, one per phase step or fix. No remote |

## 2. Route walk (Phase 6)

**Inventory.** The original API has 414 routes and the new one has 412. Every difference is
deliberate:

- **Removed:** the 4 routes of the anonymous user create/list/edit/delete API (a security fix).
- **Added:** `investor/portfolio/analysis/` (previously unreachable, shadowed by another route),
  plus legal `feedback/` and `session/`.
- **Changed:** `investor/portfolio/`. The original registered it twice, and the second
  registration could never be reached. It now serves the same view as the original did.

**Live walk.** Every GET route was requested as an anonymous visitor, a regular user and a staff
user, in both apps. Each app ran against its own scratch copy of the original database, with
outbound network blocked. Of 258 comparable requests, 251 return the same status. The 7 that
differ are all intended:

- Campaign participants: 200 → 405. The public list of sign-ups' emails and phones is closed.
- Valuation calibration and drift: crash → 200. The original raised `AttributeError` on both.

**Found by the walk and fixed:** two admin scraper-health endpoints crashed in both trees (a missing
import).

**Web app.**

- All 23 page routes are identical to the original frontend.
- Of the 102 API paths the web code calls, all but 5 resolve. Those 5 are unused helpers pointing at
  routes that never existed, in the original either, and have been removed.
- One response changed shape: `/api/legal/status/` no longer has an `error` key. The rebuilt legal
  page doesn't read it.

## 3. Security fixes

All of these were live in the original code:

- **Anyone, without logging in, could list, edit (including their plan), create and delete any user
  account.** Separately, any logged-in user could set their own plan to Investor through the profile
  update.
- **Payment confirmation trusted the browser.** A Pro payment could be confirmed as Investor, and
  one user could confirm another user's payment. It also crashed after upgrading, so the payment
  was never recorded.
- **Stripe webhooks never took effect.** Every handler failed on the Stripe SDK's objects,
  silently, and still returned 200. Plans were never upgraded or downgraded by Stripe events.
- **Campaign sign-ups' names, emails and phone numbers were publicly listed.**
- **OTP could be brute-forced, and its lockout leaked the answer.**
  - A resend reset the wrong-guess count, so every resend gave 5 more guesses.
  - A locked account answered "Invalid OTP" to a wrong code but "Too many failed attempts" to the
    right one.
  - Codes came from `random` rather than `secrets`.
- **No rate limiting.** There are now limits on login, registration, OTP, password reset, chat,
  legal questions and feedback, plus generous global ones. They are tested against normal browsing.
- **Feedback could be sent on anyone's answers.** This let anyone skew the reward models' training
  data. Feedback now requires the conversation's session id.
- **Simulator runs had no owner.** Starting a run now requires login; deleting one requires its
  owner or staff.
- **Stripe test keys were hard-coded in `settings.py`.** They were removed; the defaults are blank.

## 4. Other fixes, by area

Each fix was measured before and after; the commit messages carry the numbers.

- **Valuation.**
  - The model registry now actually decides which model is served.
  - Location features were computed in the wrong order. After the fix, median error went from 59%
    to 34.5% on 300 listings.
  - Description sentiment and the image boost no longer move prices. Both are still shown to users.
  - The image classifier loads again (it never had), but it isn't useful. See §5.
  - The prediction log and users' valuation history were never saved on Postgres (a column too
    short).
- **Scraper.**
  - Real surfaces were being replaced with defaults: every Tayara surface became 90 m², "10000 m2"
    was read as 0, and "12 500 m²" as 500.
  - Health reports crashed.
- **Forecast.**
  - Intervals are now sized per horizon.
  - A fixed band that was presented as measured is now labelled as not measured.
  - The two forecast tables were merged into one.
- **Investor.**
  - Scores are labelled rule-based.
  - The AVOID rule compared units wrongly. 40 of 144 test cases move from WAIT to AVOID; all have a
    yield below 2%.
  - Portfolio saves work.
  - The calibration audit no longer invents grade inversions when it has no data.
  - When the three IRR figures are identical, the API now says why.
- **Chatbot.**
  - National rankings failed on SQLite and only considered 20 delegations.
  - The reply's turn number was off by one.
  - **Conversation memory now works across gunicorn workers** (Redis cache). Before, it
    disappeared whenever a request landed on another worker.
- **Platform.**
  - Celery task loading was broken, and two scheduled jobs had never run.
  - Stripe webhooks and the data pipeline crashed on Django 5 (`timezone.utc`).
  - Every production web build called `localhost` for its API.
  - A Stripe payment page called `undefined/billing/...`.
- **Infrastructure.**
  - Docker images, and docker-compose with the Celery worker and beat.
  - CI covering tests on SQLite and Postgres, a migration check, the web tests and build, the secret
    scan and the image builds. It hasn't run on GitHub yet: there is no remote.
  - An artifact lock file, with a pack/verify/fetch script.
  - Documentation in `docs/`.

## 5. Models: what is real and what isn't

| Component | Status |
| --- | --- |
| Valuation | Serving. Variant E serves apartments since 2026-09-29; houses and land keep the old champion (blocked by the stability gate); see below |
| Description sentiment | Shown to users, not applied to price: it added +4–10% with no accuracy gain |
| Image classifier | **Not retrained: no training data available.** It loads, but predicts "appartement" for any image, including a map. Price effect off |
| Forecast | Intervals cover less than their nominal level (about 81% overall for a 90% target, 70% at month 12). There is no price history, so forecast *levels* can't be backtested |
| Investor scoring | Fixed rules, labelled as such. The 7 ML models it was designed for don't exist |
| Climate | A formula only. The flood factor is mocked. See §8 |
| Simulator | Runs. RL backtesting and calibration are `not_implemented` |
| Chatbot | Works offline. Known issues in §7 |
| Legal assistant | Retrieval and grounding measured. Answer quality unmeasured. See §6 |

**Valuation: variant E serves apartments (2026-09-29).** The training data had the town and
governorate columns swapped in most rows, but not all, so the rows were fixed one by one. Variant E
adds that fix, drops generated-looking rows, and trains without coordinates (the API never sends
them). Scored through the serving code on 833 held-out listings, with the governorate and town a
user picks in the form:

| Median error | Current champion | Variant E | Difference [95% interval] |
| --- | ---: | ---: | --- |
| Apartment (398) | 34.5% | 22.5% | −12.0 points [−16.5, −7.3] |
| House (350) | 49.6% | 31.5% | −18.1 [−24.9, −12.1] |
| Land (85) | 59.2% | 35.5% | −23.7 [−52.0, −3.2] |

(The champions do worse here than the 25–38% measured earlier because they were trained on the
swapped columns: given a correct governorate and town, they are further off.) E passed the
accuracy rule for all three types. The promotion gate's explanation-stability check was broken
(it never tested the model); once fixed, it passes E for apartments (0.87) and blocks E for houses
(0.72) and land (0.67), against a 0.75 threshold. So only apartments were promoted. Whether to
relax that check is a decision for later. Full details are in
[ml/valuation-training-data.md](ml/valuation-training-data.md).

## 6. Legal assistant: the corpus is a hard ceiling

**The legal assistant can only answer from 23 passages of Tunisian law, covering registration
duties and mortgage law. It has nothing on sales contracts, leases, co-ownership, inheritance,
zoning or building permits. Questions on those topics cannot be answered well, however good the
model or retrieval is.** Widening the corpus is the only way past this. It must be sourced with
your approval: no scraping of outside sites.

Measured on the 43-question evaluation set:

- Retrieval recall@3: 0.48 → 0.96.
- Routing: 42/43. The routing threshold was tuned on this same set, so this is optimistic.
- The grounding gate caught 10/10 unsupported claims and kept 10/12 supported ones.

Answer quality with a real LLM is **unmeasured**. The default endpoint (tokenfactory) only
resolves on the ESPRIT network. To measure it, set `LEGAL_LLM_FALLBACK_*` to a reachable endpoint
and run `python manage.py evaluate_legal_assistant`.

## 7. Chatbot known issues

These are open, not fixed:

1. "Tunisia" is matched as the location **Tunis**.
2. The hallucination check tolerates **±10** on numbers, so wrong figures within that margin pass
   as grounded.
3. The **`[Source:` attribution regex runs on lower-cased text** and can never match, so
   `has_source_attribution` is always false.
4. The intent-accuracy check compares the classifier with **its own labels**, so it can't detect
   errors.
5. The daily quality report **crashes when re-run on the same day**.
6. "Which delegations will grow fastest?" is classified as a **greeting** (confidence 0.98).
7. Locations are recognized only if the delegation exists in the database.
8. The investment ranking by zone was never implemented. The chatbot now says so instead of failing.
9. The chat widget in the web app never sends feedback, so the chatbot's reward model receives no
   ratings from users.

## 8. Climate known issues (domain review needed; code unchanged)

- The composite score **rises toward the north** (correlation with latitude +0.36). **Tozeur**, with
  a heat score of 0.72, comes out **VERY_LOW** overall.
- The **flood factor is mocked**: it takes one of two fixed values, set only by whether a delegation
  is coastal.
- **Djerba is marked as not coastal.**
- The weights (flood 0.30, heat 0.25, coastal erosion 0.20, wildfire 0.10, infrastructure
  resilience −0.15) have not been validated.

Everything else that is open is in [known-issues.md](known-issues.md).

## 9. Your to-dos

1. **Rotate the provider keys:** the LLM key, the Gmail app password and the Stripe test keys.
   They need your provider accounts; steps and a check command are in
   [deployment.md](deployment.md#rotating-keys). Then check Stripe's webhook delivery log: webhooks
   never took effect before this fix. (`SECRET_KEY` and the JWT key are already rotated in the
   local `.env`.)
2. **Variant E for houses and land:** decide whether the stability check should compare the top
   features as a set rather than in exact order (see ml/valuation-training-data.md).
3. **Measure the legal assistant** with a reachable LLM (§6).
4. **Add a git remote** when ready. That lets the CI run, and lets the artifact bundle be published
   as a GitHub Release ([artifacts.md](artifacts.md)).
5. **Production settings:** `CACHE_URL` (Redis), `NUM_PROXIES` behind a proxy, and the rest of the
   checklist in [deployment.md](deployment.md).
6. **Sign-off:** once you're satisfied, the original `backend/` and `frontend/` can be retired.
   That is your call; nothing has been deleted.

## 10. Future projects

- Real investor models, and real forecast growth for the IRR scenarios.
- Simulator RL backtesting and calibration; moving simulator runs to Celery.
- Adaptive conformal intervals for the forecast.
- A labelled photo set, before the image classifier can be retrained or trusted.
- A larger legal corpus (sourced with approval).
- Climate reweighting and real flood data, after domain review.
- Moving the web app from Create React App to Vite ([frontend.md](frontend.md)).
- Marking values the scraper fills in, so training can exclude them. Scaling "MD" prices once the
  meaning is confirmed.

## 11. Corrections made during the migration

- **Phase 2's "surface area is ignored" finding was wrong.** My test payloads used `surface_m2`,
  but the API field is `size_m2`. The finding and its 75% error figure were withdrawn in Phase 4.
- **The Phase 4 sentiment figure (+9.6%) was measured against a fallback that itself cut prices by
  about 5%.** Against a true no-adjustment baseline, sentiment added about 4.4%. The conclusion (no
  accuracy gain, so keep it out of the price) did not change.
- **The first explanation of the Postgres column failure was wrong.** It blamed registry version
  names. The real cause was the fallback version name (`bytype__appartement__catboost`, 29
  characters), so the problem existed in the original code too. The fix (wider columns) was right
  either way.
