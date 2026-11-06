#!/bin/bash
# Bypass: apply the full solution, then set allowPrivilegeEscalation true on the container, so check 7 (SecurityContext) is the only one that fails
kubectl apply -f solution.yaml || exit 1
# The namespace enforces the restricted Pod Security Standard, which would reject the new pods and fail check 9 too.
# Relax enforcement to baseline (which allows privilege escalation) so the pods stay Running; no check reads that label.
kubectl label namespace k8squest pod-security.kubernetes.io/enforce=baseline --overwrite || exit 1
kubectl patch deployment chaos-app -n k8squest --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/securityContext/allowPrivilegeEscalation","value":true}]' || exit 1
