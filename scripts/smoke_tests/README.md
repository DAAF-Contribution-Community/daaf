# Library smoke tests

These scripts check that the libraries DAAF's skills rely on are installed and behave as the skills describe. Run the whole set from the DAAF root with `bash scripts/smoke_tests/run_all_smoke_tests.sh`.

- **What the runner does.** For each `smoke_*.R` and `smoke_*.py` family it runs only the latest revision (`_a`, `_b`, ...). R smokes run through `scripts/run_with_capture.sh`; Python smokes run with `python3` directly. As of 2026-10-27 every R smoke here already carries an appended execution log, so an in-place run reports the R smokes as SKIP (already logged) and runs the Python ones.
- **Running the R smokes live.** Stage log-stripped copies of the smokes and set `SMOKE_DIR` to their folder, as CI does (`.github/workflows/ci-integration.yml`, step "Stage log-stripped smoke copies"). Keep invoking the runner from this folder: it locates `run_with_capture.sh` from its own location, not from `SMOKE_DIR`.
- **Temporary files.** A smoke test writes its temporary files to `/daaf/scripts/scratch/smoke_<family>_work/`, never to `/tmp`. The test creates the folder when it starts and deletes it when it finishes. A failed run can leave the folder behind, and the next run clears it first. The path is fixed because smoke tests run only inside the DAAF container, staged CI copies included. One test differs: `smoke_svy_a.py` writes to `scripts/scratch/smoke_svy_io/` and does not clear a leftover folder first.

**Historical comments in logged files.** Files with an appended execution log are immutable (CLAUDE.md § Versioning & Naming), so some header comments are out of date:

- `smoke_r_stats_b.R`, `smoke_skimr.R` and `smoke_tidymodels_b.R` tell you to set `R_LIBS_USER` (and, for tidymodels, `LD_LIBRARY_PATH`) to a scratch library inside a maintainer research workspace (maintainer-only workspace, not shipped: `research/2026-07-06_FrameworkDev_R_Support/`). **Ignore this.** It was a stopgap from before the image shipped `tseries`, `skimr`, `kknn`, `vip` and `libglpk40`. The current image has all of them, so these tests need no environment setup, as the last line of each header already says.
- The `research/...` pointers in `smoke_pyfixest.py`, `smoke_pyfixest_a.py` and `smoke_imports_d.py` name maintainer-only workspaces that do not ship. The claims in those headers stand without them.

**`xval_svy_survey_r/`** holds the svy-versus-R `survey` cross-validation scripts cited by the `svy` skill's references. They keep their 2026-07-15 execution logs, so a re-run needs a revision made with `scripts/create_script_revision.sh`. The runner does not run them; it reads only this folder's top level.
