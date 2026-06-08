FROM python:3.12-slim

WORKDIR /app

# Ferramentas do sistema: git (build/scanner), docker CLI (build), curl (instalação de tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# ── Trivy (scan de imagens e dependências) ───────────────────────────────────
RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
    | sh -s -- -b /usr/local/bin

# ── Gitleaks (secret scanning) ───────────────────────────────────────────────
RUN GITLEAKS_VERSION=8.21.0 && \
    curl -sSfL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
    | tar -xz -C /usr/local/bin gitleaks

# ── Semgrep (SAST) ───────────────────────────────────────────────────────────
# Instalado via pip junto com o resto das dependências Python

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt semgrep

COPY . .
