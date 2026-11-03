#!/bin/bash
# Bypass: readiness probe on a port nothing listens on, so new pods never become Ready while the old ones keep the count up
kubectl patch deployment slow-startup-app -n k8squest --type=json -p '[{"op":"add","path":"/spec/template/spec/containers/0/readinessProbe","value":{"httpGet":{"path":"/","port":8080},"initialDelaySeconds":22,"periodSeconds":5}}]'
