# Typesafe AI Request Patterns

Copyable, flat, sequential Python patterns for calling the Typesafe AI (Jev / System One) HTTP API
from DAAF scripts. Schema authority is `./api-reference.md`; design guidance is
`./design-patterns.md`.

**These are copyable inline patterns, not an importable module.** Paste the relevant sections into
a script under `{PROJECT_DIR}/scripts/`, adapt the config, and execute via:

```
bash /daaf/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/.../script.py
```

**Constraints every pattern below obeys:**
- No function definitions — flat top-to-bottom scripts with `# --- Section ---` separators
  (CLAUDE.md § Code Style).
- IAT comments (`# INTENT:`, `# REASONING:`, `# ASSUMES:`) on every non-obvious decision.
- Inline validation with `assert` + `print`, never a separate test file.
- **The key is read once via `os.environ["TYPESAFE_API_KEY"]` and placed only in the
  `Authorization` header.** It is never printed, never written to a file, never included in a
  comment, and never inlined into a shell command. The execution log appended by
  `run_with_capture.sh` is a permanent audit artifact — anything printed is printed forever.
- `requests` 2.32.5 is installed; `httpx` 0.28.1 is available. `typesafe_sdk` is **not** installed
  and must not be installed.
- **Every call costs money** (per input token). Confirm with the user before running anything
  beyond a single smoke test, and always before a loop over rows.

> **Validation tolerances here reflect observed behaviour, not the docs.** Jev rounds
> probabilities to 2 decimal places, so these patterns assert a sum tolerance of ~0.02 rather than
> float precision, and they do **not** assert that `choice` equals the argmax (it disagrees on
> ~0.04-0.16% of rows). They also read `x-typesafe-request-id` with `.get()` because it is absent
> on at least some error responses. Full evidence and sample sizes: `./api-reference.md` § 14.

---

## A. One question of each type

Three separate minimal requests, one per primitive. In real use you would send all three in one
call (see § B) — they are split here so each response shape is visible on its own.

```python
# --- Config ---
import os
import json
import requests

# INTENT: Read the key from the environment; it exists only in memory and in the header.
# REASONING: Printing or persisting an API key into the appended execution log is an
#   irreversible credential leak into the audit trail.
# ASSUMES: TYPESAFE_API_KEY was injected into the container from host environment_settings.txt.
API_KEY = os.environ["TYPESAFE_API_KEY"]
ENDPOINT = "https://api.typesafe.ai/v1/systemone"

# INTENT: Pin the model version rather than using the `jev-latest` alias.
# REASONING: An alias moves when a release ships, so answers can change with no code change;
#   pinning keeps results reproducible. The response's `model` field resolves aliases to a
#   concrete version (confirmed live 2026-09-18), so persist it either way.
# ASSUMES: jev-1.13.0 is accepted by the account (versioned IDs are accepted whether or not
#   they appear in GET /v1/models, which lists only jev-latest and jev-preview).
MODEL = "jev-1.13.0"

# INTENT: Tolerate 2 dp probability rounding when validating distributions.
# REASONING: Jev returns probabilities on a 0.01 grid, so a well-formed distribution sums to
#   0.99-1.01, not to 1 within float epsilon. A 1e-6 assert fails in normal operation.
#   Worst-case sum error is 0.005 * n_options; scale the bound for wide option sets.
# ASSUMES: Option/level counts here are small (<= 8); see api-reference.md § 14.1.
PROB_SUM_TOL = 0.02

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",  # the only place the key appears
    "Content-Type": "application/json",
}

STATE = "My flight was cancelled last night and nobody has answered my three emails. Can I get a refund?"

# --- Transform: noul (probability a yes/no statement is true) ---
# INTENT: Phrase the instruction so that a HIGH probability means "yes".
# REASONING: Ambiguous polarity makes the returned number uninterpretable; the docs advise
#   phrasing such that a value near 1 unambiguously means yes.
# ASSUMES: `criteria` is optional for noul; it is supplied here because the yes/no boundary
#   (an explicit request vs. a mere complaint) is subtle.
noul_payload = {
    "state": STATE,
    "model": MODEL,
    "questions": {
        "refund_requested": {
            "type": "noul",
            "instructions": "Does the customer explicitly request a refund?",
            "criteria": {
                "true": "The message asks for money back, in any wording.",
                "false": "The message complains or asks a question but does not ask for money back.",
            },
        }
    },
}
r = requests.post(ENDPOINT, headers=HEADERS, json=noul_payload, timeout=30)
assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:500]}"
noul_result = r.json()

# --- Transform: choice (pick one of a fixed option set) ---
# INTENT: Include an `other` escape-hatch option.
# REASONING: Without one, an out-of-scope input is forced into a wrong category and the
#   probability distribution hides the miss.
# ASSUMES: Option descriptions, not just option names, are sent to the model — so they must
#   separate the options from one another.
choice_payload = {
    "state": STATE,
    "model": MODEL,
    "questions": {
        "department": {
            "type": "choice",
            "instructions": "Which team should handle this message?",
            "criteria": {
                "refunds": "Requests for money back, cancellations, billing adjustments.",
                "rebooking": "Requests for a replacement flight or schedule change.",
                "complaints": "Dissatisfaction with service quality with no specific remedy requested.",
                "other": "None of the above categories fit.",
            },
        }
    },
}
r = requests.post(ENDPOINT, headers=HEADERS, json=choice_payload, timeout=30)
assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:500]}"
choice_result = r.json()

# --- Transform: score (position along ordered levels) ---
# INTENT: Order criteria low -> high, 2 to 10 levels, each level described concretely.
# REASONING: `score` is a probability-weighted position along the array index, so ordering is
#   load-bearing; the response keys probabilities by level index as STRINGS ("0", "1", ...).
# ASSUMES: The HTTP wire format takes an ordered ARRAY (the integer-keyed-dict form was a
#   pre-v0.6.0 SDK shape and is not the wire format).
score_payload = {
    "state": STATE,
    "model": MODEL,
    "questions": {
        "frustration": {
            "type": "score",
            "instructions": "How frustrated does the customer appear?",
            "criteria": [
                "Calm and neutral; simply stating facts.",
                "Concerned but civil.",
                "Clearly irritated; pointed language.",
                "Very angry; strong or hostile language.",
            ],
        }
    },
}
r = requests.post(ENDPOINT, headers=HEADERS, json=score_payload, timeout=30)
assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:500]}"
score_result = r.json()

# --- Validate ---
# INTENT: Assert the type-specific shape of each answer before reading fields.
# REASONING: noul answers carry NO `confidence` key; unconditional access would KeyError.
#   A 200 can still carry a structurally invalid body, so shape is checked, not assumed.
n = noul_result["answers"]["refund_requested"]
assert n["type"] == "noul"
assert 0.0 <= n["noul"] <= 1.0
assert "confidence" not in n, "noul unexpectedly returned a confidence field — schema drift"

c = choice_result["answers"]["department"]
assert c["type"] == "choice"
assert c["choice"] in choice_payload["questions"]["department"]["criteria"]
assert abs(sum(c["probabilities"].values()) - 1.0) <= PROB_SUM_TOL

s = score_result["answers"]["frustration"]
assert s["type"] == "score"
assert abs(sum(s["probabilities"].values()) - 1.0) <= PROB_SUM_TOL
assert 0.0 <= s["score"] <= len(score_payload["questions"]["frustration"]["criteria"]) - 1

# --- Validate (report) ---
print("noul   refund_requested:", n["noul"])
print("choice department      :", c["choice"], "| confidence:", c["confidence"])
print("       probabilities   :", json.dumps(c["probabilities"]))
print("score  frustration     :", s["score"], "| confidence:", s["confidence"])
print("       legend          :", json.dumps(s["legend"]))
# INTENT: Record the model version that actually answered, and token usage, for provenance.
# REASONING: Even with a pinned request, the response's `model` field is the authoritative
#   record of what produced the numbers. Billing is on input_tokens only.
for label, res in [("noul", noul_result), ("choice", choice_result), ("score", score_result)]:
    print(f"{label}: answered by {res['model']} | usage {res['usage']}")
```

---

## B. Batching many questions in one call

This is the **default** way to call the API, not an optimization. All questions in a request see
the same state, are evaluated independently and in parallel, and share one state's token cost.
Include speculative questions whose answers only matter for some inputs and let code ignore them.

```python
# --- Config ---
import os
import json
import requests

API_KEY = os.environ["TYPESAFE_API_KEY"]
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# --- Transform ---
# INTENT: Structure the state as an object so each question can name the part it judges.
# REASONING: Named parts let instructions reference `ticket.body` etc. with backticked paths,
#   which the model uses to locate the relevant material; a flat string cannot be referenced.
# ASSUMES: Only fields the questions actually need are included — irrelevant material both
#   costs input tokens and measurably degrades accuracy ("context rot").
state = {
    "ticket": {
        "subject": "App crashes on export",
        "body": "Every time I hit Export to PDF the app closes. Happens on every report. "
                "Steps: open report, click Export, choose PDF, crash. Third time this week.",
    },
    "account": {"plan": "enterprise", "tenure_months": 41},
}

# INTENT: Ask every question the downstream decision tree could need, in one call.
# REASONING: Questions run in parallel, so extra questions add negligible latency and only the
#   marginal question tokens in cost; a second round trip would re-bill the whole state.
# ASSUMES: Question ids are chosen by us and are NOT sent to the model, so each `instructions`
#   restates the full question even when the id looks self-explanatory.
questions = {
    "category": {
        "type": "choice",
        "instructions": "What kind of request is `ticket.body`?",
        "criteria": {
            "bug_report": "Reports software behaving incorrectly.",
            "feature_request": "Asks for functionality that does not exist.",
            "billing": "Concerns charges, invoices, or the subscription.",
            "other": "None of the above.",
        },
    },
    # Speculative: only meaningful when category == bug_report.
    "bug_severity": {
        "type": "score",
        "instructions": "How severe is the problem described in `ticket.body`?",
        "criteria": [
            "Cosmetic; no impact to functionality.",
            "Degraded feature, but a workaround exists.",
            "Blocking; no workaround exists.",
        ],
    },
    "has_reproducible_steps": {
        "type": "noul",
        "instructions": "Does `ticket.body` contain steps that would let an engineer reproduce the problem?",
    },
    # Speculative: only meaningful when category == billing.
    "refund_requested": {
        "type": "noul",
        "instructions": "Does `ticket.body` request a refund?",
    },
    "frustration": {
        "type": "score",
        "instructions": "How frustrated does the writer of `ticket.body` appear?",
        "criteria": ["Calm.", "Mildly annoyed.", "Clearly frustrated.", "Very angry."],
    },
}

payload = {"state": state, "model": MODEL, "questions": questions}
response = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=60)

# --- Validate ---
assert response.status_code == 200, f"HTTP {response.status_code}: {response.text[:500]}"
result = response.json()
# INTENT: Assert every requested id came back before reading any of them.
# REASONING: Silent omission of one answer would otherwise surface as a confusing KeyError
#   much later, in routing logic rather than at the API boundary.
missing = set(questions) - set(result["answers"])
assert not missing, f"missing answers for: {sorted(missing)}"

# --- Validate (report) ---
answers = result["answers"]
# INTENT: All routing logic lives in code, keyed off typed answers and thresholds.
# REASONING: The model supplies judgments; control flow stays deterministic and reviewable.
# ASSUMES: Thresholds below are illustrative placeholders — calibrate them on real data.
category = answers["category"]
if category["confidence"] < 0.5:
    print("ROUTE: human triage (category confidence too low)")
elif category["choice"] == "bug_report":
    if answers["bug_severity"]["score"] > 1.5 and answers["has_reproducible_steps"]["noul"] > 0.6:
        print("ROUTE: engineering escalation")
    else:
        print("ROUTE: bug backlog")
elif category["choice"] == "billing":
    print("ROUTE: billing | refund likely:", answers["refund_requested"]["noul"] > 0.7)
else:
    print("ROUTE:", category["choice"])

if answers["frustration"]["score"] > 2.0:
    print("FLAG: priority response (frustration high regardless of category)")

print("answered by:", result["model"], "| usage:", result["usage"])
```

---

## C. Evaluating many Polars rows and writing answers back to parquet

One request per row, same question set each time. **This is the expensive pattern** — cost scales
linearly with row count, so confirm the row count and a per-row token estimate with the user
before running it. Run it against a small `head()` slice first.

**If you parallelize this loop, size the worker count by tokens per second, not calls per
second.** 429s are token-rate driven: at ~16 concurrent workers, ~1,000-token prompts produced
zero 429s over 28,267 calls while ~3,000-token prompts produced 1,288 over 31,307 calls
(`./api-reference.md` § 14.4). Doubling prompt size means roughly halving workers. The loop below
is serial; the retry block is what makes a parallel version survivable, and the `retry_count`
column is what makes the throttling auditable afterwards.

```python
# --- Config ---
import os
import time
import json
import requests
import polars as pl

API_KEY = os.environ["TYPESAFE_API_KEY"]
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"  # pinned: results are persisted, so reproducibility requires a version pin
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

IN_PATH = "{PROJECT_DIR}/data/processed/tickets.parquet"
OUT_PATH = "{PROJECT_DIR}/data/processed/tickets_judged.parquet"

# INTENT: Cap the run size explicitly rather than defaulting to the whole file.
# REASONING: Each row is a paid API call; an accidental full-file run is an unrecoverable spend.
# ASSUMES: The user has approved this row count. Set to None only after a small run succeeds.
MAX_ROWS = 25

# --- Load ---
df = pl.read_parquet(IN_PATH)
print("rows available:", df.height)
if MAX_ROWS is not None:
    df = df.head(MAX_ROWS)
print("rows to evaluate:", df.height)
assert "ticket_id" in df.columns and "body" in df.columns, "expected ticket_id and body columns"

# --- Transform ---
# INTENT: Define the question set once, outside the loop.
# REASONING: Identical questions across rows keep the answers comparable; a per-row variation
#   in wording would make the resulting score/probability columns non-comparable.
questions = {
    "category": {
        "type": "choice",
        "instructions": "What kind of request is this message?",
        "criteria": {
            "bug_report": "Reports software behaving incorrectly.",
            "feature_request": "Asks for functionality that does not exist.",
            "billing": "Concerns charges, invoices, or the subscription.",
            "other": "None of the above.",
        },
    },
    "frustration": {
        "type": "score",
        "instructions": "How frustrated does the writer appear?",
        "criteria": ["Calm.", "Mildly annoyed.", "Clearly frustrated.", "Very angry."],
    },
    "refund_requested": {
        "type": "noul",
        "instructions": "Does the writer request a refund?",
    },
}

records = []
# INTENT: Iterate rows in code, one request each, accumulating flat records.
# REASONING: The API evaluates one state per request; batching is across QUESTIONS, not rows.
# ASSUMES: `body` is plain text small enough to sit well under the 32k-token state budget.
for row in df.iter_rows(named=True):
    payload = {"state": row["body"], "model": MODEL, "questions": questions}

    # INTENT: Retry transient failures with exponential backoff, honoring retry-after.
    # REASONING: 429/529 are expected under sustained looping; immediate retry makes it worse.
    # ASSUMES: Non-retryable statuses (401/422) should fail the whole run loudly and at once,
    #   because they indicate a config or schema bug that every remaining row would repeat.
    delay = 1.0
    response = None
    attempt = 0
    for attempt in range(6):
        response = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=60)
        if response.status_code == 200:
            break
        # INTENT: Read the request-id header defensively; it may be absent.
        # REASONING: A 503 was observed carrying NO x-typesafe-request-id header, so bracket
        #   access here would raise a KeyError that masks the real failure. `.get()` yields None.
        request_id = response.headers.get("x-typesafe-request-id")
        if response.status_code not in (429, 500, 502, 503, 504, 529):
            raise RuntimeError(
                f"non-retryable HTTP {response.status_code} on ticket_id={row['ticket_id']}: "
                f"{response.text[:500]} | request_id={request_id}"
            )
        # INTENT: Honor both retry-after headers, preferring the millisecond-precision one.
        # REASONING: The server sends either `retry-after-ms` or `Retry-After`; reading only one
        #   silently falls back to the local schedule when the other is present. See § D for the
        #   full policy including jitter and a retry budget.
        # ASSUMES: Both are numeric strings here; an HTTP-date `Retry-After` would fail float()
        #   and is caught so the local backoff still applies.
        wait = delay
        for header, divisor in (("retry-after-ms", 1000.0), ("Retry-After", 1.0)):
            raw = response.headers.get(header)
            if raw:
                try:
                    wait = float(raw) / divisor
                    break
                except ValueError:
                    pass
        print(f"  HTTP {response.status_code}, attempt {attempt + 1}, sleeping {wait:.1f}s")
        time.sleep(wait)
        delay = min(delay * 2, 30.0)

    assert response is not None and response.status_code == 200, (
        f"exhausted retries on ticket_id={row['ticket_id']} "
        f"(last status {response.status_code if response else 'none'})"
    )
    result = response.json()
    a = result["answers"]

    # INTENT: Persist the answering model version and token usage on every row.
    # REASONING: Provenance — a result is only reproducible if the exact model that produced it
    #   is recorded. Alias drift would otherwise be invisible in the output file.
    # INTENT: Persist a per-row retry flag alongside the answers.
    # REASONING: Backoff silently absorbs 429s, so without this column a reviewer cannot test
    #   whether throttled rows differ in outcome from clean ones. Observed: 1,288 absorbed 429s
    #   in one 31,307-call run were entirely unrecoverable from the output for this reason.
    # ASSUMES: `attempt` is the zero-based loop index at which the 200 arrived.
    records.append({
        "ticket_id": row["ticket_id"],
        "retry_count": attempt,
        "category": a["category"]["choice"],
        # INTENT: Persist the code-computed argmax next to the vendor's `choice`.
        # REASONING: They disagree on ~0.04-0.16% of rows (2 dp near-ties collapse the ordering
        #   the vendor tie-broke on unrounded values). Recording both makes the downstream
        #   decision of which to treat as THE prediction explicit and auditable.
        # ASSUMES: The analysis documents which of the two columns it uses.
        "category_argmax": max(
            a["category"]["probabilities"], key=a["category"]["probabilities"].get
        ),
        "category_confidence": a["category"]["confidence"],
        # INTENT: Store the full distribution as a JSON string, not just the winner.
        # REASONING: `confidence` is one summary of the distribution; keeping the raw
        #   probabilities lets a later analysis apply a different uncertainty measure.
        "category_probabilities": json.dumps(a["category"]["probabilities"]),
        "frustration_score": a["frustration"]["score"],
        "frustration_confidence": a["frustration"]["confidence"],
        "refund_requested_p": a["refund_requested"]["noul"],  # noul has no confidence field
        "answered_by_model": result["model"],
        "input_tokens": result["usage"]["input_tokens"],
        "output_tokens": result["usage"]["output_tokens"],
    })

judged = pl.DataFrame(records)

# --- Validate ---
assert judged.height == df.height, f"row count changed: {df.height} in, {judged.height} out"
assert judged["ticket_id"].n_unique() == judged.height, "duplicate ticket_id in output"
assert judged["refund_requested_p"].is_between(0.0, 1.0).all(), "noul outside [0, 1]"
assert judged["frustration_score"].is_between(0.0, 3.0).all(), "score outside level range"
assert judged["answered_by_model"].n_unique() == 1, (
    f"mixed model versions in one run: {judged['answered_by_model'].unique().to_list()}"
)
assert judged.null_count().sum_horizontal().item() == 0, "unexpected nulls in answers"

# --- Save ---
out = df.join(judged, on="ticket_id", how="left")
out.write_parquet(OUT_PATH)
print("wrote:", OUT_PATH, "| shape:", out.shape)
print("model:", judged["answered_by_model"][0])
print("total input tokens (billed):", judged["input_tokens"].sum())
print("total output tokens (free) :", judged["output_tokens"].sum())
```

---

## D. Exponential backoff on 429 / 529 honoring `retry-after`

Standalone version of the retry block, for reuse in any script. DAAF calls the HTTP API directly,
so backoff is **your** responsibility — the vendor's automatic retry lives in the SDK, which is
not installed here.

```python
# --- Config ---
import os
import time
import random
import requests

API_KEY = os.environ["TYPESAFE_API_KEY"]
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# INTENT: Retry the transient statuses only.
# REASONING: /api documents 429 and 529 as "retry with exponential backoff"; 5xx transport
#   errors are conventionally retryable too, and a 503 WAS observed live (undocumented, one in
#   16,296 calls, succeeded on retry). 401 (bad key) and 422 (bad body) are deterministic
#   — retrying them burns time and money to get the identical failure.
# ASSUMES: The vendor SDK's own example policy omits 529, but the HTTP-API page explicitly
#   instructs retrying it, so 529 is included here.
RETRYABLE = {429, 500, 502, 503, 504, 529}
MAX_ATTEMPTS = 6
BACKOFF_INITIAL = 1.0
BACKOFF_MAX = 30.0
JITTER_FRACTION = 0.2

payload = {
    "state": "placeholder state",
    "model": "jev-1.13.0",
    "questions": {"q": {"type": "noul", "instructions": "Is this a placeholder?"}},
}

# --- Transform ---
delay = BACKOFF_INITIAL
response = None
for attempt in range(1, MAX_ATTEMPTS + 1):
    response = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=60)
    if response.status_code == 200:
        break

    # INTENT: Read the request-id defensively — it is not guaranteed on error responses.
    # REASONING: Observed absent on a 503. `.get()` yields None rather than raising inside the
    #   error path, where a KeyError would mask the failure being reported.
    request_id = response.headers.get("x-typesafe-request-id")
    if response.status_code not in RETRYABLE:
        # INTENT: Log the server's error body and the request id, never the request headers.
        # REASONING: The body names the offending field on a 422 and is safe to print; the
        #   request headers carry the bearer token and must never reach the execution log.
        raise RuntimeError(
            f"non-retryable HTTP {response.status_code}: {response.text[:800]} "
            f"| x-typesafe-request-id={request_id}"
        )

    # INTENT: Prefer the server's own Retry-After over the local backoff schedule.
    # REASONING: The server knows when the limit resets; guessing shorter just re-trips it.
    # ASSUMES: Retry-After here is delta-seconds (the docs also mention a retry-after-ms
    #   variant); an HTTP-date form would fail float() and fall through to local backoff.
    wait = delay
    retry_after_ms = response.headers.get("retry-after-ms")
    retry_after = response.headers.get("Retry-After")
    if retry_after_ms:
        try:
            wait = float(retry_after_ms) / 1000.0
        except ValueError:
            pass
    elif retry_after:
        try:
            wait = float(retry_after)
        except ValueError:
            pass

    # INTENT: Subtract random jitter from the wait.
    # REASONING: Without jitter, parallel callers re-collide on the same schedule after a 429.
    wait = wait * (1.0 - random.uniform(0.0, JITTER_FRACTION))
    print(f"attempt {attempt}/{MAX_ATTEMPTS}: HTTP {response.status_code} "
          f"(request_id={request_id}); sleeping {wait:.2f}s")
    time.sleep(wait)
    delay = min(delay * 2, BACKOFF_MAX)

# --- Validate ---
assert response is not None and response.status_code == 200, (
    f"exhausted {MAX_ATTEMPTS} attempts; last status "
    f"{response.status_code if response else 'none'}"
)

# --- Validate (report) ---
print("succeeded on attempt", attempt)
print("usage:", response.json()["usage"])
```

---

## E. Listing models and pinning a version

```python
# --- Config ---
import os
import json
import requests

API_KEY = os.environ["TYPESAFE_API_KEY"]
MODELS_ENDPOINT = "https://api.typesafe.ai/v1/models"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# --- Load ---
# INTENT: Ask the account which model names it may send, before pinning one.
# REASONING: GET /v1/models lists the ALIASES available to the account; versioned IDs are
#   accepted whether or not they appear in the list, so this is a discovery aid rather than
#   an allow-list to validate against.
response = requests.get(MODELS_ENDPOINT, headers=HEADERS, timeout=30)
assert response.status_code == 200, f"HTTP {response.status_code}: {response.text[:500]}"
body = response.json()

# --- Validate ---
# INTENT: Tolerate either a {"models": [...]} envelope or a bare list.
# REASONING: The envelope was confirmed live 2026-09-18 — GET /v1/models returned
#   {"models": [...]} listing jev-latest and jev-preview. The bare-list fallback is kept as
#   cheap insurance against a future schema change, not because the shape is in doubt.
# ASSUMES: Each entry carries name / description / release_date, per the ModelCard interface.
# NOTE: A 200 here is NOT proof the key is valid — validate auth with an authenticated
#   evaluation call whose body you parse (see api-reference.md § 14.6).
models = body["models"] if isinstance(body, dict) and "models" in body else body
assert isinstance(models, list) and models, f"unexpected /v1/models body: {json.dumps(body)[:500]}"
for m in models:
    assert "name" in m, f"model entry missing name: {m}"

# --- Validate (report) ---
for m in models:
    print(f"{m['name']:<16} released {m.get('release_date', '?')}  {m.get('description', '')}")

# INTENT: Resolve the alias to a concrete version by making one cheap evaluation call and
#   reading the response's `model` field.
# REASONING: The response reports the versioned ID that actually answered — confirmed live
#   2026-09-18, when a "jev-latest" request came back as "jev-1.13.0". This doubles as the
#   only trustworthy auth pre-flight, because it is an AUTHENTICATED call with a parsed body.
# ASSUMES: This costs a small number of input tokens — keep the probe state tiny.
probe = requests.post(
    "https://api.typesafe.ai/v1/systemone",
    headers={**HEADERS, "Content-Type": "application/json"},
    json={
        "state": "ok",
        "model": "jev-latest",
        "questions": {"probe": {"type": "noul", "instructions": "Is this text short?"}},
    },
    timeout=30,
)
assert probe.status_code == 200, f"HTTP {probe.status_code}: {probe.text[:500]}"
resolved = probe.json()["model"]
print("jev-latest currently resolves to:", resolved)
print("pin this value in production scripts:", resolved)
print("probe usage:", probe.json()["usage"])
```

---

## F. Validating a response

Drop this after any call whose output will be persisted or acted on. It checks the invariants the
schema guarantees, so drift or a malformed-but-200 body fails at the API boundary rather than deep
in downstream logic.

```python
# --- Validate ---
# INTENT: Check structure before reading any field.
# REASONING: A 200 response can still carry a structurally invalid body — the vendor SDK has a
#   dedicated TypeSafeAPIResponseValidationError for exactly that case, with a field_path such
#   as "answers.tone.confidence". Asserting here localizes the failure.
# ASSUMES: `questions` is the dict that was sent in the request payload.
result = response.json()

for key in ("model", "answers", "usage"):
    assert key in result, f"response missing top-level '{key}': {list(result)}"

assert set(result["answers"]) == set(questions), (
    f"answer ids differ from question ids: "
    f"missing={sorted(set(questions) - set(result['answers']))}, "
    f"extra={sorted(set(result['answers']) - set(questions))}"
)

# INTENT: Accept int or float for token counts.
# REASONING: The HTTP docs type these as `integer` but the JS SDK's Usage interface types them
#   as `number`; JSON has one numeric type, so a float is a legal encoding of either.
assert isinstance(result["usage"].get("input_tokens"), (int, float))
assert isinstance(result["usage"].get("output_tokens"), (int, float))

for qid, question in questions.items():
    answer = result["answers"][qid]
    assert answer["type"] == question["type"], (
        f"{qid}: asked {question['type']}, got {answer['type']}"
    )

    if answer["type"] == "noul":
        # INTENT: noul carries only `noul`; assert the absence of `confidence`.
        # REASONING: A confidence field appearing on a noul would mean the schema changed, and
        #   silently tolerating it would let drift pass unnoticed.
        assert 0.0 <= answer["noul"] <= 1.0, f"{qid}: noul out of [0, 1]"
        assert "confidence" not in answer, f"{qid}: noul returned confidence — schema drift"

    elif answer["type"] == "choice":
        options = set(question["criteria"])
        assert answer["choice"] in options, f"{qid}: choice not among supplied options"
        probs = answer["probabilities"]
        assert set(probs) == options, f"{qid}: probability keys differ from options"
        # INTENT: Tolerate 2 dp rounding, scaled to the number of options.
        # REASONING: Jev rounds each probability to 0.01, so worst-case sum error is
        #   0.005 * n_options. A 1e-6 bound fails in normal operation; 0.02 held up to ~8
        #   options, and the max() keeps wider option sets correct too.
        tol = max(0.02, 0.5 * len(options) * 0.01)
        assert abs(sum(probs.values()) - 1.0) <= tol, f"{qid}: probabilities sum to {sum(probs.values())}"
        assert 0.0 <= answer["confidence"] <= 1.0, f"{qid}: confidence out of [0, 1]"
        # INTENT: REPORT, do not assert, when `choice` differs from the code-computed argmax.
        # REASONING: The docs define `choice` as the highest-probability option, but it
        #   disagrees on ~0.04-0.16% of rows — the vendor tie-breaks on unrounded values the
        #   response never exposes, so this is expected behaviour, not drift. Asserting here
        #   fails a long run for a known quirk; counting it keeps the quirk visible.
        # ASSUMES: The caller decides which field is THE prediction and persists both.
        if answer["choice"] != max(probs, key=probs.get):
            print(f"  NOTE {qid}: vendor choice {answer['choice']!r} != argmax "
                  f"{max(probs, key=probs.get)!r} (2 dp near-tie; confidence "
                  f"{answer['confidence']})")

    elif answer["type"] == "score":
        n_levels = len(question["criteria"])
        assert 2 <= n_levels <= 10, f"{qid}: score criteria must hold 2 to 10 levels"
        probs = answer["probabilities"]
        # INTENT: Expect STRING keys of level indices.
        # REASONING: The response keys score probabilities by level number as a string
        #   ("0", "1", ...), matching `legend`; integer keys would indicate drift.
        assert set(probs) == {str(i) for i in range(n_levels)}, (
            f"{qid}: probability keys {sorted(probs)} do not match level indices"
        )
        assert set(answer["legend"]) == set(probs), f"{qid}: legend keys differ from probability keys"
        # INTENT: Same 2 dp rounding tolerance as for choice, scaled to the level count.
        # REASONING: Score probabilities are rounded identically; see api-reference.md § 14.1.
        tol = max(0.02, 0.5 * n_levels * 0.01)
        assert abs(sum(probs.values()) - 1.0) <= tol, f"{qid}: probabilities sum to {sum(probs.values())}"
        assert 0.0 <= answer["score"] <= n_levels - 1, f"{qid}: score outside level range"
        assert 0.0 <= answer["confidence"] <= 1.0, f"{qid}: confidence out of [0, 1]"

    else:
        raise AssertionError(f"{qid}: unknown answer type {answer['type']!r} — schema drift")

print("response validated |", len(result["answers"]), "answers from", result["model"])
```

---

## G. One-off curl smoke test

`curl` 8.5.0 is present in the container. A single `curl` is acceptable for a one-off
connectivity/auth check; anything that produces analytic output belongs in a script executed via
`run_with_capture.sh` so the audit trail records it.

**The key is referenced as `$TYPESAFE_API_KEY` and never inlined.** An inlined key would land in
the shell history, the hook audit log, and the session transcript.

```bash
curl -sS -X POST https://api.typesafe.ai/v1/systemone \
  -H "Authorization: Bearer $TYPESAFE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"state":"Help! My payouts have been failing for 3 days.","model":"jev-1.13.0","questions":{"is_urgent":{"type":"noul","instructions":"Does this convey urgency?"}}}'
```

Expected **shape** of a healthy response — the structure is what to check; the specific
probability and token counts are illustrative and will differ on every call:

```json
{"model":"jev-1.13.0","answers":{"is_urgent":{"type":"noul","noul":0.92}},"usage":{"input_tokens":312,"output_tokens":48}}
```

Notes:
- Per DAAF's one-command-per-Bash-call rule, run this as a single command with no `&&`, `;`, or
  `||` chaining. Piping is permitted by that rule, but piping into `jq` here mainly costs
  readability on a one-line response — read the raw JSON instead.
- `-sS` keeps the progress meter quiet while still surfacing errors.
- A `401` means the env var is unset or wrong inside the container; check with
  `printenv | grep -c TYPESAFE_API_KEY` (which prints a **count**, not the value — never
  `echo $TYPESAFE_API_KEY`).
- This call costs money. Run it once.
