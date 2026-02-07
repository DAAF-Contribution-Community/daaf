# Data Science Dockerfile with uv, Node.js, and Claude Code
# Base: Astral uv with Python 3.12 on Debian Bookworm

FROM ghcr.io/astral-sh/uv:python3.12-bookworm

LABEL maintainer="Data Science Environment"
LABEL description="Python data science with uv, Node.js 22, and Claude Code"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set up uv environment variables
ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=1

# ============================================
# Install System Dependencies (Node.js setup + Git)
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    jq \
    git \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Install Claude Code globally via npm
# ============================================
RUN npm install -g @anthropic-ai/claude-code

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
    requests \ 
    pyarrow \
    urllib3

# Install machine learning packages
RUN uv pip install --system \
    scikit-learn

# Install visualization packages
RUN uv pip install --system \
    matplotlib \
    seaborn \
    plotnine \
    plotly \
    marimo

# Install development & testing tools
# Note: pydoc is part of the standard library (python -m pydoc)
RUN uv pip install --system \
    ruff

# ============================================
# Set up working directory
# ============================================
WORKDIR /daaf

# Default command
CMD ["bash"]