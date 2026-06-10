# Archive

Legacy benchmark components retained for reference. Nothing in this folder is
imported or executed by the current benchmark system.

| Item | What it was | Why archived |
|------|-------------|--------------|
| `runner.py` | Generic matrix runner with budget enforcement (design per `Benchmark_System_Reference.md` §6.1) | Superseded by the three standalone phase scripts in `scripts/` (`run_mode_classification.py`, `run_post_confirmation.py`, `run_dispatch_compliance.py`). Its companion `aggregator.py` was never built. |
| `cost_budget.yaml` | Budget caps consumed by `runner.py`'s halting logic | Only referenced by the archived runner. Current phase scripts use interactive cost confirmation via `harness/cost_estimator.py` instead. |
| `run_benchmark.sh` | Shell entry point wrapping `python3 -m benchmarks.harness.runner` | Wrapper for the archived runner; invoking it now would fail. Use the per-phase scripts in `scripts/` directly. |
| `golden_mode_classification/` | Per-case golden checkpoints (`mc-01.jsonl` … `mc-15.jsonl`) for a bootstrap-checkpoint Phase 1 design | Phase 1 now runs cold-start (`CHECKPOINT_LINES = 0` in `run_mode_classification.py`); these checkpoints are unused. `golden/bootstrap_template.jsonl` remains active (referenced by `scripts/generate_goldens.py`). |
