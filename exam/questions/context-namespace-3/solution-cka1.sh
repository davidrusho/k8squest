#!/bin/bash
# node: cka1
# Runs as user cka1 on k8s-lab.
kubectl config use-context cluster1
kubectl config current-context > ~/cluster1-confirm.txt
kubectl get configmap ctx-marker -n default -o jsonpath='{.data.token}' >> ~/cluster1-confirm.txt
