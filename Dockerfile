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
# Create non-root user for security
# ============================================
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home appuser

# ============================================
# Set up working directory
# ============================================
WORKDIR /daaf
RUN chown appuser:appuser /daaf
USER appuser

# Configure git identity for DAAF's internal version tracking.
# Agents make local commits during research sessions to create an audit trail.
# This identity is used for those automated commits inside the container only.
RUN git config --global user.email "daaf@local" \
    && git config --global user.name "DAAF Container"

# Install Claude Code as appuser (pinned version)
ARG CLAUDE_CODE_VERSION=2.1.87
RUN curl -fsSL https://claude.ai/install.sh | bash -s ${CLAUDE_CODE_VERSION}
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Default command
CMD ["bash"]
