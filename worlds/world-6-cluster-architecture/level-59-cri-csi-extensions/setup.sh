#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# RuntimeClass and StorageClass are cluster-scoped and their handler/provisioner
# fields are immutable, and the PVC is not covered by `kubectl delete all`.
# Remove earlier copies (cluster-scoped ones only when labelled part-of=k8squest),
# then apply the broken state.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
NS="${NAMESPACE:-k8squest}"

# The PVC is held by its pod (pvc-protection), so remove the Deployment and wait for
# its pods before deleting the claim. A slow delete must not pass silently.
kubectl delete deployment ledger -n "$NS" --ignore-not-found --wait=true --timeout=120s >/dev/null || true
kubectl delete pod -l app=ledger -n "$NS" --ignore-not-found --wait=true --timeout=120s >/dev/null || true
kubectl delete pvc ledger-data -n "$NS" --ignore-not-found --wait=true --timeout=120s >/dev/null || true
if kubectl get pvc ledger-data -n "$NS" >/dev/null 2>&1; then
    echo "[setup] PVC ledger-data is still terminating; try again in a minute" >&2
    exit 1
fi

delete_owned runtimeclass sandboxed
delete_owned storageclass fast-local
kubectl apply -f broken.yaml
