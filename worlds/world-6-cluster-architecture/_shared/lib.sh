#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
#
# Shared helpers for World 6 setup.sh scripts. Not a level: discovery only reads
# level-* directories. Source it from a level with:
#   . "$(dirname "$0")/../_shared/lib.sh"
#
# Every ensure_* function is idempotent: it returns at once when the component
# is already installed, otherwise installs the pinned version and waits (with a
# timeout) until it is ready. Versions are pinned here and nowhere else.

CERT_MANAGER_VERSION="v1.21.2"            # https://cert-manager.io/docs/installation/kubectl/
GATEWAY_API_VERSION="v1.6.3"              # https://gateway-api.sigs.k8s.io/guides/getting-started/
ENVOY_GATEWAY_VERSION="v1.9.2"            # https://gateway.envoyproxy.io/docs/install/install-helm/
METRICS_SERVER_VERSION="v0.9.0"           # https://github.com/kubernetes-sigs/metrics-server
VPA_VERSION="1.8.0"                       # https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler

log() { echo "[setup] $*"; }

# Label carried by every cluster-scoped object a World 6 level creates
# (RuntimeClass, StorageClass, CRD, GatewayClass). Setup only ever deletes such
# an object when it has this label AND the expected name.
PART_OF="app.kubernetes.io/part-of=k8squest"

# World 6 setup scripts create and delete cluster-scoped objects, so refuse to run
# against any cluster except the game's own kind cluster. (The engine also accepts
# k3s-k8squest for K8S_CLUSTER_TYPE=k3s; World 6 declares `cluster: kind` and is only
# tested on kind, so it deliberately does not.)
# Override (at your own risk): K8SQUEST_ALLOW_CONTEXT=1
require_game_context() {
    local ctx
    ctx=$(kubectl config current-context 2>/dev/null || true)
    if [ "$ctx" = "kind-k8squest" ] || [ "${K8SQUEST_ALLOW_CONTEXT:-}" = "1" ]; then
        return 0
    fi
    echo "[setup] REFUSING to run: kubectl context is '${ctx:-none}', expected 'kind-k8squest'." >&2
    echo "[setup] This level creates and deletes cluster-scoped objects. Run: kubectl config use-context kind-k8squest" >&2
    echo "[setup] (or set K8SQUEST_ALLOW_CONTEXT=1 to override)" >&2
    return 1
}

# delete_owned <kind> <name>
# Delete a cluster-scoped object of this world, only if it carries $PART_OF.
# An object of that name WITHOUT the label is not ours: stop instead of deleting it.
delete_owned() {
    local kind=$1 name=$2
    kubectl get "$kind" "$name" >/dev/null 2>&1 || return 0
    if [ -n "$(kubectl get "$kind" -l "$PART_OF" --field-selector "metadata.name=$name" -o name 2>/dev/null)" ]; then
        kubectl delete "$kind" "$name" --ignore-not-found >/dev/null   # (kubectl refuses a name together with -l)
        return 0
    fi
    echo "[setup] $kind/$name exists but is not labelled $PART_OF, so it is not this level's object. Delete it yourself (kubectl delete $kind $name) or label it ($PART_OF) and re-run." >&2
    return 1
}

# Per-level working copy of the assets a player may edit (chart, overlay, custom
# resource). Recreated from the pristine repo copy on every setup run.
level_workdir() { echo "${K8SQUEST_WORKDIR:-$HOME/.k8squest/work}/$1"; }

# prepare_workdir <level-name> <asset>...   (assets are paths relative to the level dir)
prepare_workdir() {
    local lvl=$1 w
    shift
    w=$(level_workdir "$lvl")
    [ -n "$lvl" ] || return 1
    rm -rf "$w"
    mkdir -p "$w"
    cp -R "$@" "$w"/
    log "working copy of this level's files: $w"
}

# route_attached <namespace> <route> <gateway>
# Prints a one-line diagnosis. Returns 0 only when the route has the single
# parentRef <gateway> and the status entry for THAT parentRef (including its
# sectionName) reports Accepted=True and ResolvedRefs=True for the route's
# CURRENT generation. Envoy Gateway can leave status entries behind for a parentRef
# that was changed, so entries are matched, not taken by position.
route_attached() {
    local ns=$1 route=$2 gw=$3 names sec gen entries
    names=$(kubectl get httproute "$route" -n "$ns" -o jsonpath='{range .spec.parentRefs[*]}{.name}{"\n"}{end}' 2>/dev/null)
    if [ "$names" != "$gw" ]; then
        echo "parentRefs must be the single Gateway $gw (found: ${names:-none})"
        return 1
    fi
    sec=$(kubectl get httproute "$route" -n "$ns" -o jsonpath='{.spec.parentRefs[0].sectionName}' 2>/dev/null)
    gen=$(kubectl get httproute "$route" -n "$ns" -o jsonpath='{.metadata.generation}' 2>/dev/null)
    entries=$(kubectl get httproute "$route" -n "$ns" -o jsonpath='{range .status.parents[*]}{.parentRef.name}/{.parentRef.sectionName}|{range .conditions[*]}{.type}={.status}@{.observedGeneration} {end}{"\n"}{end}' 2>/dev/null)
    if echo "$entries" | grep -F "$gw/$sec|" | grep -qF "Accepted=True@$gen " \
        && echo "$entries" | grep -F "$gw/$sec|" | grep -qF "ResolvedRefs=True@$gen "; then
        echo "Accepted=True ResolvedRefs=True at generation $gen (parentRef $gw${sec:+, sectionName $sec})"
        return 0
    fi
    echo "no entry for parentRef $gw${sec:+/$sec} with Accepted=True and ResolvedRefs=True at generation $gen (status: $(echo "$entries" | tr '\n' ';'))"
    return 1
}

# sa_extra_permissions <namespace> <serviceaccount>
# Prints every permission of the ServiceAccount that is NOT get/list on configmaps,
# ignoring the rows every authenticated identity has (non-resource URLs,
# self-subject reviews, clustertrustbundles).
sa_extra_permissions() {
    local ns=$1 sa=$2 out
    out=$(kubectl auth can-i --list --as="system:serviceaccount:${ns}:${sa}" -n "$ns" 2>/dev/null) || {
        echo "could not list the permissions of ${ns}/${sa}"
        return 0
    }
    echo "$out" | tail -n +2 | awk '
        /^[[:space:]]*\[/ { next }
        $1 ~ /^selfsubject/ { next }
        $1 ~ /^clustertrustbundles\./ {          # observed on v1.37 for every authenticated identity
            v = $0; sub(/.*\[/, "", v); sub(/\].*/, "", v)
            n = split(v, verbs, " "); ok = 1
            for (i = 1; i <= n; i++) if (verbs[i] != "get" && verbs[i] != "list" && verbs[i] != "watch") ok = 0
            if (ok) next
        }
        $1 == "configmaps" {
            v = $0; sub(/.*\[/, "", v); sub(/\].*/, "", v)
            if (v == "get list" || v == "list get") next
        }
        { print }'
}

# sa_clusterrolebindings <namespace> <serviceaccount>: names of ClusterRoleBindings naming the ServiceAccount
sa_clusterrolebindings() {
    kubectl get clusterrolebinding -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{range .subjects[*]}{.kind}/{.namespace}/{.name}{" "}{end}{"\n"}{end}' 2>/dev/null \
        | grep -F "ServiceAccount/$1/$2 " | cut -d'|' -f1
}

# delete_sa_bindings <namespace> <serviceaccount>
# Remove RoleBindings and ClusterRoleBindings that name this ServiceAccount, left
# behind by an earlier attempt (a "fix" that widened access). A ClusterRoleBinding
# that names other subjects too is skipped and reported, never deleted.
delete_sa_bindings() {
    local ns=$1 sa=$2 rb crb
    for rb in $(kubectl get rolebinding -n "$ns" -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{range .subjects[*]}{.kind}/{.namespace}/{.name}{" "}{end}{"\n"}{end}' 2>/dev/null \
            | grep -F "ServiceAccount/$ns/$sa " | cut -d'|' -f1); do
        kubectl delete rolebinding "$rb" -n "$ns" --ignore-not-found >/dev/null
    done
    for crb in $(sa_clusterrolebindings "$ns" "$sa"); do
        # a ClusterRoleBinding that also names other subjects is not ours to delete
        if [ "$(kubectl get clusterrolebinding "$crb" -o jsonpath='{range .subjects[*]}{.kind}/{.namespace}/{.name}{"\n"}{end}' 2>/dev/null | grep -vcFx "ServiceAccount/$ns/$sa")" != "0" ]; then
            echo "[setup] NOT deleting ClusterRoleBinding $crb: it names other subjects as well as $ns/$sa. Remove $ns/$sa from it yourself if it gives that account extra access." >&2
            continue
        fi
        kubectl delete clusterrolebinding "$crb" --ignore-not-found >/dev/null
    done
}

need() {
    command -v "$1" >/dev/null 2>&1 || { echo "[setup] ERROR: '$1' is required but not installed" >&2; return 1; }
}

# retry <attempts> <sleep-seconds> <command...>
retry() {
    local n=$1 s=$2 i
    shift 2
    for ((i = 1; i <= n; i++)); do
        "$@" && return 0
        sleep "$s"
    done
    return 1
}

# wait_available <namespace> <timeout>   (all Deployments in the namespace)
wait_available() {
    kubectl wait --for=condition=Available deployment --all -n "$1" --timeout="$2" >/dev/null
}

ensure_cert_manager() {
    if kubectl get crd certificates.cert-manager.io >/dev/null 2>&1 \
        && kubectl wait --for=condition=Available deployment --all -n cert-manager --timeout=5s >/dev/null 2>&1; then
        log "cert-manager already installed"
        return 0
    fi
    log "installing cert-manager ${CERT_MANAGER_VERSION}"
    retry 3 5 kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml" >/dev/null || return 1
    wait_available cert-manager 240s || { echo "[setup] cert-manager did not become ready" >&2; return 1; }
    # the webhook answers only after its CA bundle is injected. Each attempt gets the
    # YAML again from a variable: a heredoc on `retry` is consumed by the first attempt.
    local probe='apiVersion: cert-manager.io/v1
kind: Issuer
metadata: {name: probe, namespace: default}
spec: {selfSigned: {}}'
    retry 24 5 _apply_probe "$probe" || return 1
}

_apply_probe() { printf '%s\n' "$1" | kubectl apply --dry-run=server -f - >/dev/null 2>&1; }

ensure_gateway_api() {
    local have
    have=$(kubectl get crd gateways.gateway.networking.k8s.io \
        -o jsonpath='{.metadata.annotations.gateway\.networking\.k8s\.io/bundle-version}' 2>/dev/null || true)
    if [ "$have" = "$GATEWAY_API_VERSION" ]; then
        return 0
    fi
    log "installing Gateway API ${GATEWAY_API_VERSION} standard CRDs"
    retry 3 5 kubectl apply --server-side -f "https://github.com/kubernetes-sigs/gateway-api/releases/download/${GATEWAY_API_VERSION}/standard-install.yaml" >/dev/null || return 1
    kubectl wait --for=condition=Established crd/gateways.gateway.networking.k8s.io crd/httproutes.gateway.networking.k8s.io crd/referencegrants.gateway.networking.k8s.io --timeout=60s >/dev/null
}

ensure_envoy_gateway() {
    need helm || return 1
    ensure_gateway_api || return 1
    if helm status eg -n envoy-gateway-system >/dev/null 2>&1 \
        && kubectl wait --for=condition=Available deployment/envoy-gateway -n envoy-gateway-system --timeout=5s >/dev/null 2>&1; then
        :
    else
        log "installing Envoy Gateway ${ENVOY_GATEWAY_VERSION}"
        # Gateway API CRDs are installed above, so only Envoy Gateway's own CRDs are rendered here
        # (https://gateway.envoyproxy.io/docs/install/install-helm/).
        helm template eg-crds oci://docker.io/envoyproxy/gateway-crds-helm \
            --version "$ENVOY_GATEWAY_VERSION" \
            --set crds.gatewayAPI.enabled=false \
            --set crds.envoyGateway.enabled=true \
            | kubectl apply --server-side -f - >/dev/null || return 1
        helm upgrade --install eg oci://docker.io/envoyproxy/gateway-helm \
            --version "$ENVOY_GATEWAY_VERSION" \
            -n envoy-gateway-system --create-namespace \
            --set crds.enabled=false >/dev/null || return 1
        kubectl wait --timeout=5m -n envoy-gateway-system deployment/envoy-gateway --for=condition=Available >/dev/null || return 1
    fi
    kubectl apply -f - >/dev/null <<'YAML'
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: eg
  labels:
    app.kubernetes.io/part-of: k8squest
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
YAML
}

# The shared Gateway the World 6 routing levels attach to. kind has no
# LoadBalancer, so the Gateway is never "Programmed"; it only needs to be
# "Accepted", which is what an HTTPRoute's parentRef is checked against.
ensure_gateway() {
    ensure_envoy_gateway || return 1
    kubectl apply -f - >/dev/null <<'YAML'
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: web-gw
  namespace: k8squest
spec:
  gatewayClassName: eg
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces:
        from: Same
YAML
    retry 30 3 bash -c "[ \"\$(kubectl get gateway web-gw -n k8squest -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}')\" = True ]" \
        || { echo "[setup] Gateway web-gw was not Accepted" >&2; return 1; }
}

ensure_metrics_server() {
    if kubectl get apiservice v1beta1.metrics.k8s.io >/dev/null 2>&1 \
        && kubectl wait --for=condition=Available apiservice/v1beta1.metrics.k8s.io --timeout=5s >/dev/null 2>&1; then
        return 0
    fi
    log "installing metrics-server ${METRICS_SERVER_VERSION}"
    retry 3 5 kubectl apply -f "https://github.com/kubernetes-sigs/metrics-server/releases/download/${METRICS_SERVER_VERSION}/components.yaml" >/dev/null || return 1
    # kind's kubelet serves a certificate the cluster CA did not sign
    if ! kubectl get deployment metrics-server -n kube-system -o jsonpath='{.spec.template.spec.containers[0].args}' | grep -q kubelet-insecure-tls; then
        kubectl patch deployment metrics-server -n kube-system --type=json \
            -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]' >/dev/null || return 1
    fi
    kubectl rollout status deployment/metrics-server -n kube-system --timeout=180s >/dev/null || return 1
    kubectl wait --for=condition=Available apiservice/v1beta1.metrics.k8s.io --timeout=180s >/dev/null
}

# Recommender-only install of the Vertical Pod Autoscaler. The levels use
# updateMode "Off", which only needs the recommender (it writes
# status.recommendation); the updater and admission controller are left out so
# the install needs no git clone and no openssl (the full install, hack/vpa-up.sh,
# uses both). The CRD and RBAC lines are the ones installation.md itself gives
# for `kubectl apply`; recommender-deployment.yaml comes from the same deploy/ dir.
ensure_vpa() {
    ensure_metrics_server || return 1
    if kubectl get crd verticalpodautoscalers.autoscaling.k8s.io >/dev/null 2>&1 \
        && kubectl wait --for=condition=Available deployment/vpa-recommender -n kube-system --timeout=5s >/dev/null 2>&1; then
        return 0
    fi
    log "installing Vertical Pod Autoscaler ${VPA_VERSION} (recommender only)"
    local base="https://raw.githubusercontent.com/kubernetes/autoscaler/vertical-pod-autoscaler-${VPA_VERSION}/vertical-pod-autoscaler/deploy"
    local f
    for f in vpa-v1-crd-gen vpa-rbac recommender-deployment; do
        retry 3 5 kubectl apply -f "${base}/${f}.yaml" >/dev/null || return 1
    done
    kubectl wait --for=condition=Established crd/verticalpodautoscalers.autoscaling.k8s.io --timeout=60s >/dev/null || return 1
    kubectl rollout status deployment/vpa-recommender -n kube-system --timeout=180s >/dev/null
}
