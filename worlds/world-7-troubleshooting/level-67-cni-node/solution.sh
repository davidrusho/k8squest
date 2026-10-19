#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
set -e
kubectl label node k8squest-multinode-worker2 k8squest.io/cni=true
