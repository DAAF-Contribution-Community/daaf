# Data Science Dockerfile with uv and Claude Code
# Base: Astral uv with Python 3.12 on Debian Bookworm

FROM ghcr.io/astral-sh/uv:python3.12-bookworm

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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Install Python Data Science Packages via uv
# ============================================

# Install core data science packages
RUN uv pip install --system \
    numpy \
    pandas \
    polars \
    scipy \
    openpyxl \
    xlrd \
    requests \
    pyarrow \
    urllib3 \
    pre-commit \
    scikit-learn

# Install visualization packages
RUN uv pip install --system \
    matplotlib \
    seaborn \
    plotnine \
    plotly \
    marimo

# ============================================
# Create non-root user for security
# ============================================
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home appuser

# ============================================
# Set up working directory (named volume mount point)
# ============================================
RUN mkdir -p /daaf && chown appuser:appuser /daaf
WORKDIR /daaf

USER appuser

# Install Claude Code (cached — only re-runs if layers above change)
RUN curl -fsSL https://claude.ai/install.sh | bash
ENV PATH="/home/appuser/.local/bin:${PATH}"

# ============================================
# Clone full repository into image
# ============================================
# Build args allow forks and pinned versions:
#   docker compose build --build-arg DAAF_REPO=https://github.com/myuser/daaf.git
#   docker compose build --build-arg DAAF_REF=my-branch
ARG DAAF_REPO=https://github.com/brhkim/daaf.git
ARG DAAF_REF=main
RUN git clone --branch ${DAAF_REF} --single-branch ${DAAF_REPO} /home/appuser/daaf-seed

# Extract entrypoint from cloned repo and make executable
RUN cp /home/appuser/daaf-seed/docker-entrypoint.sh /home/appuser/docker-entrypoint.sh \
    && chmod +x /home/appuser/docker-entrypoint.sh

ENTRYPOINT ["/home/appuser/docker-entrypoint.sh"]
CMD ["bash"]
