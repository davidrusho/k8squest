#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
# The player does this by hand on the control-plane machine (see solution.yaml). Steps follow
# https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd/
. ../_shared/lib.sh
limactl shell --workdir /tmp "$CP_VM" sudo bash -s <<'REMOTE'
set -eu
export KUBECONFIG=/etc/kubernetes/admin.conf
SNAP=/var/backups/etcd/k8squest-snapshot.db
etcdctl --endpoints=https://127.0.0.1:2379 --cacert=/etc/kubernetes/pki/etcd/ca.crt \
    --cert=/etc/kubernetes/pki/etcd/server.crt --key=/etc/kubernetes/pki/etcd/server.key snapshot save "$SNAP" >/dev/null
etcdutl snapshot status "$SNAP" -w table
# the accident
kubectl -n k8squest delete deployment ledger
kubectl -n k8squest delete configmap ledger-config
# stop the API server and etcd: the kubelet runs what is in the manifests directory
mkdir -p /root/parked
mv /etc/kubernetes/manifests/kube-apiserver.yaml /etc/kubernetes/manifests/etcd.yaml /root/parked/
for i in $(seq 1 60); do
    [ -z "$(crictl ps -q --name '^(etcd|kube-apiserver)$' 2>/dev/null)" ] && break
    sleep 2
done
rm -rf /var/lib/etcd-restored
etcdutl --data-dir /var/lib/etcd-restored snapshot restore "$SNAP" >/dev/null
sed -i 's|path: /var/lib/etcd$|path: /var/lib/etcd-restored|' /root/parked/etcd.yaml
grep -q 'path: /var/lib/etcd-restored' /root/parked/etcd.yaml
mv /root/parked/etcd.yaml /root/parked/kube-apiserver.yaml /etc/kubernetes/manifests/
for i in $(seq 1 90); do
    kubectl get --raw /readyz >/dev/null 2>&1 && break
    sleep 2
done
REMOTE
