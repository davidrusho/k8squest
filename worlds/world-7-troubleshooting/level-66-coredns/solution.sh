#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
set -e
kubectl -n kube-system get configmap coredns -o jsonpath='{.data.Corefile}' | sed 's/kubernetes cluster\.locl /kubernetes cluster.local /' > "${TMPDIR:-/tmp}/Corefile.fixed"
kubectl -n kube-system create configmap coredns --from-file=Corefile="${TMPDIR:-/tmp}/Corefile.fixed" --dry-run=client -o yaml | kubectl replace -f -
rm -f "${TMPDIR:-/tmp}/Corefile.fixed"
kubectl -n kube-system scale deployment coredns --replicas=2
kubectl -n kube-system rollout status deployment/coredns --timeout=120s
