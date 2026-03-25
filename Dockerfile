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
# Install Python Data Science Packages via uv
# ============================================

# Install core data science packages
RUN uv pip install --system \
    numpy==2.4.2 \
    pandas==3.0.0 \
    polars==1.38.1 \
    scipy==1.17.0 \
    openpyxl==3.1.5 \
    xlrd==2.0.2 \
    requests==2.32.5 \
    pyarrow==23.0.0 \
    urllib3==2.6.3 \
    pre-commit==4.5.1 \
    scikit-learn==1.8.0 \
    umap-learn==0.5.11 \
    pyyaml==6.0.3 \
    statsmodels==0.14.6 \
    pyfixest==0.40.0

# Install econometrics & statistical modeling packages
# Primary: pyfixest + statsmodels already above
# Secondary: panel models, RDD, marginal effects, volatility, dynamic panels
# NOTE: lifelines excluded — latest (0.30.3) requires pandas<3.0, incompatible with pandas==3.0.0
RUN uv pip install --system \
    linearmodels \
    rdrobust \
    marginaleffects \
    arch \
    pydynpd==0.2.1

# Install geospatial packages
# Core: vector (geopandas + deps), raster (rasterio + xarray), mapping, PySAL spatial stats
RUN uv pip install --system \
    geopandas==1.1.3 \
    rasterio \
    xarray \
    rioxarray \
    contextily \
    folium \
    libpysal \
    esda \
    spreg \
    mapclassify \
    rasterstats \
    geopy \
    osmnx

# Install visualization packages
RUN uv pip install --system \
    matplotlib==3.10.8 \
    seaborn==0.13.2 \
    plotnine==0.15.3 \
    plotly==6.5.2 \
    marimo==0.19.11

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

# Install Claude Code as appuser (installs to ~/.claude/local/bin/)
RUN curl -fsSL https://claude.ai/install.sh | bash
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Default command
CMD ["bash"]