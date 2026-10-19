#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
set -e
NS="${NAMESPACE:-k8squest}"
kubectl patch configmap invoice-config -n "$NS" --type=json \
    -p '[{"op":"remove","path":"/data/DB_HOTS"},{"op":"add","path":"/data/DB_HOST","value":"db.internal"}]'
kubectl rollout restart deployment/invoice-api -n "$NS"
kubectl rollout status deployment/invoice-api -n "$NS" --timeout=120s
