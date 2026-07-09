# Data Science Dockerfile with uv and Claude Code
# Base: Astral uv with Python 3.12 on Debian Bookworm

FROM ghcr.io/astral-sh/uv:0.9.30-python3.12-bookworm

LABEL maintainer="Data Science Environment"
LABEL description="Python data science with uv and Claude Code"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set up uv environment variables
ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=1

# ============================================
# Install System Dependencies (Git)
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    jq \
    git \
    poppler-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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
# Optional dev tooling: in-container test toolchain (DAAF_DEV)
# ============================================
# OPT-IN, FRAMEWORK-DEVELOPER-ONLY. Everything in this section is skipped
# entirely unless DAAF_DEV=1 is passed as a build arg. A framework developer
# opts in by setting DAAF_DEV=1 in the host-side environment_settings.txt; the
# install/rebuild scripts bridge that key into the shell environment, and
# docker-compose.yml forwards it here as `--build-arg DAAF_DEV=${DAAF_DEV:-0}`.
# When DAAF_DEV is unset or 0 (the default for every normal user), the guarded
# RUN layers below are no-ops, so a standard build is byte-for-byte unchanged.
#
# What it installs (only when DAAF_DEV=1):
#   - shellcheck                 (Bash linter, Debian repo)
#   - bats                       (Bash test runner, Debian repo)
#   - PowerShell 7 + Pester +
#     PSScriptAnalyzer           (PowerShell test/lint stack)
# The goal is to let a developer run the repo's own test suites INSIDE the
# container so `bats tests/bash/` and `Invoke-Pester tests/powershell/`
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
# R 4.6.0 (released 2026-04-24) lacks P3M pre-built binaries as of May 2026 —
# all packages compile from source, and S7 <=0.2.1 fails due to removed C API
# symbols. Posit CDN .deb installs to /opt/R/{VERSION}/; symlinks expose on
# PATH. Upgrade path: bump R_VERSION once P3M announces R 4.6 binary support.
ARG R_VERSION=4.5.3

# R runtime from Posit pre-built binaries (Debian Bookworm).
RUN curl -fsSL -o /tmp/r-${R_VERSION}.deb \
      "https://cdn.posit.co/r/debian-12/pkgs/r-${R_VERSION}_1_$(dpkg --print-architecture).deb" \
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
        cmake \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Install Python Data Science Packages via uv
# ============================================
#
# CUSTOMIZATION: Adding Your Own Python Packages
# -----------------------------------------------
# To add a Python package, append it to the appropriate RUN block below
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
#   docker cp daaf-daaf-docker-1:/daaf/Dockerfile ./Dockerfile
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
    polars==1.38.1 \
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
RUN uv pip install --system \
    linearmodels==7.0 \
    rdrobust==1.3.0 \
    marginaleffects==0.5.0 \
    arch==8.0.0 \
    pydynpd==0.2.1 \
    svy==0.13.0

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

# ============================================
# Install R Data Science Packages + Quarto
# ============================================
# R is part of the standard image. The R runtime and system libraries these
# packages depend on are installed in the "R toolchain" section above the
# Python installs; this section adds the R packages themselves plus the Quarto
# CLI. Together with the runtime and system libs, the R stack accounts for
# roughly ~2.2 GB of the image.
#
# CUSTOMIZATION: To add an R package, append it to the appropriate Rscript
# install block below (or add a new block). For R packages needing C/Fortran
# libraries, add the system deps to the apt-get block in the "R toolchain"
# section above.
#
# QUARTO SCOPING: Quarto is a standalone system binary that does not depend on
# R or Python package managers; within DAAF it renders R-mode Stage 9 notebooks
# (.qmd), so it is installed alongside the R packages here.

# Configure R package repository (P3M date-pinned snapshot for reproducibility).
# Pin to a specific date snapshot so rebuilds produce identical package versions.
# Update the date when intentionally upgrading R packages (and update skill
# metadata). P3M provides pre-built binaries for Debian Bookworm — much faster
# than source compilation.
ARG P3M_SNAPSHOT_DATE=2026-04-15
RUN RPROFILE="$(Rscript -e 'cat(file.path(R.home("etc"), "Rprofile.site"))')" \
    && echo "options(repos = c(CRAN = 'https://p3m.dev/cran/__linux__/bookworm/${P3M_SNAPSHOT_DATE}'))" \
        >> "${RPROFILE}" \
    && echo 'options(Ncpus = parallel::detectCores())' \
        >> "${RPROFILE}"

# Core data manipulation and I/O
RUN Rscript -e 'install.packages(c( \
        "data.table", "dplyr", "tidyr", "tibble", "readr", "purrr", "stringr", \
        "forcats", "lubridate", "glue", "rlang", "skimr", \
        "arrow", "readxl", "writexl", "haven", "jsonlite", "yaml" \
        ))'

# Statistics and econometrics
# NOTE: the wild-cluster-bootstrap package was removed here — archived on CRAN,
# no R 4.5 binary in the P3M snapshot. It can be installed at analysis time if
# needed (e.g. via a source/archive build).
RUN Rscript -e 'install.packages(c( \
        "fixest", "sandwich", "lmtest", "car", "plm", "estimatr", \
        "marginaleffects", "rdrobust", "lme4", \
        "survey", "rugarch", "tseries", "broom", "modelsummary" \
        ))'

# Geospatial
RUN Rscript -e 'install.packages(c( \
        "sf", "terra", "stars", \
        "spdep", "spatialreg", "classInt", "exactextractr", \
        "leaflet", "maptiles", "tidygeocoder", "osmdata" \
        ))'

# Visualization
RUN Rscript -e 'install.packages(c( \
        "ggplot2", "scales", "ggridges", "ggrepel", "patchwork", "ggdist", \
        "plotly", "gt", "knitr", "kableExtra", "viridis" \
        ))'

# ML and interpretation
RUN Rscript -e 'install.packages(c( \
        "tidymodels", "ranger", "glmnet", "xgboost", "lightgbm", "kknn", \
        "iml", "uwot", "fairmodels", "vip" \
        ))'

# Presence gate: verify every intended R package actually installed. install.packages()
# does NOT fail the build on a single package error, so a missing binary (as happened
# with the archived wild-bootstrap package) can slip through silently. This RUN loops the full
# intended list — the union of the install.packages() blocks above — and stops the build
# with an explicit list if any namespace is unavailable. Keep this list in sync with the
# blocks above when adding or removing packages.
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
        "plotly", "gt", "knitr", "kableExtra", "viridis", \
        "tidymodels", "ranger", "glmnet", "xgboost", "lightgbm", "kknn", \
        "iml", "uwot", "fairmodels", "vip" \
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
    && code-server --install-extension /tmp/debugpy.vsix \
    && code-server --install-extension /tmp/python-envs.vsix \
    && code-server --install-extension /tmp/python.vsix \
    && code-server --install-extension /tmp/markdown-aio.vsix \
    && code-server --install-extension /tmp/git-graph.vsix \
    && code-server --install-extension /tmp/gitlens.vsix \
    && code-server --install-extension /tmp/rainbow-csv.vsix \
    && code-server --install-extension /tmp/yaml.vsix \
    && code-server --install-extension /tmp/github-theme.vsix \
    && rm /tmp/*.vsix

# Set default code-server vscode settings (GitHub theme, sensible defaults)
RUN echo '{"workbench.colorTheme":"GitHub Dark Default","editor.fontSize":14,"editor.minimap.enabled":false,"telemetry.telemetryLevel":"off","extensions.autoUpdate":false,"security.workspace.trust.enabled":false}' \
    > /home/appuser/.local/share/code-server/User/settings.json

# Configure git identity for DAAF's internal version tracking.
# Agents make local commits during research sessions to create an audit trail.
# This identity is used for those automated commits inside the container only.
RUN git config --global user.email "daaf@local" \
    && git config --global user.name "DAAF Container"

# Install Claude Code as appuser (pinned version)
# Latest stable as of 2026-07-02
ARG CLAUDE_CODE_VERSION=2.1.187
RUN curl -fsSL https://claude.ai/install.sh | bash -s ${CLAUDE_CODE_VERSION}
ENV PATH="/home/appuser/.local/bin:${PATH}"

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
COPY <<'DAAF_ENTRYPOINT_EOF' /usr/local/bin/daaf-entrypoint.sh
#!/usr/bin/env bash
# daaf-entrypoint.sh — container ENTRYPOINT wrapper (generated from the
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
RUN chmod +x /usr/local/bin/daaf-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/daaf-entrypoint.sh"]

# Default command
CMD ["bash"]
