#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Copies the Kustomize base and overlay to a working directory (recreated on every
# run, so the repo copy is never edited), then deploys what the broken overlay renders.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
LEVEL=level-52-kustomize-overlay

prepare_workdir "$LEVEL" kustomize
kubectl apply -f broken.yaml
