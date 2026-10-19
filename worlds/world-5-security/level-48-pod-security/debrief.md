# 🎓 LEVEL 48 DEBRIEF: Pod Security Standards

**Congratulations!** You've mastered Pod Security Standards!

---

## Pod Security Standards

Three levels of security enforcement:

### 1. Privileged (Unrestricted)
No restrictions - use with caution!

### 2. Baseline (Minimal)
Prevents known privilege escalations:
- No privileged containers
- No host path volumes
- No host networking

### 3. Restricted (Hardened)
Security best practices (what you just implemented):
- ✅ runAsNonRoot: true
- ✅ allowPrivilegeEscalation: false
- ✅ capabilities dropped
- ✅ seccompProfile
- ✅ Non-root user

---

## Namespace Labels

```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

- **enforce**: Blocks non-compliant pods
- **audit**: Logs violations
- **warn**: Warns users

### Where you see the rejection

Enforce mode is applied to Pods, not to workload objects such as a Deployment. So the
Deployment is accepted (audit and warn modes do check it, so `kubectl apply` printed a
warning), and the ReplicaSet's attempt to create each Pod is rejected. The failure appears as a
`FailedCreate` event on the ReplicaSet, not at apply time:

```bash
kubectl describe rs -n k8squest
kubectl get events -n k8squest
```

A bare Pod applied directly would be rejected immediately by `kubectl apply`.

---

## Key Takeaways

1. **Restricted = most secure** - use in production
2. **Requires complete SecurityContext** - all fields
3. **Enforced at admission** - pods rejected if non-compliant
4. **Best practice** - always run as non-root
5. **Defense in depth** - layer with NetworkPolicy, RBAC

---

## Next Steps

- **Level 49:** PriorityClass
- **Level 50:** CHAOS FINALE!

**Excellent work!** 🎉🔒
