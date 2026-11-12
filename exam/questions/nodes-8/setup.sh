#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on): Deployment drain-web (2 Pods with an emptyDir volume, pinned to node01)
# and a ConfigMap that records the Pod UIDs and the ReplicaSet name, so that the validator can tell new Pods of the SAME
# ReplicaSet (evicted) from the untouched Pods and from a rollout restart.
set -eu
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf"
IMG=$(crictl images 2>/dev/null | awk '$1 ~ /pause$/ {print $1 ":" $2; exit}')
[ -n "$IMG" ] || IMG=registry.k8s.io/pause:3.10
$KC -n default delete configmap drain-baseline --ignore-not-found
$KC apply -f - <<MANIFEST
apiVersion: apps/v1
kind: Deployment
metadata:
  name: drain-web
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: drain-web
  template:
    metadata:
      labels:
        app: drain-web
    spec:
      nodeSelector:
        kubernetes.io/hostname: node01
      containers:
      - name: web
        image: $IMG
        volumeMounts:
        - name: cache
          mountPath: /cache
      volumes:
      - name: cache
        emptyDir: {}
MANIFEST
$KC -n default rollout status deployment/drain-web --timeout=180s
UIDS=$($KC -n default get pods -l app=drain-web -o jsonpath='{range .items[*]}{.metadata.uid}{"\n"}{end}' | sort | paste -sd, -)
[ -n "$UIDS" ] || { echo "no drain-web Pods"; exit 1; }
RS=$($KC -n default get pods -l app=drain-web -o jsonpath='{.items[0].metadata.ownerReferences[0].name}')
[ -n "$RS" ] || { echo "no ReplicaSet owner"; exit 1; }
$KC -n default create configmap drain-baseline --from-literal=uids="$UIDS" --from-literal=rs="$RS"
