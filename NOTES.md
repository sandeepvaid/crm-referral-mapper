# NOTES

## What is built

A working, fully-tested service (27 passing tests, no network):

- Shared field list + per-customer templates, stored so a **new field appears on
  templates saved earlier with no row rewrite and no hand-edit**.
- `crm-field-values`: builds the fetch list from the template the customer
  currently sees, **one call per CRM object**, a **single retry** on
  `RateLimited`, Pydantic v2 validation, and errors that name the Labra field,
  the CRM object+field, the received value, what is wrong, and the fix.
- Create-time rejection of every bad-template case (stores nothing).
- Optional fields can be marked **unused**; a required field cannot.

Not built, by instruction: a distributed rate limiter (discussed in §4), plus a
UI and auth. §5 names the one extra thing left out.

---

## 1. Schema — and what introducing `customer_duns` writes

```sql
labra_fields(labra_field PK, label, required, sort_order)   -- the shared list
templates(template_id PK, name, crm_type)                   -- one row per template
mappings(template_id, labra_field, crm_object, crm_field, unused)
         PRIMARY KEY (template_id, labra_field)             -- ONLY the customer's deltas
```

- **The shared Labra field list** lives in `labra_fields` — one row per field,
  seeded with the six originals. This is the single source of truth.
- **Northwind's CRM mappings** live in `mappings` — six rows, each pointing one
  Labra field at an `Account`/`Opportunity`/`Contact` field. The template's
  identity and CRM type live in `templates`.

`GET /mapping-templates/{id}` **merges** `labra_fields` with that template's
`mappings` at read time. Nothing about the field list is copied onto the
template row.

**Introducing `customer_duns`** (`POST /labra-fields`) is **exactly one INSERT
into `labra_fields`**:

| Table | Rows written when `customer_duns` is introduced |
|-------|--------------------------------------------------|
| `labra_fields` | **1** inserted (`customer_duns`, label, required, next sort_order) |
| `templates` | **0** |
| `mappings` | **0** — every existing template is left completely alone |

The next `GET` of any template (including ones saved before the call) joins in
the new field and returns it `mapped: false`. The test
`test_new_field_appears_on_old_template` snapshots the raw `mappings` rows before
and after and asserts they are **byte-for-byte identical**.

- A customer **mapping** `customer_duns` later writes **one** `mappings` row for
  **that** template only.
- Marking it **unused** writes/updates **one** `mappings` row for that template.
- Re-calling `POST /labra-fields` for `customer_duns` updates that one
  `labra_fields` row (label/required). Mapped CRM fields on existing templates
  are untouched.

**What I refuse to store:** the full default field list copied onto every
template row (the failure in the brief). That is exactly what forces a person —
or a one-off script — to open 10,000 rows and paste the new field in. The delta
schema removes the reason to ever do that.

**Single-list note (the brief asks for this):** the referral is validated by a
Pydantic model **built dynamically from `labra_fields`** (see
`model/referral_model.py` → `build_referral_model`). There is no second list of
field names that could drift. The only per-field knowledge kept in code is a
*rule registry* (`VALIDATORS`, keyed by field name) — it holds validation rules,
not the roster; a field in the list with no specific rule falls back to a generic
required/optional check, so the list and the model can never disagree about
*which* fields exist.

---

## 2. 10,000 existing templates, one new AWS field

**This design:** introducing the field is **one INSERT into `labra_fields`** —
sub-millisecond, independent of how many templates exist. `templates` and
`mappings` are **not touched**, so **nothing is locked** on the template/mapping
tables and no template read is blocked. 10,000 templates cost the same as 10.
There is no data migration to run.

**What the old copy-JSON design would cost:** an `UPDATE` across 10,000 rows (or
a script rewriting every JSON document), holding row/page locks, re-serializing
every document, and risking a partial run that leaves some templates with the
field and some without — the exact split the brief describes. **I would refuse to
hand-edit, or script a rewrite of, 10,000 stored templates.** The cost of my
schema is paid instead at **read time**: each `GET`/prepare does a small join
(≤ a few dozen fields × the template's mappings). That is cheap, indexed by
primary key, and bounded by the field-list size, not the template count.

---

## 3. Several CRM objects

The fetch list is built from **the template the customer currently sees**, not
from any stored copy (`service/referral_service.py` → `build_referral`):

1. Load the merged view (field list ⨝ this template's mappings), so a
   newly-introduced field is included **only if the customer has mapped it**.
2. Drop **unused** and **unmapped** fields — they are never fetched.
3. Group the remaining fields by `crm_object` into **one fetch per object**.
   Northwind → 3 calls (`Account`, `Opportunity`, `Contact`), not 6. Contoso →
   3 calls (`companies`, `deals`, `contacts`). Asserted by `crm.calls`.

**When the same object backs ten fields:** it is still **one** fetch for that
object, requesting the union of the ten CRM fields in a single call. Grouping is
by object, so adding more fields to an object adds field names to one request,
never new requests. This is the main lever that keeps us under CRM rate limits.

---

## 4. Rate limits at scale

**The math.** 200 prepares/min × 3 objects = **600 CRM requests/min**. The
portal allows 100 requests / 10 s = **600/min**. We sit **exactly at the ceiling
with zero headroom**, and real traffic is bursty — so without smoothing we will
exceed the limit constantly. Grouping (§3) already minimizes requests; beyond
that we need a limiter.

**Where a shared limiter lives.** If several API processes handle prepares, an
in-process limiter is wrong — each process would permit its own 100/10 s.
The limiter must be **shared out of process**: a token bucket in **Redis**
(or DynamoDB with conditional writes), wrapping the single CRM call. Every
`crm.fetch` would first acquire a token from the shared bucket.

**How to key it.** Key by the throttled scope, which is **the CRM portal /
tenant**, not the Labra template — e.g. `ratelimit:{crm_type}:{portal_id}`,
refilling at 100 tokens / 10 s per portal. Salesforce and HubSpot limits are
per-connected-org, so a per-portal key matches where the real limit is enforced
and isolates one busy customer from everyone else.

**A prepare that cannot get a slot within a few seconds.** Fail fast rather than
pile up: return `503`/`429` with a `Retry-After`, so the caller retries later (or
the work is handed to a queue — §5). Blocking a request thread for minutes waiting
for a token is worse than a clear "try again".

**The single retry I implemented.** `service/referral_service.py` →
`_fetch_with_retry` wraps **`FakeCrm.fetch`**: on `RateLimited` it waits the
advised `retry_after_ms` and retries that object **once**. A second failure ends
the request with a rate-limit error that **names the object** and does **not**
report that object's fields as missing (`test_rate_limit_twice_names_object_only`,
and the invalid-seed rules). At scale, this same `_fetch_with_retry` seam is where
the shared-limiter `acquire()` call would wrap the fetch.

---

## 5. One thing left out — short-lived cache of CRM records

I would add a **short-lived (e.g. 30–60 s) cache of CRM records**, keyed by
`(crm_object, record_id)`, **attached at `_fetch_with_retry`** — check the cache
before calling the CRM, populate it on success. It attaches at the exact seam the
retry and the future limiter use, so all three compose in one place.

Why it helps here: a single prepare already groups fields per object, but when
many prepares reference the same hot records (a big opportunity being re-prepared,
retries after validation fixes), the cache collapses repeated object fetches and
buys real headroom against the 600/min ceiling in §4. I left it out because it
adds a freshness/invalidation trade-off (a stale CRM value shown on a referral)
that deserves its own decision, and the brief's correctness requirements don't
need it — but it is the first thing I'd add for scale.

---

## Test map (what proves each behavior)

| Behavior | Test |
|----------|------|
| Create Northwind + GET six fields | `test_create_and_get_northwind` |
| New field on old template, no second write | `test_new_field_appears_on_old_template` |
| Re-introduce updates label, keeps mappings | `test_reintroduce_updates_label_keeps_mappings` |
| Unused persists through label change | `test_mark_unused_persists_through_label_change` |
| Required field cannot be unused | `test_cannot_mark_required_field_unused` |
| Valid referral + one call per object | `test_valid_referral_and_one_call_per_object` |
| Hidden key not fetched/returned | `test_hidden_key_not_fetched_or_returned` |
| `"5000"` coerced to number | `test_numeric_string_revenue_coerced` |
| Single retry succeeds | `test_single_retry_succeeds` |
| Rate-limited twice → names object only | `test_rate_limit_twice_names_object_only` |
| Six validation errors | `test_invalid_seed_six_errors` |
| Unused field not fetched | `test_unused_field_not_fetched` |
| Unknown template / record → not found | `test_unknown_*` |
| HubSpot (Contoso) grouping | `test_contoso_hubspot` |
| All create reject rules | `test_reject_*`, `test_nothing_stored_on_reject` |
