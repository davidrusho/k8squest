# 🎓 LEVEL 55 DEBRIEF: Gateway API - The Route Nobody Accepts

**Congratulations!** You read an HTTPRoute's status and fixed both of its references.

---

## 📊 What Happened

- `parentRefs` named `web-gateway`, but the Gateway is `web-gw`, so no Gateway claimed the route and its `status.parents` stayed empty.
- `backendRefs` used port `8080`, but the `echo` Service exposes port `80`, so once the route was attached the backend could not be resolved (`ResolvedRefs=False`, reason `PortNotFound`, which is Envoy Gateway's reason, not one defined by the Gateway API standard).

## 🔧 The Fix

```yaml
parentRefs:
- name: web-gw
rules:
- backendRefs:
  - name: echo
    port: 80
```

## 🎯 Key Takeaways

1. Gateway API splits roles: GatewayClass (infrastructure provider), Gateway (listeners), routes (app owners).
2. `parentRefs` attaches a route to a Gateway; `backendRefs` points at the Services that receive traffic.
3. Status lives per parent: look for `Accepted` and `ResolvedRefs` under `status.parents[].conditions`.
4. A Gateway's `allowedRoutes` limits which namespaces may attach routes (default: the Gateway's own namespace).
5. Gateway API supersedes Ingress for new work and is part of the CKA Services & Networking domain.

## 📚 Official Docs

- [Gateway API: HTTPRoute](https://gateway-api.sigs.k8s.io/reference/api-types/httproute/)
- [Gateway API: Gateway](https://gateway-api.sigs.k8s.io/reference/api-types/gateway/)
- [Kubernetes: Gateway API](https://kubernetes.io/docs/concepts/services-networking/gateway/)

## 🚀 Next

**Level 56:** ReferenceGrant.
