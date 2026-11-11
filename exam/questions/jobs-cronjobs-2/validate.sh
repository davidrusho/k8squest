#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

C=$(kubectl get cronjob backup -n "$NS" -o json 2>/dev/null)
[[ -n "$C" ]] || fail "cronjob backup does not exist in namespace $NS"
GOT=$(echo "$C" | jq -cS '.spec.schedule')
[[ "$GOT" == '"*/5 * * * *"' ]] || fail "schedule is $GOT, expected "'"*/5 * * * *"'
GOT=$(echo "$C" | jq -cS '.spec.jobTemplate.spec.template.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"busybox"' ]] || fail "image is $GOT, expected "'"busybox"'
CMD=$(echo "$C" | jq -r '.spec.jobTemplate.spec.template.spec.containers[0] | ((.command // []) + (.args // [])) | join(" ")')
case "$CMD" in
  "date"|"/bin/sh -c date"|"sh -c date"|"/bin/sh -c date;") ;;
  *) fail "command is '$CMD', expected date" ;;
esac
echo "✅ CronJob backup runs date every 5 minutes"
exit 0
