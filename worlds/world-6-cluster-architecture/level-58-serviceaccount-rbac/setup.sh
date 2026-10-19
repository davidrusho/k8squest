#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Deploys the broken RBAC state. The engine's reset removes the namespaced RBAC objects;
# this also removes ClusterRoleBindings (and RoleBindings) that an earlier attempt
# created for reports-sa, so a "fix" that widened access does not survive a replay.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
NS="${NAMESPACE:-k8squest}"

delete_sa_bindings "$NS" reports-sa
kubectl apply -f broken.yaml
