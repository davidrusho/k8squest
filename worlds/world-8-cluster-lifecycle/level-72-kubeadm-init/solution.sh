#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
# The player does this inside the machine: limactl shell k8squest-cp
# (kubeadm init --pod-network-cidr=10.244.0.0/16, then kubectl apply -f <flannel manifest>)
. ../_shared/lib.sh
control_plane_up "$K8S_NEW"
