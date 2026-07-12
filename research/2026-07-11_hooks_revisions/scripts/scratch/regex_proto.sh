#!/usr/bin/env bash
# Prototype the §7/§8 regexes in isolation (no hook JSON envelope).
set -uo pipefail

# --- §7 building blocks ---
PSEP='/+(\./+)*'
PROTECTED_DIRS="(\.claude${PSEP}(hooks|logs)|benchmarks${PSEP}harness${PSEP}hooks|\.claude${PSEP}settings(\.local)?\.json)"
COPY_END="(/[^ ;|&<>]*)? *\$"

echo "=== §7 copy-verb (end-anchored) tests ==="
COPY_RE="(^|[;&|]) ?(cp|mv|rsync|install) [^|;&<>]*${PROTECTED_DIRS}${COPY_END}"
for t in \
  'cp evil.sh .claude//hooks/x.sh|BLOCK' \
  'cp evil.sh .claude/./hooks/x.sh|BLOCK' \
  'cp evil.sh .claude/hooks/x.sh|BLOCK' \
  'rsync evil.sh .claude/hooks/|BLOCK' \
  'cp .claude/settings.json backup.json|ALLOW' \
  'cp .claude/hooks/bash-safety.sh /daaf/research/backup.sh|ALLOW' \
  'cp evil.sh benchmarks//harness/hooks/x.sh|BLOCK' \
  'mv a.sh /daaf/.claude/hooks/a.sh|BLOCK' \
  'cp evil.json .claude/settings.json|BLOCK' \
  'cp scratch/a.sh scratch/b.sh|ALLOW' \
  'cp template.md research/2026-01-01_Project/|ALLOW' \
  ; do
  cmd="${t%|*}"; want="${t##*|}"
  if echo "$cmd" | grep -qiE "$COPY_RE"; then got=BLOCK; else got=ALLOW; fi
  [[ "$got" == "$want" ]] && s=ok || s=XX
  printf '%s  got=%-5s want=%-5s  %s\n' "$s" "$got" "$want" "$cmd"
done

echo "=== §7 target-verb (match-anywhere) tests ==="
TARGET_RE="(^|[;&|]) ?(rm|ln|dd|tee|touch|truncate|chmod|chown|chattr) [^|;&<>]*${PROTECTED_DIRS}"
for t in \
  'rm .claude/hooks/bash-safety.sh|BLOCK' \
  'chmod -x .claude/hooks/bash-safety.sh|BLOCK' \
  'touch .claude/logs/fake.log|BLOCK' \
  'rm .claude//hooks/x.sh|BLOCK' \
  'ls -la .claude/hooks|ALLOW' \
  ; do
  cmd="${t%|*}"; want="${t##*|}"
  if echo "$cmd" | grep -qiE "$TARGET_RE"; then got=BLOCK; else got=ALLOW; fi
  [[ "$got" == "$want" ]] && s=ok || s=XX
  printf '%s  got=%-5s want=%-5s  %s\n' "$s" "$got" "$want" "$cmd"
done

echo "=== §7 tee (match-anywhere target) — note tee is in target group ==="
# tee into hooks: 'cat a.sh | tee .claude/hooks/h.sh' — after pipe, segment start
for t in \
  'cat a.sh | tee .claude/hooks/h.sh|BLOCK' \
  ; do
  cmd="${t%|*}"; want="${t##*|}"
  if echo "$cmd" | grep -qiE "$TARGET_RE"; then got=BLOCK; else got=ALLOW; fi
  [[ "$got" == "$want" ]] && s=ok || s=XX
  printf '%s  got=%-5s want=%-5s  %s\n' "$s" "$got" "$want" "$cmd"
done

echo "=== §7 redirect + sed -i (unchanged shape, PSEP applied) ==="
REDIR_RE=">>? ?[^ ]*${PROTECTED_DIRS}"
for t in \
  'echo x > .claude/hooks/h.sh|BLOCK' \
  'echo y >> /daaf/.claude/logs/audit.jsonl|BLOCK' \
  'echo x > benchmarks/harness/hooks/x.sh|BLOCK' \
  'echo "{}" > .claude/settings.json|BLOCK' \
  ; do
  cmd="${t%|*}"; want="${t##*|}"
  if echo "$cmd" | grep -qiE "$REDIR_RE"; then got=BLOCK; else got=ALLOW; fi
  [[ "$got" == "$want" ]] && s=ok || s=XX
  printf '%s  got=%-5s want=%-5s  %s\n' "$s" "$got" "$want" "$cmd"
done

SED_RE="\bsed [^|;&]*-i[^|;&]*${PROTECTED_DIRS}"
for t in \
  'sed -i "s/block/allow/" .claude/hooks/bash-safety.sh|BLOCK' \
  'sed -i "s/deny/allow/" .claude/settings.json|BLOCK' \
  ; do
  cmd="${t%|*}"; want="${t##*|}"
  if echo "$cmd" | grep -qiE "$SED_RE"; then got=BLOCK; else got=ALLOW; fi
  [[ "$got" == "$want" ]] && s=ok || s=XX
  printf '%s  got=%-5s want=%-5s  %s\n' "$s" "$got" "$want" "$cmd"
done

echo "=== §8 python matcher ==="
PY_RE='\b(python[0-9.]*|py) [^|;&]*-m pip (install|uninstall)\b'
for t in \
  'python3.11 -m pip install requests|BLOCK' \
  'python -W ignore -m pip install requests|BLOCK' \
  'py -m pip install requests|BLOCK' \
  'python3 -u -m pip install --user requests|BLOCK' \
  'python -m pip install requests|BLOCK' \
  'python3 scripts/run_with_capture.sh 01_fetch.py|ALLOW' \
  ; do
  cmd="${t%|*}"; want="${t##*|}"
  if echo "$cmd" | grep -qiE "$PY_RE"; then got=BLOCK; else got=ALLOW; fi
  [[ "$got" == "$want" ]] && s=ok || s=XX
  printf '%s  got=%-5s want=%-5s  %s\n' "$s" "$got" "$want" "$cmd"
done

echo "=== §8 pip/pipx ==="
PIP_RE='(^|[;&|]) ?(pip3?|pipx) (install|uninstall|run|runpip)\b'
for t in \
  'pip install requests|BLOCK' \
  'pipx run black .|BLOCK' \
  'pipx install poetry|BLOCK' \
  'pip download requests|ALLOW' \
  'pip list|ALLOW' \
  ; do
  cmd="${t%|*}"; want="${t##*|}"
  if echo "$cmd" | grep -qiE "$PIP_RE"; then got=BLOCK; else got=ALLOW; fi
  [[ "$got" == "$want" ]] && s=ok || s=XX
  printf '%s  got=%-5s want=%-5s  %s\n' "$s" "$got" "$want" "$cmd"
done

echo "=== §8 conda + uvx/easy_install ==="
CONDA_RE='(^|[;&|]) ?uvx\b|\beasy_install\b|\bconda (install|remove|update|create|env (update|create))\b'
for t in \
  'conda install scipy|BLOCK' \
  'conda env update -f environment.yml|BLOCK' \
  'conda create -n test numpy|BLOCK' \
  'uvx ruff check .|BLOCK' \
  'easy_install foo|BLOCK' \
  ; do
  cmd="${t%|*}"; want="${t##*|}"
  if echo "$cmd" | grep -qiE "$CONDA_RE"; then got=BLOCK; else got=ALLOW; fi
  [[ "$got" == "$want" ]] && s=ok || s=XX
  printf '%s  got=%-5s want=%-5s  %s\n' "$s" "$got" "$want" "$cmd"
done

echo "=== §8 uv (existing) + uv run --with ==="
UV_RE='(^|[;&|]) ?uv (pip (install|uninstall|sync)|add|remove|sync|tool (install|run))\b'
UVRUN_RE='(^|[;&|]) ?uv run [^|;&]*--with\b'
for t in \
  'uv pip install httpx|BLOCK' \
  'uv run --with requests script.py|BLOCKrun' \
  'uv run script.py|ALLOW' \
  ; do
  cmd="${t%|*}"; want="${t##*|}"
  got=ALLOW
  if echo "$cmd" | grep -qiE "$UV_RE"; then got=BLOCK; fi
  if [[ "$got" == ALLOW ]] && echo "$cmd" | grep -qiE "$UVRUN_RE"; then got=BLOCKrun; fi
  # normalize BLOCKrun→BLOCK for uv pip case
  [[ "$want" == BLOCKrun ]] && wantn=BLOCKrun || wantn="$want"
  gotn="$got"
  [[ "$got" == BLOCK && "$want" == BLOCKrun ]] && gotn=BLOCK
  # simpler: treat both BLOCK variants as BLOCK
  g2="$got"; [[ "$g2" == BLOCKrun ]] && g2=BLOCK
  w2="$want"; [[ "$w2" == BLOCKrun ]] && w2=BLOCK
  [[ "$g2" == "$w2" ]] && s=ok || s=XX
  printf '%s  got=%-7s want=%-7s  %s\n' "$s" "$got" "$want" "$cmd"
done
