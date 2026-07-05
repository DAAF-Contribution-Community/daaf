#!/usr/bin/env bash
# Test harness: run each script/fixture pair, report exit codes.
# Not a framework artifact — a throwaway test driver for the statusline upgrade.
set -u
FX=/daaf/research/2026-07-05_FrameworkDev_StatuslineUpgrade/test_fixtures
CB=/daaf/.claude/scripts/context-bar.sh
SB=/daaf/.claude/scripts/subagent-bar.sh

for f in cb_a_full cb_b_minimal cb_c_ratelimit_75_iso cb_c2_ratelimit_95_epoch cb_d_no_transcript; do
    bash "$CB" < "$FX/$f.json" > /dev/null 2>&1
    echo "context-bar $f -> exit=$?"
done

bash "$SB" < "$FX/sb_a_varied.json" > /dev/null 2>&1
echo "subagent-bar sb_a_varied -> exit=$?"

bash "$SB" < "$FX/sb_b_empty_tasks.json" > /dev/null 2>&1
echo "subagent-bar sb_b_empty_tasks -> exit=$?"

bash "$SB" < "$FX/sb_c_garbage.txt" > /dev/null 2>&1
echo "subagent-bar sb_c_garbage -> exit=$?"

printf '' | bash "$SB" > /dev/null 2>&1
echo "subagent-bar empty-stdin -> exit=$?"
