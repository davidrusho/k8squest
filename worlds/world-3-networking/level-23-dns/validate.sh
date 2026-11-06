#!/bin/bash

# The client pod must be running
PHASE=$(kubectl get pod app-client -n k8squest -o jsonpath='{.status.phase}' 2>/dev/null)
if [[ "$PHASE" != "Running" ]]; then
  echo "❌ app-client is not Running (phase: ${PHASE:-missing})"
  exit 1
fi

# Which host does the client pod's own connection check use? (pg_isready -h <host>, also -hHOST, --host HOST, --host=HOST)
# The pod spec is printed as JSON, so quotes arrive escaped (\"host\") and a command list is comma-separated:
# drop quotes and backslashes, and turn , [ ] into spaces first.
CMDLINE=$(kubectl get pod app-client -n k8squest -o jsonpath='{.spec.containers[0].command} {.spec.containers[0].args}' 2>/dev/null | tr -d "\\\\\"'" | tr ',[]' '   ')
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

# DNS names are case-insensitive
HOST=$(echo "$HOST" | tr 'A-Z' 'a-z')

# The level is about Service DNS names: an IP literal "resolves" to itself without DNS at all
if [[ "$HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\.?$ ]]; then
  echo "❌ The client connects to the IP address '$HOST', which skips DNS"
  echo "💡 Use the Service name instead (kubectl get svc -n k8squest)"
  exit 1
fi

# hostAliases writes the name into the pod's /etc/hosts, so getent never asks cluster DNS
if [[ -n "$(kubectl get pod app-client -n k8squest -o jsonpath='{.spec.hostAliases}' 2>/dev/null)" ]]; then
  echo "❌ The client pod defines hostAliases, so '$HOST' is answered from /etc/hosts, not cluster DNS"
  echo "💡 Remove hostAliases and make the name resolve through a Service"
  exit 1
fi

# HOST must name a Service in k8squest: <svc>, <svc>.k8squest, <svc>.k8squest.svc or <svc>.k8squest.svc.cluster.local
NAME="${HOST%.}"
SVC="${NAME%%.*}"
if [[ "$NAME" == *.* ]]; then
  case "${NAME#*.}" in
    k8squest|k8squest.svc|k8squest.svc.cluster.local) ;;
    *)
      echo "❌ '$HOST' is not a Service name in the k8squest namespace"
      echo "💡 Use <service> or <service>.k8squest.svc.cluster.local"
      exit 1
      ;;
  esac
fi
if ! kubectl get svc "$SVC" -n k8squest >/dev/null 2>&1; then
  echo "❌ There is no Service named '$SVC' in the k8squest namespace"
  echo "💡 kubectl get svc -n k8squest"
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
