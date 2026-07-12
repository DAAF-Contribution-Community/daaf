#!/usr/bin/env bash
# test-safety-hooks.sh — regression battery for the installed bash-safety.sh
# and gws-safety.sh hooks. Run after any hook change: bash scripts/test-safety-hooks.sh
# Test-case strings live in this FILE (not on a command line) so the live
# hooks never see them when the script is invoked.
set -uo pipefail

FAIL=0

run_case() {
    local hook="$1" expect="$2" desc="$3" cmd="$4"
    local out rc verdict="ALLOW"
    out=$(jq -n --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c}}' | bash "$hook" 2>&1); rc=$?
    if [[ $rc -eq 2 ]]; then verdict="BLOCK"
    elif echo "$out" | grep -q '"permissionDecision": *"ask"'; then verdict="ASK"; fi
    if [[ "$verdict" == "$expect" ]]; then
        printf 'PASS  %-5s %s\n' "$verdict" "$desc"
    else
        printf 'FAIL  got=%-5s want=%-5s %s\n' "$verdict" "$expect" "$desc"
        FAIL=1
    fi
}

# Optional positional overrides let the battery run against DRAFT hooks
# (e.g. bash scripts/test-safety-hooks.sh scratch/bash-safety.sh scratch/gws-safety.sh)
# before the user installs them into .claude/hooks/ (which is write-protected).
B="${1:-${CLAUDE_PROJECT_DIR:-/workspace}/.claude/hooks/bash-safety.sh}"
G="${2:-${CLAUDE_PROJECT_DIR:-/workspace}/.claude/hooks/gws-safety.sh}"

echo "=== bash-safety: tampering guard ==="
run_case "$B" BLOCK "cp into hooks"            'cp scratch/x.sh .claude/hooks/x.sh'
run_case "$B" BLOCK "cp abs path into hooks"   'cp /tmp/a.sh "$CLAUDE_PROJECT_DIR"/.claude/hooks/b.sh'
run_case "$B" BLOCK "mv into hooks"            'mv a.sh /workspace/.claude/hooks/a.sh'
run_case "$B" BLOCK "rm a hook"                'rm .claude/hooks/gws-safety.sh'
run_case "$B" BLOCK "chmod a hook"             'chmod -x .claude/hooks/bash-safety.sh'
run_case "$B" BLOCK "redirect into hooks"      'echo x > .claude/hooks/h.sh'
run_case "$B" BLOCK "append into logs"         'echo y >> /workspace/.claude/logs/audit.jsonl'
run_case "$B" BLOCK "tee into hooks"           'cat a.sh | tee .claude/hooks/h.sh'
run_case "$B" BLOCK "sed -i on hook"           'sed -i "s/block/allow/" .claude/hooks/bash-safety.sh'
run_case "$B" BLOCK "chained cp into hooks"    'cd /workspace && cp x.sh .claude/hooks/y.sh'
run_case "$B" BLOCK "touch in logs"            'touch .claude/logs/fake.log'
echo "=== bash-safety: tampering guard must NOT catch ==="
run_case "$B" ALLOW "ls hooks"                 'ls -la .claude/hooks'
run_case "$B" ALLOW "cat a hook"               'cat .claude/hooks/bash-safety.sh'
run_case "$B" ALLOW "grep a hook"              'grep -n block .claude/hooks/bash-safety.sh'
run_case "$B" ALLOW "run a hook for testing"   'echo "{}" | bash .claude/hooks/context-reporter.sh'
run_case "$B" ALLOW "git add hook"             'git add .claude/hooks/gws-safety.sh'
run_case "$B" ALLOW "git update-index chmod"   'git update-index --chmod=+x .claude/hooks/gws-safety.sh'
run_case "$B" ALLOW "git ls-files hooks"       'git ls-files -s .claude/hooks/gws-safety.sh'
run_case "$B" ALLOW "cp elsewhere"             'cp scratch/a.sh scratch/b.sh'
run_case "$B" ALLOW "redirect elsewhere"       'echo hello > out.txt'
echo "=== bash-safety: package installs ==="
run_case "$B" BLOCK "pip install"              'pip install requests'
run_case "$B" BLOCK "pip3 install"             'pip3 install numpy pandas'
run_case "$B" BLOCK "pip uninstall"            'pip uninstall -y requests'
run_case "$B" BLOCK "python -m pip install"    'python -m pip install requests'
run_case "$B" BLOCK "python3 -m pip w/ flag"   'python3 -u -m pip install --user requests'
run_case "$B" BLOCK "uv pip install"           'uv pip install httpx'
run_case "$B" BLOCK "uv add"                   'uv add httpx'
run_case "$B" BLOCK "uv sync"                  'uv sync'
run_case "$B" BLOCK "uv tool install"          'uv tool install ruff'
run_case "$B" BLOCK "uvx"                      'uvx ruff check .'
run_case "$B" BLOCK "pipx install"             'pipx install poetry'
run_case "$B" BLOCK "conda install"            'conda install scipy'
run_case "$B" BLOCK "chained pip install"      'cd /tmp && pip install requests'
echo "=== bash-safety: package cmds that must stay ALLOWED ==="
run_case "$B" ALLOW "pip list"                 'pip list'
run_case "$B" ALLOW "pip show"                 'pip show numpy'
run_case "$B" ALLOW "pip freeze"               'pip freeze'
run_case "$B" ALLOW "uv --version"             'uv --version'
run_case "$B" ALLOW "python script"            'python3 scripts/transcribe.py meeting.mkv'
run_case "$B" ALLOW "echo mentioning pip"      'echo pip install is blocked here'
echo "=== bash-safety: /tmp provenance boundary (write-gated) ==="
run_case "$B" BLOCK "redirect into /tmp"       'echo hi > /tmp/x.txt'
run_case "$B" BLOCK "append into /tmp"         'python3 gen.py >> /tmp/out.log'
run_case "$B" BLOCK "stderr into /tmp"         'python3 x.py 2> /tmp/err.log'
run_case "$B" BLOCK "tee into /tmp"            'cat a.txt | tee /tmp/out.txt'
run_case "$B" BLOCK "cp dest /tmp"             'cp file.txt /tmp/'
run_case "$B" BLOCK "mv dest /tmp"             'mv a.txt /tmp/b.txt'
run_case "$B" BLOCK "mkdir in /tmp"            'mkdir -p /tmp/workdir'
run_case "$B" BLOCK "touch in /tmp"            'touch /tmp/marker'
run_case "$B" BLOCK "curl -o into /tmp"        'curl -o /tmp/f.zip https://example.com/f.zip'
run_case "$B" BLOCK "sed -i on /tmp file"      'sed -i "s/a/b/" /tmp/f.txt'
run_case "$B" BLOCK "tar -C /tmp"              'tar -xf a.tar -C /tmp'
run_case "$B" BLOCK "git clone into /tmp"      'git clone https://github.com/x/y /tmp/repo'
run_case "$B" BLOCK "dd of=/tmp"               'dd if=disk.img of=/tmp/copy.img'
run_case "$B" BLOCK "ln link in /tmp"          'ln -s /workspace/f /tmp/link'
run_case "$B" BLOCK "ln target in /tmp"        'ln -s /tmp/target projectlink'
echo "=== bash-safety: /tmp reads + rescue must stay ALLOWED ==="
run_case "$B" ALLOW "cat /tmp cache"           'cat /tmp/claude-ctx-window-cache'
run_case "$B" ALLOW "rescue cp /tmp to project" 'cp /tmp/claude-model-x scratch/rescued.txt'
run_case "$B" ALLOW "ls -ln /tmp (ln flag)"    'ls -ln /tmp'
run_case "$B" ALLOW "grep in /tmp"             'grep foo /tmp/log.txt'
run_case "$B" ALLOW "read /tmp redirect to project" 'cat /tmp/x.json > scratch/y.json'
run_case "$B" ALLOW "head /tmp pipe jq"        'head -c 200 /tmp/x.json | jq .'
echo "=== bash-safety: regressions on original rules ==="
run_case "$B" BLOCK "force push"               'git push --force origin main'
run_case "$B" BLOCK "rm -rf root"              'rm -rf /'
run_case "$B" BLOCK "sudo"                     'sudo apt update'
run_case "$B" ALLOW "plain git push"           'git push origin main'
run_case "$B" ALLOW "targeted rm"              'rm scratch/old-draft.md'
echo "=== gws-safety: credential access ==="
run_case "$G" BLOCK "cat the key"              'cat /home/appuser/.claude/gws/service-account.json'
run_case "$G" BLOCK "python opens key path"    'python3 -c "print(open(\"/home/appuser/.claude/gws/service-account.json\").read())"'
run_case "$G" BLOCK "ls config dir"            'ls -la ~/.claude/gws'
run_case "$G" BLOCK "token cache"              'cat /home/appuser/.claude/gws/sa_token_cache.json'
run_case "$G" BLOCK "env var reference"        'echo $GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE'
run_case "$G" BLOCK "python env var indirection" 'python3 -c "import os; print(open(os.environ[\"GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE\"]).read())"'
run_case "$G" BLOCK "google.oauth2 import"     'python3 -c "from google.oauth2 import service_account"'
run_case "$G" BLOCK "google.auth import"       'python3 -c "import google.auth; print(google.auth.default())"'
run_case "$G" BLOCK "googleapiclient"          'python3 -c "from googleapiclient.discovery import build"'
run_case "$G" BLOCK "gws auth export chained"  'cd /tmp && gws auth export > creds.json'
echo "=== gws-safety: must NOT catch (Gemini SDK + normal work) ==="
run_case "$G" ALLOW "google.genai import"      'python3 -c "from google import genai"'
run_case "$G" ALLOW "google-genai module"      'python3 -c "import google.genai as genai"'
run_case "$G" ALLOW "transcribe pipeline"      'python3 .claude/skills/meeting-transcription/scripts/transcribe.py rec.mkv'
run_case "$G" ALLOW "gws files list"           'gws drive files list --params "{\"fields\":\"files(id,name)\"}"'
run_case "$G" ALLOW "gws export"               'gws drive files export --params "{\"fileId\":\"d\",\"mimeType\":\"text/markdown\"}" -o out.md'
echo "=== gws-safety: regressions on destructive-op rules ==="
run_case "$G" BLOCK "files delete"             'gws drive files delete --params "{\"fileId\":\"abc\"}"'
run_case "$G" BLOCK "trash via update"         'gws drive files update --params "{\"fileId\":\"a\"}" --json "{\"trashed\": true}"'
run_case "$G" BLOCK "gmail send"               'gws gmail users messages send --params "{\"userId\":\"me\"}"'
run_case "$G" ASK   "permissions update"       'gws drive permissions update --params "{\"fileId\":\"a\",\"permissionId\":\"p\"}" --json "{\"role\":\"reader\"}"'
run_case "$G" ASK   "files update rename"      'gws drive files update --params "{\"fileId\":\"a\"}" --json "{\"name\":\"new\"}"'
run_case "$G" ALLOW "docs batchUpdate"         'gws docs documents batchUpdate --params "{\"documentId\":\"d\"}" --json "{\"requests\":[]}"'

echo
if [[ $FAIL -eq 0 ]]; then echo "ALL TESTS PASSED"; else echo "FAILURES PRESENT"; exit 1; fi
