# Modified 2026 by David Rusho; see CHANGES.md
FROM python:3.11-slim

ARG TARGETARCH

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl \
    && KUBECTL_URL="https://dl.k8s.io/release/v1.37.1/bin/linux/${TARGETARCH:-amd64}/kubectl" \
    && curl -fsSL -o /usr/local/bin/kubectl "${KUBECTL_URL}" \
    && curl -fsSL -o /tmp/kubectl.sha256 "${KUBECTL_URL}.sha256" \
    && echo "$(cat /tmp/kubectl.sha256)  /usr/local/bin/kubectl" | sha256sum --check \
    && rm /tmp/kubectl.sha256 \
    && chmod +x /usr/local/bin/kubectl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine ./engine
COPY worlds ./worlds

ENV K8SQUEST_WEB=true

CMD ["python", "engine/engine.py"]