#!/bin/bash
# Bypass: apply the full solution, then delete the allow-app NetworkPolicy so deny-all still blocks the app, so check 3 (NetworkPolicy) is the only one that fails
kubectl apply -f solution.yaml || exit 1
kubectl delete networkpolicy allow-app -n k8squest || exit 1
