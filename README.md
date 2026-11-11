# Labra referral mapping service

A small FastAPI service that turns a CRM deal (Salesforce or HubSpot) into an
AWS **referral**, using a per-customer **mapping template**. The design goal:
when Labra/AWS introduce a new referral field, every template saved earlier
shows it **with no row rewrite and no hand-editing** — because the shared field
list is stored once and merged with each template's mappings at read time.

- Python 3.11+ · FastAPI · Pydantic v2 · SQLite
- No network, no real CRM — a `FakeCrm` is injected via `create_app(crm)`.

---

## 1. Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Create the database.** No separate step is needed — the schema is created and
seeded on first boot. To create it explicitly:

```bash
python -c "from labra.db import connect, init_db; from labra.seed import seed_fields; \
c = connect('labra.db'); init_db(c); seed_fields(c); print('db ready: labra.db')"
```

## 2. Run the API

```bash
uvicorn labra.main:app --reload
# http://127.0.0.1:8000  ·  docs at /docs
```

`labra.main` wires a `FakeCrm` pre-seeded with Northwind's `opp-100` record so
the walkthrough below works end to end (there is no real CRM in this exercise).

## 3. Run the tests

```bash
pytest
```

---

## 4. Schema

Three tables carry the whole design. The shared field list lives in **one**
place; each template stores **only the customer's own mappings** (their deltas).

```sql
CREATE TABLE labra_fields (          -- the shared list Labra + AWS own
    labra_field  TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    required     INTEGER NOT NULL DEFAULT 0,   -- 0/1
    sort_order   INTEGER NOT NULL
);

CREATE TABLE templates (             -- one row per customer template
    template_id  TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    crm_type     TEXT NOT NULL                 -- 'salesforce' | 'hubspot'
);

CREATE TABLE mappings (              -- ONLY the customer's choices (deltas)
    template_id  TEXT NOT NULL,
    labra_field  TEXT NOT NULL,
    crm_object   TEXT,                         -- null when unmapped/unused
    crm_field    TEXT,
    unused       INTEGER NOT NULL DEFAULT 0,   -- 0/1
    PRIMARY KEY (template_id, labra_field),
    FOREIGN KEY (template_id) REFERENCES templates(template_id) ON DELETE CASCADE,
    FOREIGN KEY (labra_field) REFERENCES labra_fields(labra_field) ON DELETE CASCADE
);
```

`GET /mapping-templates/{id}` is a join of `labra_fields` (every current field)
with that template's `mappings`. A field added to `labra_fields` after a
template was saved therefore shows up on the next GET as unmapped, with zero
writes to `templates` or `mappings`. See `NOTES.md` for the cost at 10,000
templates.

---

## 5. API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/mapping-templates` | Create a template (rejects + stores nothing on bad input) |
| `GET`  | `/mapping-templates/{template_id}` | Merged view: every current Labra field |
| `POST` | `/labra-fields` | Introduce a new field, or update an existing one |
| `PATCH`| `/mapping-templates/{template_id}/fields/{labra_field}` | Mark an optional field used/unused |
| `POST` | `/mapping-templates/{template_id}/crm-field-values` | Fetch CRM, build + validate the referral |

### Create a template

```json
POST /mapping-templates
{
  "template_id": "northwind-default",
  "name": "Northwind Default",
  "crm_type": "salesforce",
  "mappings": [
    {"labra_field": "company_name", "crm_object": "Account", "crm_field": "Name"},
    {"labra_field": "website", "crm_object": "Account", "crm_field": "Website"},
    {"labra_field": "country", "crm_object": "Account", "crm_field": "BillingCountry"},
    {"labra_field": "expected_monthly_revenue", "crm_object": "Opportunity", "crm_field": "Amount"},
    {"labra_field": "target_close_date", "crm_object": "Opportunity", "crm_field": "CloseDate"},
    {"labra_field": "primary_sales_rep_email", "crm_object": "Contact", "crm_field": "Email"}
  ]
}
```
`template_id` is optional; if omitted it is slugged from `name`.

### Introduce a field

```json
POST /labra-fields
{"labra_field": "customer_duns", "label": "Customer DUNS", "required": false}
```
Calling again with the same `labra_field` updates its label/required. Existing
mappings are untouched.

### Mark a field unused

```json
PATCH /mapping-templates/northwind-default/fields/customer_duns
{"unused": true}
```
Marking a **required** field unused is rejected (422) — AWS requires it.

### Fetch CRM values and build the referral

```json
POST /mapping-templates/northwind-default/crm-field-values
{"record_id": "opp-100"}
```
Success → `{"referral": {...}, "errors": []}`.
Invalid CRM data → `422` with `{"referral": null, "errors": [...]}`, one entry
per bad field naming the Labra field, CRM object+field, the value received, what
is wrong, and the fix.

---

## 6. End-to-end walkthrough (with the server running)

```bash
# 1. Create Northwind
curl -s -X POST localhost:8000/mapping-templates -H 'content-type: application/json' \
  -d '{"template_id":"northwind-default","name":"Northwind Default","crm_type":"salesforce",
       "mappings":[
         {"labra_field":"company_name","crm_object":"Account","crm_field":"Name"},
         {"labra_field":"website","crm_object":"Account","crm_field":"Website"},
         {"labra_field":"country","crm_object":"Account","crm_field":"BillingCountry"},
         {"labra_field":"expected_monthly_revenue","crm_object":"Opportunity","crm_field":"Amount"},
         {"labra_field":"target_close_date","crm_object":"Opportunity","crm_field":"CloseDate"},
         {"labra_field":"primary_sales_rep_email","crm_object":"Contact","crm_field":"Email"}]}'

# 2. Introduce customer_duns (one write to the shared list)
curl -s -X POST localhost:8000/labra-fields -H 'content-type: application/json' \
  -d '{"labra_field":"customer_duns","label":"Customer DUNS","required":false}'

# 3. GET the template saved BEFORE step 2 — customer_duns is now there, unmapped,
#    and company_name is still Account.Name. No second write happened.
curl -s localhost:8000/mapping-templates/northwind-default

# 4. Build the referral for opp-100
curl -s -X POST localhost:8000/mapping-templates/northwind-default/crm-field-values \
  -H 'content-type: application/json' -d '{"record_id":"opp-100"}'
```

---

## 7. Layout

```
labra/
  app.py            create_app(crm) — the injection seam
  db.py             SQLite connection + schema
  seed.py           seeds the six base fields
  clock.py          today_utc() (freezable in tests)
  crm.py            FakeCrm, RateLimited, CrmRecordNotFound
  main.py           runnable demo server (seeded FakeCrm)
  queries/          raw SQL, one module per concern
  model/            Pydantic request/response + dynamic referral model + error object
  service/          business logic (template / field / referral)
  routes/           FastAPI routers
tests/              pytest; no network
```
