#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
# The player does this inside the node: docker exec -it k8squest-multinode-worker2 bash
set -e
docker exec k8squest-multinode-worker2 sed -i 's#/etc/kubernetes/pki/ca.crtt#/etc/kubernetes/pki/ca.crt#' /var/lib/kubelet/config.yaml
docker exec k8squest-multinode-worker2 systemctl restart kubelet
