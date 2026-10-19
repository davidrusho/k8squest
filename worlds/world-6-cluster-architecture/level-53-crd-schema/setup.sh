#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Installs the (faulty) Website CRD. CustomResourceDefinitions are cluster-scoped,
# so the engine's `kubectl delete all` leaves them behind; remove an earlier copy first
# (only if it carries the k8squest part-of label). The CRD and the custom resource are
# also copied to a working directory that is recreated on every run.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
LEVEL=level-53-crd-schema

delete_owned crd websites.k8squest.io
prepare_workdir "$LEVEL" website.yaml
cp broken.yaml "$(level_workdir "$LEVEL")/crd.yaml"
kubectl apply -f broken.yaml
kubectl wait --for=condition=Established crd/websites.k8squest.io --timeout=60s
# the API server needs a moment to start serving the new kind
for i in $(seq 1 20); do
    kubectl get websites -n "${NAMESPACE:-k8squest}" >/dev/null 2>&1 && exit 0
    sleep 1
done
echo "Website kind is not being served" >&2
exit 1
