# 🎓 LEVEL 58 DEBRIEF: RBAC - The Binding That Binds Nobody

**Congratulations!** You found a binding that existed but pointed at the wrong identity.

---

## 📊 What Happened

The RoleBinding's subject was `reports-sa` in the `default` namespace. The pod runs as
`reports-sa` in `k8squest`, which is a different identity (`system:serviceaccount:k8squest:reports-sa`),
so the API server answered every call with `403 Forbidden`.

## 🔧 The Fix

```yaml
subjects:
- kind: ServiceAccount
  name: reports-sa
  namespace: k8squest
```

## 🎯 Key Takeaways

1. A ServiceAccount subject is `name` plus `namespace`; the same name in another namespace is another identity.
2. `kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<ns>:<name>` tests an identity from the outside.
3. A RoleBinding grants permissions only inside its own namespace.
4. A RoleBinding's `roleRef` cannot be changed after creation; its `subjects` can.
5. Fix the narrowest thing: binding the account to `cluster-admin` would also make the pod "work".

## 📚 Official Docs

- [Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Configure Service Accounts for Pods](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/)

## 🚀 Next

**Level 59:** Cluster extension interfaces (CRI and CSI).
