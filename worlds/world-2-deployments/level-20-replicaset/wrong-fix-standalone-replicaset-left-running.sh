#!/bin/bash
# Bypass: create the Deployment but leave the old standalone ReplicaSet running its own pods
kubectl apply -f solution.yaml || exit 1
