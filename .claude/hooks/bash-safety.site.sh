# shellcheck shell=bash disable=SC2034
# bash-safety.site.sh — DAAF's site settings for the bash-safety.sh hook
#
# bash-safety.sh (the file next to this one) is identical at every site that
# runs it. It sources THIS file at startup for the values that differ per site;
# the contract (required and optional settings, the optional
# site_extension_guards function, the stable interface it may use) is in that
# file's header, under SITE FILE CONTRACT.
#
# Fail-closed: if this file is missing, unreadable, fails to load (a syntax
# error or a failing command), leaves SITE_ROOT empty or malformed, or lists
# a malformed SITE_EXTRA_PROTECTED_DIRS entry, the hook BLOCKS EVERY Bash
# command until the file is fixed, saying the site file is broken. A
# site_extension_guards function, if a site defines one, must return 0 when
# it allows; a non-zero return or a failing command inside it blocks too.
#
# This file is part of the safety system and is user-only, like every file in
# .claude/hooks/: the Edit(.claude/hooks/*) deny rule and the hook's own §7
# block agent edits. Draft changes in a project folder and have the user
# install them.
#
# Not registered in settings.json: it is sourced, never run as a hook. It
# carries the .sh name (and mode 100755) so the shell tooling and ShellCheck
# treat it as Bash. SC2034 is disabled file-wide because every value here is
# used by the sourcing hook, not by this file.
#
# DAAF defines no site-only guards, so there is no site_extension_guards
# function here.

# Absolute project root: ^(/[A-Za-z0-9._-]+)+$ (no trailing or doubled slash,
# no . or .. component)
SITE_ROOT='/daaf'

# Extra §7 protected directories, relative paths (bash array; may be empty;
# no leading, trailing or doubled slash, no . or .. component).
# benchmarks/harness/hooks/ holds block-git-writes.sh, which settings.json
# registers as an active PreToolUse hook.
SITE_EXTRA_PROTECTED_DIRS=('benchmarks/harness/hooks')

# Where the §6 /tmp messages tell the model to put working files.
SITE_SCRATCH_DIR='{PROJECT_DIR}/scripts/scratch/'

# The sentence that ends each §8 package-install message: where to add the
# package and how to rebuild. The sentence before it ends on the package, so
# "it" reads as the package. DAAF's Control Panel menu labels the rebuild
# "10) Rebuild Container"; the user additions block is the USER ADDITIONS
# section near the end of the Dockerfile, which rebuilds fast.
# SC2016: the backticks are literal message text, not expansions.
# shellcheck disable=SC2016
SITE_REBUILD_HINT='Add it to /daaf/Dockerfile (the user additions block), then choose 10) Rebuild Container in the DAAF Control Panel, or run `bash rebuild_daaf.sh` (`.\rebuild_daaf.ps1` on Windows) from your daaf-docker folder.'

# The closing alternative in the §9 category D (interpreter one-liner
# environment print) message. DAAF's script runner scans for environment prints.
SITE_ENV_PRINT_HINT='move the logic into a script run via run_with_capture.sh, which scans for environment prints'
