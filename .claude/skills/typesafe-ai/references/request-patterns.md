# Typesafe AI Request Patterns

Copyable, flat, sequential Python patterns for calling the Typesafe AI (Jev / System One) HTTP API
from DAAF scripts. Schema authority is `./api-reference.md`; design guidance is
`./design-patterns.md`.

## Contents

- A. One question of each type
- B. Batching many questions in one call
- C. Evaluating many Polars rows and writing answers back to parquet
- D. Exponential backoff on 429 / 529 honoring `retry-after`
- E. Listing models and pinning a version
- F. Validating a response
- G. One-off curl smoke test
- H. One image with a `box` and a `noul` (experimental)

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

> **Validation tolerances here reflect live-API behaviour, not just the docs.** Probabilities come
> back rounded (2 decimal places, observed on jev-1.13.0 and jev-1.14.0), so these patterns assert a
> sum tolerance scaled to the option count rather than float precision, and they do **not** assert
> that `choice` equals the argmax of the returned distribution (near-ties can collapse after
> rounding). They read `x-typesafe-request-id` with `.get()` because it can be absent on error
> responses, and they tolerate a `null` token count, which both vendor SDKs allow for. A pin does
> not fix the exact output, so the persisting patterns save the full response, the request
> payload, and the request time. Check each against your own responses: `./api-reference.md`
> § 8.5 and § 14 "Things to verify on your own calls".
>
> **Model pin.** The templates pin `jev-1.14.0`, DAAF's default for new work (`./api-reference.md`
> § 12). `jev-1.13.0` is also current and pinnable at the same price; keep it for a study already
> validated on it.

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
#   pinning keeps the model fixed. The response's `model` field reports the concrete version
#   that answered (observed on the live API, 2026-11-01), so persist it either way.
# ASSUMES: jev-1.14.0 is accepted by the account (versioned IDs are accepted although
#   GET /v1/models lists only aliases) — check the response `model` field.
MODEL = "jev-1.14.0"

# INTENT: Tolerate probability rounding when validating distributions.
# REASONING: Probabilities can come back rounded (e.g. to 2 dp), so a well-formed distribution
#   can sum to 0.99-1.01, not to 1 within float epsilon; a 1e-6 assert would fail in normal
#   operation. With 2 dp rounding the worst-case sum error is 0.005 * n_options.
# ASSUMES: 2 dp rounding and at most 4 options/levels in this pattern, so 0.02 covers the
#   worst case. Set this from your option count (see api-reference.md § 8.5) and check it
#   against the sums in your own responses.
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
# REASONING: Without an escape hatch, an out-of-scope input is forced into a wrong category and
#   the probability distribution hides the miss. A companion noul in the same request ("Does
#   the message fit any of these teams?"), with the choice read only when the noul is high, is
#   the other valid design; the vendor says it "usually works better" on Jev 1.14.
#   design-patterns.md § 3 says when to prefer each. Pick one and keep it fixed across a run.
# ASSUMES: Option names and descriptions are both sent to the model — so they must separate
#   the options from one another. Option order can sway the answer (jev-1.13 leans toward the
#   first option), so a pilot should check a reordered option set.
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
#   The schema accepts 1 to 10 levels; 2 to 10 is DAAF policy, because one level is not a scale.
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
MODEL = "jev-1.14.0"
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
# REASONING: Questions run in parallel, so extra questions usually have little effect on response
#   time and cost only their own question tokens; a second round trip would re-bill the state.
# ASSUMES: Question ids are chosen by us and are NOT sent to the model, so each `instructions`
#   restates the full question even when the id looks self-explanatory. The `other` option is
#   one valid escape hatch; a companion noul ("Does `ticket.body` fit any of these
#   categories?") is the other, which the vendor says usually works better on Jev 1.14.
#   design-patterns.md § 3 says when to prefer each.
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
second.** Rate limits have a token leg and a request leg, and long prompts can hit the token leg
at a concurrency that is fine for short ones (`./api-reference.md` § 10). Measure mean
`usage.input_tokens` on the `head()` slice first; doubling prompt size roughly halves the safe
worker count. The loop below is serial; the retry block is what makes a parallel version
survivable, and the `retry_count` column is what makes the throttling auditable afterwards (a
loop that tolerates non-200 final outcomes should also persist the final HTTP status per row).
Timeouts and dropped connections are retried within the same attempt budget as retryable
statuses. Every `body` is checked to be text before the first paid call. If a row still fails,
or a `200` body cannot be read into a record (not JSON, or an answer or field missing), the loop
writes the completed rows to a `_partial` parquet and then stops, so these failures do not
throw away the completed rows; an unreadable `200` was probably billed too, so its raw body goes
into the error message (the execution log keeps it). Once the loop finishes, the same file is written with every row
before the validation asserts run, so it also remains after a successful run.

```python
# --- Config ---
import os
import time
import json
from datetime import datetime, timezone
import requests
import polars as pl

API_KEY = os.environ["TYPESAFE_API_KEY"]
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.14.0"  # pinned: results are persisted, so the model version must be fixed
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

IN_PATH = "{PROJECT_DIR}/data/processed/tickets.parquet"
OUT_PATH = "{PROJECT_DIR}/data/processed/tickets_judged.parquet"
# INTENT: Name a separate file for the rows already paid for, saved before validation and
#   whenever a run stops early.
# REASONING: A distinct "_partial" name cannot be mistaken for the finished output, and a
#   rerun can skip the ticket_ids it holds instead of paying for them again. write_parquet
#   overwrites, so rename an existing partial file before rerunning.
PARTIAL_PATH = "{PROJECT_DIR}/data/processed/tickets_judged_partial.parquet"

# INTENT: Retry transient statuses and transport failures within one attempt budget.
# REASONING: 429/529 are expected under sustained looping; 408 is in the vendor SDK's default
#   retry set, and 503 occurs although it is not in the documented status table. A timeout, a
#   dropped connection, or a response cut off mid-body is a transport failure, not a request
#   fault. Other requests exceptions (InvalidJSONError for a NaN in the body, a malformed URL)
#   describe the request itself, so they are not caught and stop the run at once, like a 400.
# ASSUMES: Non-retryable statuses (400/401/413/415/422) mean a config or request bug that every
#   remaining row would repeat, so they stop the run rather than skip the row.
RETRYABLE = {408, 429, 500, 502, 503, 504, 529}
TRANSIENT_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)
MAX_ATTEMPTS = 6

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
# INTENT: Check every body is non-null text before any paid call.
# REASONING: A bad body found mid-loop would stop the run after earlier rows were paid for.
assert df["body"].dtype == pl.Utf8 and df["body"].null_count() == 0, "every body must be text"

# --- Transform ---
# INTENT: Define the question set once, outside the loop.
# REASONING: Identical questions across rows keep the answers comparable; a per-row variation
#   in wording would make the resulting score/probability columns non-comparable.
# ASSUMES: The `other` option is the chosen escape hatch for this run. A companion noul is the
#   other valid design (design-patterns.md § 3 says when to prefer each); whichever is chosen
#   stays fixed for the whole run.
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
# ASSUMES: `body` is plain text small enough to sit well under the 32k-token per-question
#   context (state plus any one question; 64k for state plus all questions).
for row in df.iter_rows(named=True):
    # INTENT: Send only text as the state.
    # REASONING: A null or numeric `body` would be sent as JSON null or a number and judged as
    #   if it were the message. A state built from numeric columns needs the non-finite-float
    #   cleanup shown after this pattern.
    # ASSUMES: Every row's `body` is a string; a non-string body stops the run at this row.
    assert isinstance(row["body"], str), f"ticket_id={row['ticket_id']}: body is not text"
    payload = {"state": row["body"], "model": MODEL, "questions": questions}
    requested_at = datetime.now(timezone.utc).isoformat()

    # INTENT: Retry transient failures with exponential backoff, honoring retry-after.
    # REASONING: Immediate retry under a rate limit makes it worse. A transport failure uses up
    #   an attempt like a retryable status, so a dead network cannot loop forever.
    # ASSUMES: RETRYABLE and TRANSIENT_ERRORS (Config) cover every failure worth retrying.
    delay = 1.0
    response = None
    transport_error = None
    attempt = 0
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=60)
            transport_error = None
        except TRANSIENT_ERRORS as exc:
            response = None
            transport_error = exc
        if response is not None and response.status_code == 200:
            break
        if response is not None and response.status_code not in RETRYABLE:
            break  # non-retryable: handled after the loop, which saves the paid rows first
        wait = delay
        if response is not None:
            # INTENT: Honor both retry-after headers, preferring the millisecond-precision one.
            # REASONING: The server sends either `retry-after-ms` or `Retry-After`; reading only
            #   one silently falls back to the local schedule when the other is present. See § D
            #   for the full policy, including jitter.
            # ASSUMES: Both are numeric strings here; an HTTP-date `Retry-After` would fail
            #   float() and is caught so the local backoff still applies.
            for header, divisor in (("retry-after-ms", 1000.0), ("Retry-After", 1.0)):
                raw = response.headers.get(header)
                if raw:
                    try:
                        wait = float(raw) / divisor
                        break
                    except ValueError:
                        pass
        # INTENT: Stop without sleeping once the final attempt has failed.
        # REASONING: A sleep after the last attempt only delays the failure report.
        if attempt == MAX_ATTEMPTS - 1:
            break
        outcome = (f"HTTP {response.status_code}" if response is not None
                   else type(transport_error).__name__)
        print(f"  {outcome}, attempt {attempt + 1}, sleeping {wait:.1f}s")
        time.sleep(wait)
        delay = min(delay * 2, 30.0)

    # INTENT: On a row that still failed, save the rows already paid for, then stop the run.
    # REASONING: Every row in `records` was billed; ending the script without writing them
    #   throws that spend away. Stopping (rather than skipping the row) is right because a
    #   non-retryable status repeats on every row and exhausted retries mean the service is
    #   unavailable.
    # ASSUMES: The partial file holds the per-row answer columns (not the input columns),
    #   unvalidated.
    if response is None or response.status_code != 200:
        # INTENT: Read the request-id header defensively; it may be absent.
        # REASONING: Error responses (e.g. a 503) can arrive without an x-typesafe-request-id
        #   header, so bracket access would raise a KeyError that masks the real failure.
        request_id = response.headers.get("x-typesafe-request-id") if response is not None else None
        last_outcome = (
            f"HTTP {response.status_code}: {response.text[:500]}" if response is not None
            else f"{type(transport_error).__name__}: {str(transport_error)[:300]}"
        )
        if records:
            pl.DataFrame(records).write_parquet(PARTIAL_PATH)
            print("saved", len(records), "completed rows to:", PARTIAL_PATH)
        raise RuntimeError(
            f"stopped at ticket_id={row['ticket_id']} after {attempt + 1} attempt(s): "
            f"{last_outcome} | request_id={request_id}"
        )
    # INTENT: Read the 200 body and build the record inside one guard.
    # REASONING: Even a 200 can carry a malformed body (api-reference.md § 9): not JSON, a
    #   missing answer, or a missing nested field such as answers.category.probabilities.
    #   Any of these would otherwise end the script with the paid rows unsaved.
    # ASSUMES: An unreadable body is drift, not noise, so the run stops after saving.
    try:
        result = response.json()
        a = result["answers"]
        # INTENT: Persist the answering model version and token usage on every row.
        # REASONING: Provenance — a result is only reproducible if the exact model that produced
        #   it is recorded. Alias drift would otherwise be invisible in the output file.
        record = {
            "ticket_id": row["ticket_id"],
            # INTENT: Persist a per-row retry count alongside the answers.
            # REASONING: Backoff silently absorbs 429s, so without this column a reviewer cannot
            #   test whether throttled rows differ in outcome from clean ones — the retry history
            #   is unrecoverable from the output after the fact.
            # ASSUMES: `attempt` is the zero-based loop index at which the 200 arrived.
            "retry_count": attempt,
            "category": a["category"]["choice"],
            # INTENT: Persist the code-computed argmax next to the vendor's `choice`.
            # REASONING: They can disagree on rounding near-ties (api-reference.md § 14).
            #   Recording both makes the decision of which to treat as THE prediction explicit.
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
            # INTENT: Read token counts with .get(), keeping None when the API omits them.
            # REASONING: The OpenAPI spec makes them required integers, but both vendor SDKs
            #   type them nullable ("null when the API did not report it"); a crash here would
            #   discard a paid row. Nulls are counted and reported below, never imputed.
            "input_tokens": (result.get("usage") or {}).get("input_tokens"),
            "output_tokens": (result.get("usage") or {}).get("output_tokens"),
            # INTENT: Keep the exact request, its time, and the full response for every row.
            # REASONING: A pinned version fixes the model, not the exact output
            #   (api-reference.md § 14), so the saved response is the only exact record.
            "requested_at_utc": requested_at,
            "request_json": json.dumps(payload),
            "response_json": response.text,
            "request_id": response.headers.get("x-typesafe-request-id"),
        }
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        # ValueError covers a non-JSON body (requests' JSONDecodeError is a ValueError).
        if records:
            pl.DataFrame(records).write_parquet(PARTIAL_PATH)
            print("saved", len(records), "completed rows to:", PARTIAL_PATH)
        raise RuntimeError(
            f"ticket_id={row['ticket_id']}: unreadable 200 body ({type(exc).__name__}: {exc}) "
            f"| body: {response.text[:500]} "
            f"| request_id={response.headers.get('x-typesafe-request-id')}"
        ) from exc
    records.append(record)

judged = pl.DataFrame(records)
# INTENT: Save every paid row before the validation asserts run.
# REASONING: A failed assert after a full paid loop would otherwise discard all of it; the
#   finished OUT_PATH is still written only after validation passes.
judged.write_parquet(PARTIAL_PATH)

# --- Validate ---
assert judged.height == df.height, f"row count changed: {df.height} in, {judged.height} out"
assert judged["refund_requested_p"].is_between(0.0, 1.0).all(), "noul outside [0, 1]"
assert judged["frustration_score"].is_between(0.0, 3.0).all(), "score outside level range"
assert judged["answered_by_model"].n_unique() == 1, (
    f"mixed model versions in one run: {judged['answered_by_model'].unique().to_list()}"
)
# INTENT: Require complete answers, but only report missing token counts and request ids.
# REASONING: A missing answer field is drift and must stop the run; a null token count or an
#   absent request-id header is allowed by the vendor and should be visible, not fatal.
ANSWER_COLS = ["category", "category_argmax", "category_confidence", "category_probabilities",
               "frustration_score", "frustration_confidence", "refund_requested_p",
               "answered_by_model", "response_json"]
assert judged.select(ANSWER_COLS).null_count().sum_horizontal().item() == 0, "unexpected nulls in answers"
print("rows with null input_tokens:", judged["input_tokens"].null_count())
print("rows with no request id     :", judged["request_id"].null_count())

# --- Save ---
# INTENT: Attach the judgments to the input rows by ticket_id, keeping every input row.
# REASONING: A left join keeps each input row and its columns. A duplicate ticket_id in
#   `judged` would fan rows out, so uniqueness is asserted before the join and the row count
#   after it.
# ASSUMES: Each input row was judged exactly once (the loop above appends one record per row).
assert judged["ticket_id"].n_unique() == judged.height, "duplicate ticket_id in judged rows"
out = df.join(judged, on="ticket_id", how="left")
assert out.height == df.height, f"join changed the row count: {df.height} in, {out.height} out"
out.write_parquet(OUT_PATH)
print("wrote:", OUT_PATH, "| shape:", out.shape)
print("model:", judged["answered_by_model"][0])
print("total input tokens (billed, non-null rows):", judged["input_tokens"].sum())
print("total output tokens (free)                :", judged["output_tokens"].sum())
```

**A state built from numeric columns.** The API rejects `NaN`, `Infinity`, and numbers too large to
represent, and `requests`' `json=` refuses non-finite floats before sending
(`requests.exceptions.InvalidJSONError`, observed offline with `requests` 2.32.5 on 2026-11-01).
Clean the frame before the row loop:

```python
# --- Transform ---
# INTENT: Turn non-finite floats into null and identifiers into strings before building states.
# REASONING: NaN/inf would stop the run at the first affected row (InvalidJSONError) or, in a
#   hand-built body, return 400; the vendor asks for identifiers and exact large quantities as
#   strings so they survive number parsing.
# ASSUMES: FLOAT_COLS are the float columns that go into the state; record_id is an identifier.
FLOAT_COLS = ["amount", "rating"]
df = df.with_columns(
    [pl.when(pl.col(c).is_finite()).then(pl.col(c)).otherwise(None).alias(c) for c in FLOAT_COLS]
    + [pl.col("record_id").cast(pl.Utf8)]
)
print("nulls after non-finite cleanup:", df.select(FLOAT_COLS).null_count().to_dicts())
```

---

## D. Exponential backoff on 429 / 529 honoring `retry-after`

Standalone version of the retry block, for reuse in any script. DAAF calls the HTTP API directly,
so backoff is **your** responsibility — the vendor's automatic retry lives in the SDK, which is
not installed here. It also retries timeouts and dropped connections within the same attempt
budget, adds jitter on top of the server's wait rather than shortening it, and does not sleep
after the final attempt.

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
# REASONING: /api/errors documents 429 and 529 as "retry with exponential backoff"; 500, 502
#   and 504 are conventionally retryable server and gateway errors, 503 occurs on the live API
#   although it is not in the documented table, and the vendor SDK's default retry set
#   includes 408. Other 5xx statuses (501, 505 and up, except 529) fail fast.
#   400, 401, 413, 415 and 422 describe the request itself — retrying them burns time and
#   money to get the identical failure.
# ASSUMES: The vendor SDK's documented example policy omits 529, but the HTTP-API page
#   explicitly instructs retrying it, so 529 is included here.
RETRYABLE = {408, 429, 500, 502, 503, 504, 529}
# INTENT: Also retry a timeout, a dropped connection, or a response cut off mid-body.
# REASONING: These are transport failures, not request faults, and the next attempt usually
#   succeeds. Other requests exceptions (InvalidJSONError for a NaN in the body, a malformed
#   URL) describe the request itself, so they are not caught and fail at once, like a 400.
TRANSIENT_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)
MAX_ATTEMPTS = 6
BACKOFF_INITIAL = 1.0
BACKOFF_MAX = 30.0
JITTER_FRACTION = 0.2

payload = {
    "state": "placeholder state",
    "model": "jev-1.14.0",
    "questions": {"q": {"type": "noul", "instructions": "Is this a placeholder?"}},
}

# --- Transform ---
delay = BACKOFF_INITIAL
response = None
transport_error = None
for attempt in range(1, MAX_ATTEMPTS + 1):
    # INTENT: Count a transport failure as a used attempt, then back off like a retryable status.
    # REASONING: Sharing one attempt budget means a dead network cannot loop forever.
    try:
        response = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=60)
        transport_error = None
    except TRANSIENT_ERRORS as exc:
        response = None
        transport_error = exc
    if response is not None and response.status_code == 200:
        break

    wait = delay
    if response is not None:
        # INTENT: Read the request-id defensively — it is not guaranteed on error responses.
        # REASONING: It can be absent on error responses (e.g. a 503). `.get()` yields None
        #   rather than raising inside the error path, where a KeyError would mask the failure.
        request_id = response.headers.get("x-typesafe-request-id")
        if response.status_code not in RETRYABLE:
            # INTENT: Log the server's error body and the request id, never the request headers.
            # REASONING: The body names the offending field (a 422's `detail` is a list with
            #   `loc` and `msg`; a 400's `detail` is a string or an object) and is safe to print;
            #   the request headers carry the bearer token and must never reach the log.
            raise RuntimeError(
                f"non-retryable HTTP {response.status_code}: {response.text[:800]} "
                f"| x-typesafe-request-id={request_id}"
            )

        # INTENT: Prefer the server's own wait over the local backoff schedule.
        # REASONING: The server knows when the limit resets; waiting less than it asks just
        #   re-trips the limit.
        # ASSUMES: Retry-After here is delta-seconds; an HTTP-date form would fail float() and
        #   fall through to the local backoff.
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
        outcome = f"HTTP {response.status_code} (request_id={request_id})"
    else:
        # The exception text names the host and the failure, never the request headers.
        outcome = f"{type(transport_error).__name__}: {str(transport_error)[:300]}"

    # INTENT: Stop without sleeping once the final attempt has failed.
    # REASONING: A sleep after the last attempt only delays the failure report.
    if attempt == MAX_ATTEMPTS:
        break

    # INTENT: Add random jitter on top of the wait, never subtract it.
    # REASONING: Without jitter, parallel callers re-collide on the same schedule after a 429.
    #   Adding keeps a server-given wait as the minimum, so the retry never comes earlier than
    #   the server asked.
    wait = wait * (1.0 + random.uniform(0.0, JITTER_FRACTION))
    print(f"attempt {attempt}/{MAX_ATTEMPTS}: {outcome}; sleeping {wait:.2f}s")
    time.sleep(wait)
    delay = min(delay * 2, BACKOFF_MAX)

# --- Validate ---
# INTENT: Fail loudly after the last attempt, naming its status or its transport error.
# REASONING: Test `response is not None`, never `if response`: a requests Response with a 4xx
#   or 5xx status is falsy, so `if response` would hide exactly the status that matters.
last_outcome = (
    response.status_code if response is not None
    else f"{type(transport_error).__name__}: {str(transport_error)[:300]}"
)
assert response is not None and response.status_code == 200, (
    f"exhausted {MAX_ATTEMPTS} attempts; last outcome {last_outcome}"
)

# --- Validate (report) ---
print("succeeded on attempt", attempt)
print("usage:", response.json().get("usage"))
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
# REASONING: The {"models": [...]} envelope is the documented shape and the live one (it lists
#   aliases only). The bare-list fallback is cheap insurance against a schema change, not a
#   sign that the shape is in doubt.
# ASSUMES: Each entry carries name / description / release_date (OpenAPI ModelMetadata).
#   release_date is printed as an opaque string: the schema says YYYY-MM-DD, but the live API
#   returned ISO-8601 datetimes on 2026-11-01, so a date-only parser would fail.
# NOTE: A 200 here is NOT proof the key is valid — validate auth with an authenticated
#   evaluation call whose body you parse (see api-reference.md § 14 "Things to verify on your
#   own calls" > Auth pre-flight).
models = body["models"] if isinstance(body, dict) and "models" in body else body
assert isinstance(models, list) and models, f"unexpected /v1/models body: {json.dumps(body)[:500]}"
for m in models:
    assert "name" in m, f"model entry missing name: {m}"

# --- Validate (report) ---
for m in models:
    print(f"{m['name']:<16} released {m.get('release_date', '?')}  {m.get('description', '')}")

# INTENT: Resolve the alias to a concrete version by making one cheap evaluation call and
#   reading the response's `model` field.
# REASONING: The response reports the versioned ID that actually answered (on 2026-11-01 a
#   "jev-latest" request reported "jev-1.14.0"). This doubles as the only trustworthy auth
#   pre-flight, because it is an AUTHENTICATED call with a parsed body.
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
print("probe usage:", probe.json().get("usage"))
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

# INTENT: Accept a number or None for each token count; report None instead of failing.
# REASONING: The OpenAPI spec makes both counts required integers, but both vendor SDKs type
#   them nullable ("null when the API did not report it"). Every response observed on
#   2026-11-01 carried integers, so a None is rare but legal — count it, never impute it.
for token_key in ("input_tokens", "output_tokens"):
    token_value = (result.get("usage") or {}).get(token_key)
    assert token_value is None or isinstance(token_value, (int, float)), (
        f"usage.{token_key} is neither a number nor null: {token_value!r}"
    )
    if token_value is None:
        print(f"  NOTE usage.{token_key} is null on this response — counted, not imputed")

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
        # INTENT: Tolerate probability rounding, scaled to the number of options.
        # REASONING: Probabilities can come back rounded (e.g. to 2 dp), so the worst-case sum
        #   error is 0.005 * n_options; a 1e-6 bound would fail in normal operation. The 0.02
        #   floor keeps tiny option sets from being over-tight.
        # ASSUMES: 2 dp rounding — check the sums in your own responses (api-reference.md § 8.5).
        tol = max(0.02, 0.005 * len(options))
        assert abs(sum(probs.values()) - 1.0) <= tol, f"{qid}: probabilities sum to {sum(probs.values())}"
        assert 0.0 <= answer["confidence"] <= 1.0, f"{qid}: confidence out of [0, 1]"
        # INTENT: REPORT, do not assert, when `choice` differs from the code-computed argmax.
        # REASONING: The docs define `choice` as the highest-probability option, but near-ties
        #   that collapse after rounding can make it differ from the argmax of the returned
        #   distribution (the vendor presumably tie-breaks on unrounded values), so this is
        #   expected behaviour, not drift. Asserting here could fail a long run on that quirk;
        #   reporting it keeps the disagreement visible and countable.
        # ASSUMES: The caller decides which field is THE prediction and persists both.
        if answer["choice"] != max(probs, key=probs.get):
            print(f"  NOTE {qid}: vendor choice {answer['choice']!r} != argmax "
                  f"{max(probs, key=probs.get)!r} (rounding near-tie; confidence "
                  f"{answer['confidence']})")

    elif answer["type"] == "score":
        n_levels = len(question["criteria"])
        # INTENT: Enforce DAAF's 2-to-10 level rule.
        # REASONING: The schema accepts 1 to 10 levels; one level is not a scale, so DAAF
        #   policy asks for at least two.
        assert 2 <= n_levels <= 10, f"{qid}: score criteria must hold 2 to 10 levels"
        probs = answer["probabilities"]
        # INTENT: Expect STRING keys of level indices.
        # REASONING: The response keys score probabilities by level number as a string
        #   ("0", "1", ...), matching `legend`; integer keys would indicate drift.
        assert set(probs) == {str(i) for i in range(n_levels)}, (
            f"{qid}: probability keys {sorted(probs)} do not match level indices"
        )
        assert set(answer["legend"]) == set(probs), f"{qid}: legend keys differ from probability keys"
        # INTENT: Same rounding tolerance as for choice, scaled to the level count.
        # REASONING: Score probabilities can be rounded identically; see api-reference.md § 8.5.
        tol = max(0.02, 0.005 * n_levels)
        assert abs(sum(probs.values()) - 1.0) <= tol, f"{qid}: probabilities sum to {sum(probs.values())}"
        assert 0.0 <= answer["score"] <= n_levels - 1, f"{qid}: score outside level range"
        assert 0.0 <= answer["confidence"] <= 1.0, f"{qid}: confidence out of [0, 1]"

    elif answer["type"] == "box":
        # INTENT: Check a box answer's edges and its nullable confidence.
        # REASONING: Box is experimental (vendor: "Dreamer-ready"); its edges are fractions of
        #   the image size with left < right and top < bottom, and the schema allows a null
        #   confidence. Only requests with images and the images header return this type.
        edges = answer["box"]
        for edge in ("top", "bottom", "left", "right"):
            assert 0.0 <= edges[edge] <= 1.0, f"{qid}: box edge {edge} outside [0, 1]"
        assert edges["left"] < edges["right"] and edges["top"] < edges["bottom"], f"{qid}: inverted box"
        assert answer["confidence"] is None or 0.0 <= answer["confidence"] <= 1.0, (
            f"{qid}: box confidence neither null nor in [0, 1]"
        )

    else:
        # INTENT: Treat any other answer type as drift.
        # REASONING: The four documented types are handled above; anything else means the
        #   schema changed and the code above may misread it.
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
  -d '{"state":"Help! My payouts have been failing for 3 days.","model":"jev-1.14.0","questions":{"is_urgent":{"type":"noul","instructions":"Does this convey urgency?"}}}'
```

Expected **shape** of a healthy response — the structure is what to check; the specific
probability and token counts are illustrative and will differ on every call:

```json
{"model":"jev-1.14.0","answers":{"is_urgent":{"type":"noul","noul":0.92}},"usage":{"input_tokens":312,"output_tokens":48}}
```

Notes:
- Per DAAF's one-command-per-Bash-call rule, run this as a single command with no `&&`, `;`, or
  `||` chaining. Piping is permitted by that rule, but piping into `jq` here mainly costs
  readability on a one-line response — read the raw JSON instead.
- `-sS` keeps the progress meter quiet while still surfacing errors.
- A `401` means the env var is unset, empty, or wrong inside the container. Check that it is set
  and non-empty without revealing it: `[ -n "${TYPESAFE_API_KEY:+set}" ]` (exit status 0 means
  set and non-empty). Never `echo $TYPESAFE_API_KEY` or dump the environment. If it is set and
  you still get `401`, the key itself is wrong or expired — see `./api-reference.md`
  § 14 "Things to verify on your own calls" > Auth pre-flight.
- This call costs money. Run it once.

---

## H. One image with a `box` and a `noul` (experimental)

> **Experimental — read before using.** The vendor labels images and `box` questions
> "Dreamer-ready", not production: "The request format, the answers, and the limits on this page
> can change between releases, and accuracy will change as we update the models." DAAF has **not
> tested them thoroughly**. This template follows DAAF's one `box` smoke call, on 2026-11-01 (a
> synthetic 400×300 PNG sent as base64 JSON to jev-1.14.0), which returned `200` with a plausible
> box; what else DAAF has run is in `./api-reference.md` § 14. Do not use its answers as a
> research measurement without first validating box accuracy against hand-drawn boxes on your own
> images. Schemas and limits: `./api-reference.md` § 6.4,
> § 6.5, § 8.6.

The shape is the vendor's own: one image in the state, a `noul` asking whether the target is
there, and a `box` locating it. A `box` answer is always four edges, even when the target is
absent, so the `noul` decides whether the box means anything. The image travels as base64 inside
the JSON body. The vendor recommends `multipart/form-data` for any image sent without its SDK
(base64 makes each image about a third larger, and that extra size counts toward the 32 MiB body
limit), and base64 only when multipart is not possible. DAAF has not exercised multipart, so this
template uses the base64 form DAAF has run.

The template checks the image against the limits but does not change it: the API strips metadata,
ignores EXIF orientation, and rejects (never resizes) an out-of-range image. Rotating, resizing,
and converting to PNG or JPEG belong in a separate, validated script that writes the prepared image
to the project before this one runs.

```python
# --- Config ---
import os
import json
import uuid
import base64
import hashlib
from datetime import datetime, timezone
import requests
import polars as pl
from PIL import Image

API_KEY = os.environ["TYPESAFE_API_KEY"]
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
# INTENT: Pin jev-1.14.0.
# REASONING: Box questions need Jev 1.14 (vendor docs, 2026-11-01); jev-1.13.0 accepts images
#   but not box questions.
MODEL = "jev-1.14.0"
# INTENT: Turn on images for this request.
# REASONING: Without TypeSafe-Danger-Zone-Images: true, a request with an image or a box
#   question returns 400 ("Images are experimental. Send the header ...", observed 2026-11-01).
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",  # the only place the key appears
    "Content-Type": "application/json",
    "TypeSafe-Danger-Zone-Images": "true",
}
IMAGE_PATH = "{PROJECT_DIR}/data/processed/images/example.png"
OUT_PATH = "{PROJECT_DIR}/data/processed/image_box_answer.parquet"
TARGET = "the red stop sign"
# INTENT: Use the box only when the presence noul is high enough.
# REASONING: The vendor gives 0.7 for yes as a starting point for noul thresholds.
# ASSUMES: Illustrative starting value — tune it on labelled images before relying on it.
PRESENT_THRESHOLD = 0.7

# --- Load ---
# INTENT: Check the image against the documented limits before paying for a call.
# REASONING: An image outside the limits is rejected and the whole request fails; checking
#   locally gives a clearer error and costs nothing.
# ASSUMES: The image was already rotated upright, sized, and saved as PNG or JPEG.
with open(IMAGE_PATH, "rb") as f:
    image_bytes = f.read()
with Image.open(IMAGE_PATH) as img:
    width, height = img.size
    pil_format = img.format
print("image:", IMAGE_PATH, "| format:", pil_format, "| size:", width, "x", height,
      "| bytes:", len(image_bytes))
assert pil_format in ("PNG", "JPEG"), f"format {pil_format} not accepted: send PNG or JPEG"
assert 280 <= width <= 1568 and 280 <= height <= 1568, "each side must be 280 to 1568 pixels"
assert 78_400 <= width * height <= 2_458_624, "total pixels outside 78,400 to 2,458,624"
assert len(image_bytes) <= 16 * 1024 * 1024, "image file over 16 MiB"
image_sha256 = hashlib.sha256(image_bytes).hexdigest()

# --- Transform ---
# INTENT: Reference the image with a fresh UUID, placed once in the state.
# REASONING: References are matched as plain text anywhere in the request, so a UUID cannot
#   collide with real text. Each place a reference appears adds another copy of the image,
#   so it goes in the state once and both questions point to it by path (`photo`).
# ASSUMES: Every asset is referenced somewhere; an unreferenced asset returns 400.
image_ref = str(uuid.uuid4())
asset = {
    "type": "image",
    "format": "png" if pil_format == "PNG" else "jpg",
    # Standard base64 alphabet with padding, no line breaks, no "data:" prefix.
    "data_base64": base64.b64encode(image_bytes).decode("ascii"),
}
# INTENT: Ask for presence and location of the same target in one request.
# REASONING: A box answer is always a box, with no "not found" answer; the companion noul
#   tells code whether to use it.
questions = {
    "target_present": {"type": "noul", "instructions": f"Does `photo` show {TARGET}?"},
    "target_box": {"type": "box", "instructions": f"{TARGET} in `photo`"},
}
payload = {
    "state": {"photo": image_ref},
    "model": MODEL,
    "assets": {image_ref: asset},
    "questions": questions,
}
requested_at = datetime.now(timezone.utc).isoformat()
response = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=60)

# --- Validate ---
# INTENT: Fail loudly on a non-200, printing only the error body and the request id.
# REASONING: A 400 body names the problem (missing header, rejected image, unreferenced
#   asset); the request headers carry the key and are never printed.
request_id = response.headers.get("x-typesafe-request-id")
assert response.status_code == 200, (
    f"HTTP {response.status_code}: {response.text[:800]} | request_id={request_id}"
)
result = response.json()
assert result["model"] == MODEL, f"answered by {result['model']}, expected {MODEL}"
present = result["answers"]["target_present"]
box_answer = result["answers"]["target_box"]
assert present["type"] == "noul" and 0.0 <= present["noul"] <= 1.0, "bad noul answer"
assert box_answer["type"] == "box", "expected a box answer"
edges = box_answer["box"]
for edge in ("top", "bottom", "left", "right"):
    assert 0.0 <= edges[edge] <= 1.0, f"box edge {edge} outside [0, 1]"
assert edges["left"] < edges["right"] and edges["top"] < edges["bottom"], "inverted box"
# INTENT: Accept a null box confidence.
# REASONING: The schema says "Null when the model does not provide confidence"; the
#   2026-11-01 `box` smoke call returned a number, so both must be handled.
box_conf = box_answer["confidence"]
assert box_conf is None or 0.0 <= box_conf <= 1.0, "box confidence neither null nor in [0, 1]"

# INTENT: Convert edges to pixels and apply the presence gate in code.
# REASONING: Edges are fractions measured from the top-left corner: left/right of the width,
#   top/bottom of the height. The gate keeps the decision in reviewable code.
box_px = (
    round(edges["left"] * width), round(edges["top"] * height),
    round(edges["right"] * width), round(edges["bottom"] * height),
)
box_usable = present["noul"] >= PRESENT_THRESHOLD
print("target present p:", present["noul"], "| box usable:", box_usable)
print("box (fractions):", json.dumps(edges), "| box confidence:", box_conf)
print("box (pixels: left, top, right, bottom):", box_px)
print("answered by:", result["model"], "| usage:", result.get("usage"), "| request id:", request_id)

# --- Save ---
# INTENT: Persist the answer with full provenance, but not the base64 image.
# REASONING: The image file and its SHA-256 identify the input exactly, so the logged request
#   replaces the base64 text with the hash. The full response is kept because a pinned model
#   does not guarantee identical output on a re-run.
payload_logged = {
    **payload,
    "assets": {image_ref: {"type": "image", "format": asset["format"], "sha256": image_sha256}},
}
row = pl.DataFrame([{
    "image_path": IMAGE_PATH,
    "image_sha256": image_sha256,
    "width_px": width,
    "height_px": height,
    "target": TARGET,
    "target_present_p": present["noul"],
    "box_top": edges["top"],
    "box_bottom": edges["bottom"],
    "box_left": edges["left"],
    "box_right": edges["right"],
    "box_confidence": box_conf,
    "box_usable": box_usable,
    "answered_by_model": result["model"],
    "input_tokens": (result.get("usage") or {}).get("input_tokens"),
    "requested_at_utc": requested_at,
    "request_id": request_id,
    "request_json": json.dumps(payload_logged),
    "response_json": response.text,
}]).with_columns(
    # INTENT: Give the nullable columns a fixed type.
    # REASONING: A null confidence or token count would otherwise give an all-null column with
    #   no type, which does not stack with later rows.
    pl.col("box_confidence").cast(pl.Float64),
    pl.col("input_tokens").cast(pl.Int64),
)
row.write_parquet(OUT_PATH)
print("wrote:", OUT_PATH, "| shape:", row.shape)
```

Notes:
- A `400` with `{"detail":{"error_type":"api_usage_error","message":"Images are experimental. ..."}}`
  means the images header is missing. Other `400`s name a rejected image, a bad base64 string or
  `format`, or an unreferenced asset; a `413` means a size limit (`./api-reference.md` § 6.5).
- The image adds a few hundred input tokens for a small picture (635 input tokens for this request
  shape with a 400×300 PNG, observed 2026-11-01). Measure on your own images before a loop.
- To ask about many images, loop over files the way Pattern C loops over rows, one request per
  image, with the same cost confirmation first.
