# 🎓 LEVEL 69 DEBRIEF: The Crash You Can Only Read Afterwards

**Congratulations!** You asked for the right container and the right instance, and the log told you what to fix.

---

## 📊 What Happened

The `invoice-api` container exited on start-up with `FATAL: DB_HOST is not set`, because the ConfigMap it takes its environment from (`envFrom`) defined `DB_HOTS`. `kubectl logs deploy/invoice-api` answered with the healthy `log-shipper` sidecar (it prints "Defaulted container ... out of: ..."), and the crashed container's output was only available by naming the container and asking for the previous instance:

```bash
kubectl logs <pod> -n k8squest -c invoice-api --previous
```

## 🔧 The Fix

```bash
kubectl edit configmap invoice-config -n k8squest         # DB_HOTS -> DB_HOST
kubectl rollout restart deployment/invoice-api -n k8squest
```

Environment variables from a ConfigMap are read when a container starts, so the pods need a restart.

## 🎯 Key Takeaways

1. In a multi-container pod, `kubectl logs` picks a container for you. Always name it with `-c` when the pod has more than one, and list them with `kubectl get pod -o jsonpath='{.spec.containers[*].name}'`.
2. `--previous` (`-p`) prints the logs of the previous instance of the container. After a crash that is where the cause is. The kubelet keeps one terminated container and its logs by default.
3. `kubectl describe pod` shows `Last State: Terminated` with an exit code and reason, and the `Environment Variables from` section tells you where the configuration comes from.
4. The Kubernetes documentation says ConfigMaps consumed as environment variables "are not updated automatically and require a pod restart".
5. A container in CrashLoopBackOff retries with a growing delay. A `rollout restart` creates a fresh pod and skips the wait.

## 📚 Official Docs

- [Logging architecture](https://kubernetes.io/docs/concepts/cluster-administration/logging/)
- [Debug Running Pods: examine pod logs](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)
- [kubectl logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/)
- [ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)

## 🚀 Next

**Level 70 (finale):** back up etcd, then handle a worker that is gone.
