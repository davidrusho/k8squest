#!/bin/bash

# The client pod must be running
PHASE=$(kubectl get pod app-client -n k8squest -o jsonpath='{.status.phase}' 2>/dev/null)
if [[ "$PHASE" != "Running" ]]; then
  echo "❌ app-client is not Running (phase: ${PHASE:-missing})"
  exit 1
fi

# Which host does the client pod's own connection check use? (pg_isready -h <host>, also -hHOST, --host HOST, --host=HOST)
# The pod spec is printed as JSON, so quotes arrive escaped (\"host\"): drop quotes and backslashes first.
CMDLINE=$(kubectl get pod app-client -n k8squest -o jsonpath='{.spec.containers[0].command} {.spec.containers[0].args}' 2>/dev/null | tr -d "\\\"'")
CHECK=$(echo "$CMDLINE" | grep -oE 'pg_isready[^|;&]*' | head -1)
HOST=$(echo "$CHECK" | grep -oE ' (-h|--host)[ =]*[A-Za-z0-9._-]+' | head -1 | sed -E 's/^ (-h|--host)[ =]*//')

if [[ -z "$HOST" ]]; then
  if [[ "$CHECK" == *'$'* ]]; then
    echo "❌ The connection check takes its host from a variable ($CHECK)"
    echo "💡 Write the Service name directly after -h so it can be checked"
  else
    echo "❌ The client pod does not run a pg_isready connection check against a host"
  fi
  exit 1
fi

# Runtime proof, from inside the client pod: the name it uses must resolve through cluster DNS
# and the database must accept a connection on it (a pod that only prints the success line cannot do this)
if ! kubectl exec app-client -n k8squest -- getent hosts "$HOST" >/dev/null 2>&1; then
  echo "❌ DNS resolution failing. '$HOST' does not resolve from the client pod"
  echo "Hint: Service is named 'database-service', not 'database'"
  exit 1
fi

if kubectl exec app-client -n k8squest -- pg_isready -h "$HOST" -p 5432 2>&1 | grep -q "accepting connections"; then
  echo "✅ Level complete! DNS resolution working"
  echo "   Client resolved '$HOST' and the database accepted a connection"
  exit 0
else
  echo "❌ '$HOST' resolves but the database is not accepting connections yet"
  exit 1
fi
