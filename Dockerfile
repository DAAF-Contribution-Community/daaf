# Data Science Dockerfile with uv and Claude Code
# Base: Ubuntu 24.04 (noble) with Python 3.12 + Astral uv (binary COPY)

FROM ubuntu:24.04

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
# makes every `uv pip install --system` layer refuse with exit 2 (the old base
# image's Python had no such marker). That guard protects live systems from
# apt/pip conflicts; this image IS the managed environment (uv-only, pinned
# versions, runtime installs hook-blocked), and uv's docs designate this
# variable for exactly this containerized use.
ENV UV_SYSTEM_PYTHON=1
ENV UV_BREAK_SYSTEM_PACKAGES=1
ENV UV_COMPILE_BYTECODE=1

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
# an Ubuntu base). The tag carries the same uv version the old bookworm base
# pinned (0.9.30). noble's default `python3` is 3.12, so the interpreter, its dev
# headers, and venv support are installed from apt to back UV_SYSTEM_PYTHON=1.
# The bare `python3` metapackage is required too: minimal ubuntu:24.04 ships no
# /usr/bin/python3 symlink, and DAAF's execution wrapper (run_with_capture.sh)
# invokes the bare `python3` name for every Python script.
COPY --from=ghcr.io/astral-sh/uv:0.9.30 /uv /uvx /usr/local/bin/

# ============================================
# Install System Dependencies (Git, Python 3.12)
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
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
# (geospatial). More arrive later in the R system-libs block (libnode-dev,
# libtbb-dev, libhdf5-dev, libnetcdf-dev, libglpk40). This guard therefore runs
# BEFORE the geospatial block — its earliest consumer — so a base with universe
# disabled fails here with a clear message instead of dying later inside an
# apt-install with a cryptic "unable to locate package" error.
#
# The official ubuntu:24.04 image ships universe enabled in
# /etc/apt/sources.list.d/ubuntu.sources, so on the normal base this guard is a
# fast no-op. It exists to make that assumption explicit and to self-heal a
# minimal base: it enables universe if absent and fails fast (exit 1) only if it
# still cannot. `apt-get update` for the real installs is left to the blocks
# below, so the no-op path costs nothing beyond a grep.
RUN if grep -rqE '^[[:space:]]*(Components:.*\buniverse\b|deb .*\buniverse\b)' \
        /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null; then \
        echo "universe component already enabled"; \
    else \
        echo "universe component not found; enabling via add-apt-repository"; \
        apt-get update; \
        apt-get install -y --no-install-recommends software-properties-common; \
        add-apt-repository -y universe; \
        apt-get clean; \
        rm -rf /var/lib/apt/lists/*; \
        grep -rqE '^[[:space:]]*(Components:.*\buniverse\b|deb .*\buniverse\b)' \
            /etc/apt/sources.list /etc/apt/sources.list.d/ \
            || { echo "FATAL: could not enable the apt 'universe' component" >&2; exit 1; }; \
    fi

# ============================================
# Install Geospatial System Libraries (GDAL/GEOS/PROJ)
# ============================================
# Required by fiona (rasterstats dep) and beneficial for rasterio, geopandas, osmnx
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    gdal-bin \
    libgeos-dev \
    libproj-dev \
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
ARG CODEX_VERSION=0.144.1
ARG DAAF_DEV_GH_VERSION=2.95.0

# shellcheck + bats from the Debian repo (mirrors the CI bats-tests job).
RUN if [ "${DAAF_DEV}" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends \
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
RUN DEB_ARCH=$(dpkg --print-architecture) \
    && case "${DEB_ARCH}" in \
         amd64) CODEX_TRIPLE=x86_64 ;; \
         arm64) CODEX_TRIPLE=aarch64 ;; \
         *) echo "Unsupported architecture '${DEB_ARCH}' for Codex CLI" >&2; exit 1 ;; \
       esac \
    && CODEX_TGZ="codex-${CODEX_TRIPLE}-unknown-linux-musl.tar.gz" \
    && curl -fsSL -o "/tmp/${CODEX_TGZ}" \
         "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/${CODEX_TGZ}" \
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
# BOTH x86_64 and arm64 (verified 2026-07-14: x-package-binary-tag 4.5-noble and
# 4.5-noble-arm64 on the pinned snapshot), so neither architecture compiles the
# framework R packages from source — the Apple Silicon source-build path that the
# old Debian Bookworm base forced (bookworm being end-of-support for P3M binaries)
# is gone. R 4.6.x is deliberately NOT adopted here: as of 2026-07-14 P3M still
# serves NO noble R 4.6 binaries on either arch (live-probe UA fallback to source,
# contradicting Posit's docs), and the pinned snapshot's S7 0.2.1 is broken under
# R 4.6. Posit CDN .deb installs to /opt/R/{VERSION}/; symlinks expose on PATH.
# Upgrade path: bump R_VERSION only once a live probe confirms 4.6-noble /
# 4.6-noble-arm64 binary tags AND the snapshot date is >= 2026-04-22 (S7 0.2.2).
ARG R_VERSION=4.5.3

# R runtime from Posit pre-built binaries (Ubuntu 24.04 / noble).
RUN curl -fsSL -o /tmp/r-${R_VERSION}.deb \
      "https://cdn.posit.co/r/ubuntu-2404/pkgs/r-${R_VERSION}_1_$(dpkg --print-architecture).deb" \
    && apt-get update \
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
#   1. USER-ADDED source packages. A user who adds an R package (USER ADDITIONS
#      block, or an analysis-time install.packages()) that is absent from the
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
#      `libnode.so.NNN: cannot open shared object file` if libnode-dev is absent
#      (R-support Parity Matrix Ticket 8). The presence gate's
#      requireNamespace("V8") dlopens libnode.so and so catches this at build
#      time. Do NOT drop libnode-dev.
#
# UNIVERSE NOTE: five of the deps below (libnode-dev, libtbb-dev, libhdf5-dev,
# libnetcdf-dev, libglpk40) live in Ubuntu's `universe` component. universe is
# guaranteed present by the "Ensure the apt `universe` component is enabled"
# guard RUN earlier in this file (placed before the geospatial block, universe's
# first consumer), which fails fast if it cannot be enabled — so these installs
# do not need to re-check it.
RUN apt-get update && apt-get install -y --no-install-recommends \
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
# IMPORTANT — CONTAINER-HOST BOUNDARY: If you (or DAAF/Claude Code) are
# editing this file from inside a running DAAF container, your edits
# live in the VOLUME copy of the Dockerfile — NOT the HOST copy that
# Docker Compose actually reads at build time. You must copy the
# modified Dockerfile back to the host project folder BEFORE running
# the rebuild, or your changes will silently fail to take effect (the
# build will "succeed" with no errors, but your new package will not
# be installed). From your host terminal, in your DAAF project folder:
#
#   docker compose cp daaf-docker:/daaf/Dockerfile ./Dockerfile
#   docker compose up -d --build
#
# Docker layer caching makes rebuilds fast — only changed layers re-run.
# For packages needing C libraries (e.g., libfoo-dev), also add them to
# the apt-get block in "Install System Dependencies" above (a single
# copy-back step covers both edits, since they're in the same file).
#
# For the full explanation, step-by-step procedure, common scenarios,
# and runtime install options, see:
#   user_reference/04_extending_daaf.md
#   (section: "The Recommended Path: Modify the Dockerfile")
# -----------------------------------------------

# Install core data science packages
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
    pyfixest==0.40.0 \
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
RUN uv pip install --system \
    matplotlib==3.10.8 \
    seaborn==0.13.2 \
    plotnine==0.15.3 \
    plotly==6.5.2 \
    marimo==0.19.11

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

# Install provider-shim direct runtime dependencies after all other framework
# Python packages. Both arrive transitively today (httpx via svy; uvicorn via
# marimo), but the persistent shim imports them directly and must not depend on
# unrelated packages retaining compatible versions. Keeping these direct pins
# last in the Python stack also prevents a later framework Python block from
# replacing them. The build is still root here; the single runtime transition to
# appuser remains at the existing security boundary below.
RUN uv pip install --system \
    httpx==0.28.1 \
    uvicorn==0.51.0

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
# (.qmd), so it is installed alongside the R packages here.

# Configure R package repository (P3M date-pinned snapshot for reproducibility).
# Pin to a specific date snapshot so rebuilds produce identical package versions.
# Update the date when intentionally upgrading R packages (and update skill
# metadata). On the Ubuntu 24.04 (noble) base P3M provides pre-built binaries on
# BOTH x86_64 and arm64 — much faster than source compilation — so no framework R
# package compiles from source on either architecture (verified 2026-07-14:
# x-package-binary-tag 4.5-noble on x86_64 and 4.5-noble-arm64 on aarch64 for the
# pinned snapshot). This replaced the former Debian Bookworm base, which served
# binaries on x86_64 only and forced ~25-35 min of all-source R compilation on
# Apple Silicon (bookworm being end-of-support for P3M binaries). The four extra
# dev headers (libuv1-dev, libharfbuzz-dev, libfribidi-dev, libnode-dev) are
# still installed in the R-toolchain apt block above, now for USER-ADDED source
# packages and for libnode's runtime dlopen linkage under V8 (see that block).
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
# NOTE: the wild-cluster-bootstrap package was removed here — archived on CRAN,
# no R 4.5 binary in the P3M snapshot. It can be installed at analysis time if
# needed (e.g. via a source/archive build).
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
# dlopens libnode.so. Listing V8 here and in the presence gate means the gate now
# EXERCISES that native linkage at build time, catching the missing-runtime-lib
# failure class (libnode.so absent) rather than letting it surface only when a
# report is first rendered (R-support Parity Matrix Ticket 8).
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

# Presence gate: the FINAL identity check that the installed package set matches the
# union of the install.packages() blocks above. Its role changed with the per-block
# fail-fast pattern: the per-block requireNamespace() checks now catch a failed package
# INSIDE its own layer (fast, adjacent to the compile error), so this gate is no longer
# the first line of defense against a silently-dropped package (as happened with the
# archived wild-bootstrap package). It still earns its keep as the union check — one
# authoritative list that must stay identical to the blocks — and it additionally
# EXERCISES native linkage: requireNamespace("V8") dlopens libnode.so, so the gate
# fails at build time if the libnode.so runtime library is missing (the gt::as_raw_html
# failure class; R-support Parity Matrix Ticket 8) rather than deferring it to first use.
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
        "simstudy", "fabricatr" \
        ); \
        missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]; \
        if (length(missing)) stop("Missing R packages: ", paste(missing, collapse = ", ")); \
        cat("All", length(pkgs), "R packages present.\n")'

# Quarto CLI (language-agnostic notebook system; DAAF uses it for R Stage 9).
# Pin the version; update when intentionally upgrading.
ARG QUARTO_VERSION=1.7.29
RUN ARCH=$(dpkg --print-architecture) \
    && curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-${ARCH}.deb" \
        -o /tmp/quarto.deb \
    && dpkg -i /tmp/quarto.deb \
    && rm /tmp/quarto.deb

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
# ubuntu:24.04 ships a default `ubuntu` user at UID/GID 1000 (bookworm did not),
# which collides with the explicit --gid/--uid 1000 below ("GID 1000 is not
# unique", exit 4). Remove it first; keeping appuser at 1000 preserves file
# ownership parity for existing volumes. The mail-spool touch/chown suppresses
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

# Configure git identity for DAAF's internal version tracking.
# Agents make local commits during research sessions to create an audit trail.
# This identity is used for those automated commits inside the container only.
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
# never dies here. gh's flag/setup-git behavior cannot be exercised in this
# authoring environment (no gh binary, no Docker), and with no authenticated
# host gh needs `--force --hostname github.com` (cli/cli#8521) — a hard failure
# on that edge would break every DAAF_DEV build for a non-essential convenience.
# Runtime GH_TOKEN auth (see the install RUN above) does not depend on this step.
RUN if [ "${DAAF_DEV}" = "1" ]; then \
        gh auth setup-git --force --hostname github.com \
        || echo "gh setup-git skipped (non-fatal)"; \
    fi

# Install Claude Code as appuser (pinned version)
# Latest stable as of 2026-07-15 (user-verified stable channel; 2.1.210 was latest).
# Delta review 2.1.188-2.1.202 + regression checklist:
#   research/2026-07-15_FrameworkDev_ClaudeCode_Upgrade_2.1.202/
# Rollback target: 2.1.187
ARG CLAUDE_CODE_VERSION=2.1.202
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
# A standalone tool that nothing else depends on (a CLI utility, an extra
# analysis package) is the ideal candidate for this block.
#
# CONTAINER-HOST BOUNDARY: the same warning that applies to the mid-file
# customization blocks applies here — if you edit this file from inside a running
# DAAF container you are editing the VOLUME copy, not the HOST copy Docker
# Compose builds from. Copy it back to the host before rebuilding (the
# rebuild_daaf.sh / .ps1 scripts do this for you). See
# user_reference/04_extending_daaf.md § "The Recommended Path: Modify the
# Dockerfile" for the full procedure.
#
# HOW TO USE: everything below is COMMENTED OUT so an unused block adds ZERO
# instructions and produces a byte-for-byte identical image to a default build.
# Uncomment the directives and the example(s) you need, following the patterns
# already used elsewhere in this file.
#
# ---- ROOT-LEVEL INSTALLS (uncomment `USER root` + your install line[s]) ----
# Root is needed for apt-get and for system-wide (`--system`) package installs.
#
# USER root
#
# System package (apt) — matches the apt hygiene pattern used up top:
# RUN apt-get update && apt-get install -y --no-install-recommends \
#         your-package-here \
#     && apt-get clean \
#     && rm -rf /var/lib/apt/lists/*
#
# Python package (uv, system-wide) — matches the Python install blocks above:
# RUN uv pip install --system \
#     your-package==1.2.3
#
# R package (installs from the P3M snapshot configured above) — matches the
# R install blocks above. NOTE: packages added here are NOT covered by the
# presence gate; if you need gate coverage, add them to the framework R blocks
# instead (see caveat (b)).
# RUN Rscript -e 'install.packages("yourPackage")'
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
# restored: curl|bash-style per-user installers, editor extensions, dotfiles,
# `uv pip install --user` / `pip install --user`, etc. Running these as root
# would write into /root or leave root-owned files in /home/appuser.
# RUN curl -fsSL https://example.com/install.sh | bash
# ============================================

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
