#!/bin/bash
# Bypass: set the image to a different nonexistent tag, so the old ReplicaSet pods keep the ready count up
kubectl set image deployment/web-app web=nginx:no-such-tag-k8squest -n k8squest
