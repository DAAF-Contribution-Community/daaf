#!/bin/bash
# Initialize git repo in the named volume if not already present.
# Since users install from a zip/tarball (not git clone), there is no .git
# directory by default. This creates a local-only repo for VS Code integration
# and DAAF's internal script versioning. No remote is configured — developers
# who need one can run: git remote add origin <url>
if [ ! -d "/daaf/.git" ]; then
    git init /daaf
    git -C /daaf branch -m main
    git -C /daaf config user.email "daaf@local"
    git -C /daaf config user.name "DAAF Container"
    git -C /daaf add -A
    git -C /daaf commit -m "Initial commit: DAAF framework"
fi

exec "$@"
