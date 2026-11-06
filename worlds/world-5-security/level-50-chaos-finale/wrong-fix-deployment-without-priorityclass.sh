#!/bin/bash
# Bypass: apply the full solution, then drop priorityClassName from the Deployment (the PriorityClass itself stays), so check 4 (PriorityClass) is the only one that fails
kubectl apply -f solution.yaml || exit 1
kubectl patch deployment chaos-app -n k8squest --type=json -p '[{"op":"remove","path":"/spec/template/spec/priorityClassName"}]' || exit 1
