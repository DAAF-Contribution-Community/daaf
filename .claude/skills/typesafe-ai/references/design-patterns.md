# Typesafe AI Design Patterns

How to *shape* Typesafe AI (Jev / System One) questions and compose their answers, curated from the
`docs.typesafe.ai` plain-text corpus (`llms-full.txt`) read on **2026-11-01**, when the current
models were **jev-1.14.0** and **jev-1.13.0**.

Wire schema lives in `./api-reference.md`; copyable code lives in `./request-patterns.md`. This
file covers the judgment calls that sit above both.

## Contents

1. The governing idea: code owns control flow
2. State vs. instructions vs. criteria
3. Sizing a question: one snap judgment (choosing a type, "none of the above" vs a companion
   Noul, the noul-vs-score trap, Noul phrasing and thresholds)
4. Confidence semantics
5. Composition patterns: fan-out (5.1), confidence-gated routing (5.2), composite scoring (5.3),
   intent routing (5.4)
6. When two requests are actually needed
7. Known limitations ("model jaggedness")
8. Cookbooks in the vendor docs
9. Where Typesafe plausibly fits research work, and the vendor's data handling terms
10. Evaluating fit for your task (option order, repeat calls, confidence ties, metrics,
    calibration, batching items, wording, class-level checks, cost)

**Evidence convention:** `>` blockquotes are **quoted verbatim** from the vendor docs as read on
2026-11-01 (or, where named, from the vendor's agent skill, release post, or legal documents read
the same day); everything else is synthesis by the skill author. Gaps are marked "not documented
(2026-11-01)" rather than inferred. Each section names its source page.

**Which model the guidance was measured on.** The vendor's documented limitations (§ 7) are for
jev-1.13; there is no jev-1.14 limitations page (HTTP 404 on 2026-11-01). DAAF's at-scale live
observations (2-dp rounding, confidence ties, `choice` differing from the argmax) were measured on
jev-1.13.0 in September 2026; 2-dp rounding was seen again on jev-1.14.0 on 2026-11-01 in a small
sample. Treat jev-1.14 behaviour as unvalidated until your own pilot (§ 10) checks it.

---

## 1. The governing idea: code owns control flow

Source: `https://docs.typesafe.ai/concepts/how-to-build-with-system-one`

> System One is TypeSafe's model for building AI-powered software, not agents. It does not generate
> code or choose its own next action. It provides AI primitives that embed into software, so code
> remains in control while the model handles common-sense judgments over unstructured data.

The vendor's own summary box, verbatim:

> **Summary:** build a normal software workflow and insert System One only where AI is needed.
>
> * Keep control flow, deterministic rules, and side effects in code.
> * Break broad judgments into narrow, typed questions with explicit instructions and criteria.
> * Give each question only the context it needs.
> * Use probabilities and confidence to act, ask for review, or escalate.
> * Ask independent questions together, then compose their answers in code.

Claimed properties that make the answers composable, verbatim from the same page:

| Property | Claim |
|----------|-------|
| Structured | "Decisions and probabilities conform to the structured software types and JSON schema your code expects, so it never has to recover a value from generated prose." |
| Parallel | "Questions are evaluated independently and in parallel. One primitive's result does not become hidden context that changes another primitive's result." |
| Comparable | "Outputs are sortable and can drive smart `if` statements, thresholds, and comparisons." |
| Fast | "Most calls complete in about 100 ms." |
| Calibrated confidence | "RLCD communicates uncertainty through calibrated probabilities instead of tending toward overconfidence." |
| Self-consistent | "System One is designed to return stable answers across repeated evaluations." |

These are **vendor claims**. The latency figure is stated twice with different numbers — "about
100 ms" on the how-to-build page and "150ms" on the use-case map (both on 2026-11-01) — which is a
reasonable signal to treat all such figures as marketing-grade rather than specification-grade.
DAAF's nine successful calls on 2026-11-01 took 143–214 ms each, measured at the client including
the network. "Self-consistent" does not mean bit-identical (`./api-reference.md` § 14).

**DAAF reading:** this maps cleanly onto DAAF's own sequential-script philosophy. The model
supplies judgments; the script supplies the `if`s, the thresholds, the joins, and the arithmetic.
Never let a Jev answer decide what the script does next in an open-ended way.

---

## 2. State vs. instructions vs. criteria

Source: `https://docs.typesafe.ai/concepts/state`, `https://docs.typesafe.ai/primitives`

The division of labor is the single most important design decision:

| Slot | Holds | Rule of thumb |
|------|-------|---------------|
| `state` | The **material** being judged: the document, record, conversation, policy | Everything the judgment is *about*; nothing else |
| `instructions` | The **question** being asked about that material | The evaluation logic. One judgment, stated literally |
| `criteria` | The **answer space**: options, levels, or yes/no definitions | The rubric. Boundary cases go here |

Verbatim from `/concepts/state`:

> The state contains the content and supporting facts. Questions define the judgments the model
> should make about that material. For example, keep the refund request and policy in the state,
> then ask whether the customer requested a refund and whether the policy supports it.

> Think of state as the material you would present to a panel of experts before asking them to
> make a judgment.

**Prefer an object state.** Verbatim:

> Use an object for most requests so each part of the state has a descriptive name and its
> relationships remain clear. A string is suitable when the use case is simple and requires only
> one piece of text.

**Name the part each question judges.** With an object state, reference keys inside `instructions`
using a backticked dot-and-index path — `` `ticket.messages[0].text` ``, `` `refund_policy` ``.
Verbatim from `/primitives`:

> Explicit paths make it clear which parts of a structured state should inform each judgment.

**Related information belongs in one state.** Verbatim from `/concepts/state`, about an example
combining a conversation, an order, and a policy:

> This object is one state, even though it contains a conversation, an order, and a policy. Put
> related information together when the decision requires comparing those parts.

But only what the decision needs — § 7 documents the accuracy cost of irrelevant material.

### Question IDs are for code

Verbatim from `/primitives`:

> Question IDs are for your code. They are not sent to the model. Write the complete question in
> `instructions`, even when the ID seems self-explanatory.

Restated on `/primitives/choice`: "The model never sees the question id." This is a common and
silent failure mode — a question id of `is_pii` with `instructions` of "Check this" gives the model
nothing to work with, because it never sees the word "PII."

### Criteria are an extension of the instruction

From `/model-jaggedness/jev-1.13`:

> When the `instructions` and the `criteria` ask for different things, `jev-1.13` might get
> confused. The best performance comes from clear phrasing. For example, a Noul where `true` maps
> to no and `false` maps to yes will perform worse. Aim for instructions which are easy for the
> average person to read and understand.
>
> **Instead:** treat the criteria as an extension of the instruction. Align the two using clear and
> precise language.

**Option names carry meaning too.** From the vendor's agent skill (`typesafe-ai/skills`, MIT,
v0.6.2): "**Option names are sent to the model; question IDs are not.** Names that describe the
content (`refund_request`, `shipping_delay`) help the model. Positional names (`A`, `left`,
`option_1`) give it nothing meaningful to go on and can bias the answer."

---

## 3. Sizing a question: one snap judgment

Source: `https://docs.typesafe.ai/primitives`

Verbatim:

> Ask for a judgment a knowledgeable person makes in a second given the right context. "Does this
> message convey urgency?" is a good question. "Analyze this message and determine the best course
> of action" is not. That needs slow reasoning, and it is a signal to break the task into small
> questions and compose the answers in code.

> If the judgment you want depends on several independent factors, ask about each factor separately
> and combine the answers with your own logic. Instead of "rate this startup pitch", ask about
> market size, technical feasibility, and differentiation, then weight them in code based on their
> relative importance. When priorities shift, change the value of weights rather than rewriting a
> prompt.

That last clause is the underrated argument: a weighted composite keeps the tuning surface in
reviewable code constants rather than in prose that has to be re-litigated on every change.

### Choosing a type

Verbatim from `/primitives`:

> * **Choice** fits when the answer is one of a known set of options with no order between them:
>   routing a ticket to a department, classifying a document type, detecting a programming
>   language. Give the full list of options, and add an `other` or `none of the above` option when
>   the list might not cover every input.
>
> * **Score** fits when the answer falls on a spectrum and you can describe what each point on that
>   spectrum means: bug severity, customer frustration, skill level. The levels are yours to
>   define, and the model returns a position along them.
>
> * **Noul** fits a clean yes/no question where the probability itself is the useful signal: does
>   this message contain personally identifiable information, is the customer requesting a refund,
>   does the resume mention distributed systems.

A fourth type, `box`, locates something in an image. It is image-only, needs Jev 1.14, and is
vendor-labelled "Dreamer-ready" (not production); DAAF has run one `box` smoke call
(`./api-reference.md` § 14). Pair every `box` with a `noul` asking whether the target is present,
because "A Box answer is always a box" even when the target is absent.

### "None of the above": an option or a companion Noul

The `/primitives` advice above adds an `other` or `none of the above` option. The Choice page adds
a caution, verbatim from `/primitives/choice`:

> A `none of the above` option may not work well in many use cases. As an alternative, ask a
> companion Noul question in the same request that checks whether anything fits at all, such as
> "Does `message` name any of `our_products`?" Your code then reads the Choice answer only when the
> Noul says yes.

The vendor's agent skill (v0.6.2) is more direct: "As of Jev 1.14, this companion Noul usually
works better than a "none of the above" option." Both designs are valid and both are cheap (the
companion Noul rides in the same request). When to prefer each:

- **Companion Noul** — a sensible default on Jev 1.14, since the vendor says it "usually works
  better"; especially when inputs outside the list are common, or when "does anything fit?" is
  worth thresholding on its own.
- **`other` option** — when the coding scheme itself needs "other" as a category of the variable,
  or when a pilot shows it catches out-of-scope inputs as well as the companion Noul does.

On a pilot with out-of-scope items, compare them: how often does each catch an input that fits no
option, and how often does each wrongly reject one that fits? Then fix the design for the run,
because the two produce differently defined variables.

Tie-breaker, verbatim:

> If two types both seem to fit, prefer the one whose answer your code can act on directly. A
> Choice between `refund`, `rebook`, and `information` maps straight onto three code paths. A Score
> of customer frustration maps onto a threshold. A Noul maps onto an `if`.

### The noul-vs-score trap

The most consequential modeling mistake the docs call out, verbatim from `/primitives`:

> Use Noul for a yes/no judgment and Score to measure a position on a spectrum. "Is this candidate
> strong in Python?" needs a clear definition of "strong". A Noul value of 0.5 means the model
> gives yes and no equal probability. It does not mean the candidate has a medium skill level. An
> unclear definition makes that probability hard to interpret.
>
> If you want to measure skill level, use a Score with defined levels, such as no experience, some
> familiarity, daily use, and deep expertise. If you need a yes/no decision, define the condition
> clearly, such as "Does the resume state that the candidate has used Python at work?"

**A noul near 0.5 is ambiguity about a yes/no, never a middling magnitude.** Any pipeline that
reads a noul as an intensity is reading it wrong.

### Noul phrasing

From `/primitives/noul`:

> Ask one yes/no question per Noul. If a question has two conditions, such as "Is the customer
> angry and asking for a refund?", the model has to judge both at once and the value means less.
> Ask two Nouls and combine them in code.
>
> Phrase the question so that a high value means yes. "Does the message contain personal data?" is
> clear. "Is the message free of personal data?" inverts the meaning, and code that reads it later
> will get it backwards.
>
> A statement works as well as a question. For "The customer is requesting a refund", a value near
> 1 means the statement is true. Try both phrasings with your own data to see which works better.
>
> Make the boundary between yes and no unambiguous. ... When the boundary is subtle, add
> `criteria` with `true` and `false` descriptions ... The instruction is enough for most Nouls, so
> try your questions with and without `criteria` and keep whichever gives better answers on your
> documents.

### Reading a Noul: starting thresholds

From `/primitives/noul`:

> A good starting point is 0.7 for yes and 0.3 for no. Often you only care whether the answer is
> yes, and 0.7 is the only threshold you need. Where to set it depends on the cost of being wrong.
> Raise it when acting on a false yes is expensive, such as paging someone or issuing a refund.
> Lower it when missing a true yes is expensive, such as failing to flag a safety issue. Avoid
> fitting thresholds closely to a handful of test cases. Values between 0.3 and 0.7 can go to a
> person rather than either code path.

These are vendor starting points, not validated cut-offs for a research variable; § 10 covers
checking them on a labelled pilot.

---

## 4. Confidence semantics

Source: `https://docs.typesafe.ai/confidence`

**What it is.** Verbatim:

> All Score and Choice answers from TypeSafe include a `probabilities` property representing the
> probability distribution across the options (for Choice) or levels (for Score). The *shape* of
> that distribution is what tells you how certain the model is: concentrated on one outcome means a
> confident answer, spread out means an uncertain one.
>
> The answer's `confidence` property collapses that shape into a single number from 0 to 1, so you
> can threshold on it without doing the math yourself. It is 1 when all the probability is on one
> outcome and 0 when the probability is spread evenly. (Noul answers don't carry one; see Noul
> below.)

**It is a convenience statistic with a documented formula, not a ground truth.** Verbatim:

> TypeSafe's `confidence` is one reasonable way to summarize a distribution, not the only one. We
> return a fixed measure so that every answer comes with a sensible default: you can gate on
> `confidence` from your first call, on the same 0 to 1 scale for every question, without first
> choosing and validating a statistic of your own. Because the formulas below are exact and every
> answer includes its full `probabilities`, you can compute whichever measure matters most to your
> application instead.

The formulas (full text in `./api-reference.md` § 8.5):

| Type | `confidence` | What it ignores |
|------|--------------|-----------------|
| Choice | `(p_max − 1/n) / (1 − 1/n)` for n options | Everything but the top probability: "(0.6, 0.3, 0.1) and (0.6, 0.2, 0.2) both have confidence 0.4" |
| Score | `max(0, 1 − Σ p_i·\|i − m\| / MAD_unif)`, m = most likely level, `MAD_unif = (1/n) Σ \|i − (n−1)/2\|` | Nothing: probability on distant levels lowers it more than on neighbours |
| Noul | none returned; the vendor suggests `\|2p − 1\|` if a confidence-style number is needed | — |

The page names two alternatives "often very effective in practice": "**Top probability**, p_max",
whose meaning depends on the option count, and "**Top-to-second ratio**, p_max / p_second", which
"measures how clearly the selected option beats the runner-up". **Persist the full
`probabilities`**, not just `confidence`, so a later analysis can apply any of these, or entropy,
without re-spending on API calls. Reported values appear to be computed before rounding, so a
value recomputed from the returned 2-dp probabilities can differ from the reported one by about
0.01 (`./api-reference.md` § 8.5).

**What low confidence means.** Verbatim:

> low confidence on a Choice often means none of the options are a clear winner over the others,
> and low confidence on a Score often means the levels are ambiguous, multi-dimensional, or the
> state doesn't contain enough to go on.

That second reading is diagnostic: a systematically low-confidence Score usually means the rubric
is conflating dimensions and should be split into several Scores (§ 5.3).

**What it does NOT mean.** The vendor's own agent skill (`typesafe-ai/skills`, MIT, v0.6.2), under
"Confidence is rarely the gate": "Confidence measures how concentrated an answer's probability
distribution is, which is not the same as how likely the answer is to be correct." A confident
answer to a badly-posed question is confidently wrong. And from `/concepts/system-one`:

> Calibration is measured across groups of predictions; it does not guarantee that an individual
> answer is correct.

**Three-band usage.** Verbatim from `/confidence`:

> **High confidence:** Act automatically. The model has a clear read and you can proceed without
> human involvement.
>
> **Medium confidence:** Proceed with caution. The model has a reasonable answer but is not
> certain. Depending on context, you might ask the user to confirm, flag for review, or gather more
> information before acting.
>
> **Low confidence:** Do not act. Route to a human, request clarification, or fall back to a
> different system. The model is telling you it does not have enough information or the question is
> not a good fit.

**Check whether confidence is a band or a ranking on your data.** `confidence` is reported at 2
decimals, and a Choice's depends only on its top probability and option count, so it can take few
distinct values and form large ties — including at the top (measured on jev-1.13.0, September 2026;
`./api-reference.md` § 8.5). Banded thresholds like the three-band usage above can
still work on a coarse grid; ranking *within* a band may not. Inspect the distinct-value count and
tie blocks before ranking on it — see § 10 "Evaluating fit for your task" below.

**Thresholds scale with stakes, and there is no universal number.** Verbatim:

> A confidence threshold is not one number. Different actions within the same system should be
> gated at different levels depending on the consequences of getting it wrong.

> The correct threshold values depend on your domain and the performance of the model for your use
> case. Start with conservative thresholds, test with your own data, and adjust as you observe
> results.

The docs' worked examples use a 0.5 floor with a 0.9 gate on a destructive action
(`/confidence`) and a 0.6 floor with a 0.85 gate (`/patterns/confidence-routing`) — **illustrative
values, explicitly not defaults to copy.** Note also that thresholds tuned against one model
version are invalidated by an alias move, which is the practical argument for pinning a versioned
ID — `jev-1.14.0` for new work, or `jev-1.13.0` for a study tuned on it (see `./api-reference.md`
§ 12).

---

## 5. Composition patterns

Source: `https://docs.typesafe.ai/patterns` and its four child pages

The index table, verbatim:

| Pattern | What it does | Benefits |
|---------|--------------|----------|
| Speculative Fan-Out | Send many questions in a single call, including speculative ones, and let your code decide what's relevant | Cost, Speed |
| Confidence-Gated Routing | Utilize confidence as a second decision axis to build safer systems | Reliability, Safety |
| Composite Scoring | Combine several dimensions of analysis into a single score | Cost, Reliability, Speed |
| Intent Routing | Classify a user's intent and route to the appropriate handler | Cost, Speed |

Framing, verbatim from `/patterns`:

> Learning to think in terms of discrete, atomic decisions that compose into complex system
> behavior is a key skill for getting the most out of TypeSafe.

### 5.1 Speculative fan-out

Source: `https://docs.typesafe.ai/patterns/fan-out`

> Because TypeSafe supports sending many questions in a single API call, we recommend putting all
> of the questions your system needs in a single request, and then using code to decide what is
> relevant after the fact. All questions are evaluated in parallel, so adding more questions
> usually has little effect on response time.

> **Speculative questions:** `bug_severity` and `has_reproducible_steps` only matter if the ticket
> is a bug report. `refund_requested` only matters for billing. We include all upfront because
> additional questions usually have little effect on response time. ...

The economics, from `/primitives`:

> Adding questions barely changes the response time and costs only the tokens for the extra
> questions, which are cheap. Asking a question you might not need is close to free.

**This is the default, not an optimization.** Because billing is per input token and the `state` is
re-billed on every request, N questions in one call cost roughly one state instead of N. See
`./request-patterns.md` § B.

A drift note worth recording: the measured speedup for the parallel-questions cookbook is quoted
as **"11.5x cheaper and 9.6x faster"** on `/primitives` and **"12.2x cheaper and 10.0x faster"** in
the `llms.txt` index entry (both on 2026-11-01). The docs disagree with themselves; treat the
magnitude ("roughly an order of magnitude") as the durable claim. `./api-reference.md` § 11 quotes
the first figure with the same caveat.

### 5.2 Confidence-gated routing

Source: `https://docs.typesafe.ai/patterns/confidence-routing`

> Use confidence as a second axis. The answer tells you what; confidence tells you whether to act.

The shape is a floor plus per-action gates, verbatim from the worked example:

> The 0.6 floor catches anything the model is genuinely uncertain about. Above that floor, each
> action type has its own threshold based on the consequences of acting on a wrong classification.
> Checking a balance at 0.6 is fine because the worst case is the user having to listen to the
> balance read-out. But approving a transfer requires very high confidence (>0.85), otherwise the
> system should ask the user to confirm.

**Guardrail for DAAF use:** the threshold constants belong in one named dict at the top of the
script, not scattered through branches. One cookbook states the reason directly: "Every number the
routing reads lives in this dict and nowhere else, so a change of policy is a constant edit under
code review, not a reworded question."

### 5.3 Composite scoring

Source: `https://docs.typesafe.ai/patterns/composite-scoring`

> Break a complex judgment into atomic scores, combine with weights you control in code.

> Each dimension is normalized to 0–1 and weighted. The weights give you an easy way to adjust the
> relative importance of each dimension, without losing any of the nuance of the individual scores.

Normalization is by the top level index — the docs' resume example divides each `score` by 4 for a
5-level rubric, i.e. `score / (n_levels - 1)`. The payoff, verbatim:

> But more importantly, it gives you visibility into how exactly the final score is being
> calculated. If the highest ranking candidates are not matching your expectations, you can adjust
> the weights to find the right balance.

**This is the pattern most compatible with DAAF's auditability requirements**: the model produces
several narrow, independently-inspectable scores, and a reviewable weighted sum in the script
produces the composite. A single "rate this overall" question hides the same judgment inside an
unauditable black box. **Caution:** § 7 records that jev-1.13's score levels "are weak in numerical
calibration" (no jev-1.14 statement exists either way), so a composite is defensible for *ranking*
and *thresholding*, not for treating the number as a measured quantity.

### 5.4 Intent routing

Source: `https://docs.typesafe.ai/patterns/intent-routing`

> Classify incoming requests and route each to the optimal handler: deterministic logic, a
> specialist LLM, or a human.

> Rather than sending every message through an expensive LLM to figure out what kind of request it
> is, you classify first and route accordingly.

> One intent routes to deterministic code with no LLM involved. Two route to different specialist
> LLMs, each loaded with different context. One uses the complexity score to decide between an LLM
> and a human. TypeSafe handles the classification all in a single quick call; the expensive
> resources only get invoked for the requests that actually need them.

Note the page also gates on the *secondary* answer's confidence, not just the primary one:

> As discussed in Confidence, it is always important to consider the meaning of a low confidence
> score in the context of the system and the stakes of the decision.

---

## 6. When two requests are actually needed

Source: `https://docs.typesafe.ai/primitives`

> Questions in the same request are independent: one answer does not become context for another
> question. If a later judgment depends on an earlier answer, make a second request in code. The
> dependency is real only when your code cannot build the second request until it has the first
> answer: it needs the answer to fetch more data for the state, to decide what the state is made
> of, or to pick the next question's options. Otherwise, ask the questions together and combine
> their answers in code.

> Two requests are the exception, not the rule. If the second request's questions could have been
> asked against the original state, ask them in the first request and let the code ignore the ones
> it doesn't need.

The three legitimate cases the docs cite, verbatim:

> Skill suggestion ranks 182 skills in one request, then fetches the full text of the top three and
> judges them again against that better evidence. Structure recovery asks whether each line break
> split a sentence, merges lines into blocks from those answers, then classifies the blocks, which
> did not exist until the first request had answered. Hierarchical classification uses each Choice
> answer to decide which options the next request offers.

The test: **does the second request's *state* or *option set* depend on the first answer?** If not,
it is one request.

---

## 7. Known limitations ("model jaggedness")

Source: `https://docs.typesafe.ai/model-jaggedness/jev-1.13`

> **Applies to `jev-1.13`.** Last reviewed 2026-10-02.

**These are the vendor's limitations for jev-1.13.** No limitations page exists for jev-1.14
(`/model-jaggedness/jev-1.14` returned HTTP 404 on 2026-11-01), and the vendor's short link
`https://docs.typesafe.ai/go/jaggedness` redirects to the jev-1.13 page. The vendor describes
Jev 1.14 as "small, subtle improvements to everything" with "the largest gain in multi-lingual
support" (release post, 2026-10-14), which does not say which of the failure modes below still
apply. So: assume each one applies to jev-1.14
until your own pilot shows otherwise, and run the pilot checks in § 10 (including option order)
before relying on jev-1.14 for a research variable. The page is maintained, so re-fetch it before
any substantial new integration. Headline, verbatim:

> `jev-1.13` is fast, calibrated, and good at common-sense judgment but it is not perfect.
> `jev-1.13` does the best on System One tasks. It may struggle with tasks that require additional
> levels of indirection. It can be quite literal in its understanding. It struggles with tasks that
> require numeric precision.

| Failure mode | The problem (verbatim excerpt) | The prescribed fix |
|---|---|---|
| **Literal reading** | "answers the question you wrote, not the one you meant. Scoping words, negations, and implied conditions are read at face value." | "state the exact condition in the instructions. Be specific. Put boundary cases in the criteria." Split unavoidable interpretation into two literal questions and combine in code |
| **Math and numbers** | "Jev is not a calculator." | "implementing any mathematical logic in code" |
| **Counting** | "does not count reliably. This covers characters in a word, occurrences of a term in a passage, and items in a long list. The model recognizes the shape of an answer rather than tallying, and the error grows with the size of the thing being counted." | "count in code." Or iterate candidates and ask one question each, then sum yourself |
| **Numeric representations** | "questions about colors using hex values will underperform compared to those using the English names." Same for assembly vs. high-level code | "do the conversion in code and pass in either the computed number or a named bucket" |
| **Math using score** | "do not use score outputs (e.g., expectations and probability) to compute the exact magnitude of a number between two levels ... `jev-1.13`'s score levels are weak in numerical calibration." | Use the expectation only to test a threshold, never to interpolate a real quantity |
| **Date and time comparison** | "reads dates as text, not as ordered quantities. Asking which of two dates comes first, how far apart they are, or whether one falls inside a window is unreliable." | Extract date *parts* as Choices over enumerated options (with an explicit "not stated" option); assemble and compare in code |
| **Indirection** | "Instructions carrying double negatives or complex indirection are answered less reliably." | "write your instructions as directly as possible. When possible, identify the relevant parts of state by name" |
| **Large state full of irrelevant detail** | "Accuracy falls as the state grows with content unrelated to the decision. Unrelated detail acts as a distractor." | "retrieve and filter in code first, and send only the fields the question needs." A Noul relevance filter works when code filtering cannot |
| **Adversarial content** | "State is data, and `jev-1.13` does not treat it as hostile by default. Content written to adversarially steer the model ... can move the answer. We expect to improve on this in the future." | "be explicit in the criteria. Test your integration thoroughly before deploying it to many users" |
| **Contradictory instructions and criteria** | "a Noul where `true` maps to no and `false` maps to yes will perform worse." | Align criteria with instructions in clear, precise language |
| **Choice option order** | "In some cases, we observed that the order of a Choice's options can affect the answer, and `jev-1.13` leans toward the option that comes first." | "reorder the options to double check that the answer stays consistent." On a research pilot, make this a pre-specified permutation check (§ 10) |
| **Generation** | "`jev-1.13` is not trained to generate text. While you can force it to by chaining choices, this will not work well and will be very slow." | Turn extraction into a Choice over bounded options; use a different model for actual generation |

The page's own closing summary, verbatim:

> As a reminder, avoid the following:
> - Asking the model something code can compute exactly.
> - Hiding several judgments inside one question.
> - System Two tasks: more layers of indirections
> - Giving it more context in state than the question needs. Jev suffers from context rot, so
>   unrelated material in the `state` costs you accuracy.

**Context limits.** The page points to `/models`: "The `state` counts once against each of
`jev-1.13`'s context limits, the per-request context and the per-question context." Both models
allow 64k tokens for the state plus all questions and 32k for the state plus any one question
(`./api-reference.md` § 5.1).

**Language.** From `/models` (2026-11-01): "English is the primary training language and where
accuracy is currently best. Other languages, including CJK scripts, are handled but not equally
well; test on your own content before relying on Jev for a non-English workload". Validate each
language separately (§ 10).

### DAAF-specific reading of these limits

The adversarial-content admission matters directly here. Research corpora — scraped web text,
user-submitted documents, LLM-generated traces — are exactly the material that can carry injected
instructions, and Jev does not defend against that by default. Treat any `state` drawn from
untrusted sources accordingly, and note that the `classifying_rag_passages` cookbook uses Jev
itself as an injection detector, which is a mitigation, not a guarantee.

The counting and arithmetic limitations also rule out a tempting shortcut: **do not ask Jev to
compute summary statistics over a document.** Extract with Jev, aggregate in Polars.

---

## 8. Cookbooks in the vendor docs

Source: `https://docs.typesafe.ai/llms.txt` index (2026-11-01; the `/cookbooks` page lists the same
set); full text of each is in `https://docs.typesafe.ai/llms-full.txt`. Descriptions below are
**quoted from the index**, shortened with "..." where long. Image cookbooks use the
vendor-labelled "Dreamer-ready" image and `box` features (`./api-reference.md` § 6.4).

| Cookbook | What it demonstrates |
|---|---|
| `parallel_questions` | "Runs a 13-question regulatory briefing over the GDPR Wikipedia article, showing that batching every question into one TypeSafe call is 12.2x cheaper and 10.0x faster with no change in answers." |
| `classification_using_confidence` | "Classify SEC annual reports into 75 industry groups with one Choice each, then read the answer's own confidence to decide whether to report that group or the broader division above it." |
| `hierarchical_classification` | "Classifies documents through deep patent, retail product, biomedical, and source-code hierarchies using parallel beam search over TypeSafe Choice probabilities." |
| `rerank_typesafe` | "Builds 30-passage BM25 shortlists for 40 CLERC legal queries, then uses one TypeSafe question per query-candidate pair to raise top-1 accuracy from 5% to 18% and top-10 accuracy from 38% to 62%." |
| `semantic_find` | "Build semantic search for GitHub's Terms of Service. In one request, score 218 line ids against a plain-language query with a Choice question, and use a Noul question to check whether the document contains an answer." |
| `classifying_rag_passages` | "Score each retrieved passage with one TypeSafe request, then decide in code which ones reach the answering model." |
| `citation_check` | "Catch wrong or hallucinated citations by checking against the source document. One Choice question decides whether the quote's context supports the claim." |
| `llm_guardrails` | "Screens every message into and out of an LLM app with one TypeSafe request, then passes, reviews, blocks, or sends it to support by thresholds you set." |
| `date_extraction_cookbook` | "Extracts absolute and relative dates by asking TypeSafe for the parts named in a document, then resolving and validating them in code with confidence-based review." |
| `pre_parsed_value_extraction_cookbook` | "Finds candidate emails, phone numbers, and amounts with a regex, has TypeSafe pick the one you ask for, and normalizes that exact span in code." |
| `function_calling` | "Turns natural-language trading requests into calls to ordinary typed functions by mapping function names and closed-set arguments to confidence-aware TypeSafe questions." |
| `entity_alignment` | "Decides which of 450 candidate pairs from two beer catalogues describe the same product using one Score question plus three companion Nouls that surface which fields disagree." |
| `sde_cascade` | "Extracts structured data with a cheap model, checks each field with TypeSafe, and escalates to a reasoning model only when a check fires." |
| `autoformat` (Structure recovery) | "Reconstructs Markdown from plain text that lost its formatting in two requests: one stitches hard-wrapped lines back together, one classifies every block (heading, list, code, callout)." |
| `skill_suggestion` | "Picks at most one skill for an agent turn out of the 194 in Nous Research's Hermes catalog, using two TypeSafe requests to rank and re-check the top candidates." |
| `autoresearch_feature_discovery` | "Runs an autoresearch loop that proposes TypeSafe questions, converts free text into numeric features, and uses model errors to improve a supervised CatBoost regressor." |
| `consistency_noul_cookbook` | "Route uncertain probabilities to human review while keeping the underlying noul values visible." |
| `consistency_choice_cookbook` | "Add an uncertain outcome to moderation decisions and compare label agreement with the share of automatic actions." |
| `basic_memory` | "Let Jev decide which requests and answers are worth remembering, then wrap the Jev call in a small function that adds memories to later calls." |
| `cart_from_primitives` | "Turns a natural-language cafe order into a structured cart: a shrinking-options loop of Choice questions finds every item, then one batched request per item fills its known fields." |
| `intelliprompter` | "Tick off a presenter's notes as they speak: TypeSafe scores the live transcript against each note not yet covered ..." |
| `twitch_chat_filter` | "Hides insults, spam, and unasked-for gameplay tips in Twitch chat, blurs spoilers, and highlights questions. ..." |
| `reading_scanned_documents` (images) | "Find each vaccine on a scanned travel record with a Noul and a Box, read the year of each dose with a Choice that can answer unreadable, and check each dose still covers the trip in a text-only request." |
| `ocr_confidence_bounding_boxes` (images) | "Check the values an OCR extractor read from invoice photos: Jev boxes each value, scores it against the page and against a crop of its box, and flags low scores for review." |
| `feeder_watch` (images) | "Send frames from bird feeder camera footage to Jev with five questions, one of them a Box that finds the bird, then use plain code to turn the answers into a visit log per species." |

**Two design ideas worth lifting out of the list:**

- `entity_alignment`'s framing in the cookbook itself — one Score whose levels are the actions
  available for a pair (merge it, leave it unlinked, or hand it to a curator) — is the cleanest
  statement of the action-shaped-answer principle. Define the answer space as the set of *actions
  available to your code*, and the threshold-fitting problem largely disappears.
- `pre_parsed_value_extraction_cookbook` and the jaggedness page agree on the extraction idiom:
  find candidates deterministically (regex, parser), then use a Choice to *select* among them.
  Jev picks; it does not transcribe.

**Untrusted-content reminder:** cookbook code in the corpus writes local caches and fires live paid
API calls. Read it for design ideas; do not execute it.

---

## 9. Where Typesafe plausibly fits research work

Source: `https://docs.typesafe.ai/concepts/use-case-map`, "Scientific discovery" accordion,
verbatim:

> * Screen papers against inclusion and exclusion criteria for systematic reviews.
> * Label passages in interview transcripts, open-ended survey responses, and field notes using
>   predefined themes or categories.
> * Check whether cited passages support claims in manuscripts and generated summaries.
> * Flag missing methodological details, such as controls, dataset descriptions, and experimental
>   settings.
> * Identify entities and relationships across papers to build research knowledge graphs, linking
>   findings to supporting passages.

These are vendor-proposed use cases, not validated DAAF workflows.

**If Jev output enters a DAAF research artifact, it is derived data and needs the usual treatment:**

- **Pin the model version** (`jev-1.14.0` for new work, or `jev-1.13.0` for a study already
  validated on it; never `jev-latest`) and persist the response's `model` field on every row. An
  alias move silently changes results and invalidates tuned thresholds. The vendor promises 60
  days' notice before `jev-1.13.0` is deprecated (release post, 2026-10-14); no date is set.
- **A pin fixes the model, not the exact output** (`./api-reference.md` § 14). Persist the full
  response body, the request payload, and the UTC request time for every call, so the exact
  values behind a result survive even though a re-run may differ slightly.
- **Persist the full `probabilities`**, not just the winner and `confidence` — the documented
  confidence formula is one summary among several (§ 4), the vendor may change it, and re-running
  costs money.
- **Persist `usage`** so cost and token volume are auditable; keep a null count as null.
- **Persist both the vendor `choice` and the code-computed argmax**, and say in the write-up which
  one the analysis treats as the prediction (`./api-reference.md` § 14).
- **Persist a per-row retry count and final status.** Backoff absorbs 429s invisibly; without a
  `retry_count` column, "did throttled rows differ in outcome?" is untestable after the fact.
- **Validate against human coding.** Calibration is a property of groups of predictions, not of any
  single answer; a coded variable built from Jev needs the same inter-rater reliability treatment
  you would demand of any automated coder, on a human-coded subsample.
- **Disclose it.** Jev output is AI-generated classification. It belongs in the AI disclosure and
  in the limitations section, described by model version and date.
- **Nothing numeric.** No counting, no arithmetic, no date comparison, no interpolating a real
  quantity from score levels (§ 7).
- **Validate each language.** The vendor says accuracy is best in English and lower in other
  languages, including CJK scripts (§ 7). A variable coded from multilingual text needs validation
  per language, and a pooled accuracy figure can hide a weak one.
- **No image measurements without validation.** Image inputs and `box` are vendor-labelled
  "Dreamer-ready" and only smoke-tested by DAAF (`./api-reference.md` § 14); treat any image
  answer as unvalidated until checked against hand coding on your own images.

### Data handling terms

Sending research text (or images) to Typesafe discloses it to a third-party processor. Before any
research data leaves the container, confirm with the user, check that the data's consent, IRB
approval, and data-use agreements permit a third-party processor, read the vendor's current terms,
and archive a dated copy with the project (fetch them with `web_fetch.sh` into the project's
`web_fetches/`). Never send sensitive, personal, or governed text (for example FERPA or HIPAA
data); route those cases to the `synthetic-data-workflow` skill. The general governance check is in
`data-scientist` → `references/text-annotation-measurement.md` § 8.

What the vendor's documents said when read on 2026-11-01 (a summary to orient that review, not a
substitute for reading the current terms):

| Topic | Vendor text (verbatim) | Source |
|-------|------------------------|--------|
| Training | "Jev is not trained on customer requests or responses." | `https://docs.typesafe.ai/models` (Data handling) |
| Training | TypeSafe "will not, include Customer Data in a dataset used to train (i.e., to modify the model weights of) any artificial intelligence or machine learning models without Customer's prior consent." | Master Customer Agreement § 4.1, last updated 2026-09-23 (`https://typesafe.ai/legal/mca`) |
| Licence to derive data | A licence "in perpetuity, any Customer Data (i) to derive and generate Telemetry, (ii) to monitor for fraud and abuse of the Services, and (iii) as necessary to comply with applicable Laws." | MCA § 4.1 |
| Telemetry | "'Telemetry' means information generated in connection with the Services, such as technical logs, hashes, summary statistics and classifications, metrics, and learnings related to Customer's use of the Services. TypeSafe may Process Telemetry without restriction, including to improve the Services" | MCA § 4.3 |
| Retention | "Customer Personal Data will be retained for as long as necessary taking into account the purpose of the Processing, and in compliance with applicable laws" | Data Processing Addendum, last updated 2026-04-24 (`https://typesafe.ai/legal/data-processing`) |
| Retention | "We retain personal data about you for as long as reasonably necessary to provide you with the Services, or otherwise in support of our business or commercial purposes." | Privacy Policy, last updated 2025-11-19 (`https://typesafe.ai/legal/privacy-policy`) |
| Zero data retention | "We also offer zero data retention (ZDR) for enterprise customers." | `https://docs.typesafe.ai/legal` |
| Query sharing | "We've added an opt-in to allow you to help find model jaggedness with your queries. We will still not train on your queries". Where the opt-in is set, and its default, are not documented (2026-11-01) | Jev 1.14 release post, 2026-10-14 |

Two points matter most for research data. "Summary statistics and classifications" derived from
your requests are Telemetry the vendor may process "without restriction", and that derivation
right is perpetual — so "not used for training" does not mean "not retained or reused". Zero data
retention is offered to enterprise customers; assume a standard account has none. Before a
research run, ask the user whether the account's query-sharing opt-in is on; the docs do not say
where it is set.

---

## 10. Evaluating fit for your task

How well Jev serves a particular task is data- and context-dependent: it varies with the option
set, the class balance, the length and noise of the `state`, the model version, and what the
application does with the answer. This section lists things to think about and verify, not
results to rely on. Wire-level checks (rounding, argmax, headers, rate limits, auth) are in
`./api-reference.md` § 14 "Things to verify on your own calls".

**Start with a labelled pilot.** Before committing to a design, run a representative, human-labelled
sample — large enough for the comparisons you plan, including per-class ones — through the exact
question set and pinned model version you intend to use, persisting the full response per item
(`model`, `usage`, `probabilities`, `choice`, `confidence`, retry count), the request payload, and
the request time. Every check below runs on that pilot, and the same file later documents the
design decision. On jev-1.14.0 the pilot is the only evidence of fit: the vendor's limitations page
covers jev-1.13 only (§ 7). Pilot calls cost money — confirm the size with the user first.

**Pre-specify the checks.** Decide before the pilot which of the checks below you will run (at
least option order, repeat calls, and per-class accuracy), with what sample and what counts as a
problem. A check chosen after seeing the results is easy to tune toward a good-looking number.

### Option order

The vendor documents a primacy lean for jev-1.13 — "the order of a Choice's options can affect the
answer, and `jev-1.13` leans toward the option that comes first" — and recommends reordering the
options to check consistency (§ 7). Make that a pre-specified permutation check on the pilot:

- Run the same labelled items with the options in two or more orders (for example as written,
  reversed, and one fixed random shuffle), keeping names, descriptions, and instructions identical.
- Measure agreement across orders and, for each order, how often each option position is chosen;
  a choice rate that tracks position rather than content is the warning sign.
- Fix the order you will use in production (or randomize it per item and record it) before the
  main run, and report the agreement figure.

This is the option-order check that `data-scientist` → `references/text-annotation-measurement.md`
§ 5 recommends for any annotator choosing from a fixed option set ("Run several option
permutations and measure agreement across them. No single order is neutral"). It applies to
jev-1.14 too until a pilot shows otherwise, since no jev-1.14 limitations page exists.

### Repeat calls

Identical requests pinned to one version are not bit-identical (`./api-reference.md` § 14), and
DAAF's small sample shows the effect exists, not its size on your data. Include a few repeat calls
per item for a subset of the pilot, and check:

- how often the decision your code makes (a `choice`, a threshold crossing) flips between repeats;
- whether items near your thresholds flip more often than others.

If decisions flip, widen the review band around the threshold or report the repeat-agreement rate
with the results. Either way, the persisted response — not a re-run — is the record of what the
analysis used.

### Confidence: band or ranking?

`confidence` is reported at 2 decimals, and a Choice's `confidence` depends only on its top
probability and option count (§ 4), so it may take few distinct values and form large tie blocks.
Before using it to **rank**, route the top-k, "act on the most confident X%," or draw
coverage-accuracy curves:

- Count the distinct `confidence` values and the size of the largest tie blocks (especially at the
  top). A coverage curve over a heavily tied score is a staircase, and "the top 10%" may be one
  undifferentiated block.
- Banded thresholds (§ 4's three-band usage, § 5.2's floor plus per-action gates) can still work on
  a coarse grid — check accuracy *within* each band on the pilot.
- If you need a finer ranking, a statistic derived from the full distribution (the vendor's
  top-to-second ratio, a top-2 margin, entropy) may help but inherits the same rounding;
  recalibration against held-out labels (e.g. isotonic regression) is the other option. Measure
  either on held-out data.

### Metric choice under rounded probabilities

Rounded probabilities can be exactly `0.00`, including for the true label. Log-loss and NLL on raw
values are then infinite or undefined:

- If you report a log-scale metric, floor or clip the probabilities first (e.g. to half the grid
  step), say so, and recognise that the number then partly reflects the floor you chose.
- Brier score and expected calibration error (ECE) do not need flooring and are often the better
  default.
- When comparing against a model that emits continuous probabilities, state the rounding
  explicitly: the comparison is not like-for-like, especially for log-scale and ranking metrics.

### Calibration: which event?

The vendor describes `confidence` and `probabilities` as calibrated, and "calibration is measured
across groups of predictions" (§ 4). Calibration also depends on **which event you score
against**. With a single gold label, "the chosen option is the gold label" is one event; with a
multi-label truth (several acceptable answers per item), "the chosen option is *any* acceptable
label" is a different event with a different calibration curve. Compute calibration for the event
your application actually acts on, and say which one in the write-up.

### Batching many items into one call

A `state` can be an array, so several items can share one call (one question per item). This
trades tokens against possible accuracy change, and the trade is workload-specific:

- Accuracy may shift relative to single-item calls, plausibly more so for large option sets with
  long per-option criteria. Moving shared criteria into the `state` saves more tokens but means
  the model no longer sees the rubric attached to the question it is answering.
- Long batches with repeated criteria can run into the context limits (§ 7: 64k tokens for the
  state plus all questions, 32k for the state plus any one question).
- Check for **positional effects** — does an item late in the batch score like the same item
  placed first?
- Pilot batched vs single-item calls on the same labelled items with a paired comparison before
  adopting batching. Note this is different from batching *questions* about one state (§ 5.1),
  which the vendor documents as the default.

### Instruction wording vs option criteria

Wording effects should be measured, not assumed. A reasonable hypothesis to check — consistent
with the vendor's "treat the criteria as an extension of the instruction" (§ 2) — is that for
classification with well-specified option criteria, the completeness and discriminating detail of
the **option set** (including an `other` escape hatch) matter more than how the `instructions`
are phrased. Test it on your task: run instruction variants over the same labelled items with
identical option sets, and compare with a paired test rather than eyeballing two accuracies. A
task whose difficulty lives in the question rather than the answer space may behave differently.

### Class-level checks

Aggregate accuracy can hide where a classifier fails. On the pilot:

- Build a per-class confusion matrix. Option sets with **semantically overlapping categories**
  deserve particular attention — confusion concentrates between neighbours, and sharpening the
  criteria that separate them is often the fix.
- Check **rare classes** separately; with few pilot examples their accuracy estimates are noisy,
  so report counts alongside rates.
- If the text spans **several languages**, report accuracy per language; the vendor says
  non-English accuracy is lower (§ 7).
- If an escape hatch is part of the design (`other`, or a companion Noul, § 3), include
  out-of-scope items in the pilot and measure how often each kind of miss happens.
- When comparing against a **trained classifier**, the trade-off can depend on how much labelled
  training data each class has: a supervised model may do well on well-supported classes and
  poorly on sparse ones, and a criteria-driven model may not follow the same pattern. Evaluate on
  your own data, stratified by class support, rather than relying on a single headline number
  from anyone else's comparison.

### Cost against value

Estimate cost from `usage.input_tokens` on the pilot (`./api-reference.md` § 11). For large option
sets the `criteria` text tends to dominate input tokens, so trimming criteria saves money but may
change accuracy — measure both on the same pilot before choosing.
