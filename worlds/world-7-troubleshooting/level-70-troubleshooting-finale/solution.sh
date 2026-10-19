#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
set -e
CP=k8squest-multinode-control-plane
LOST=k8squest-multinode-worker
NS="${NAMESPACE:-k8squest}"

# Part 1: snapshot, then check it (flags are the etcd static pod's own certificate paths)
kubectl -n kube-system exec etcd-$CP -- etcdctl --endpoints=https://127.0.0.1:2379 \
    --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/server.crt \
    --key=/etc/kubernetes/pki/etcd/server.key snapshot save /var/lib/etcd/k8squest-snapshot.db
kubectl -n kube-system exec etcd-$CP -- etcdutl snapshot status /var/lib/etcd/k8squest-snapshot.db -w table

# Part 2: cordon, then drain. The node's kubelet is down, so the evicted pods never finish
# terminating and drain times out; the ReplicaSet has already started replacements elsewhere.
kubectl cordon $LOST
kubectl drain $LOST --ignore-daemonsets --delete-emptydir-data --force --timeout=30s \
    || echo "drain timed out: expected, the node's kubelet cannot confirm the pods are gone"
# a pod stuck Terminating on a dead node is removed from the API with a force delete
for p in $(kubectl get pods -n "$NS" -l app=shop --field-selector "spec.nodeName=$LOST" -o name); do
    kubectl delete -n "$NS" "$p" --force --grace-period=0
done
kubectl rollout status deployment/shop -n "$NS" --timeout=120s
