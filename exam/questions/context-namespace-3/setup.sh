#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on): ConfigMap ctx-marker with a random token. Only a kubectl that really
# reaches this cluster can read it, and a stale answer from an earlier run cannot contain it. The level runs setup-cka1.sh first.
set -eu
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf"
$KC -n default delete configmap ctx-marker --ignore-not-found
TOKEN=$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')
[ "${#TOKEN}" = 24 ] || { echo "could not generate a token"; exit 1; }
$KC -n default create configmap ctx-marker --from-literal=token="$TOKEN"
