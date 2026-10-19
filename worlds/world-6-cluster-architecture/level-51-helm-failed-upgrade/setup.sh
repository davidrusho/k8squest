#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Builds a Helm release with a good revision 1 and a broken revision 2.
# The chart and values file are copied to a working directory that is recreated on
# every run, so the repo copy is never edited by the player.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
NS="${NAMESPACE:-k8squest}"
LEVEL=level-51-helm-failed-upgrade
need helm

# Helm keeps its release history in Secrets, which the engine's
# `kubectl delete all` does not remove, so start from a clean release.
# (--ignore-not-found needs Helm 3.13 or newer)
helm uninstall webapp -n "$NS" --ignore-not-found >/dev/null

prepare_workdir "$LEVEL" chart broken.yaml
WORK=$(level_workdir "$LEVEL")

log "installing webapp revision 1 (good)"
helm install webapp "$WORK/chart" -n "$NS" --wait --timeout 120s >/dev/null
log "upgrading webapp to revision 2 (broken)"
helm upgrade webapp "$WORK/chart" -n "$NS" -f "$WORK/broken.yaml" >/dev/null
helm history webapp -n "$NS"
