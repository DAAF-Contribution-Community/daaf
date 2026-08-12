# DAAFBench Changelog

A plain-language record of notable changes to the DAAFBench: Orchestration
report — new models, pricing updates, scoring changes, display refinements,
and corpus hygiene. Newest entries first. Dates are the day each change landed
in the public report.

## 2026-08-12

- **Models** Added xAI Grok 4.6 and DeepSeek V4 Pro (0813). The preview
  version of DeepSeek V4 Pro stays in the matrix for side-by-side comparison
  with its revision.

## 2026-08-11

- **Pricing** GPT-5.6 Terra and Luna are now cheaper: OpenAI cut their list
  prices. Costs in this report reflect the current, lower prices.
- **Corpus** Fully removed the earlier, undated DeepSeek V4 Flash from the
  report. It was replaced by the DeepSeek V4 Flash (0731) revision on
  2026-08-02, and its historical runs no longer appear in the leaderboard,
  costs, or takeaways.
- **Display** Added this changelog, reachable from the button beside the report
  date.

## 2026-08-10

- **Models** Added Thinking Machines Inkling and Inkling Small.
- **Corpus** Refreshed the billing figures behind the cost estimates from an
  up-to-date spending export.

## 2026-08-03

- **Scoring** Refined the reliability takeaway so it uses the same
  consistency measure shown in the leaderboard, for a clearer read.

## 2026-08-02

- **Models** Added DeepSeek V4 Flash (0731) and retired the earlier, undated
  DeepSeek V4 Flash entry.
- **Corpus** Reconciled costs against the latest billing export.

## 2026-07-29

- **Scoring** Overhauled the Key Takeaways for the July 2026 field, corrected
  several scoring definitions for fairer comparisons, and added a
  run-to-run consistency measure.
- **Display** Extended cost estimates to the full model fleet and ran a broad
  visual cleanup pass; removed the relative-duration leaderboard column.
- **Corpus** Removed several unusable runs flagged during a billing and
  scoring audit so they no longer affect the results.

## 2026-07-27

- **Models** Added Gemini 3.5 Flash, Gemini 3.6 Flash, Gemini 3.5 Flash Lite,
  and Gemini 2.5 Pro.

## 2026-07-25

- **Models** Added Claude Opus 5.

## 2026-07-21

- **Scoring** Made the headline metrics ignore timed-out runs and added an
  estimated time-to-run-the-battery figure.
- **Corpus** Applied a uniform time limit to every run for consistency.

## 2026-07-17

- **Models** Added Kimi K3 and corrected its pricing from the provider's
  published rates.

## 2026-07-10

- **Models** Ran a GPT model evaluation and added the GPT-5.6 family (Sol,
  Terra, and Luna); dropped the GPT "pro" variants that could not complete the
  battery.

## 2026-07-02

- **Models** Added Sonnet 5.

## 2026-06-18

- **Display** Fine-tuned the report layout and interactivity for the public
  release.
- **Corpus** Fixed a cost-averaging issue so timed-out runs no longer depress
  per-run cost estimates.

## 2026-06-17

- **Models** Added GLM 5.2 and Kimi K2.7 Code.

## 2026-06-12

- **Display** First public release of the DAAFBench: Orchestration report, with
  the leaderboard, cost-versus-performance view, per-phase deep dives, and the
  battery-cost headline.
