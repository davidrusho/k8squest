# 🎓 LEVEL 56 DEBRIEF: ReferenceGrant - Crossing the Namespace Line

**Congratulations!** You fixed a cross-namespace reference by editing the right side of the grant.

---

## 📊 What Happened

A ReferenceGrant existed in `k8squest-backend`, but its `from.namespace` said `default`.
The route lives in `k8squest`, so the grant did not cover it and the route's
`ResolvedRefs` condition stayed `False` with reason `RefNotPermitted`.

## 🔧 The Fix

```yaml
from:
- group: gateway.networking.k8s.io
  kind: HTTPRoute
  namespace: k8squest
```

## 🎯 Key Takeaways

1. A route may forward traffic to a backend in another namespace only if a ReferenceGrant allows it.
2. The grant is created in the namespace of the **target** (here the Service), by the team that owns it.
3. `from` names the referrer's group, kind and namespace; `to` names the target's group and kind.
4. `RefNotPermitted` on `ResolvedRefs` is the signature of a missing or non-matching grant.
5. Gateways may also refer to Secrets in other namespaces, and use the same mechanism.

## 📚 Official Docs

- [Gateway API: ReferenceGrant](https://gateway-api.sigs.k8s.io/reference/api-types/referencegrant/)

## 🚀 Next

**Level 57:** Vertical Pod Autoscaler.
