#!/bin/bash

NAMESPACE="k8squest"
DEPLOYMENT="chaos-app"

echo "🔥 CHAOS FINALE VALIDATION 🔥"
echo "Checking ALL World 5 concepts..."
echo ""

ERRORS=0

# Unit helpers: CPU in millicores, memory in Mi
to_milli() {
    case "$1" in
        *m) echo "${1%m}" ;;
        *) awk -v v="$1" 'BEGIN { printf "%d", v * 1000 }' ;;
    esac
}
to_mib() {
    awk -v v="$1" 'BEGIN {
        n = v + 0; u = v; sub(/^[0-9.]+/, "", u)
        if (u == "Ti") n *= 1048576; else if (u == "Gi") n *= 1024; else if (u == "Mi") n *= 1
        else if (u == "Ki") n /= 1024; else if (u == "G") n = n * 1000000000 / 1048576
        else if (u == "M") n = n * 1000000 / 1048576; else if (u == "k") n = n * 1000 / 1048576
        else if (u == "") n /= 1048576
        printf "%d", n }'
}
# A PDB value is a number or a percentage; percentages round up
to_pods() {
    if [[ "$1" == *"%"* ]]; then
        echo $(( (${1%\%} * REPLICAS + 99) / 100 ))
    else
        echo "$1"
    fi
}

# The Deployment is read once; the checks below need its replicas, template and status
DEP_JSON=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o json 2>/dev/null)
REPLICAS=$(echo "$DEP_JSON" | jq -r '.spec.replicas // 0' 2>/dev/null)
REPLICAS=${REPLICAS:-0}

# 1. RBAC
echo "🔍 1/9: Checking RBAC (ServiceAccount, Role, RoleBinding)..."
if ! kubectl get serviceaccount app-sa -n $NAMESPACE &>/dev/null; then
    echo "❌ ServiceAccount missing"; ((ERRORS++))
elif ! kubectl get role app-role -n $NAMESPACE &>/dev/null; then
    echo "❌ Role missing"; ((ERRORS++))
elif ! kubectl get rolebinding app-binding -n $NAMESPACE &>/dev/null; then
    echo "❌ RoleBinding missing"; ((ERRORS++))
else
    # The Role must let the app read pods, and the RoleBinding must tie that Role to app-sa
    ROLE_RULES=$(kubectl get role app-role -n $NAMESPACE -o json | jq -r '[.rules[]?
        | select(((.apiGroups // []) | (index("") != null or index("*") != null)))
        | select(((.resources // []) | (index("pods") != null or index("*") != null)))
        | select(((.verbs // []) | (index("*") != null or (index("get") != null and index("list") != null))))] | length')
    BINDING_OK=$(kubectl get rolebinding app-binding -n $NAMESPACE -o json | jq -r '
        (.roleRef.kind == "Role" and .roleRef.name == "app-role")
        and ([.subjects[]? | select(.kind == "ServiceAccount" and .name == "app-sa" and ((.namespace // "k8squest") == "k8squest"))] | length > 0)')
    if [ "${ROLE_RULES:-0}" -lt 1 ]; then
        echo "❌ Role 'app-role' has no rule granting get and list on pods"; ((ERRORS++))
    elif [ "$BINDING_OK" != "true" ]; then
        echo "❌ RoleBinding 'app-binding' does not bind Role 'app-role' to ServiceAccount 'app-sa'"; ((ERRORS++))
    else
        echo "✅ RBAC configured"
    fi
fi

# 2. ResourceQuota
echo "🔍 2/9: Checking ResourceQuota..."
QUOTA_CPU=$(kubectl get resourcequota chaos-quota -n $NAMESPACE -o jsonpath='{.spec.hard.requests\.cpu}' 2>/dev/null)
QUOTA_MEM=$(kubectl get resourcequota chaos-quota -n $NAMESPACE -o jsonpath='{.spec.hard.requests\.memory}' 2>/dev/null)
QUOTA_PODS=$(kubectl get resourcequota chaos-quota -n $NAMESPACE -o jsonpath='{.spec.hard.pods}' 2>/dev/null)
if [ -z "$QUOTA_CPU" ]; then
    echo "❌ ResourceQuota missing"; ((ERRORS++))
else
    echo "✅ ResourceQuota: $QUOTA_CPU CPU"
fi

# 3. NetworkPolicy
echo "🔍 3/9: Checking NetworkPolicy..."
# Traffic of the app pods is blocked in a direction when policies select them for it and none of those has an allow rule
NP_BLOCKED=$(kubectl get networkpolicy -n $NAMESPACE -o json | jq -r '
    def selects: (.spec.podSelector // {}) as $s
        | ((($s.matchLabels // {}) | to_entries | all(.key == "app" and .value == "chaos")) and (($s.matchExpressions // []) | length == 0));
    def types: (.spec.policyTypes // (["Ingress"] + (if ((.spec.egress // []) | length) > 0 then ["Egress"] else [] end)));
    def rules($t): (if $t == "Ingress" then (.spec.ingress // []) else (.spec.egress // []) end);
    [.items[] | select(selects)] as $p
    | def blocked($t): ([$p[] | select(types | index($t) != null)]) as $q
        | (($q | length) > 0) and (([$q[] | select(rules($t) | length > 0)] | length) == 0);
    [(if blocked("Ingress") then "ingress" else empty end), (if blocked("Egress") then "egress" else empty end)] | join(" ")' 2>/dev/null)
if [ -n "$NP_BLOCKED" ]; then
    echo "❌ NetworkPolicy still blocks the app's $NP_BLOCKED traffic (no allow rule, or no allow policy)"; ((ERRORS++))
else
    echo "✅ NetworkPolicy configured"
fi

# 4. PriorityClass
echo "🔍 4/9: Checking PriorityClass (looking for: 'production-priority')..."
PRIORITY_VALUE=$(kubectl get priorityclass production-priority -o jsonpath='{.value}' 2>/dev/null)
POD_PRIORITY_CLASS=$(echo "$DEP_JSON" | jq -r '.spec.template.spec.priorityClassName // ""' 2>/dev/null)
if [ -z "$PRIORITY_VALUE" ]; then
    echo "❌ PriorityClass 'production-priority' missing"; ((ERRORS++))
elif [ "$PRIORITY_VALUE" -le 0 ]; then
    echo "❌ PriorityClass 'production-priority' has value $PRIORITY_VALUE, not above the default (0)"; ((ERRORS++))
elif [ "$POD_PRIORITY_CLASS" != "production-priority" ]; then
    echo "❌ Deployment does not use priorityClassName 'production-priority'"; ((ERRORS++))
else
    echo "✅ PriorityClass 'production-priority' exists (value $PRIORITY_VALUE) and is assigned"
fi

# 5. PodDisruptionBudget
echo "🔍 5/9: Checking PodDisruptionBudget..."
if ! kubectl get pdb chaos-pdb -n $NAMESPACE &>/dev/null; then
    echo "❌ PDB missing"; ((ERRORS++))
else
    MIN_AVAIL=$(kubectl get pdb chaos-pdb -n $NAMESPACE -o jsonpath='{.spec.minAvailable}')
    MAX_UNAVAIL=$(kubectl get pdb chaos-pdb -n $NAMESPACE -o jsonpath='{.spec.maxUnavailable}')
    PDB_ALLOWED=$(kubectl get pdb chaos-pdb -n $NAMESPACE -o jsonpath='{.status.disruptionsAllowed}')
    if [ -n "$MIN_AVAIL" ]; then
        PDB_KEEP=$(to_pods "$MIN_AVAIL")
        PDB_DESC="minAvailable: $MIN_AVAIL"
    elif [ -n "$MAX_UNAVAIL" ]; then
        PDB_KEEP=$((REPLICAS - $(to_pods "$MAX_UNAVAIL")))
        PDB_DESC="maxUnavailable: $MAX_UNAVAIL"
    else
        PDB_KEEP=$REPLICAS
        PDB_DESC="no budget"
    fi
    if [ "$PDB_KEEP" -ge "$REPLICAS" ]; then
        echo "❌ PDB ($PDB_DESC) keeps $PDB_KEEP of $REPLICAS replicas up - it blocks every eviction"; ((ERRORS++))
    elif [ "$PDB_KEEP" -le 0 ]; then
        echo "❌ PDB ($PDB_DESC) protects nothing - keep at least one pod available"; ((ERRORS++))
    elif [ -z "$PDB_ALLOWED" ] || [ "$PDB_ALLOWED" = "0" ]; then
        echo "❌ PDB ($PDB_DESC) currently allows no disruptions (disruptionsAllowed: ${PDB_ALLOWED:-0})"; ((ERRORS++))
    else
        echo "✅ PDB configured ($PDB_DESC, disruptionsAllowed: $PDB_ALLOWED)"
    fi
fi

# 6. Deployment
echo "🔍 6/9: Checking Deployment..."
if ! kubectl get deployment $DEPLOYMENT -n $NAMESPACE &>/dev/null; then
    echo "❌ Deployment missing"; ((ERRORS++))
    exit 1
fi
echo "✅ Deployment exists"

# 7. SecurityContext (container-level wins over pod-level, as in Kubernetes)
echo "🔍 7/9: Checking SecurityContext (runAsNonRoot, allowPrivilegeEscalation)..."
SEC=$(echo "$DEP_JSON" | jq -r '
    def eff($a; $b): if $a == null then $b else $a end;
    .spec.template.spec as $p | $p.containers[0].securityContext as $c | $p.securityContext as $ps
    | [ (eff($c.runAsNonRoot; $ps.runAsNonRoot) | tostring),
        (eff($c.runAsUser; $ps.runAsUser) | tostring),
        ($c.allowPrivilegeEscalation | tostring),
        ((($c.capabilities.drop // []) | index("ALL")) != null | tostring),
        (eff($c.seccompProfile.type; $ps.seccompProfile.type) | tostring) ] | join(" ")')
read -r RUN_AS_NON_ROOT RUN_AS_USER ALLOW_PRIV CAPS_DROPPED SECCOMP <<< "$SEC"
if [ "$RUN_AS_NON_ROOT" != "true" ]; then
    echo "❌ runAsNonRoot not true"; ((ERRORS++))
elif [ "$RUN_AS_USER" = "0" ]; then
    echo "❌ runAsUser is 0 (root)"; ((ERRORS++))
elif [ "$ALLOW_PRIV" != "false" ]; then
    echo "❌ allowPrivilegeEscalation not false"; ((ERRORS++))
elif [ "$CAPS_DROPPED" != "true" ]; then
    echo "❌ capabilities.drop does not include ALL"; ((ERRORS++))
elif [ "$SECCOMP" != "RuntimeDefault" ] && [ "$SECCOMP" != "Localhost" ]; then
    echo "❌ seccompProfile must be RuntimeDefault or Localhost (restricted standard)"; ((ERRORS++))
else
    echo "✅ SecurityContext configured securely"
fi

# 8. Resources within quota
echo "🔍 8/9: Checking resource requests fit quota..."
CPU_REQUEST=$(echo "$DEP_JSON" | jq -r '.spec.template.spec.containers[0].resources.requests.cpu // ""')
MEM_REQUEST=$(echo "$DEP_JSON" | jq -r '.spec.template.spec.containers[0].resources.requests.memory // ""')
echo "   CPU per pod: $CPU_REQUEST, Memory per pod: $MEM_REQUEST, Replicas: $REPLICAS"
if [ -z "$CPU_REQUEST" ] || [ -z "$MEM_REQUEST" ]; then
    echo "❌ Container needs CPU and memory requests (the quota counts them)"; ((ERRORS++))
elif [ -n "$QUOTA_CPU" ] && [ $((REPLICAS * $(to_milli "$CPU_REQUEST"))) -gt "$(to_milli "$QUOTA_CPU")" ]; then
    echo "❌ $REPLICAS x $CPU_REQUEST CPU exceeds the quota ($QUOTA_CPU)"; ((ERRORS++))
elif [ -n "$QUOTA_MEM" ] && [ $((REPLICAS * $(to_mib "$MEM_REQUEST"))) -gt "$(to_mib "$QUOTA_MEM")" ]; then
    echo "❌ $REPLICAS x $MEM_REQUEST memory exceeds the quota ($QUOTA_MEM)"; ((ERRORS++))
elif [ -n "$QUOTA_PODS" ] && [ "$REPLICAS" -gt "$QUOTA_PODS" ]; then
    echo "❌ $REPLICAS replicas exceed the quota's pod limit ($QUOTA_PODS)"; ((ERRORS++))
else
    echo "✅ Resource requests fit the quota"
fi

# 9. Pod status: every replica of the current spec is ready (this also proves the taint is tolerated)
echo "🔍 9/9: Checking pod status..."
READY=$(echo "$DEP_JSON" | jq -r '.status.readyReplicas // 0')
UPDATED=$(echo "$DEP_JSON" | jq -r '.status.updatedReplicas // 0')
TOTAL=$(echo "$DEP_JSON" | jq -r '.status.replicas // 0')
GENERATION=$(echo "$DEP_JSON" | jq -r '.metadata.generation')
OBSERVED=$(echo "$DEP_JSON" | jq -r '.status.observedGeneration // 0')
if [ "$READY" = "0" ] || [ "$READY" != "$REPLICAS" ] || [ "$UPDATED" != "$REPLICAS" ] || [ "$TOTAL" != "$REPLICAS" ] || [ "$OBSERVED" != "$GENERATION" ]; then
    echo "❌ Pods not ready: $READY/$REPLICAS ready, $UPDATED updated (may need time to start)"; ((ERRORS++))
else
    echo "✅ $READY/$REPLICAS pods ready"
fi

echo ""
echo "================================"
if [ $ERRORS -eq 0 ]; then
    echo "🎉🎉🎉 SUCCESS! 🎉🎉🎉"
    echo ""
    echo "YOU'VE CONQUERED THE CHAOS FINALE!"
    echo ""
    echo "All World 5 concepts mastered:"
    echo "  ✅ RBAC"
    echo "  ✅ SecurityContext"
    echo "  ✅ ResourceQuota"
    echo "  ✅ NetworkPolicy"
    echo "  ✅ Node Affinity"
    echo "  ✅ Taints & Tolerations"
    echo "  ✅ PodDisruptionBudget"
    echo "  ✅ Pod Security Standards"
    echo "  ✅ PriorityClass"
    echo ""
    echo "🏆 WORLD 5 COMPLETE! 🏆"
    echo ""
    echo "THE STORM HAS PASSED! 🌈"
    echo "================================"
else
    echo "❌ $ERRORS issue(s) found"
    echo "Keep fixing! You're almost there!"
    echo "================================"
    exit 1
fi
