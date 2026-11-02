# Data Science Dockerfile with uv and Claude Code
# Base: Ubuntu 24.04 (noble) with Python 3.12 + Astral uv (binary COPY)

# ============================================
# ENVIRONMENT DATE -- what a rebuild reproduces
# ============================================
# DAAF freezes its build inputs to ONE "environment date" so that rebuilding
# this file later reproduces the same image, instead of whatever the package
# indexes happen to serve on the day of the rebuild. The environment date is
# 2026-09-24T13:20:00Z (the build time of the image these values were verified
# against). Four inputs carry it (the apt snapshot runs ahead of it under
# security exception (3), see SECURITY EXCEPTIONS below):
#
#   UBUNTU_BASE_IMAGE  ubuntu:24.04@sha256:008173c2...  base OS layers
#                      (multi-arch index digest; = tag noble-20260911)
#   uv COPY --from     ghcr.io/astral-sh/uv:0.9.30@sha256:538e0b39...
#                      the uv/uvx binaries (multi-arch index digest)
#   UV_EXCLUDE_NEWER   2026-09-24T13:20:00Z  EVERY Python distribution,
#                      including transitive and isolated build dependencies
#   UBUNTU_SNAPSHOT    20261024T000000Z      EVERY apt package an install
#                      line brings in, served from snapshot.ubuntu.com
#                      instead of the live archive. By default the SAME
#                      instant as UV_EXCLUDE_NEWER; it runs one month ahead
#                      as security exception (3) below. Base-image packages
#                      that no install line names or pins keep the base
#                      image's versions (this file never runs apt-get upgrade)
#
# R packages are frozen separately by P3M_SNAPSHOT_DATE (2026-04-15, the Posit
# Package Manager CRAN snapshot). It is deliberately independent of the date
# above: the R 4.5 / P3M binary-availability and S7 constraints documented at
# the R toolchain and P3M blocks below govern when it can move.
#
# NOT covered by the environment date: binary downloads pinned by the version
# in their URL (R runtime .deb, Quarto, TinyTeX, code-server, Codex CLI, gh,
# PowerShell, VS Code extensions) and Claude Code (CLAUDE_CODE_VERSION) --
# version-pinned, but not date-frozen. All except the Codex CLI and TinyTeX
# are also unchecksummed; the Codex and TinyTeX tarballs are verified against
# per-architecture SHA-256 values pinned beside CODEX_VERSION and
# TINYTEX_VERSION. The eight TeX Live packages added to TinyTeX come from the
# texlive.info tlnet archive of 2026-10-19 (TINYTEX_TLNET_ARCHIVE, a date of
# its own). A pinned SHA-512 (TINYTEX_TLPDB_SHA512) binds that archive's
# package database at its date: the build checks its own download of the
# database against it; tlmgr checks each package against the copy IT
# downloads; and a check after the install confirms that the installed
# revisions equal the pinned database's. Claude Code's
# installer script (https://claude.ai/install.sh) is additionally fetched
# live on every build; only the version it installs is pinned.
#
# SECURITY EXCEPTIONS (dated). The environment date itself is deliberately
# NOT moved for these fixes, because moving it moves every Python package
# (DAAF keeps analytic library versions stable). Each exception moves only
# what it must:
#   (1) Trust store: the keys of eMudhra intermediate CAs under
#       the root "emSign ECC Root CA - G3" were compromised, so the root is
#       distrusted. The "Distrust compromised CA roots" layer below removes G3
#       from the system CA store; certifi alone resolves past UV_EXCLUDE_NEWER
#       by a one-package --exclude-newer-package override (certifi 2026.10.19,
#       instant 2026-10-20T03:00:00Z) in the last Python package layer; and
#       daaf-check-distrusted-roots fails the build if G3 is still trusted by
#       the system store or certifi (it runs after the distrust layer, at the
#       end of the Python stack and as the last RUN of the build, which also
#       scans TinyTeX's tlmgr CA file; see NEUTRALISED below).
#   (2) Pillow: pillow 13.0.0 by a one-package override (instant
#       2026-10-17T00:00:00Z) in the PDF reading stack block. 12.3.0 has 41
#       published advisories (5 critical), all fixed in 13.0.0. No other
#       Python package moves (dry-run, x86_64 and aarch64). A version check
#       just before the build's last RUN fails the build if a later install
#       moved Pillow off 13.0.0.
#   (3) apt snapshot ahead of UV_EXCLUDE_NEWER: UBUNTU_SNAPSHOT
#       is 20261024T000000Z, one month after the Python date, to take the
#       Ubuntu security updates that a snapshot at the Python date lacks:
#       poppler 24.02.0-1ubuntu9.11 (poppler reads every PDF DAAF ingests),
#       ca-certificates 20260816ubuntu0.24.04.1 (ships no G3), openssl
#       3.0.13-0ubuntu3.16 and others. Measured on amd64 and arm64: compared
#       with snapshot 20260924T132000Z, 52 apt binaries (22 source packages)
#       differ, and the image takes the newer version of 48 of them (20
#       source packages). The other 4 are base-image binaries (libaudit1,
#       libaudit-common, libsystemd0, libudev1) that keep their base
#       versions: no install line names them, and OSV (checked 2026-10-24)
#       lists no fix advisory for them. The 48 are Ubuntu patch releases
#       (mostly security fixes) of the same upstream version, except
#       ca-certificates (the CA list) and tzdata 2026c -> 2026e, which changes
#       time-zone rules: America/Winnipeg (permanent -05) and America/Inuvik
#       (permanent -06) from 2026-11-01, plus a few historical dates (IANA tz
#       NEWS, 2026d and 2026e). pandas and base R read the system rules;
#       polars appears to bundle its own (inference). python3.12, GDAL, PROJ,
#       GEOS, Tesseract and nodejs do not change; no Python package moves.
#       (tests/bash/daaf_lib.bats matches this item's title and the
#       sentence that names the snapshot ID: keep their wording.)
# Three related settings are not date exceptions: ENV UV_NATIVE_TLS=1 (uv
# 0.9.30 verifies against the system store, not its built-in list), ENV
# CLAUDE_CODE_CERT_STORE=system (Claude Code 2.1.281 skips its bundled list;
# REVISIT at the next Claude Code upgrade) and the Codex CLI bump to 0.164.0
# (its built-in roots leave out G3).
# RETIRING THEM at the next routine date bump, which puts UV_EXCLUDE_NEWER and
# UBUNTU_SNAPSHOT back on ONE instant no earlier than 2026-10-24T00:00:00Z
# (so no apt package moves back): remove the certifi override layer (it
# becomes redundant once the date is on or after 2026-10-20T03:00:00Z), the
# pillow override flag (on or after 2026-10-17T00:00:00Z; keep a pillow pin)
# and the Pillow version check before the last RUN (and its note in USER
# ADDITIONS); drop exceptions (1)-(3) from this list, and the "runs ahead"
# text from the top of this banner and from the comment above
# ARG UBUNTU_SNAPSHOT; and update the copies outside this file: the dated
# "exception (3)" note in the
# comment of the snapshot check in tests/bash/daaf_lib.bats, and the docs
# that describe the exceptions. The distrust layer and the check stay as
# harmless guards. Full list: user_reference/04_extending_daaf.md §
# "Bumping the environment date", step 5.
# STILL TRUSTING G3 (own built-in root lists; low reachability, deferred):
# code-server's bundled Node 22.22.1 by default (scripts/launch_code_server.sh
# sets NODE_OPTIONS=--use-openssl-ca so it uses the system store); Quarto's
# deno (Quarto's launcher forces DENO_TLS_CA_STORE=system,mozilla, and its
# mozilla list holds G3); the R `openssl` package's own cacert.pem
# (/opt/R/4.5.3/lib/R/library/openssl/cacert.pem, read by openssl::ca_bundle();
# R's curl package uses the system store); libnode.so.109 (Node 18, only with
# --use-bundled-ca); and dart-sass (makes no network calls, inference).
# NEUTRALISED: TinyTeX ships its own CA list for tlmgr,
# tlpkg/installer/curl/curl-ca-bundle.crt (Mozilla data of 2026-09-25, holds
# G3). The TinyTeX layer replaces it with a symlink to the system bundle
# before any tlmgr network call, runs tlmgr with TEXLIVE_DOWNLOADER=curl (the
# system curl and store; also set by ENV for any later tlmgr call), and the
# last RUN passes that path to
# daaf-check-distrusted-roots.
#
# BUMPING: move UV_EXCLUDE_NEWER and UBUNTU_SNAPSHOT TOGETHER to one new
# instant. Same instant is the rule; the only allowed divergence is a dated
# security exception listed above in which the snapshot runs AHEAD of the
# Python date, never behind (tests/bash/daaf_lib.bats checks both). Pick the
# new instant no earlier than the current UBUNTU_SNAPSHOT, so no apt package
# moves back; optionally re-pin the base digest, then rebuild and diff
# `uv pip list` and `dpkg-query -W`. Whenever a snapshot move changes poppler
# (it reads every PDF DAAF ingests), re-check a few known papers after the
# rebuild, as .claude/skills/pdf-reading/references/toolchain.md describes: a
# poppler patch release can change its text extraction in rare cases. RULE:
# the base image's dated tag (noble-YYYYMMDD) must be ON OR BEFORE the snapshot
# date. Packages such as libc6-dev and libssl-dev depend on the EXACT version of
# a library the base already ships (libc6-dev Depends: libc6 (= ...)); apt never
# downgrades, so a base newer than the snapshot can make those installs fail.
# Full procedure: user_reference/04_extending_daaf.md § "Bumping the environment
# date".
#
# RETENTION: snapshot.ubuntu.com intends "to ensure snapshots are available for
# dates up to at least 2 years in the past, which we may extend if there is
# demand" -- a stated intent, not a guarantee, so an exact rebuild of the
# current snapshot (20261024T000000Z) is only stated to remain possible until
# about 2028-10. For long-term
# reproducibility, archive the BUILT IMAGE itself (`docker save`), not just
# this file.
#
# ARM64 (Apple Silicon): the snapshot layer below REPLACES the base image's apt
# sources with direct snapshot URIs (https://snapshot.ubuntu.com/ubuntu/<ID>/,
# which serves amd64 AND arm64 binaries), so it does not depend on which archive
# URIs the base ships for either architecture. Index resolution was verified in
# a sandboxed apt 2.8.3 (APT::Architecture=arm64, direct snapshot URIs,
# 2026-10-01), and the binary-arm64 indexes of snapshot 20261024T000000Z
# (noble-updates, -security and -backports, all four components) were fetched
# from that same /ubuntu/ path (snapshot.ubuntu.com, fetched 2026-10-28, HTTP
# 200); a full arm64 image build is UNVERIFIED. If an arm64 build fails at
# the snapshot layer, the escape hatch is to
# set the UBUNTU_SNAPSHOT default below to empty: the stock sources are then
# left untouched, apt resolves against the live archive (system packages NOT
# frozen), and every apt layer prints a WARNING.

# Base image, pinned by DIGEST (not just tag) so a re-pushed `24.04` tag cannot
# silently change the OS layers. This is the multi-arch OCI INDEX digest (not a
# per-arch manifest digest), so amd64 and arm64 hosts each still pull their own
# platform image from it. It equals the dated tag noble-20260911 (on or before
# the UBUNTU_SNAPSHOT date, as required -- see BUMPING in the banner). To bump:
# pick a dated tag noble-YYYYMMDD ON OR BEFORE the new environment date (inspect
# that dated tag, not the moving `24.04` tag, which may be newer), on the host
# run `docker buildx imagetools inspect ubuntu:noble-YYYYMMDD`, copy the
# top-level `Digest:` value here, and note the tag in this comment.
# (An ARG declared before FROM is usable only in FROM; it is not visible to the
# build steps below, which do not need it.)
ARG UBUNTU_BASE_IMAGE=ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
FROM ${UBUNTU_BASE_IMAGE}

LABEL maintainer="Data Science Environment"
LABEL description="Python data science with uv and Claude Code"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set up uv environment variables
# UV_SYSTEM_PYTHON=1 tells uv to install into the system Python (the apt-provided
# python3.12 below) rather than a managed venv, preserving the `uv pip install
# --system` semantics used throughout this file. Astral publishes no uv-on-noble
# image, so uv is vendored in as a static binary via the COPY below (the
# canonical pattern from Astral's Docker docs) instead of via a base-image tag.
# UV_BREAK_SYSTEM_PACKAGES=1 lifts noble's PEP 668 "externally-managed" guard:
# Ubuntu's apt python3.12 ships /usr/lib/python3.12/EXTERNALLY-MANAGED, which
# makes every `uv pip install --system` layer refuse with exit 2. That guard
# protects live systems from apt/pip conflicts; this image IS the managed
# environment (uv-only, pinned versions, runtime installs hook-blocked), and
# uv's docs designate this variable for exactly this containerized use.
ENV UV_SYSTEM_PYTHON=1
ENV UV_BREAK_SYSTEM_PACKAGES=1
ENV UV_COMPILE_BYTECODE=1

# UV_NATIVE_TLS=1 makes uv verify HTTPS against the operating system's CA store
# (/etc/ssl/certs) instead of the webpki root list compiled into the uv binary.
# uv 0.9.30's built-in list still trusts "emSign ECC Root CA - G3", the root of
# the eMudhra compromise (uv fixed its list in 0.13.4, GHSA-hq85-5cpj-mr62),
# whereas the system store has G3 removed by the "Distrust compromised CA
# roots" layer below, which runs before uv's first download. This covers the
# build's PyPI downloads and any in-container `uv pip compile` dry-run. It
# also lets uv work behind a TLS-inspecting proxy whose root is installed in
# the OS store. It is not a version change: the uv
# binary and every resolution stay the same; only the roots uv trusts change.
# uv documents the variable: `--native-tls  Whether to load TLS certificates
# from the platform's native store [env: UV_NATIVE_TLS=]` (uv 0.9.30 help).
ENV UV_NATIVE_TLS=1

# Freeze Python resolution to the environment date (see the ENVIRONMENT DATE
# banner at the top of this file). The `==` pins in the uv blocks below fix only
# the packages they name; their dependencies re-resolve against live PyPI on
# every rebuild, and without a cutoff they drift (PyPI, observed 2026-10-01:
# re-resolving the same pins seven days after the cutoff changed 13 of 164
# packages, numba 0.67.0 -> 0.68.0 and llvmlite 0.49.0 -> 0.50.0 among them).
# UV_EXCLUDE_NEWER makes uv ignore every distribution file uploaded after the
# cutoff, so the same pins re-resolve to the same full set (verified against
# PyPI on 2026-10-01: `uv pip compile --exclude-newer 2026-09-24T13:20:00Z` of
# the pins reproduced the installed set exactly).
#   - ALWAYS a full RFC 3339 timestamp ending in `Z`. uv interprets a bare
#     date (2026-09-24) in the local time zone of whatever machine runs it.
#     Inside this build that is the image's UTC, but the same value used in a
#     `uv pip compile` dry-run elsewhere (or after a future image time-zone
#     change) could resolve a different set; an explicit `Z` instant cannot.
#   - It also freezes isolated BUILD dependencies (build-system.requires such as
#     setuptools/hatchling) for any package built from an sdist -- e.g. fiona,
#     which has no arm64 wheel and builds from source on Apple Silicon.
#   - It persists as an image ENV (not just a build ARG) so an in-container
#     `uv pip compile` dry-run resolves against the SAME date as the build --
#     which is what makes that dry-run a meaningful compatibility check for a
#     proposed addition (user_reference/04_extending_daaf.md).
#   - Residual risk (inference, not observed): PyPI yank status and file
#     deletions are read live. A transitive version yanked after the cutoff
#     would be skipped on a rebuild (drift); a deleted file would fail it.
#   - Adding a package released AFTER the cutoff: either bump the environment
#     date (procedure in user_reference/04_extending_daaf.md), or exempt only
#     that package on its own install line:
#       uv pip install --system --exclude-newer-package PKG=<RFC 3339 Z time> PKG==X.Y
#     Its dependencies still resolve at the global cutoff; if they too need
#     newer releases, bump the date instead. NOTE: uv's "No solution found"
#     error does NOT mention that the cutoff excluded anything, so an `==` pin
#     newer than the cutoff looks like a nonexistent version.
ARG UV_EXCLUDE_NEWER=2026-09-24T13:20:00Z
ENV UV_EXCLUDE_NEWER=${UV_EXCLUDE_NEWER}

# Set the process locale to UTF-8 (root-cause fix for R's Unicode handling).
# Unlike Python — which self-coerces an unset/POSIX locale to UTF-8 at startup
# via PEP 538, flipping sys.flags.utf8_mode to 1 — R has NO locale-coercion
# mechanism of its own. The stock ubuntu:24.04 base leaves LANG/LC_ALL unset, so
# every LC_* category resolves to POSIX and R 4.5 starts with codeset
# ANSI_X3.4-1968 (MBCS off). Under that locale R silently corrupts UTF-8:
# yaml::read_yaml() on a multibyte file returns NULL with only a warning, base
# readLines() byte-mangles strings, and — the failure a runtime Sys.setlocale()
# can NEVER repair — non-ASCII string literals are rewritten to octal-escape
# text by the parser BEFORE execution. Only a UTF-8 locale present at process
# startup fixes all three. C.UTF-8 (not a full locale like en_US.UTF-8) is
# chosen deliberately: it ships in the stock image with no locale-gen or
# `locales` package, and it keeps `.` as the decimal separator and English
# diagnostics, so numeric parsing and date formatting are unchanged (the one
# intended semantic shift is base-R sort()/order() moving to ICU collation).
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# ============================================
# Vendor the uv/uvx binaries + provision Python 3.12
# ============================================
# Copy the pinned uv/uvx static binaries from Astral's published image (no
# uv-on-noble image exists, so this is the canonical way to get a pinned uv onto
# an Ubuntu base). The tag pins uv 0.9.30, and the reference is additionally
# pinned by DIGEST (part of the environment date; see the banner at the top of
# this file) so a re-pushed tag cannot swap the binaries. Like the base
# image, this is the multi-arch OCI INDEX digest (linux/amd64 + linux/arm64),
# so each platform still copies its own binaries. To bump: `docker buildx
# imagetools inspect ghcr.io/astral-sh/uv:<version>` on the host and copy the
# top-level `Digest:`.
# The reference stays literal on purpose (no ARG): variable expansion in
# `COPY --from` is not something this file relies on. noble's default `python3`
# is 3.12, so the interpreter, its dev headers, and venv support are installed
# from apt ("Install System Dependencies" below) to back UV_SYSTEM_PYTHON=1.
# The bare `python3` metapackage is required too: minimal ubuntu:24.04 ships no
# /usr/bin/python3 symlink, and DAAF's execution wrapper (run_with_capture.sh)
# invokes the bare `python3` name for every Python script.
COPY --from=ghcr.io/astral-sh/uv:0.9.30@sha256:538e0b39736e7feae937a65983e49d2ab75e1559d35041f9878b7b7e51de91e4 /uv /uvx /usr/local/bin/

# ============================================
# apt index refresh helper (snapshot origin guard)
# ============================================
# Every apt layer in this file calls `daaf-apt-update` instead of a bare
# `apt-get update`. It runs `apt-get update` with any arguments passed through,
# then -- when the build froze apt to an Ubuntu snapshot (the marker file the
# snapshot layer below writes) -- FAILS the layer unless every index apt will
# resolve packages from is served by snapshot.ubuntu.com at that snapshot ID.
# Two mechanisms share the work:
#   - `apt-get update --error-on=any` makes ANY index download failure fatal.
#     Plain `apt-get update` only warns (exit 0) and silently drops the failed
#     source, so later installs could fall back to older versions from the
#     remaining suites. This flag is what guarantees the indexes are complete.
#   - The origin guard then reads apt's own index-target records
#     (`apt-get indextargets`, the targets the solver resolves from) rather than
#     guessing from file names in /var/lib/apt/lists, and requires every site to
#     be https://snapshot.ubuntu.com/ubuntu/<ID>. A live-archive source, an
#     unfrozen third-party repository, or a `Shadowed: true` target (the
#     live-archive twin apt 2.8 creates for a sources-level `Snapshot:` field --
#     a mode DAAF deliberately does not use, see the snapshot layer) each FAIL
#     the layer, naming the offending index, instead of yielding an image that
#     merely looks frozen.
# With the snapshot disabled (marker absent) it prints a WARNING and lets the
# layer continue.
#
# apt semantics this relies on (observed 2026-10-01, Ubuntu noble's apt 2.8.3):
# without `--no-release-info`, `indextargets` lists only targets whose index
# files exist, and its `$(SHADOWED)` format field is substituted only for
# shadowed targets (otherwise the literal text `$(SHADOWED)` is printed).
#
# Written inline via a BuildKit heredoc for the same reason as the entrypoint
# wrapper at the end of this file: the host build context is the distributed
# daaf-docker folder, which does not contain the DAAF repo tree, so a COPY of a
# repo file can never succeed (see that block's NOTE).
COPY --chmod=0755 <<'DAAF_APT_UPDATE_EOF' /usr/local/bin/daaf-apt-update
#!/usr/bin/env bash
# daaf-apt-update -- build-time `apt-get update` wrapper with an Ubuntu-snapshot
# origin guard (generated from the Dockerfile heredoc above; there is no
# separate source file). Usage: daaf-apt-update [apt-get update options...]
# Snapshot mode is decided by the marker file the Dockerfile's snapshot layer
# writes (absent = snapshot disabled), so callers need no ARG plumbing.
# DAAF_APT_SNAPSHOT_MARKER exists only as a test seam for exercising this guard
# against a sandboxed apt (APT_CONFIG); builds never set it.
set -euo pipefail

readonly SNAPSHOT_MARKER="${DAAF_APT_SNAPSHOT_MARKER:-/etc/daaf/ubuntu-snapshot}"

# --error-on=any: plain `apt-get update` only WARNS (exit 0) when an index
# fails to download, and apt then silently drops that source's targets -- a
# transient failure of one snapshot suite (e.g. noble-updates) would let later
# installs fall back to older versions from the remaining suites. Any fetch
# failure therefore fails the layer (observed: exit 100 with apt 2.8.3). This
# is the ONLY download-completeness check: indextargets below lists just the
# targets whose files exist, so it cannot detect a missing index itself.
apt-get update --error-on=any "$@"

if [ ! -s "$SNAPSHOT_MARKER" ]; then
    echo "daaf-apt-update: WARNING: no Ubuntu snapshot configured ($SNAPSHOT_MARKER absent) -- this layer resolved apt against the LIVE archive; system packages are NOT frozen to the environment date." >&2
    exit 0
fi

snapshot_id="$(head -n 1 "$SNAPSHOT_MARKER")"
if [ -z "$snapshot_id" ]; then
    echo "daaf-apt-update: ERROR: snapshot marker $SNAPSHOT_MARKER has an empty first line." >&2
    exit 1
fi

# One line per index target: shadowed flag | site. apt prints `true` for a
# shadowed target and the literal text `$(SHADOWED)` otherwise.
# shellcheck disable=SC2016  # $(FIELD) is apt's --format syntax, not a shell expansion
targets="$(apt-get indextargets --format '$(SHADOWED)|$(SITE)' "$@")"

active=0
offenders=()
while IFS='|' read -r is_shadowed site; do
    [ -n "$site" ] || continue
    active=$((active + 1))
    if [ "$is_shadowed" = "true" ]; then
        offenders+=("shadowed live-archive target (a sources-level 'Snapshot:' field is in use; DAAF writes direct snapshot URIs instead): ${site}")
        continue
    fi
    case "$site" in
        https://snapshot.ubuntu.com/ubuntu/"${snapshot_id}" | https://snapshot.ubuntu.com/ubuntu/"${snapshot_id}"/) ;;
        *) offenders+=("not served by snapshot ${snapshot_id}: ${site}") ;;
    esac
done <<< "$targets"

if [ "$active" -eq 0 ]; then
    echo "daaf-apt-update: ERROR: apt reports no index targets; cannot verify the snapshot origin." >&2
    exit 1
fi

if [ "${#offenders[@]}" -gt 0 ]; then
    echo "daaf-apt-update: ERROR: apt is frozen to Ubuntu snapshot ${snapshot_id}, but these indexes would NOT resolve from it:" >&2
    printf '  %s\n' "${offenders[@]}" | sort -u >&2
    echo "daaf-apt-update: a source points at a live archive or a third-party repository, so this build would NOT be frozen. Point every apt source at https://snapshot.ubuntu.com/ubuntu/${snapshot_id}/ or install third-party software another way; to build unfrozen deliberately, set the UBUNTU_SNAPSHOT default in the Dockerfile to empty." >&2
    exit 1
fi

echo "daaf-apt-update: OK -- all ${active} index targets served from Ubuntu snapshot ${snapshot_id}"
DAAF_APT_UPDATE_EOF

# ============================================
# Freeze apt to the Ubuntu snapshot (environment date) + TLS bootstrap
# ============================================
# Points every apt source at snapshot.ubuntu.com as of UBUNTU_SNAPSHOT, so all
# apt packages in this image (python3.12, GDAL, OpenSSL, tzdata, nodejs, the R
# system libraries, ...) are the versions the archive served at the environment
# date rather than whatever a later rebuild would fetch. Snapshot IDs have the
# form YYYYMMDDTHHMMSSZ (UTC); keep this value the SAME instant as
# UV_EXCLUDE_NEWER above, except during a dated security exception listed in
# the banner, when it may run AHEAD of it (never behind). Value:
# 20261024T000000Z under exception (3), one month ahead of UV_EXCLUDE_NEWER
# 2026-09-24T13:20:00Z, for Ubuntu's poppler, ca-certificates, openssl and
# other security updates; both return to one instant at the next routine date
# bump.
#
# HOW (direct snapshot URIs): the deb822 sources file is OVERWRITTEN with two
# stanzas -- noble/noble-updates/noble-backports and noble-security, all four
# components (main universe restricted multiverse) -- whose URIs point
# straight at https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT}/, keeping
# the stock `Signed-By` Ubuntu archive keyring. Because it replaces whatever
# URIs the base ships, it is architecture-independent: the snapshot's /ubuntu/
# path serves amd64 and arm64 binaries alike (it has no /ubuntu-ports/ path),
# and no ports.ubuntu.com mapping is needed. Every index comes from the
# snapshot and nothing is fetched from the live archive (observed 2026-10-01,
# sandboxed apt 2.8.3: on amd64 the package candidates matched the installed
# image; with APT::Architecture=arm64 every index resolved from the snapshot
# host only).
# Deliberately NOT used: apt's own snapshot options. The global `APT::Snapshot`
# / `--snapshot` silently falls back to the live archive for any source it
# cannot map, and a sources-level `Snapshot:` field makes apt also download a
# "shadowed" live-archive copy of every index (twice the downloads, a
# live-archive dependency, and 404s for arm64 indexes on archive.ubuntu.com).
# The layer fails the build if the base is not noble (the stanzas name noble
# suites), if the Signed-By keyring is missing, or if a legacy one-line
# /etc/apt/sources.list carries active entries (they would float on the live
# archive).
#
# TLS BOOTSTRAP: snapshot.ubuntu.com is HTTPS-only, but the stock base image
# ships no ca-certificates, so apt cannot verify its certificate until that
# package is installed. This layer's own `daaf-apt-update` and
# `apt-get install ca-certificates` therefore pass
# `-o Acquire::https::snapshot.ubuntu.com::Verify-Peer=false` -- scoped to
# those two commands and that one host, and never written to a config file.
# (Key order matters: this host-scoped form disables peer verification for
# snapshot.ubuntu.com, while the look-alike
# `Acquire::https::Verify-Peer::snapshot.ubuntu.com` has NO effect; observed
# 2026-10-01, Ubuntu noble's apt 2.8.3 in a sandbox with an empty CA bundle.)
# apt's package integrity does not rest on TLS: the InRelease index is
# GPG-verified against the `Signed-By` Ubuntu archive keyring, and every package
# hash chains from it (the stock sources themselves use plain http). From the
# next layer on, ca-certificates is present and every apt layer verifies TLS
# normally.
#
# ESCAPE HATCH: set the UBUNTU_SNAPSHOT default below to EMPTY (edit this file;
# it is not wired as a compose build arg) to skip all snapshot configuration --
# the base image's stock sources are left untouched (whatever URIs it ships for
# its architecture), no Verify-Peer override, ca-certificates from the live
# archive. apt is then NOT frozen; this layer and every `daaf-apt-update` print
# a WARNING saying so. The ID is also recorded in /etc/daaf/ubuntu-snapshot
# (the marker daaf-apt-update reads), so a built image reports what it was
# frozen to.
ARG UBUNTU_SNAPSHOT=20261024T000000Z
RUN set -eu; \
    SOURCES=/etc/apt/sources.list.d/ubuntu.sources; \
    KEYRING=/usr/share/keyrings/ubuntu-archive-keyring.gpg; \
    SNAPSHOT_MARKER=/etc/daaf/ubuntu-snapshot; \
    if [ -z "${UBUNTU_SNAPSHOT}" ]; then \
        echo "WARNING: UBUNTU_SNAPSHOT is empty -- the Ubuntu snapshot is DISABLED. The stock apt sources are left untouched and every apt layer in this build resolves against the LIVE archive, so system packages are NOT frozen to the environment date." >&2; \
        rm -f "${SNAPSHOT_MARKER}"; \
        daaf-apt-update; \
        apt-get install -y --no-install-recommends ca-certificates; \
    else \
        case "${UBUNTU_SNAPSHOT}" in \
            [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z) ;; \
            *) echo "FATAL: UBUNTU_SNAPSHOT='${UBUNTU_SNAPSHOT}' is not a YYYYMMDDTHHMMSSZ snapshot ID" >&2; exit 1 ;; \
        esac; \
        if ! grep -qx 'VERSION_CODENAME=noble' /etc/os-release; then \
            echo "FATAL: the base image is not Ubuntu noble, but the snapshot sources written here name noble suites -- update them together with the base image." >&2; \
            exit 1; \
        fi; \
        if [ ! -s "${KEYRING}" ]; then \
            echo "FATAL: Signed-By keyring ${KEYRING} is missing or empty -- apt could not verify the snapshot indexes." >&2; \
            exit 1; \
        fi; \
        if grep -qE '^[[:space:]]*deb(-src)?[[:space:]]' /etc/apt/sources.list 2>/dev/null; then \
            echo "FATAL: /etc/apt/sources.list has active one-line entries that the snapshot sources do not replace -- they would float on the live archive." >&2; \
            exit 1; \
        fi; \
        SNAPSHOT_URI="https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT}/"; \
        mkdir -p "$(dirname "${SOURCES}")"; \
        printf '%s\n' \
            "# Written by the DAAF Dockerfile snapshot layer: apt frozen to Ubuntu snapshot ${UBUNTU_SNAPSHOT}." \
            "Types: deb" \
            "URIs: ${SNAPSHOT_URI}" \
            "Suites: noble noble-updates noble-backports" \
            "Components: main universe restricted multiverse" \
            "Signed-By: ${KEYRING}" \
            "" \
            "Types: deb" \
            "URIs: ${SNAPSHOT_URI}" \
            "Suites: noble-security" \
            "Components: main universe restricted multiverse" \
            "Signed-By: ${KEYRING}" \
            > "${SOURCES}"; \
        mkdir -p "$(dirname "${SNAPSHOT_MARKER}")"; \
        printf '%s\n' "${UBUNTU_SNAPSHOT}" > "${SNAPSHOT_MARKER}"; \
        echo "apt frozen to Ubuntu snapshot ${UBUNTU_SNAPSHOT}:"; \
        cat "${SOURCES}"; \
        daaf-apt-update -o Acquire::https::snapshot.ubuntu.com::Verify-Peer=false; \
        apt-get install -y --no-install-recommends \
            -o Acquire::https::snapshot.ubuntu.com::Verify-Peer=false \
            ca-certificates; \
    fi; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# ============================================
# Distrust compromised CA roots (emSign ECC Root CA - G3)
# ============================================
# INCIDENT: on 2026-10-20 it was disclosed that eight eMudhra intermediate CAs
# (six TLS, two code-signing) had private keys derivable from their public
# certificates, so anyone could mint certificates that chain to the root
# "emSign ECC Root CA - G3" (certificate SHA-256 86A1ECBA...36BBE6B). Mozilla
# emergency-distrusted G3 (NSS 3.131.1); Ubuntu, certifi and uv followed. Only
# G3 is affected: emSign G1, C1 and C3 stay trusted, matching NSS and Ubuntu.
#
# WHY A TARGETED DISTRUST: Ubuntu's fixed package, ca-certificates
# 20260816ubuntu0.24.04.1 (snapshot IDs >= 20261020T170000Z), ships no G3 (its
# .deb has no emSign_ECC_Root_CA_-_G3.crt; G1, C1 and C3 remain), so at the
# pinned snapshot this layer prints "... is not listed ... nothing to
# deselect". It stays as a guard that does not depend on the snapshot: if a
# later snapshot or the live-archive escape hatch brought G3 back, it
# deselects only G3 with Ubuntu's documented method (prefix the entry in
# /etc/ca-certificates.conf with `!`, then run update-ca-certificates), and
# the check below runs either way.
#
# PERSISTENCE: later apt layers may re-run update-ca-certificates through
# package triggers; it honors the `!` entry. The package's own configure step
# also reads `!` entries back as deselected (ca-certificates.config,
# CERTS_DISABLED), so the deselection survives a reconfigure. The check re-runs
# at the end of the Python stack and as the last RUN of the build regardless.
#
# FORWARD COMPATIBILITY: idempotent. With a ca-certificates that ships no G3
# (the pinned snapshot and any later one), its entry is absent and
# this layer is a harmless no-op that still runs the check. On the
# UBUNTU_SNAPSHOT-empty escape hatch (live archive) the same holds.
#
# ORDER: it runs directly after ca-certificates is installed and before any
# other network download in this build (apt indexes and packages, PowerShell
# and its Pester/PSScriptAnalyzer modules from the PowerShell Gallery (both
# DAAF_DEV only), Codex, gh (DAAF_DEV only), R, PyPI via uv, P3M, Quarto,
# TinyTeX and its TeX Live archive, code-server, VS Code extensions, Claude
# Code), so every later HTTPS fetch is
# verified against the fixed store.
#
# CHECK: daaf-check-distrusted-roots (installed just below; inline heredoc for
# the reason given at daaf-apt-update) fails the layer if G3 is still in the
# system CA bundle or the hashed CA directory, matched by SHA-256 fingerprint,
# not by file name. It runs again at the end of the Python stack and as the
# last RUN of the build, where it also checks certifi's bundle.
COPY --chmod=0755 <<'DAAF_CHECK_DISTRUSTED_ROOTS_EOF' /usr/local/bin/daaf-check-distrusted-roots
#!/usr/bin/env bash
# daaf-check-distrusted-roots -- build-time assertion that no distrusted CA
# root is trusted (generated from the Dockerfile heredoc above; there is no
# separate source file). Usage: daaf-check-distrusted-roots [PEM_BUNDLE...]
# Scans, by certificate SHA-256 fingerprint:
#   - the system CA bundle (/etc/ssl/certs/ca-certificates.crt), read by
#     OpenSSL, curl, git, Python's default ssl context, Node and uv;
#   - every certificate file in the system CA directory (/etc/ssl/certs), the
#     hashed CApath that curl and other OpenSSL clients also search;
#   - each extra PEM bundle named on the command line (e.g. certifi's).
# Exits 1 if a DISTRUSTED root is found, or if a source cannot be checked.
# Every source must also contain the CONTROL root (ISRG Root X1), so a scan
# that reads no certificates (no openssl, an empty or unparseable file) fails
# instead of passing vacuously.
# DAAF_TRUST_BUNDLE and DAAF_TRUST_CERT_DIR exist only as test seams for
# exercising this check against copies of the stores; builds never set them.
set -euo pipefail

readonly SYSTEM_BUNDLE="${DAAF_TRUST_BUNDLE:-/etc/ssl/certs/ca-certificates.crt}"
readonly CERT_DIR="${DAAF_TRUST_CERT_DIR:-/etc/ssl/certs}"

# Distrusted roots, one per line: certificate SHA-256 (uppercase hex, no
# colons), then the name. To distrust another root, add a line here and its
# deselection to the "Distrust compromised CA roots" layer.
#   emSign ECC Root CA - G3: anchor of the eMudhra intermediates whose private
#   keys were derivable (Mozilla emergency distrust, NSS 3.131.1, 2026-10-20).
readonly DISTRUSTED="86A1ECBA089C4A8D3BBE2734C612BA341D813E043CF9E8A862CD5C57A36BBE6B emSign ECC Root CA - G3"
# Positive control that every scanned source must contain: ISRG Root X1.
readonly CONTROL="96BCEC06264976F37460779ACF28C5A7CFE8A3C0AAE11A8FFCEE05C0BDDF08C6"

if ! command -v openssl >/dev/null 2>&1; then
    echo "daaf-check-distrusted-roots: ERROR: openssl not found; cannot fingerprint certificates." >&2
    exit 1
fi

failures=0
summary=()

# Bundles. awk hands each PEM block to its own openssl process. The number of
# fingerprints must equal the number of PEM blocks, so a certificate openssl
# cannot parse fails the check instead of being skipped.
for bundle in "$SYSTEM_BUNDLE" "$@"; do
    if [ ! -s "$bundle" ]; then
        echo "daaf-check-distrusted-roots: ERROR: CA bundle '${bundle}' is missing or empty." >&2
        failures=$((failures + 1))
        continue
    fi
    blocks="$(grep -c -e '-----BEGIN CERTIFICATE-----' "$bundle" || true)"
    fingerprints="$(awk '
        /-----BEGIN CERTIFICATE-----/ { cmd = "openssl x509 -noout -fingerprint -sha256" }
        cmd != "" { print | cmd }
        /-----END CERTIFICATE-----/ && cmd != "" { close(cmd); cmd = "" }
    ' "$bundle" | sed -e 's/^[^=]*=//' -e 's/://g' | tr 'a-f' 'A-F')"
    count="$(grep -c -x -e '[0-9A-F]\{64\}' <<< "$fingerprints" || true)"
    if [ "$blocks" -eq 0 ] || [ "$count" -ne "$blocks" ]; then
        echo "daaf-check-distrusted-roots: ERROR: ${bundle}: only ${count} of ${blocks} PEM certificates could be fingerprinted." >&2
        failures=$((failures + 1))
    fi
    if ! grep -q -x -e "$CONTROL" <<< "$fingerprints"; then
        echo "daaf-check-distrusted-roots: ERROR: ${bundle}: control root ISRG Root X1 not found, so this scan cannot be trusted." >&2
        failures=$((failures + 1))
    fi
    while read -r bad name; do
        [ -n "$bad" ] || continue
        if grep -q -x -e "$bad" <<< "$fingerprints"; then
            echo "daaf-check-distrusted-roots: ERROR: distrusted root '${name}' (SHA-256 ${bad}) is in ${bundle}" >&2
            failures=$((failures + 1))
        fi
    done <<< "$DISTRUSTED"
    summary+=("${bundle}: ${count} certificates")
done

# CA directory: every certificate file and hash link (OpenSSL reads the first
# certificate in each). Files openssl cannot parse are not certificates and
# are skipped; the bundle itself was scanned above.
dir_files=0
dir_control=0
while IFS= read -r -d '' file; do
    fp="$(openssl x509 -noout -fingerprint -sha256 -in "$file" 2>/dev/null | sed -e 's/^[^=]*=//' -e 's/://g' | tr 'a-f' 'A-F')" || fp=""
    [ -n "$fp" ] || continue
    dir_files=$((dir_files + 1))
    if [ "$fp" = "$CONTROL" ]; then
        dir_control=1
    fi
    while read -r bad name; do
        if [ -n "$bad" ] && [ "$fp" = "$bad" ]; then
            echo "daaf-check-distrusted-roots: ERROR: distrusted root '${name}' (SHA-256 ${bad}) is in ${file}" >&2
            failures=$((failures + 1))
        fi
    done <<< "$DISTRUSTED"
done < <(find "$CERT_DIR" -maxdepth 1 \( -type f -o -type l \) ! -name "$(basename "$SYSTEM_BUNDLE")" -print0)
if [ "$dir_control" -ne 1 ]; then
    echo "daaf-check-distrusted-roots: ERROR: CA directory ${CERT_DIR}: control root ISRG Root X1 not found among ${dir_files} certificate files, so this scan cannot be trusted." >&2
    failures=$((failures + 1))
fi
summary+=("${CERT_DIR}: ${dir_files} certificate files")

if [ "$failures" -gt 0 ]; then
    echo "daaf-check-distrusted-roots: FAILED -- ${failures} problem(s) above. This image would trust a distrusted CA root, or its trust store could not be checked." >&2
    exit 1
fi
echo "daaf-check-distrusted-roots: OK -- no distrusted CA root found in:"
printf '  %s\n' "${summary[@]}"
DAAF_CHECK_DISTRUSTED_ROOTS_EOF

RUN set -eu; \
    CONF=/etc/ca-certificates.conf; \
    G3=mozilla/emSign_ECC_Root_CA_-_G3.crt; \
    if [ ! -s "${CONF}" ]; then \
        echo "FATAL: ${CONF} is missing or empty -- the snapshot layer above should have installed ca-certificates." >&2; \
        exit 1; \
    fi; \
    if grep -qxF "${G3}" "${CONF}"; then \
        sed -i 's|^mozilla/emSign_ECC_Root_CA_-_G3\.crt$|!&|' "${CONF}"; \
        echo "Deselected ${G3} in ${CONF}."; \
    elif grep -qxF "!${G3}" "${CONF}"; then \
        echo "${G3} is already deselected in ${CONF}."; \
    else \
        echo "${G3} is not listed in ${CONF}: this ca-certificates no longer ships it, so there is nothing to deselect."; \
    fi; \
    if grep -qxF "${G3}" "${CONF}"; then \
        echo "FATAL: ${G3} is still selected in ${CONF}." >&2; \
        exit 1; \
    fi; \
    grep -nF "${G3}" "${CONF}" || true; \
    update-ca-certificates --fresh; \
    daaf-check-distrusted-roots

# ============================================
# Install System Dependencies (Git, Python 3.12)
# ============================================
# ca-certificates is already installed by the snapshot layer above; it stays
# listed here so this block still states the image's full system-dependency
# set (re-listing an installed package is a no-op).
RUN daaf-apt-update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    jq \
    git \
    poppler-utils \
    python3 \
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Ensure the apt `universe` component is enabled
# ============================================
# Several apt deps DAAF installs live in Ubuntu's `universe` component, and the
# FIRST of them appears in the very next block: libgdal-dev and gdal-bin
# (geospatial), alongside tesseract-ocr (PDF OCR) in the same layer. More arrive
# later in the R system-libs block (libnode-dev, libtbb-dev, libhdf5-dev,
# libnetcdf-dev, libglpk40). This guard therefore runs BEFORE the geospatial
# block — its earliest consumer — so a base with universe disabled fails here
# with a clear message instead of dying later inside an apt-install with a
# cryptic "unable to locate package" error.
#
# The official ubuntu:24.04 image ships universe enabled in
# /etc/apt/sources.list.d/ubuntu.sources, so on the normal base this guard is a
# fast no-op. It exists to make that assumption explicit and to self-heal a
# minimal base: it enables universe if absent and fails fast (exit 1) only if it
# still cannot. The index refresh (`daaf-apt-update`) for the real installs is
# left to the blocks below, so the no-op path costs nothing beyond a grep.
# With the snapshot enabled, the snapshot layer above writes `universe`
# explicitly into its sources, so this guard is a no-op there too; the self-heal
# branch can only run on the escape-hatch (stock sources) path. On that path,
# `daaf-apt-update || exit 1` keeps the helper's failures fatal even though this
# branch otherwise runs without `set -e`.
RUN if grep -rqE '^[[:space:]]*(Components:.*\buniverse\b|deb .*\buniverse\b)' \
        /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null; then \
        echo "universe component already enabled"; \
    else \
        echo "universe component not found; enabling via add-apt-repository"; \
        daaf-apt-update || exit 1; \
        apt-get install -y --no-install-recommends software-properties-common; \
        add-apt-repository -y universe; \
        apt-get clean; \
        rm -rf /var/lib/apt/lists/*; \
        grep -rqE '^[[:space:]]*(Components:.*\buniverse\b|deb .*\buniverse\b)' \
            /etc/apt/sources.list /etc/apt/sources.list.d/ \
            || { echo "FATAL: could not enable the apt 'universe' component" >&2; exit 1; }; \
    fi

# ============================================
# Install Geospatial System Libraries (GDAL/GEOS/PROJ) + PDF OCR (Tesseract)
# ============================================
# Geospatial: required by fiona (rasterstats dep) and beneficial for rasterio,
# geopandas, osmnx.
#
# PDF OCR: the system half of the DAAF PDF reading layer: scripts/pdf_ingest.sh
# runs OCR only on pages it flags as scanned. poppler-utils (pdftotext, pdftoppm,
# pdfinfo) is in the system-deps block above; the Python half is the "PDF
# reading stack" block in the Python section below. tesseract-ocr lives in
# Ubuntu's `universe` component, so it sits after the universe guard. CPU-only:
# no GPU and no model downloads; at run time pdf_ingest caps Tesseract at one
# thread (OMP_THREAD_LIMIT=1 in the subprocess environment), so OCR stays light.
# License: Apache-2.0 (tesseract-ocr, -eng, -osd).
# WHY ONE LAYER, not a separate OCR block: each apt layer's daaf-apt-update
# re-downloads the ~33 MB snapshot index, which can take over two minutes on a
# slow snapshot server, several times as long as Tesseract's 8.4 MB of
# packages; sharing this layer's refresh avoids that cost.
RUN daaf-apt-update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    gdal-bin \
    libgeos-dev \
    libproj-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-osd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Install Codex CLI + optional developer test tooling (DAAF_DEV)
# ============================================
# The pinned OpenAI Codex CLI ships in EVERY DAAF image. Installing the binary
# does not activate a provider route or authenticate anything: the default
# provider remains unchanged unless the user explicitly enables the shim, and
# the ChatGPT-subscription lane additionally requires SHIM_BACKEND_MODE=chatgpt
# plus a user-created `codex login --device-auth` OAuth state. Codex is installed
# Node-free from the pinned GitHub release binary (the musl static build), so no
# Node/npm toolchain is added.
#
# The test toolchain remains OPT-IN and FRAMEWORK-DEVELOPER-ONLY. Its guarded RUN
# layers are skipped unless DAAF_DEV=1 is passed as a build arg. A framework
# developer opts in by setting DAAF_DEV=1 in the host-side
# environment_settings.txt; the install/rebuild scripts bridge that key into the
# shell environment, and docker-compose.yml forwards it here as
# `--build-arg DAAF_DEV=${DAAF_DEV:-0}`.
#
# What DAAF_DEV=1 additionally installs:
#   - shellcheck                 (Bash linter, Debian repo)
#   - bats                       (Bash test runner, Debian repo)
#   - PowerShell 7 + Pester +
#     PSScriptAnalyzer           (PowerShell test/lint stack)
#   - GitHub CLI (gh)            (CI runs/logs inspection, PR/issue access, and
#                                 git HTTPS credential helper for framework devs;
#                                 GitHub release tarball)
# The primary goal is to let a developer run the repo's own test suites INSIDE
# the container so `bats tests/bash/` and `Invoke-Pester tests/powershell/`
# reproduce what .github/workflows/ci-scripts.yml runs in CI.
#
# CI PARITY (bats): the CI `bats-tests` job installs bats with a plain
# `apt-get install -y bats` and does NOT vendor bats-support/bats-assert; the
# suite's tests/bash/test_helper.bash provides fallback assertions when those
# helper libraries are absent (and looks for them under tests/libs, test/libs,
# or /usr/lib/bats if a developer adds them later). So the Debian `bats`
# package alone reproduces CI here -- no helper libraries are required.
#
# ARCH NOTE (PowerShell): PowerShell is installed from the GitHub release
# tarball, NOT Microsoft's apt feed, because that feed has no arm64 packages and
# DAAF supports Apple Silicon. The tarball asset is selected from
# `dpkg --print-architecture` (amd64 -> linux-x64, arm64 -> linux-arm64).
ARG DAAF_DEV=0
ARG DAAF_DEV_PWSH_VERSION=7.6.3
ARG DAAF_DEV_PESTER_VERSION=5.7.1
ARG DAAF_DEV_PSSA_VERSION=1.24.0
ARG CODEX_VERSION=0.164.0
# SHA-256 of each release tarball, verified against the GitHub release asset
# digests of Codex rust-v0.164.0 on 2026-10-27 (the downloaded bytes matched).
# Bumping CODEX_VERSION requires updating BOTH hashes; each release also
# publishes a codex-package_SHA256SUMS asset to copy them from. See the Codex
# RUN below.
ARG CODEX_SHA256_AMD64=90dd0b03b28afcb7fa733a4f73b413db2916a47347efd43fb669cc1c774ee8e4
ARG CODEX_SHA256_ARM64=29a507a2a3fd8f6cd94b96b762d281d299d15d7902dee6132d314b78cf9108eb
ARG DAAF_DEV_GH_VERSION=2.95.0

# shellcheck + bats from the Debian repo (mirrors the CI bats-tests job).
RUN if [ "${DAAF_DEV}" = "1" ]; then \
        daaf-apt-update && apt-get install -y --no-install-recommends \
            shellcheck \
            bats \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*; \
    fi

# PowerShell 7 from the GitHub release tarball (arch-mapped for amd64/arm64).
# Installs to /opt/microsoft/powershell/7 with a /usr/bin/pwsh symlink, matching
# the layout Microsoft's own packages use so `pwsh` is on PATH for all users.
RUN if [ "${DAAF_DEV}" = "1" ]; then \
        DEB_ARCH=$(dpkg --print-architecture) \
        && case "${DEB_ARCH}" in \
             amd64) PWSH_ARCH=x64 ;; \
             arm64) PWSH_ARCH=arm64 ;; \
             *) echo "DAAF_DEV: unsupported architecture '${DEB_ARCH}' for PowerShell" >&2; exit 1 ;; \
           esac \
        && PWSH_TGZ="powershell-${DAAF_DEV_PWSH_VERSION}-linux-${PWSH_ARCH}.tar.gz" \
        && curl -fsSL -o "/tmp/${PWSH_TGZ}" \
             "https://github.com/PowerShell/PowerShell/releases/download/v${DAAF_DEV_PWSH_VERSION}/${PWSH_TGZ}" \
        && mkdir -p /opt/microsoft/powershell/7 \
        && tar zxf "/tmp/${PWSH_TGZ}" -C /opt/microsoft/powershell/7 \
        && chmod +x /opt/microsoft/powershell/7/pwsh \
        && ln -sf /opt/microsoft/powershell/7/pwsh /usr/bin/pwsh \
        && rm -f "/tmp/${PWSH_TGZ}"; \
    fi

# Pester + PSScriptAnalyzer for the PowerShell suite. Installed AllUsers (root
# build context) so the modules are available to any user's pwsh session.
# Versions are pinned here because CI installs them unpinned (Pester is
# pre-provisioned on the runners; PSScriptAnalyzer via `Install-Module` with no
# version) -- pinning current stable releases keeps in-container runs
# deterministic while still reproducing the CI toolchain.
RUN if [ "${DAAF_DEV}" = "1" ]; then \
        pwsh -NoProfile -Command "Set-PSRepository -Name PSGallery -InstallationPolicy Trusted; \
            Install-Module -Name Pester -RequiredVersion '${DAAF_DEV_PESTER_VERSION}' -Force -Scope AllUsers -SkipPublisherCheck; \
            Install-Module -Name PSScriptAnalyzer -RequiredVersion '${DAAF_DEV_PSSA_VERSION}' -Force -Scope AllUsers"; \
    fi

# OpenAI Codex CLI from the GitHub release tarball (arch-mapped for amd64/arm64).
# Node-free install: these assets are self-contained musl static binaries, so no
# Node/npm toolchain is required. The GitHub release TAG is `rust-v${VERSION}`
# (the `rust-v` prefix, not a bare `v`). Each tarball contains a single
# executable named for the full target triple
# (codex-<triple>-unknown-linux-musl); it is renamed to the arch-generic path
# /usr/local/bin/codex so `codex` is on PATH for all users (matching R's symlink
# convention). The binary is available in every image; provider activation and
# authentication remain separate, explicit runtime choices.
#
# VERSION 0.164.0 (Codex stable release of 2026-10-23) is the first stable
# release whose embedded root list (webpki-roots 1.0.10) omits the compromised
# "emSign ECC Root CA - G3" (see "Distrust compromised CA roots" above). Codex
# 0.153.2 embeds G3, and pointing CODEX_CA_CERTIFICATE or SSL_CERT_FILE at a
# G3-free bundle does not remove it: those bundles ADD to the embedded roots
# rather than replace them (static scan of the x86_64 and aarch64 release
# binaries of Codex with positive controls, 2026-10-24).
#
# CHECKSUM: the tarball is verified against the per-architecture SHA-256 pinned
# beside CODEX_VERSION (`sha256sum -c`, after the download and before
# extraction), so a mismatched or substituted download fails this layer.
RUN DEB_ARCH=$(dpkg --print-architecture) \
    && case "${DEB_ARCH}" in \
         amd64) CODEX_TRIPLE=x86_64; CODEX_SHA256="${CODEX_SHA256_AMD64}" ;; \
         arm64) CODEX_TRIPLE=aarch64; CODEX_SHA256="${CODEX_SHA256_ARM64}" ;; \
         *) echo "Unsupported architecture '${DEB_ARCH}' for Codex CLI" >&2; exit 1 ;; \
       esac \
    && CODEX_TGZ="codex-${CODEX_TRIPLE}-unknown-linux-musl.tar.gz" \
    && curl -fsSL -o "/tmp/${CODEX_TGZ}" \
         "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/${CODEX_TGZ}" \
    && echo "${CODEX_SHA256}  /tmp/${CODEX_TGZ}" | sha256sum -c - \
    && tar zxf "/tmp/${CODEX_TGZ}" -C /tmp \
    && mv "/tmp/codex-${CODEX_TRIPLE}-unknown-linux-musl" /usr/local/bin/codex \
    && chmod +x /usr/local/bin/codex \
    && rm -f "/tmp/${CODEX_TGZ}"

# GitHub CLI (gh) from the GitHub release tarball (arch-mapped for amd64/arm64).
# Unlike PowerShell/Codex above, gh's release assets use the SAME arch tokens
# Debian does (amd64/arm64), so `dpkg --print-architecture` feeds the URL
# directly with no case-mapping. The tarball unpacks to a versioned dir
# (gh_<version>_linux_<arch>/) with the executable at bin/gh inside it; that
# binary is moved to the arch-generic path /usr/local/bin/gh so `gh` is on PATH
# for all users (matching R's/Codex's symlink convention). Used by framework
# developers to inspect CI runs/logs, work PRs/issues, and (see the appuser
# setup-git RUN below) as git's HTTPS credential helper.
#
# AUTH: gh authenticates at RUNTIME from the GH_TOKEN env var, injected from the
# host-side environment_settings.txt via docker-compose env_file (see
# scripts/host/environment_settings_example.txt). gh honors GH_TOKEN with no
# `gh auth login`, so there is no stored credential baked into the image and
# auth survives rebuilds. Nothing about auth happens at build time here.
RUN if [ "${DAAF_DEV}" = "1" ]; then \
        DEB_ARCH=$(dpkg --print-architecture) \
        && GH_TGZ="gh_${DAAF_DEV_GH_VERSION}_linux_${DEB_ARCH}.tar.gz" \
        && curl -fsSL -o "/tmp/${GH_TGZ}" \
             "https://github.com/cli/cli/releases/download/v${DAAF_DEV_GH_VERSION}/${GH_TGZ}" \
        && tar zxf "/tmp/${GH_TGZ}" -C /tmp \
        && mv "/tmp/gh_${DAAF_DEV_GH_VERSION}_linux_${DEB_ARCH}/bin/gh" /usr/local/bin/gh \
        && chmod +x /usr/local/bin/gh \
        && rm -rf "/tmp/${GH_TGZ}" "/tmp/gh_${DAAF_DEV_GH_VERSION}_linux_${DEB_ARCH}"; \
    fi

# ============================================
# R toolchain: runtime + system libraries
# ============================================
# R ships in every DAAF image. This section installs the R runtime and the
# system libraries R packages link against; the R packages themselves and the
# Quarto CLI are installed in the "Install R Data Science Packages" section
# below the Python installs. The full R footprint (runtime + libs + packages +
# Quarto) accounts for roughly ~2.2 GB of the image.
#
# Placed AFTER the always-run apt/uv layers (and after the DAAF_DEV block) so
# that the R layers sit at a stable point in the cache — this mirrors where the
# DAAF_DEV blocks sit relative to the Python installs.
#
# What it installs:
#   - R 4.5.x runtime           (Posit pre-built .deb binaries)
#   - R build/link system libs  (gfortran, libcurl/xml2/ssl/udunits2, etc.)
#
# R VERSION NOTE: Pinned to R 4.5.x for P3M binary package compatibility.
# On the Ubuntu 24.04 (noble) base, P3M serves pre-built binaries for R 4.5.3 on
# BOTH x86_64 and arm64 (verified against P3M on 2026-07-14: x-package-binary-tag
# 4.5-noble and 4.5-noble-arm64 on the pinned snapshot), so neither architecture
# compiles the framework R packages from source. R 4.6.x is deliberately NOT
# adopted: P3M served NO noble R 4.6 binaries on either arch (observed
# 2026-07-14, P3M live probe: the User-Agent fallback returned source,
# contradicting Posit's docs), and the pinned snapshot's S7 0.2.1 is broken
# under R 4.6. Posit CDN .deb installs to /opt/R/{VERSION}/; symlinks expose
# on PATH.
# Upgrade path: bump R_VERSION only once a live probe confirms 4.6-noble /
# 4.6-noble-arm64 binary tags AND the snapshot date is >= 2026-04-22 (S7 0.2.2).
ARG R_VERSION=4.5.3

# R runtime from Posit pre-built binaries (Ubuntu 24.04 / noble).
RUN curl -fsSL -o /tmp/r-${R_VERSION}.deb \
      "https://cdn.posit.co/r/ubuntu-2404/pkgs/r-${R_VERSION}_1_$(dpkg --print-architecture).deb" \
    && daaf-apt-update \
    && apt-get install -y --no-install-recommends /tmp/r-${R_VERSION}.deb \
    && rm /tmp/r-${R_VERSION}.deb \
    && ln -s /opt/R/${R_VERSION}/bin/R /usr/local/bin/R \
    && ln -s /opt/R/${R_VERSION}/bin/Rscript /usr/local/bin/Rscript \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Additional system libraries needed by R packages.
# libgdal-dev, libgeos-dev, libproj-dev are already installed unconditionally
# in the "Install Geospatial System Libraries" block above (shared with Python),
# so they are NOT re-listed here. libudunits2-dev is critical — must be present
# before installing sf. libtbb-dev required by terra; cmake required by the
# lightgbm R bindings. libglpk40 required at load time by igraph (a kknn
# dependency) — P3M's pre-built igraph binary links libglpk.so.40, and the
# presence gate below fails on kknn without it.
#
# On the noble base BOTH arches install the framework R packages as P3M
# pre-built binaries (no source compilation), so the last four dev libs
# (libuv1-dev, libharfbuzz-dev, libfribidi-dev, libnode-dev) are NOT needed to
# build the framework's own package set. They are retained for two ongoing
# reasons:
#   1. USER-ADDED source packages. A user who adds an R package to this file
#      (the USER ADDITIONS block or a framework R block) that is absent from the
#      pinned P3M snapshot — or that has no binary — compiles it from source and
#      needs these headers present. Keeping them installed preserves that path:
#        - libuv1-dev     -> uv.h    (fs -> sass -> bslib -> rmarkdown/leaflet)
#        - libharfbuzz-dev,
#          libfribidi-dev -> hb-ft.h (textshaping -> svglite -> kableExtra/gt)
#        - libnode-dev    -> v8.h    (V8 -> juicyjuice -> gt)
#   2. libnode RUNTIME linkage (the load-bearing reason on noble). libnode-dev
#      installs the libnode.so RUNTIME library that P3M's pre-built V8 binary
#      dlopens at load time on EVERY arch — a runtime dlopen, not a NEEDED link
#      (objdump-confirmed on the noble V8 binary), so V8 installs cleanly but
#      gt::as_raw_html() fails at first use with
#      `libnode.so.NNN: cannot open shared object file` if libnode-dev is
#      absent. The presence gate's
#      requireNamespace("V8") dlopens libnode.so and so catches this at build
#      time. Do NOT drop libnode-dev.
#
# UNIVERSE NOTE: five of the deps below (libnode-dev, libtbb-dev, libhdf5-dev,
# libnetcdf-dev, libglpk40) live in Ubuntu's `universe` component. universe is
# guaranteed present by the "Ensure the apt `universe` component is enabled"
# guard RUN earlier in this file (placed before the geospatial block, universe's
# first consumer), which fails fast if it cannot be enabled — so these installs
# do not need to re-check it.
RUN daaf-apt-update && apt-get install -y --no-install-recommends \
        gfortran \
        libcurl4-openssl-dev \
        libxml2-dev \
        libfontconfig1-dev \
        libudunits2-dev \
        libtbb-dev \
        libnetcdf-dev \
        libsqlite3-dev \
        libssl-dev \
        libhdf5-dev \
        libglpk40 \
        libuv1-dev \
        libharfbuzz-dev \
        libfribidi-dev \
        libnode-dev \
        cmake \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Install Python Data Science Packages via uv
# ============================================
#
# CUSTOMIZATION: Adding Your Own Python Packages
# -----------------------------------------------
# RECOMMENDED DEFAULT (when feasible): add your own packages in the "USER
# ADDITIONS" block near the END of this file, not here. That block sits below
# every expensive layer, so Docker layer caching re-runs only your additions;
# appending to the categorized blocks below re-runs all the expensive Python/R
# layers underneath them. Use these mid-file blocks only when placement here is
# actually required — e.g. a system library a downstream package needs at build
# time, or an R package you want covered by the presence gate. See the USER
# ADDITIONS banner for the full rationale and caveats.
#
# To add a Python package here, append it to the appropriate RUN block below
# (or add a new block), then rebuild.
#
# FROZEN ENVIRONMENT DATE: every uv install here resolves against
# UV_EXCLUDE_NEWER, and every apt install against the UBUNTU_SNAPSHOT snapshot
# (see the ENVIRONMENT DATE banner at the top of this file). A version released
# AFTER that date is invisible to the build: uv fails with "No solution found"
# (without mentioning the cutoff) and apt with "Unable to locate package" or
# "Version ... was not found". Either bump the environment date, or for a single
# Python package add `--exclude-newer-package PKG=<RFC 3339 Z time>` to its own
# `uv pip install` line (details at the UV_EXCLUDE_NEWER comment above). For a
# new apt package, call `daaf-apt-update` (never a bare `apt-get update`) so the
# snapshot origin guard still runs.
#
# IMPORTANT — CONTAINER-HOST BOUNDARY: if you (or DAAF) edit this file
# inside the DAAF container, the edits land in the container's copy of the
# Dockerfile, not the copy in your daaf-docker folder that the build reads.
# A build that skips copying it back "succeeds" with no error, but your new
# package is not installed. To copy it back and rebuild in one step, choose
# 10) Rebuild Container in the DAAF Control Panel, or exit the container and
# run `bash rebuild_daaf.sh` (`.\rebuild_daaf.ps1` on Windows) from your
# daaf-docker folder.
#
# Docker layer caching makes rebuilds fast — only the changed layer and the
# layers after it re-run.
# For packages needing C libraries (e.g., libfoo-dev), also add them to
# the apt-get block in "Install System Dependencies" above (one rebuild
# covers both edits, since they're in the same file).
#
# For the full explanation, step-by-step procedure, common scenarios,
# and why packages are not installed into a running container, see:
#   user_reference/04_extending_daaf.md
#   (section: "The Recommended Path: Modify the Dockerfile")
# -----------------------------------------------

# Install core data science packages
# NOTE: pyfixest pinned 0.60.0 — the 0.40.0 wheel declared zero runtime deps
#       (packaging bug: no Requires-Dist in METADATA; import only worked because
#       numba/formulaic/etc. arrived transitively via umap-learn, wildboottest,
#       linearmodels), and the 0.40.1 hotfix declares a scipy upper bound that
#       conflicts with scipy==1.17.0. 0.60.0 has correct metadata; of its
#       dependencies only maketables (its table backend) comes from this
#       block alone.
RUN uv pip install --system \
    numpy==2.4.2 \
    pandas==3.0.0 \
    polars==1.39.3 \
    scipy==1.17.0 \
    openpyxl==3.1.5 \
    fastexcel==0.19.0 \
    xlrd==2.0.2 \
    requests==2.32.5 \
    pyarrow==23.0.0 \
    urllib3==2.6.3 \
    pre-commit==4.5.1 \
    scikit-learn==1.8.0 \
    umap-learn==0.5.11 \
    pyyaml==6.0.3 \
    statsmodels==0.14.6 \
    pyfixest==0.60.0 \
    tabulate==0.10.0 \
    great-tables==0.21.0 \
    wildboottest==0.3.2

# Install econometrics & statistical modeling packages
# Primary: pyfixest + statsmodels already above
# Secondary: panel models, RDD, marginal effects, volatility, dynamic panels, survey statistics
# NOTE: lifelines excluded — latest (0.30.3) requires pandas<3.0, incompatible with pandas==3.0.0
# NOTE: svy-rs/svy-io are svy's own runtime deps, pinned explicitly for reproducibility
#       (svy 0.19.0 declares svy-rs>=0.10.0,<0.11.0 and svy-io>=0.1.1,<0.2.0;
#       svy-rs 0.10.0 sets the effective polars floor of >=1.39.1 — see polars pin above;
#       polars is pinned 1.39.3 because 1.39.1 was never published to PyPI and
#       1.39.2 is yanked there — 1.39.3 is the patch-identical stable republication)
RUN uv pip install --system \
    linearmodels==7.0 \
    rdrobust==1.3.0 \
    marginaleffects==0.5.0 \
    arch==8.0.0 \
    pydynpd==0.2.1 \
    svy==0.19.0 \
    svy-rs==0.10.0 \
    svy-io==0.1.1

# Install geospatial packages
# Core: vector (geopandas + deps), raster (rasterio + xarray), mapping, PySAL spatial stats
RUN uv pip install --system \
    geopandas==1.1.3 \
    rasterio==1.5.0 \
    xarray==2026.2.0 \
    rioxarray==0.22.0 \
    contextily==1.7.0 \
    folium==0.20.0 \
    libpysal==4.14.1 \
    esda==2.9.0 \
    spreg==1.9.0 \
    mapclassify==2.10.0 \
    rasterstats==0.20.0 \
    geopy==2.4.1 \
    osmnx==2.1.0

# Install visualization packages
# NOTE: marimo is pinned at 0.25.0 for security: every release before 0.23.15
#       is affected by at least one of: CVE-2026-39987 (critical pre-auth RCE
#       via the edit-mode /terminal/ws endpoint, fixed 0.23.0), CVE-2026-54386
#       (XSS, fixed 0.23.9), CVE-2026-67618 and CVE-2026-75149
#       (malicious-notebook PEP 723 and MCP config injection, fixed 0.23.15),
#       so never pin below 0.23.15. 0.25.0 was uploaded before
#       UV_EXCLUDE_NEWER, so it needs no per-package override. pyzmq 27.2.0 and
#       python-multipart 0.0.32 are installed for marimo alone, and
#       pymdown-extensions resolves to 11.0.2 within marimo's >=10.21.2,<12
#       bound; all are left to resolution under the freeze, not pinned.
RUN uv pip install --system \
    matplotlib==3.10.8 \
    seaborn==0.13.2 \
    plotnine==0.15.3 \
    plotly==6.5.2 \
    marimo==0.25.0

# Install ML interpretation & fairness packages
RUN uv pip install --system \
    shap==0.51.0 \
    fairlearn==0.12.0 \
    lightgbm==4.6.0

# Install network analysis packages
# python-igraph ships a manylinux wheel (no compilation, no extra system libs
# for the core install — verified against PyPI 2026-07-15); plotting uses the
# matplotlib backend from the visualization block above, so cairocffi is not
# installed. Same C core as the R igraph package (cross-language skill pair).
RUN uv pip install --system \
    igraph==1.0.0

# Install synthetic data generation packages
# faker: seeded, locale-aware synthetic values for identifier-shaped columns
# (names, emails, phones) in the synthetic-data-workflow skill's generation
# step (generation-patterns-python.md). Statistical structure comes from the
# NumPy/SciPy copula patterns (packages already above). Tier 4 synthesis tools
# (sdv, synthcity) are deliberately NOT installed — T4 runs on the user's own
# machine against their real data, never in-container.
RUN uv pip install --system \
    faker==40.31.0

# Install the DAAF web-retrieval extraction stack (scripts/web_fetch.py)
# trafilatura provides high-fidelity main-content extraction for the DAAF
# web-retrieval fetch utility (scripts/web_fetch.py + web_fetch.sh). lxml is
# pinned to the version the other blocks resolve (no ownership conflict);
# courlan, htmldate and justext are pinned here as well.
# urllib3 is left to existing resolution to avoid duplicate pin ownership (it
# is pinned in the core block); charset_normalizer is pinned once, in the PDF
# reading stack block below. certifi is not pinned here either: its one pin is
# the trust-store exception layer at the end of the Python stack (security
# exception (1)), which overrides whatever these blocks resolve.
# web_fetch.py falls back to a minimal bs4 extractor if trafilatura cannot be
# imported (an image built without this block).
RUN uv pip install --system \
    trafilatura==2.2.0 \
    lxml==6.1.1 \
    courlan==1.4.0 \
    htmldate==1.10.0 \
    justext==3.0.2

# Install the DAAF PDF reading stack (scripts/pdf_ingest.py, scripts/lit_verify.py)
# The Python half of the PDF reading layer; Tesseract shares the geospatial apt
# layer above.
# pdf_ingest uses poppler pdftotext as its anchor text lane, pypdfium2 as a
# second lane and pdfplumber for table hints; lit_verify uses rapidfuzz for
# quote matching. Every distribution these four packages install is pinned
# here, and no other block pins any of them:
#   pypdfium2 5.13.0            Apache-2.0 / BSD-3-Clause (+ bundled PDFium deps)
#   pdfplumber 0.11.10          MIT
#   pdfminer.six 20260107       MIT (pdfplumber dep)
#   rapidfuzz 3.14.6            MIT
#   cryptography 50.0.1         Apache-2.0 OR BSD-3-Clause (pdfminer.six dep)
#   cffi 2.1.1                  MIT-0 (cryptography dep)
#   pycparser 3.0               BSD-3-Clause (cffi dep)
#   pillow 13.0.0               MIT-CMU (pdfplumber dep; also matplotlib, contextily)
#   charset-normalizer 3.5.1    MIT (pdfminer.six dep; also requests, trafilatura)
# Earlier blocks also bring in pillow and charset-normalizer without pinning
# them. charset-normalizer is pinned at the version they resolve (the lxml rule
# above), so this block does not change it. pillow is the exception:
# SECURITY EXCEPTION (2) in the banner. The earlier blocks resolve
# pillow 12.3.0 at UV_EXCLUDE_NEWER, which has 41 published advisories (5
# critical, 23 high; e.g. CVE-2026-112403, a JPEG heap overflow), all fixed in
# 13.0.0. This block moves pillow alone to 13.0.0 with a one-package override:
#   - 13.0.0's files were uploaded 2026-10-16T22:15:24Z..22:18:09Z (verified
#     against the PyPI JSON API on 2026-10-28); the override instant
#     2026-10-17T00:00:00Z follows all of them.
#   - pillow declares no dependencies, and its dependents accept 13.0.0
#     (pdfplumber 0.11.10 Pillow>=12.2.0, matplotlib pillow>=8, contextily any).
#     A dry-run `uv pip compile` of every `==` pin in this file with this
#     override and the certifi one, at UV_EXCLUDE_NEWER, resolved the same
#     173-package set except certifi and pillow on x86_64 and aarch64
#     (resolved against PyPI on 2026-10-28).
#   - Pillow 13 drops Python 3.10 and removes a few APIs (the silent clipping
#     when saving I-mode images as PNG, fromarray(mode=...) where the mode
#     changes the dtype, Image._show, ImageCms product_name; get_child_images
#     moved). No DAAF code or skill uses them; user
#     figure code that does needs a mode conversion first.
#   - REMOVE the --exclude-newer-package flag when the environment date is
#     next bumped to an instant on or after 2026-10-17T00:00:00Z (keep the
#     pin, then re-check it), together with the Pillow version check before
#     the build's last RUN.
# A pin in this later block wins over what the earlier blocks resolve, so
# re-check both pins against matplotlib, requests and trafilatura whenever the
# environment date is bumped.
# PyMuPDF is deliberately EXCLUDED: AGPL. CPU-only: prebuilt wheels for x86_64
# and aarch64, all at or before UV_EXCLUDE_NEWER except pillow 13.0.0 (override
# above). A dry-run `uv pip compile` with both overrides resolved exactly these
# 9 versions, pillow 13.0.0 included, on both architectures (resolved against
# PyPI on 2026-10-28).
RUN uv pip install --system \
    --exclude-newer-package pillow=2026-10-17T00:00:00Z \
    pypdfium2==5.13.0 \
    pdfplumber==0.11.10 \
    pdfminer.six==20260107 \
    rapidfuzz==3.14.6 \
    cryptography==50.0.1 \
    cffi==2.1.1 \
    pycparser==3.0 \
    pillow==13.0.0 \
    charset-normalizer==3.5.1

# Install provider-shim direct runtime dependencies after all other framework
# Python packages. Both arrive transitively today (httpx via svy; uvicorn via
# marimo), but the persistent shim imports them directly and must not depend on
# unrelated packages retaining compatible versions. Keeping these direct pins
# last among the framework package blocks also prevents a later framework
# Python block from replacing them (only the certifi trust-store exception and
# the trust check follow, and neither touches httpx or uvicorn). The build is
# still root here; the single runtime transition to appuser remains at the
# existing security boundary below.
RUN uv pip install --system \
    httpx==0.28.1 \
    uvicorn==0.51.0

# Trust-store exception (security exception (1) in the banner): certifi past
# the environment date.
# certifi is the CA bundle that requests and httpx verify against (the
# provider shim's model traffic, web_fetch, scholar_search, data fetches). At
# UV_EXCLUDE_NEWER it resolves to certifi 2026.7.22, which still trusts the
# compromised "emSign ECC Root CA - G3" (see "Distrust compromised CA roots"
# near the top). This one package is therefore exempted from the cutoff with
# uv's per-package override (the mechanism described at UV_EXCLUDE_NEWER):
#   - 2026.10.19 (uploaded 2026-10-20T02:24:15Z), not 2026.10.18 or 2026.10.23:
#     10.19 removes exactly G3, the same set as Mozilla NSS 3.131.1 and the
#     system store after the distrust layer; 10.18 also removed the
#     unaffected emSign G1/C1/C3 roots, and 10.23 drops C1/C3 as well.
#   - The override instant 2026-10-20T03:00:00Z follows both 2026.10.19 files
#     (wheel 02:24:15Z, sdist 02:24:16Z) and precedes 2026.10.23.
#   - certifi is a data-only package (one PEM file and where()); it has no
#     dependencies and no analytic effect. A dry-run `uv pip compile` of every
#     `==` pin in this file plus this line, at the environment date with this
#     override, resolved the identical 173-package set except certifi
#     (2026.7.22 -> 2026.10.19) on x86_64 and aarch64
#     (resolved against PyPI on 2026-10-27).
#   - It is the last Python package layer so no later framework Python block
#     can replace it (the build's last RUN re-checks certifi's bundle anyway).
#   - REMOVE this layer when the environment date is next bumped to an
#     instant on or after 2026-10-20T03:00:00Z: the bump then resolves a fixed
#     certifi by itself
#     (user_reference/04_extending_daaf.md § "Bumping the environment date").
RUN uv pip install --system \
    --exclude-newer-package certifi=2026-10-20T03:00:00Z \
    certifi==2026.10.19

# Durable regression guard for the eMudhra distrust: fail the build if
# "emSign ECC Root CA - G3" is trusted by the system CA store (bundle and hashed
# directory) or by certifi's bundle, matched by SHA-256 fingerprint. It re-runs
# the check from the "Distrust compromised CA roots" layer after every apt and
# Python layer above it, so a trigger, reconfigure or resolution change there
# that brought G3 back stops the build here. The layers further down (R
# packages, Quarto, TinyTeX, code-server, nodejs, Claude Code, USER ADDITIONS) are
# covered by the same check repeated as the last RUN of the build. Keep both
# across environment-date bumps: they are cheap, and they guard the same
# failure for any future root added to the check's DISTRUSTED list. An empty
# certifi path (import failed) also fails.
RUN daaf-check-distrusted-roots "$(python3 -c 'import certifi; print(certifi.where())')"

# ============================================
# Install R Data Science Packages + Quarto
# ============================================
# R is part of the standard image. The R runtime and system libraries these
# packages depend on are installed in the "R toolchain" section above the
# Python installs; this section adds the R packages themselves plus the Quarto
# CLI. Together with the runtime and system libs, the R stack accounts for
# roughly ~2.2 GB of the image.
#
# CUSTOMIZATION: When feasible, add your own R packages in the "USER ADDITIONS"
# block near the END of this file — it rebuilds fast because Docker layer caching
# spares the expensive layers above it. Append an R package to the appropriate
# Rscript install block below (or add a new block) only when you need it here —
# most importantly, when you want the package covered by the presence gate below
# (the gate only verifies packages listed in these blocks). For R packages
# needing C/Fortran libraries, add the system deps to the apt-get block in the
# "R toolchain" section above. See the USER ADDITIONS banner for full rationale.
#
# QUARTO SCOPING: Quarto is a standalone system binary that does not depend on
# R or Python package managers; within DAAF it renders R-mode Stage 9 notebooks
# (.qmd), so it is installed alongside the R packages here. TinyTeX, the LaTeX
# distribution Quarto uses for `format: pdf`, follows directly after it.

# Configure R package repository (P3M date-pinned snapshot for reproducibility).
# Pin to a specific date snapshot so rebuilds produce identical package versions.
# Update the date when intentionally upgrading R packages (and update skill
# metadata). This is the R member of the frozen build inputs listed in the
# ENVIRONMENT DATE banner at the top of this file, but it moves on its own
# schedule -- independent of UV_EXCLUDE_NEWER / UBUNTU_SNAPSHOT -- because of the
# R 4.5 binary-availability and S7 constraints in the R VERSION NOTE above.
# On the Ubuntu 24.04 (noble) base P3M provides pre-built binaries on
# BOTH x86_64 and arm64 — much faster than source compilation — so no framework R
# package compiles from source on either architecture (verified against
# P3M on 2026-07-14: x-package-binary-tag 4.5-noble on x86_64 and
# 4.5-noble-arm64 on aarch64 for the pinned snapshot). The four extra dev
# headers (libuv1-dev, libharfbuzz-dev, libfribidi-dev, libnode-dev) in the
# R-toolchain apt block above serve USER-ADDED source packages and libnode's
# runtime dlopen linkage under V8 (see that block).
ARG P3M_SNAPSHOT_DATE=2026-04-15
RUN RPROFILE="$(Rscript -e 'cat(file.path(R.home("etc"), "Rprofile.site"))')" \
    && echo "options(repos = c(CRAN = 'https://p3m.dev/cran/__linux__/noble/${P3M_SNAPSHOT_DATE}'))" \
        >> "${RPROFILE}" \
    && echo 'options(Ncpus = parallel::detectCores())' \
        >> "${RPROFILE}"

# Core data manipulation and I/O
#
# PER-BLOCK FAIL-FAST PATTERN (used by all five R install blocks below):
# install.packages() reports a failed package only as a WARNING, not an error,
# so a failed install — a binary that fails to link a system lib, or a
# USER-ADDED source package with a missing header (see the P3M repo-config note
# above) — would let the build limp on and only surface later at the presence
# gate, far from the output that explains it. Each block below therefore verifies
# its OWN package list with requireNamespace() immediately after install and
# stop()s inside the failing layer — so the build dies fast, with the failing
# package's error adjacent in the same layer's log. The presence gate at the end
# remains the final identity check (see its comment).
RUN Rscript -e 'pkgs <- c( \
        "data.table", "dplyr", "tidyr", "tibble", "readr", "purrr", "stringr", \
        "forcats", "lubridate", "glue", "rlang", "skimr", \
        "arrow", "readxl", "writexl", "haven", "jsonlite", "yaml" \
        ); \
        install.packages(pkgs); \
        missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]; \
        if (length(missing)) stop("R install block failed — missing: ", paste(missing, collapse = ", "))'

# Statistics and econometrics
# NOTE: the wild-cluster-bootstrap package (fwildclusterboot) is not installed:
# it is archived on CRAN and has no R 4.5 binary in the P3M snapshot. To use it,
# add a source or archive install to this file; runtime installs are blocked
# (CLAUDE.md § Runtime Package Installation).
RUN Rscript -e 'pkgs <- c( \
        "fixest", "sandwich", "lmtest", "car", "plm", "estimatr", \
        "marginaleffects", "rdrobust", "lme4", \
        "survey", "rugarch", "tseries", "broom", "modelsummary" \
        ); \
        install.packages(pkgs); \
        missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]; \
        if (length(missing)) stop("R install block failed — missing: ", paste(missing, collapse = ", "))'

# Geospatial
RUN Rscript -e 'pkgs <- c( \
        "sf", "terra", "stars", \
        "spdep", "spatialreg", "classInt", "exactextractr", \
        "leaflet", "maptiles", "tidygeocoder", "osmdata" \
        ); \
        install.packages(pkgs); \
        missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]; \
        if (length(missing)) stop("R install block failed — missing: ", paste(missing, collapse = ", "))'

# Visualization
# "V8" is pinned explicitly (it would otherwise arrive only as a transitive
# dependency of gt's HTML path) because gt's HTML rendering — gt::as_raw_html(),
# used to inline tables into reports — requires it, and requireNamespace("V8")
# dlopens libnode.so. Listing V8 here and in the presence gate means the gate
# EXERCISES that native linkage at build time, catching the missing-runtime-lib
# failure class (libnode.so absent) rather than letting it surface only when a
# report is first rendered.
RUN Rscript -e 'pkgs <- c( \
        "ggplot2", "scales", "ggridges", "ggrepel", "patchwork", "ggdist", \
        "plotly", "gt", "V8", "knitr", "kableExtra", "viridis" \
        ); \
        install.packages(pkgs); \
        missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]; \
        if (length(missing)) stop("R install block failed — missing: ", paste(missing, collapse = ", "))'

# ML and interpretation
RUN Rscript -e 'pkgs <- c( \
        "tidymodels", "ranger", "glmnet", "xgboost", "lightgbm", "kknn", \
        "iml", "uwot", "fairmodels", "vip" \
        ); \
        install.packages(pkgs); \
        missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]; \
        if (length(missing)) stop("R install block failed — missing: ", paste(missing, collapse = ", "))'

# Network analysis
# igraph is already present as a kknn transitive dependency (see ML block and the
# libglpk40 note in the R-toolchain apt block); listing it here makes it a
# first-class framework package — explicitly installed and gate-covered — so it
# survives any future change to the ML stack. tidygraph/ggraph are the
# tidyverse-native manipulation and grammar-of-graphics layers over igraph.
RUN Rscript -e 'pkgs <- c( \
        "igraph", "tidygraph", "ggraph" \
        ); \
        install.packages(pkgs); \
        missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]; \
        if (length(missing)) stop("R install block failed — missing: ", paste(missing, collapse = ", "))'

# Synthetic data generation (privacy-preserving onboarding path)
# simstudy: profile-only generation via Gaussian copula from declared marginals
# + correlation matrix — the flagship in-container generation path of the
# synthetic-data-workflow skill (generation-patterns-r.md); fabricatr:
# hierarchical/design-shaped structure generation named by the same skill.
# Tier 4 synthesis tools (synthpop) are deliberately NOT installed — T4 runs
# on the user's own machine against their real data, never in-container.
RUN Rscript -e 'pkgs <- c( \
        "simstudy", "fabricatr" \
        ); \
        install.packages(pkgs); \
        missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]; \
        if (length(missing)) stop("R install block failed — missing: ", paste(missing, collapse = ", "))'

# R package lockfiles
# renv: a lockfile/snapshot tool that records exact R package versions in a
# renv.lock file. No shipped DAAF workflow uses it yet. Inside the container,
# use it only to SNAPSHOT the packages a project's R scripts import into a lockfile — never
# to install or restore packages inside the container (runtime installs are
# blocked; see CLAUDE.md § Runtime Package Installation).
RUN Rscript -e 'pkgs <- c( \
        "renv" \
        ); \
        install.packages(pkgs); \
        missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]; \
        if (length(missing)) stop("R install block failed — missing: ", paste(missing, collapse = ", "))'

# Presence gate: the FINAL identity check that the installed package set matches the
# union of the install.packages() blocks above. The per-block requireNamespace()
# checks catch a failed package INSIDE its own layer (fast, adjacent to the compile
# error); this gate is the union check — one authoritative list that must stay
# identical to the blocks — and it also EXERCISES native linkage:
# requireNamespace("V8") dlopens libnode.so, so the gate fails at build time if the
# libnode.so runtime library is missing (the gt::as_raw_html failure class) rather
# than deferring it to first use.
# Keep this list in sync with the blocks above when adding or removing packages.
RUN Rscript -e 'pkgs <- c( \
        "data.table", "dplyr", "tidyr", "tibble", "readr", "purrr", "stringr", \
        "forcats", "lubridate", "glue", "rlang", "skimr", \
        "arrow", "readxl", "writexl", "haven", "jsonlite", "yaml", \
        "fixest", "sandwich", "lmtest", "car", "plm", "estimatr", \
        "marginaleffects", "rdrobust", "lme4", \
        "survey", "rugarch", "tseries", "broom", "modelsummary", \
        "sf", "terra", "stars", \
        "spdep", "spatialreg", "classInt", "exactextractr", \
        "leaflet", "maptiles", "tidygeocoder", "osmdata", \
        "ggplot2", "scales", "ggridges", "ggrepel", "patchwork", "ggdist", \
        "plotly", "gt", "V8", "knitr", "kableExtra", "viridis", \
        "tidymodels", "ranger", "glmnet", "xgboost", "lightgbm", "kknn", \
        "iml", "uwot", "fairmodels", "vip", \
        "igraph", "tidygraph", "ggraph", \
        "simstudy", "fabricatr", \
        "renv" \
        ); \
        missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]; \
        if (length(missing)) stop("Missing R packages: ", paste(missing, collapse = ", ")); \
        cat("All", length(pkgs), "R packages present.\n")'

# Quarto CLI (language-agnostic notebook system; DAAF uses it for R Stage 9
# notebooks, and it can also render Typst PDF and DOCX).
# Pin the version; update when intentionally upgrading. 1.10.18 provides Typst
# linestretch/abstract-title, list tables, the multi-bib Typst fix,
# manuscript-project fixes, apaquarto (>=1.9) and PDF/UA alt text. It bundles
# pandoc 3.10 + typst 0.15.1.
ARG QUARTO_VERSION=1.10.18
RUN ARCH=$(dpkg --print-architecture) \
    && curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-${ARCH}.deb" \
        -o /tmp/quarto.deb \
    && dpkg -i /tmp/quarto.deb \
    && rm /tmp/quarto.deb

# TinyTeX (LaTeX for Quarto's `format: pdf`, engine lualatex), pinned and
# checksummed like the Codex CLI.
#
# WHY: Quarto renders `format: pdf` through LaTeX, so the image needs a LaTeX
# distribution (without one, agents fall back to Typst). TinyTeX is the TeX Live
# subset Quarto's own `quarto install tinytex` uses. It is installed HERE, at
# build time, root-owned in /opt/TinyTeX, and not per user at runtime: CLAUDE.md
# § Runtime Package Installation forbids runtime installs, and a frozen tree is
# what keeps a later KOMA-Script release (see the #15143 GUARD below) out.
# Unpacked about 420 MB.
#
# VERSION v2026.11 (TinyTeX monthly release, published 2026-11-01; the TAG
# carries the leading `v`), bundle `TinyTeX` (not -0/-1, which lack
# koma-script, tcolorbox and fontawesome5; not -2, which exists only on the
# mutable `daily` tag). Its assets are byte-identical to the daily build of
# 2026-10-21 (TinyTeX `daily` tag), and its package database matches the
# texlive.info tlnet archive of 2026-10-19 revision for revision (320 of 320
# records), so that archive is the repository for the extra packages:
# selnolig (loaded whenever `lang:` is set), lua-ul + luacolor (strikeout and
# `.mark` highlight), marginfix (natbib
# margin citations), xurl + footnotehyper (optional, template-guarded), and
# luatexbase with its one dependency ctablestack (the bundle lacks both, and
# babel's luababel.def and selnolig.sty load luatexbase, so any `lang:` render
# stops at "File `luatexbase.sty' not found"). Apart from luatexbase ->
# ctablestack, none of the eight declares a dependency in that archive; both
# are listed so the revision check covers them. tlmgr's repository
# stays on the archive afterwards, so a later tlmgr call never reaches the
# live CTAN. texlive.info states no retention period for its archive (gap):
# if it disappears, the extra packages cannot be reinstalled from it.
#
# LICENSE: TinyTeX's build scripts and bundle are distributed under GPL-2
# (rstudio/tinytex-releases README: "All code in this repository and TinyTeX
# are licensed under GPL-2"; its authors describe TinyTeX as an unchanged
# subset of TeX Live and claim no copyright on it). The bundled TeX Live
# packages carry their own free-software licenses (TeX Live's LICENSE.TL; per
# package, the catalogue-license field in tlpkg/texlive.tlpdb).
#
# #15143 GUARD: v2026.11 carries KOMA-Script 3.49.2. KOMA-Script 3.49.3
# (on CTAN 2026-10-19, in the archive from 2026-10-20) makes every KOMA class
# stop with a fatal error under `\DocumentMetadata`, which Quarto emits for
# `pdf-standard`; Quarto fixed it in 1.10.20 (quarto-dev/quarto-cli#15143),
# and 1.10.18 does not have the fix. Do NOT bump TinyTeX (or the archive date)
# to a release with KOMA-Script 3.49.3 or later unless QUARTO_VERSION is
# 1.10.20 or later. The package layer below fails the build on that
# combination, and the smoke render near the end of the build (pdf-standard
# ua-2) would fail on it too.
#
# CHECKSUM: the tarball is verified against the per-architecture SHA-256
# pinned beside TINYTEX_VERSION (GitHub release asset digests for v2026.11; the
# TinyTeX tarballs matched them on 2026-11-01) with `sha256sum -c`, after the
# download and before extraction. The build downloads the archive's package
# database (tlpkg/texlive.tlpdb, uncompressed) and checks it against
# TINYTEX_TLPDB_SHA512 before tlmgr installs anything: the pin binds the
# package set to the archive at its date. tlmgr does not use that file: it
# downloads its own copy of the database (tlmgr.pl loads it with verify => 1)
# and checks each package container against the SHA-512 recorded in THAT
# copy. After the install, the layer confirms that every installed revision
# equals the pinned database's; a container changed without a new revision
# between the two fetches, seconds apart, would not be caught. texlive.info
# answers some User-Agents with HTTP 200 and an "Access Denied" page, so the
# check compares CONTENT, never the HTTP status. Bumping TINYTEX_VERSION
# requires BOTH SHA-256 values and a matching archive date plus its SHA-512.
#
# ARCH: `dpkg --print-architecture` selects the asset and bin directory:
# amd64 -> TinyTeX-linux-x86_64-*, bin/x86_64-linux; arm64 ->
# TinyTeX-linux-arm64-*, bin/aarch64-linux (the arm64 prebuilt arrived after
# v2026.03.02; prebuilt arm64 tarballs are verified for v2026.08-v2026.11; no
# source build). `tlmgr path add` symlinks every binary into /usr/local/bin,
# so later steps and Quarto find `lualatex` and `tlmgr` on PATH without naming
# the arch directory. Quarto 1.10.18 then reports "Installation From Path";
# it treats only ~/.TinyTeX as "TinyTeX". Many entries in the bin directory are
# themselves relative links into texmf-dist (tlmgr ->
# ../../texmf-dist/scripts/texlive/tlmgr.pl, likewise mktexlsr and
# luaotfload-tool), so the layer checks each tool in three parts: PATH finds the
# /usr/local/bin link, that link points at the bin directory entry, and its
# final target stays inside /opt/TinyTeX (a resolved path under bin/ would
# wrongly fail tlmgr).
#
# TRUST STORE: the tarball ships tlpkg/installer/curl/curl-ca-bundle.crt
# (Mozilla data of 2026-09-25), which contains the distrusted "emSign ECC Root
# CA - G3" (banner, exception (1)). tlmgr hands it to Perl's LWP through
# HTTPS_CA_FILE when LWP is installed (it is not in this image). It is replaced
# by a symlink to the system bundle before any tlmgr network call, tlmgr runs
# with TEXLIVE_DOWNLOADER=curl (system curl and store; never wget, which tlmgr
# runs with --no-check-certificate), the first TinyTeX layer fails if any other
# file in the unpacked tarball holds a PEM certificate (that scan runs before
# the extra packages are installed, so it does not cover them), and the build's
# last RUN passes that one path to daaf-check-distrusted-roots.
#
# NO RUNTIME INSTALLS: the tree is extracted with --no-same-owner (the tar
# entries belong to uid 1001) and stays root-owned and not writable by
# appuser, so `tlmgr install`/`update` and Quarto's `latex-auto-install`
# cannot change it at runtime. `tlmgr --usermode`, `quarto install tinytex`
# and R's `tinytex::install_tinytex()` remain possible, but would install an
# unpinned TeX Live under ~/.TinyTeX (which Quarto prefers over this tree) or
# in a user tree; DAAF policy forbids them (CLAUDE.md § Runtime Package
# Installation), and no hook guards them yet (a hook change is the user's to
# make). Quarto 1.10.18 has no global switch for `latex-auto-install` (no
# environment variable or user config; it defaults to true): after a failed
# LaTeX run it tries `tlmgr update --self`, `update --all` and `install`, and
# on this tree that fails with an error that gives no context (open issue
# quarto-dev/quarto-cli#14413). Documents and templates should set
# `latex-auto-install: false`, which reports the missing package instead.
#
# FONT CACHE: TinyTeX keeps TEXMFVAR inside the tree, and luaotfload needs a
# writable cache, so the font-name database is built here as root
# (luaotfload-tool --update) and ENV TEXMFVAR below points appuser's cache at
# /home/appuser/.cache/texmf-var, a per-user cache (font-name and font data
# that luaotfload rebuilds on demand). TeX does search TEXMFVAR (texmf.cnf
# lists it in TEXMF, ahead of the system tree), so it is not an enforcement
# boundary: DAAF's build does not populate it with packages, and nothing in
# DAAF installs into it.
#
# Evidence: the asset digests pinned below, bundle coverage, the archive match,
# the CA file and the font-cache settings were verified against the TinyTeX
# release assets and the dated texlive.info archive on 2026-11-01. An amd64
# image built from these layers passed the build's own checks and the smoke
# render. The arm64 tarball has not been built; on arm64 the build's own
# checks and smoke render are its only test.
ARG TINYTEX_VERSION=v2026.11
ARG TINYTEX_SHA256_AMD64=50e68059058db770a28bcca44d5a323cb57fc10d470017c858404aafeaac9dd7
ARG TINYTEX_SHA256_ARM64=a493b548ba82aafd715f297397de959bc8131c16a9be9e4b90fa6454e5d57fb1
ARG TINYTEX_TLNET_ARCHIVE=https://texlive.info/tlnet-archive/2026/10/19/tlnet
ARG TINYTEX_TLPDB_SHA512=60000e6bc449e5a553dac53e0fd94c5fc713e25e2c3796721d61ff45b83e1b1491eac570c9f4481aa2e949908206da6abac4fec9fad471125c9a3e5309e15606

# Download, verify, extract and put on PATH. xz-utils (snapshot-frozen) is
# needed only to unpack the .tar.xz; tlmgr brings its own xz for packages.
# It gets its own small apt call here instead of joining an early apt layer:
# adding it there would invalidate the cache of almost every layer, and a late
# apt call frozen to the snapshot still follows the environment date.
RUN set -eu; \
    DEB_ARCH="$(dpkg --print-architecture)"; \
    case "${DEB_ARCH}" in \
        amd64) TT_ASSET=x86_64; TT_BINDIR=x86_64-linux; TT_SHA256="${TINYTEX_SHA256_AMD64}" ;; \
        arm64) TT_ASSET=arm64; TT_BINDIR=aarch64-linux; TT_SHA256="${TINYTEX_SHA256_ARM64}" ;; \
        *) echo "FATAL: unsupported architecture '${DEB_ARCH}' for TinyTeX (prebuilt for amd64 and arm64 only)." >&2; exit 1 ;; \
    esac; \
    case "${TINYTEX_VERSION}" in \
        v[0-9]*) ;; \
        *) echo "FATAL: TINYTEX_VERSION='${TINYTEX_VERSION}' must be the release TAG with its leading v (e.g. v2026.11)." >&2; exit 1 ;; \
    esac; \
    daaf-apt-update; \
    apt-get install -y --no-install-recommends xz-utils; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*; \
    TT_TXZ="TinyTeX-linux-${TT_ASSET}-${TINYTEX_VERSION}.tar.xz"; \
    TT_URL="https://github.com/rstudio/tinytex-releases/releases/download/${TINYTEX_VERSION}/${TT_TXZ}"; \
    if ! curl -fsSL -o "/tmp/${TT_TXZ}" "${TT_URL}"; then \
        echo "FATAL: TinyTeX download failed: ${TT_URL} (does release ${TINYTEX_VERSION} still carry ${TT_TXZ}?)." >&2; \
        exit 1; \
    fi; \
    if ! echo "${TT_SHA256}  /tmp/${TT_TXZ}" | sha256sum -c -; then \
        echo "FATAL: ${TT_TXZ} does not match the SHA-256 pinned for ${DEB_ARCH}. A bumped TINYTEX_VERSION needs both TINYTEX_SHA256_* values from that release's asset digests; otherwise the download was altered." >&2; \
        exit 1; \
    fi; \
    mkdir -p /opt/TinyTeX; \
    tar -xJf "/tmp/${TT_TXZ}" -C /opt/TinyTeX --strip-components=1 --no-same-owner; \
    rm -f "/tmp/${TT_TXZ}"; \
    TT_BIN="/opt/TinyTeX/bin/${TT_BINDIR}"; \
    for tool in tlmgr lualatex kpsewhich luaotfload-tool mktexlsr; do \
        if [ ! -x "${TT_BIN}/${tool}" ]; then \
            echo "FATAL: ${TT_BIN}/${tool} is missing after extraction: the tarball layout changed (expected a single .TinyTeX/ top directory with bin/${TT_BINDIR}/)." >&2; \
            exit 1; \
        fi; \
    done; \
    TT_CA=/opt/TinyTeX/tlpkg/installer/curl/curl-ca-bundle.crt; \
    mkdir -p "$(dirname "${TT_CA}")"; \
    ln -sf /etc/ssl/certs/ca-certificates.crt "${TT_CA}"; \
    if [ "$(readlink -f "${TT_CA}")" != "$(readlink -f /etc/ssl/certs/ca-certificates.crt)" ]; then \
        echo "FATAL: ${TT_CA} does not resolve to the system CA bundle." >&2; \
        exit 1; \
    fi; \
    TT_PEM="$(grep -rlI -e '-----BEGIN CERTIFICATE-----' /opt/TinyTeX || true)"; \
    if [ -n "${TT_PEM}" ]; then \
        echo "FATAL: files in /opt/TinyTeX hold PEM certificates outside the system store (neutralise them like ${TT_CA}): ${TT_PEM}" >&2; \
        exit 1; \
    fi; \
    "${TT_BIN}/tlmgr" option sys_bin /usr/local/bin; \
    "${TT_BIN}/tlmgr" postaction install script xetex; \
    "${TT_BIN}/tlmgr" path add; \
    for tool in tlmgr lualatex kpsewhich luaotfload-tool mktexlsr; do \
        TT_LINK="$(command -v "${tool}" || true)"; \
        if [ "${TT_LINK}" != "/usr/local/bin/${tool}" ] || [ "$(readlink "${TT_LINK}" || true)" != "${TT_BIN}/${tool}" ] || [ ! -x "${TT_LINK}" ]; then \
            echo "FATAL: '${tool}' on PATH is '${TT_LINK}' -> '$(readlink "${TT_LINK}" || true)', not the 'tlmgr path add' link /usr/local/bin/${tool} -> ${TT_BIN}/${tool}." >&2; \
            exit 1; \
        fi; \
        case "$(readlink -f "${TT_LINK}")" in \
            /opt/TinyTeX/*) ;; \
            *) echo "FATAL: /usr/local/bin/${tool} resolves outside /opt/TinyTeX: '$(readlink -f "${TT_LINK}")'." >&2; exit 1 ;; \
        esac; \
    done; \
    if [ -e /home/runner ]; then \
        echo "FATAL: /home/runner exists: tlmgr used the tarball's recorded sys_bin (/home/runner/bin)." >&2; \
        exit 1; \
    fi; \
    echo "TinyTeX ${TINYTEX_VERSION} (${DEB_ARCH}) unpacked to /opt/TinyTeX; binaries linked into /usr/local/bin."

# Extra packages from the dated archive, after verifying its package database.
RUN set -eu; \
    TT_PKGS="selnolig lua-ul luacolor marginfix xurl footnotehyper luatexbase ctablestack"; \
    TT_TLPDB=/opt/TinyTeX/tlpkg/texlive.tlpdb; \
    TT_TMP="$(mktemp -d /tmp/daaf-tinytex.XXXXXX)"; \
    if ! curl -fsSL -o "${TT_TMP}/texlive.tlpdb" "${TINYTEX_TLNET_ARCHIVE}/tlpkg/texlive.tlpdb"; then \
        echo "FATAL: could not download ${TINYTEX_TLNET_ARCHIVE}/tlpkg/texlive.tlpdb." >&2; \
        exit 1; \
    fi; \
    if ! echo "${TINYTEX_TLPDB_SHA512}  ${TT_TMP}/texlive.tlpdb" | sha512sum -c -; then \
        echo "FATAL: the package database of ${TINYTEX_TLNET_ARCHIVE} does not match TINYTEX_TLPDB_SHA512. texlive.info can answer HTTP 200 with an 'Access Denied' page, so the first bytes received are shown below; if the archive itself changed, re-verify it before re-pinning." >&2; \
        head -c 300 "${TT_TMP}/texlive.tlpdb" >&2 || true; \
        echo >&2; \
        exit 1; \
    fi; \
    TEXLIVE_DOWNLOADER=curl tlmgr option repository "${TINYTEX_TLNET_ARCHIVE}"; \
    TEXLIVE_DOWNLOADER=curl tlmgr install ${TT_PKGS}; \
    for pkg in ${TT_PKGS}; do \
        want="$(awk -v p="${pkg}" '$1 == "name" { n = $2 } n == p && $1 == "revision" { print $2; exit }' "${TT_TMP}/texlive.tlpdb")"; \
        got="$(awk -v p="${pkg}" '$1 == "name" { n = $2 } n == p && $1 == "revision" { print $2; exit }' "${TT_TLPDB}")"; \
        if [ -z "${want}" ] || [ "${got}" != "${want}" ]; then \
            echo "FATAL: ${pkg} is at revision '${got}', but the verified archive database lists '${want}'." >&2; \
            exit 1; \
        fi; \
        echo "TinyTeX: ${pkg} revision ${got} (matches the verified archive)"; \
    done; \
    if ! grep -qF "opt_location:${TINYTEX_TLNET_ARCHIVE}" "${TT_TLPDB}"; then \
        echo "FATAL: tlmgr's repository is not ${TINYTEX_TLNET_ARCHIVE}; a later tlmgr call could reach the live CTAN." >&2; \
        exit 1; \
    fi; \
    KOMA="$(awk '$1 == "name" { n = $2 } n == "koma-script" && $1 == "catalogue-version" { print $2; exit }' "${TT_TLPDB}")"; \
    if [ -z "${KOMA}" ] || [ -z "${QUARTO_VERSION}" ]; then \
        echo "FATAL: cannot read the KOMA-Script version ('${KOMA}') or QUARTO_VERSION ('${QUARTO_VERSION}') for the #15143 guard." >&2; \
        exit 1; \
    fi; \
    if dpkg --compare-versions "${KOMA}" ge 3.49.3 && dpkg --compare-versions "${QUARTO_VERSION}" lt 1.10.20; then \
        echo "FATAL: KOMA-Script ${KOMA} with Quarto ${QUARTO_VERSION}: pdf-standard renders fail (quarto-dev/quarto-cli#15143, fixed in Quarto 1.10.20). Keep TinyTeX on KOMA-Script 3.49.2 or raise QUARTO_VERSION." >&2; \
        exit 1; \
    fi; \
    echo "TinyTeX: KOMA-Script ${KOMA}, Quarto ${QUARTO_VERSION}, repository ${TINYTEX_TLNET_ARCHIVE}"; \
    rm -rf "${TT_TMP}"

# Font-name cache, file database, and the tree's final state.
RUN set -eu; \
    luaotfload-tool --update; \
    if [ -z "$(find /opt/TinyTeX/texmf-var -name 'luaotfload-names.lu*' -print)" ]; then \
        echo "FATAL: luaotfload-tool --update wrote no font-name database under /opt/TinyTeX/texmf-var." >&2; \
        exit 1; \
    fi; \
    mktexlsr; \
    TT_LOOSE="$(find /opt/TinyTeX \( ! -user root -o ! -group root -o \( ! -type l -perm /022 \) \) -print | head -n 20)"; \
    if [ -n "${TT_LOOSE}" ]; then \
        echo "FATAL: these TinyTeX paths are not root-owned or are group/world-writable, so a runtime install could change the tree: ${TT_LOOSE}" >&2; \
        exit 1; \
    fi; \
    echo "TinyTeX: root-owned, read-only for other users, font cache built ($(kpsewhich -var-value TEXMFSYSVAR))."

# appuser's TeX cache (see FONT CACHE above). Set after the root steps so they
# write into the tree, not into a root-owned directory in /home/appuser. A later
# root step (in USER ADDITIONS, for example) that runs lualatex or
# luaotfload-tool would create that directory owned by root, leaving appuser a
# TeX cache it cannot write; no build check catches this, because the smoke
# render points TEXMFVAR at its own temporary directory. Run such a step as
# appuser, or follow it with chown -R appuser:appuser /home/appuser/.cache.
ENV TEXMFVAR=/home/appuser/.cache/texmf-var
# Any later tlmgr download (in a user-mode tree, for example) uses the system
# curl and the G3-free system store, never the bundled CA file or wget with
# --no-check-certificate.
ENV TEXLIVE_DOWNLOADER=curl

# ============================================
# Install code-server (browser-based VS Code)
# ============================================
ARG CODE_SERVER_VERSION=4.117.0
RUN ARCH=$(dpkg --print-architecture) \
    && curl -fOL https://github.com/coder/code-server/releases/download/v${CODE_SERVER_VERSION}/code-server_${CODE_SERVER_VERSION}_${ARCH}.deb \
    && dpkg -i code-server_${CODE_SERVER_VERSION}_${ARCH}.deb \
    && rm -f code-server_${CODE_SERVER_VERSION}_${ARCH}.deb

# ============================================
# Create non-root user for security
# ============================================
# ubuntu:24.04 ships a default `ubuntu` user at UID/GID 1000, which collides
# with the explicit --gid/--uid 1000 below ("GID 1000 is not unique", exit 4).
# Remove it first; keeping appuser at 1000 preserves file ownership parity for
# existing volumes. The mail-spool touch/chown suppresses
# a harmless "mail spool not found" warning from userdel so build logs stay
# clean. userdel -r also removes /home/ubuntu and the ubuntu group (GID 1000).
RUN touch /var/mail/ubuntu \
    && chown ubuntu /var/mail/ubuntu \
    && userdel -r ubuntu
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home appuser

# Create code-server directories owned by appuser
RUN mkdir -p /home/appuser/.local/share/code-server/User \
             /home/appuser/.config/code-server \
    && chown -R appuser:appuser /home/appuser/.local \
                                /home/appuser/.config

# ============================================
# Node.js runtime for codex-plugin-cc
# ============================================
# codex-plugin-cc (the Codex plugin for Claude Code) needs a Node.js runtime in
# the container. Node already arrives transitively via libnode-dev (the R gt/V8
# stack), but that presence is incidental -- install `nodejs` explicitly so a
# future R-stack change cannot silently drop it. There is no exact version pin
# in the package name, per DAAF convention -- yet the version is still frozen:
# like every apt package it resolves from the Ubuntu snapshot (UBUNTU_SNAPSHOT;
# see the banner at the top of this file), so it changes only when the
# snapshot moves (noble's nodejs is 18.19.1+dfsg-6ubuntu5 at both
# 20260924T132000Z and 20261024T000000Z). The build-time floor assertion FAILS
# the build loudly if the packaged Node is older than 18.18 (the minimum
# codex-plugin-cc supports), rather than letting a too-old runtime surface as an
# obscure plugin failure later.
RUN daaf-apt-update && apt-get install -y --no-install-recommends \
        nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && node -e 'const v=process.versions.node, [maj,min]=v.split(".").map(Number); if (maj<18 || (maj===18 && min<18)) { console.error("ERROR: Node "+v+" is older than the 18.18 floor required by codex-plugin-cc"); process.exit(1); } console.log("Node "+v+" satisfies the codex-plugin-cc >= 18.18 floor");'

# ============================================
# Set up working directory
# ============================================
WORKDIR /daaf
RUN chown appuser:appuser /daaf
USER appuser

# Install code-server extensions from Open VSX (pinned via VSIX download)
# The @version CLI syntax is broken (silently installs latest), so we download
# each .vsix directly from Open VSX and install from file.
# ms-python.python dependencies (debugpy, vscode-python-envs) must be installed
# before the parent extension to avoid activation errors.
ARG EXT_MS_PYTHON=2026.4.0
ARG EXT_MS_DEBUGPY=2026.6.0
ARG EXT_MS_PYTHON_ENVS=1.36.0
ARG EXT_MARKDOWN_AIO=3.6.2
ARG EXT_GIT_GRAPH=1.30.0
ARG EXT_GITLENS=17.12.2
ARG EXT_RAINBOW_CSV=3.24.1
ARG EXT_YAML=1.22.0
ARG EXT_GITHUB_THEME=6.3.5
ARG EXT_VSCODE_ARCHIVE=0.9.6
RUN VSCODE_ARCH=$(if [ "$(dpkg --print-architecture)" = "amd64" ]; then echo x64; else echo arm64; fi) \
    && curl -fsSL -o /tmp/debugpy.vsix \
      "https://open-vsx.org/api/ms-python/debugpy/linux-${VSCODE_ARCH}/${EXT_MS_DEBUGPY}/file/ms-python.debugpy-${EXT_MS_DEBUGPY}@linux-${VSCODE_ARCH}.vsix" \
    && curl -fsSL -o /tmp/python-envs.vsix \
      "https://open-vsx.org/api/ms-python/vscode-python-envs/${EXT_MS_PYTHON_ENVS}/file/ms-python.vscode-python-envs-${EXT_MS_PYTHON_ENVS}.vsix" \
    && curl -fsSL -o /tmp/python.vsix \
      "https://open-vsx.org/api/ms-python/python/${EXT_MS_PYTHON}/file/ms-python.python-${EXT_MS_PYTHON}.vsix" \
    && curl -fsSL -o /tmp/markdown-aio.vsix \
      "https://open-vsx.org/api/yzhang/markdown-all-in-one/${EXT_MARKDOWN_AIO}/file/yzhang.markdown-all-in-one-${EXT_MARKDOWN_AIO}.vsix" \
    && curl -fsSL -o /tmp/git-graph.vsix \
      "https://open-vsx.org/api/mhutchie/git-graph/${EXT_GIT_GRAPH}/file/mhutchie.git-graph-${EXT_GIT_GRAPH}.vsix" \
    && curl -fsSL -o /tmp/gitlens.vsix \
      "https://open-vsx.org/api/eamodio/gitlens/${EXT_GITLENS}/file/eamodio.gitlens-${EXT_GITLENS}.vsix" \
    && curl -fsSL -o /tmp/rainbow-csv.vsix \
      "https://open-vsx.org/api/mechatroner/rainbow-csv/${EXT_RAINBOW_CSV}/file/mechatroner.rainbow-csv-${EXT_RAINBOW_CSV}.vsix" \
    && curl -fsSL -o /tmp/yaml.vsix \
      "https://open-vsx.org/api/redhat/vscode-yaml/${EXT_YAML}/file/redhat.vscode-yaml-${EXT_YAML}.vsix" \
    && curl -fsSL -o /tmp/github-theme.vsix \
      "https://open-vsx.org/api/GitHub/github-vscode-theme/${EXT_GITHUB_THEME}/file/GitHub.github-vscode-theme-${EXT_GITHUB_THEME}.vsix" \
    && curl -fsSL -o /tmp/vscode-archive.vsix \
      "https://open-vsx.org/api/YuTengjing/vscode-archive/${EXT_VSCODE_ARCHIVE}/file/YuTengjing.vscode-archive-${EXT_VSCODE_ARCHIVE}.vsix" \
    && code-server --install-extension /tmp/debugpy.vsix \
    && code-server --install-extension /tmp/python-envs.vsix \
    && code-server --install-extension /tmp/python.vsix \
    && code-server --install-extension /tmp/markdown-aio.vsix \
    && code-server --install-extension /tmp/git-graph.vsix \
    && code-server --install-extension /tmp/gitlens.vsix \
    && code-server --install-extension /tmp/rainbow-csv.vsix \
    && code-server --install-extension /tmp/yaml.vsix \
    && code-server --install-extension /tmp/github-theme.vsix \
    && code-server --install-extension /tmp/vscode-archive.vsix \
    && rm /tmp/*.vsix

# Set default code-server vscode settings (GitHub theme, sensible defaults)
RUN echo '{"workbench.colorTheme":"GitHub Dark Default","editor.fontSize":14,"editor.minimap.enabled":false,"telemetry.telemetryLevel":"off","extensions.autoUpdate":false,"security.workspace.trust.enabled":false}' \
    > /home/appuser/.local/share/code-server/User/settings.json

# Git identity for commits made inside the container: by the orchestrator, only
# when git commit management is enabled and the user approves the commit
# (CLAUDE.md § User Preferences), or by the user. It applies inside the
# container only.
RUN git config --global user.email "daaf@local" \
    && git config --global user.name "DAAF Container"

# Register gh as git's HTTPS credential helper (DAAF_DEV only).
# This lives HERE, in the appuser section (after USER appuser above), rather than
# beside the gh install in the DAAF_DEV root block, because `gh auth setup-git`
# writes the credential-helper line into the INVOKING user's ~/.gitconfig — and
# git operations in the container run as appuser. The DAAF_DEV root install block
# runs as root before `USER appuser`, so it cannot configure appuser's gitconfig.
# ARG DAAF_DEV (declared once near the top of this single build stage) is still
# in scope here — there is no intervening FROM.
#
# FAIL-SOFT by design: `|| echo ...` swallows a non-zero exit so a dev build
# never dies here. With no authenticated host, gh needs `--force --hostname
# github.com` (cli/cli#8521), and a hard failure on that edge would break every
# DAAF_DEV build for a non-essential convenience.
# Runtime GH_TOKEN auth (see the install RUN above) does not depend on this step.
RUN if [ "${DAAF_DEV}" = "1" ]; then \
        gh auth setup-git --force --hostname github.com \
        || echo "gh setup-git skipped (non-fatal)"; \
    fi

# Install Claude Code as appuser (pinned version)
# Pinned to 2.1.281 (npm `latest` = `next` and changelog head on 2026-09-24).
# 2.1.280 is the first version that ships Claude Opus 5.5 (`claude-opus-5-5`;
# 1M context; the default `opus` alias at 2.1.280 and 2.1.281). DAAF's
# .claude/settings.json ships the soft session default
# `ANTHROPIC_DEFAULT_MODEL=opus` (honored from Claude Code 2.1.236), which at
# this pin resolves to Opus 5.5 on a standard Anthropic subscription / API key;
# a pin before 2.1.280 resolves the same `opus` to an earlier Opus. Every
# Claude Code version bump must re-check what the `opus` alias resolves to (and
# the Opus 5.5 default named in user_reference/01_installation_and_quickstart.md
# and user_reference/07_faq_technical.md), and must re-check that Auto mode
# still works on a provider-shim route: shim routes rely on Claude Code's
# client-side classifier fallback, which a third party reports may be removed
# in Claude Code releases after 2026-10-23 (see the deploy-smoke skill's
# interpreting-results.md § Auto mode). 2.1.276 is the HARD MINIMUM for any
# shim-lane install:
# three separate `ANTHROPIC_BASE_URL` gateway/proxy regressions landed in
# 2.1.265 (Artifact-tool input-schema regex -> HTTP 400, fixed 2.1.268;
# `CLAUDE_CODE_USE_GATEWAY` forcing Cloud sign-in, fixed 2.1.266) and 2.1.275
# (`Input tag 'advisor_20260301'` -> 400, fixed 2.1.276), so any pin in
# 2.1.265-2.1.275 is a known-broken shim lane. 2.1.280 additionally adds
# symlinked-write permission judging, two subagent-report-loss fixes, and the
# generalized advisor-header retry for gateways. 2.1.281 makes the dangerous-rm
# check prompt for command-substitution targets (`rm -r "$(pwd)"`) even in
# bypass mode (2-minute wait, then deny), and fixes proxy/gateway stream
# handling (clean-close truncation, dropped or duplicated events).
# Rollback target: 2.1.280 (the only earlier pin at which the shipped `opus`
# default still resolves to Opus 5.5; 2.1.261 predates Opus 5.5, so there it
# would resolve to an earlier Opus)
ARG CLAUDE_CODE_VERSION=2.1.281
# CLAUDE_CODE_CERT_STORE=system (eMudhra distrust): Claude Code
# 2.1.281 bundles its own Mozilla CA list, and that list still contains the
# compromised "emSign ECC Root CA - G3" (see "Distrust compromised CA roots"
# near the top). Its default store setting is `bundled,system`, so G3 would stay
# trusted whatever the OS store holds. `system` makes it trust only the OS
# store, from which G3 is removed. Observed on 2.1.281 with a G3-free system
# store: it rejected a certificate chain to G3 and accepted the control host.
# Documented at code.claude.com/docs/en/network-config: CLAUDE_CODE_CERT_STORE
# "accepts a comma-separated list of sources ... bundled ... system ... The
# default is bundled,system". TLS-inspecting proxies still work when their root
# is installed in the OS store (same page). CAVEAT: `system` is not absolute.
# In the 2.1.281 binary's loader (read 2026-10-28), an empty or failed
# system-store load ("system store returned empty", "Failed to load system CA
# certificates") re-adds the bundled list, which holds G3, and a missing
# system-CA API ("deferring to runtime") leaves the runtime's default store in
# place (inference: Bun's bundled list). In testing on Claude Code 2.1.281 the
# system store loaded ("Loaded 120 system CA certificates", stores=system).
# Inference from the same code, not tested: certificates in NODE_EXTRA_CA_CERTS
# are still appended under `system`. Set before the installer RUN so the
# install step uses it too. REVISIT at the next Claude Code upgrade: releases
# from 2.1.304 no longer bundle G3 (2.1.303 added a distrust list), so the
# default may return.
ENV CLAUDE_CODE_CERT_STORE=system
RUN curl -fsSL https://claude.ai/install.sh | bash -s ${CLAUDE_CODE_VERSION}
ENV PATH="/home/appuser/.local/bin:${PATH}"

# ============================================
# USER ADDITIONS — add your own packages and tools here
# ============================================
# This is the recommended default place to add your own software: Python
# packages, R packages, system libraries, or standalone CLI tools. It sits as
# late as possible in the build on purpose.
#
# WHY HERE (fast rebuilds via Docker layer caching): Docker caches each build
# layer and only re-runs a layer when it (or a layer above it) changes. This
# block is below every expensive framework layer — the apt/GDAL system libs, the
# ~2.2 GB R stack, the Python installs, the code-server + VS Code extension
# layers — so editing it invalidates essentially nothing downstream. A rebuild
# takes only as long as installing your additions themselves (typically seconds
# to a couple of minutes). By contrast, appending to the mid-file categorized
# Python/R blocks re-runs every expensive layer below them (all the R packages,
# all later Python blocks, the extensions), which can turn a quick rebuild into
# a many-minute one.
#
# CAVEAT — convenience default, not an absolute rule; functionality wins. Some
# additions MUST go earlier and will legitimately trigger a longer rebuild:
#   (a) A system library that a mid-file Python/R package needs at IMAGE BUILD
#       TIME must be installed BEFORE that package's install block (e.g. a
#       geospatial lib a pip/Rscript block links against). Put it in the
#       relevant apt-get block up top, not here.
#   (b) An R package you want covered by the framework's install-verification
#       presence gate belongs with the framework R blocks above (and its name
#       added to the presence-gate list), not here — the gate only checks the
#       packages listed there.
#   (c) Anything a later framework layer depends on must precede that layer.
#   (d) A LaTeX package goes in `TT_PKGS` in the TinyTeX block above, not here,
#       so it installs from the same dated archive as the other extra LaTeX
#       packages (user_reference/04_extending_daaf.md § "LaTeX Packages").
# A standalone tool that nothing else depends on (a CLI utility, an extra
# analysis package) is the ideal candidate for this block.
#
# FROZEN ENVIRONMENT DATE: additions here inherit the image's frozen inputs (see
# the ENVIRONMENT DATE banner at the top of this file). `uv pip install` resolves
# against UV_EXCLUDE_NEWER and apt against the UBUNTU_SNAPSHOT snapshot, so you
# get the newest release AS OF THAT DATE -- a rebuild next year installs the same
# versions (good for reproducibility), but a package or version published after
# the date cannot be installed as-is. uv then says "No solution found" WITHOUT
# mentioning the cutoff; apt says "Unable to locate package" / "Version ... was
# not found". Two ways forward:
#   - one Python package: add `--exclude-newer-package PKG=<RFC 3339 Z time>`
#     to its `uv pip install` line (its dependencies stay at the cutoff);
#   - anything else: bump the environment date (user_reference/04_extending_daaf.md
#     § "Bumping the environment date") -- this rebuilds every layer.
# Pillow is held at 13.0.0 by a security override (banner, exception (2)). A
# package added here that requires pillow<13 would quietly move it back to
# 12.3.0 (inference: uv re-resolves an installed package that a new
# requirement excludes); the Pillow version check after this block then fails
# the build. Pick a version of that package that accepts Pillow 13; if a line
# here moved Pillow for another reason, repeat
# `--exclude-newer-package pillow=2026-10-17T00:00:00Z` on it.
# Use `daaf-apt-update`, never a bare `apt-get update`: it runs the snapshot
# origin guard, which also means a third-party apt repository (no snapshot)
# FAILS the build by design -- install such software from a version-pinned
# release download instead. R installs use the separate P3M snapshot date.
#
# CONTAINER-HOST BOUNDARY: the same warning that applies to the mid-file
# customization blocks applies here — if you edit this file inside the DAAF
# container, you are editing the container's copy, not the copy in your
# daaf-docker folder that the build reads. The rebuild in HOW TO USE below
# copies it back for you. See user_reference/04_extending_daaf.md § "The
# Recommended Path: Modify the Dockerfile" for the full procedure.
#
# HOW TO USE: everything below is COMMENTED OUT so an unused block adds ZERO
# instructions and produces a byte-for-byte identical image to a default build.
# Uncomment the directives and the example(s) you need, following the patterns
# already used elsewhere in this file. Then rebuild the image: choose
# 10) Rebuild Container in the DAAF Control Panel, or exit the container and
# run `bash rebuild_daaf.sh` (`.\rebuild_daaf.ps1` on Windows) from your
# daaf-docker folder.
#
# Add packages here, never inside a running container: a package installed in
# a running container is lost whenever the container is rebuilt or recreated,
# and DAAF's agents will not install one there.
#
# ---- ROOT-LEVEL INSTALLS (uncomment `USER root` + your install line[s]) ----
# Root is needed for apt-get and for system-wide (`--system`) package installs.
#
# USER root
#
# System package (apt) — matches the apt hygiene pattern used up top
# (daaf-apt-update = apt-get update + the snapshot origin guard):
# RUN daaf-apt-update && apt-get install -y --no-install-recommends \
#         your-package-here \
#     && apt-get clean \
#     && rm -rf /var/lib/apt/lists/*
#
# Python package (uv, system-wide) — matches the Python install blocks above:
# RUN uv pip install --system \
#     your-package==1.2.3
#
# R package (installs from the P3M snapshot configured above) — matches the
# R install blocks above, including their check: install.packages() only warns
# when a package fails to install, so the requireNamespace() check after it
# stops the build instead of letting it finish without the package. Uncomment
# all four lines. NOTE: packages added here are NOT covered by the presence
# gate; if you need gate coverage, add them to the framework R blocks instead
# (see caveat (b)).
# RUN Rscript -e 'pkgs <- c("yourPackage"); \
#         install.packages(pkgs); \
#         missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]; \
#         if (length(missing)) stop("R install block failed — missing: ", paste(missing, collapse = ", "))'
#
# ---- RESTORE THE NON-ROOT RUNTIME USER (REQUIRED if you used `USER root`) ----
# The FINAL `USER` directive in the Dockerfile determines the container's
# runtime user, and DAAF's security posture depends on running as the non-root
# `appuser`. If you switched to root above, you MUST switch back here. Do not
# remove or reorder this relative to your root installs.
#
# USER appuser
#
# ---- USER-LEVEL / HOME-DIRECTORY INSTALLS (place AFTER `USER appuser`) ----
# Anything that writes into /home/appuser belongs here, after the user is
# restored: curl|bash-style per-user installers, editor extensions, dotfiles.
# Running these as root would write into /root or leave root-owned files in
# /home/appuser. Python and R packages go in the root-level examples above
# (`uv pip install --system`, `install.packages()`), not here.
# RUN curl -fsSL https://example.com/install.sh | bash
# ============================================

# TinyTeX smoke render (see the TinyTeX block after Quarto): as appuser,
# render a small PDF that exercises the packages added to the bundle and the
# #15143 path: `lang: en-US` (babel + selnolig, which load luatexbase), a
# callout (tcolorbox, fontawesome5), strikeout and `.mark` (lua-ul, luacolor),
# a footnote and a URL (footnotehyper, xurl), and `pdf-standard: ua-2`
# (\DocumentMetadata with KOMA-Script 3.49.2 under Quarto 1.10.18).
# `latex-auto-install: false` makes a missing package fail at once instead of
# starting tlmgr. Before rendering it checks
# that appuser runs it, that kpathsea honors ENV TEXMFVAR, and that appuser
# cannot write the tree. The render's caches (TEXMFVAR, XDG dirs) point into the
# temporary directory, which starts in the same state as appuser's real cache
# on first use (absent, in a writable directory); the directory is deleted, so
# nothing stays in the image. It sits after USER ADDITIONS so an addition that
# breaks PDF rendering fails here, and before the Pillow check and the final
# trust check, which stays the last RUN.
RUN set -eu; \
    if [ "$(id -un)" != appuser ]; then \
        echo "FATAL: the TinyTeX smoke render runs as '$(id -un)', not appuser. A USER ADDITIONS edit probably left 'USER root' active: restore 'USER appuser' after root installs." >&2; \
        exit 1; \
    fi; \
    if [ "$(kpsewhich -var-value TEXMFVAR)" != "${TEXMFVAR}" ]; then \
        echo "FATAL: kpathsea reports TEXMFVAR='$(kpsewhich -var-value TEXMFVAR)', not ENV TEXMFVAR='${TEXMFVAR}'." >&2; \
        exit 1; \
    fi; \
    if [ -w /opt/TinyTeX ] || [ -w /opt/TinyTeX/tlpkg/texlive.tlpdb ] || [ -w /opt/TinyTeX/texmf-dist ]; then \
        echo "FATAL: appuser can write /opt/TinyTeX, so tlmgr or Quarto's latex-auto-install could change it at runtime." >&2; \
        exit 1; \
    fi; \
    SMOKE="$(mktemp -d)"; \
    printf '%s\n' \
        '---' \
        'title: "DAAF TinyTeX smoke test"' \
        'lang: en-US' \
        'pdf-standard: ua-2' \
        'format:' \
        '  pdf:' \
        '    latex-auto-install: false' \
        '---' \
        '' \
        '::: {.callout-note}' \
        'A callout box.' \
        ':::' \
        '' \
        'Struck ~~text~~, [highlighted text]{.mark}, a footnote[^1] and <https://quarto.org>.' \
        '' \
        '[^1]: Footnote text.' \
        > "${SMOKE}/smoke.qmd"; \
    if ! ( cd "${SMOKE}" \
           && TEXMFVAR="${SMOKE}/cache/texmf-var" XDG_CACHE_HOME="${SMOKE}/cache" \
              XDG_DATA_HOME="${SMOKE}/data" XDG_CONFIG_HOME="${SMOKE}/config" \
              quarto render smoke.qmd --to pdf ); then \
        echo "FATAL: the TinyTeX smoke render failed (Quarto ${QUARTO_VERSION}, TinyTeX ${TINYTEX_VERSION}). Read the LaTeX error above: a missing .sty names a package to add to the TinyTeX package layer; an error at \\DocumentMetadata or from a KOMA class points at quarto-dev/quarto-cli#15143; a luaotfload cache error points at TEXMFVAR." >&2; \
        if [ -f "${SMOKE}/smoke.log" ]; then tail -n 60 "${SMOKE}/smoke.log" >&2; fi; \
        rm -rf "${SMOKE}"; \
        exit 1; \
    fi; \
    if [ "$(head -c 5 "${SMOKE}/smoke.pdf" 2>/dev/null || true)" != "%PDF-" ]; then \
        echo "FATAL: quarto render exited 0 but ${SMOKE}/smoke.pdf is missing or not a PDF." >&2; \
        rm -rf "${SMOKE}"; \
        exit 1; \
    fi; \
    echo "TinyTeX smoke render OK: $(wc -c < "${SMOKE}/smoke.pdf") bytes of PDF as $(id -un)."; \
    rm -rf "${SMOKE}"

# Pillow version guard (security exception (2) in the banner): pillow 13.0.0
# comes from a one-package override in the PDF reading stack block. A later
# `uv pip install` without that override (a USER ADDITIONS line, for example)
# that brings a package requiring pillow<13 would resolve Pillow again at
# UV_EXCLUDE_NEWER and put back 12.3.0 with its advisories, without any error
# (inference; uv's issue #17999 shows a per-package exemption undone the same
# way in project mode). This build-time assertion FAILS the build loudly
# instead, like the Node floor assertion above. Read-only, so it runs as
# appuser; it sits after the TinyTeX smoke render and before the final trust
# check, so that check stays the last RUN. Remove it when exception (2) is
# retired (banner, RETIRING THEM).
RUN python3 -c 'import sys, PIL; v = PIL.__version__; sys.exit("ERROR: pillow is " + v + ", expected 13.0.0 (Dockerfile security exception (2)): a later uv pip install resolved it again; repeat --exclude-newer-package pillow=2026-10-17T00:00:00Z on that line, or pick a version of the added package that accepts Pillow 13") if v != "13.0.0" else print("pillow " + v + " is installed (security exception (2))")'

# Final eMudhra trust check: the same call as at the end of the Python stack,
# repeated as the build's last RUN so no later layer (R, Quarto, TinyTeX,
# code-server, nodejs, Claude Code, USER ADDITIONS) can bring G3 back
# unnoticed. It also scans TinyTeX's tlmgr CA file, which the TinyTeX layer
# replaced with a symlink to the system bundle: if a later change put the
# shipped Mozilla list (with G3) back, this check fails. Read-only, so it runs
# as appuser.
RUN daaf-check-distrusted-roots "$(python3 -c 'import certifi; print(certifi.where())')" /opt/TinyTeX/tlpkg/installer/curl/curl-ca-bundle.crt

# Install the DAAF entrypoint wrapper. It best-effort auto-starts the provider
# shim (opt-in via DAAF_PROVIDER_SHIM) then execs CMD. Boot-safe: never fatal,
# and a silent no-op for users who have not opted into the shim. The /daaf named
# volume shadows the image at runtime, so the wrapper only references the shim
# manager defensively (guarded on existence + executability).
#
# NOTE: written inline via a BuildKit heredoc (not COPY) deliberately. The host
# build context is the distributed daaf-docker folder, which does NOT contain
# the DAAF repo tree — a COPY of a repo path can never succeed there. Keeping
# the wrapper inline makes the Dockerfile self-contained: rebuilds only ever
# need the Dockerfile itself synced container -> host (rebuild_daaf.sh's flow).
# Requires BuildKit with Dockerfile frontend >= 1.4 (heredoc syntax) — default
# on Docker Engine 23+ / any modern Docker Desktop; a legacy builder with
# DOCKER_BUILDKIT=0 would fail here with a syntax error.
COPY --chmod=0755 <<'DAAF_ENTRYPOINT_EOF' /usr/local/bin/daaf-entrypoint.sh
#!/usr/bin/env bash
# daaf-entrypoint.sh -- container ENTRYPOINT wrapper (generated from the
# Dockerfile heredoc above; there is no separate source file).
# Jobs: (1) best-effort auto-start of the provider shim (opt-in via
# DAAF_PROVIDER_SHIM, handled entirely inside start_shim.sh --auto);
# (2) exec the container CMD so the container behaves exactly as an
# un-wrapped container for everyone who has not opted into the shim.
# Boot-safety: /daaf is a named volume that shadows the image copy at runtime,
# so the shim manager may be absent, empty, or broken. Every reference is
# guarded, there is deliberately NO `set -e`, and no code path may prevent
# `exec "$@"` from running.
set -u

readonly SHIM_MANAGER="/daaf/scripts/provider_shim/start_shim.sh"

if [ -x "$SHIM_MANAGER" ]; then
    if ! "$SHIM_MANAGER" --auto; then
        echo "daaf-entrypoint: provider shim --auto returned non-zero; continuing boot." >&2
    fi
fi

exec "$@"
DAAF_ENTRYPOINT_EOF
ENTRYPOINT ["/usr/local/bin/daaf-entrypoint.sh"]

# Default command
CMD ["bash"]
