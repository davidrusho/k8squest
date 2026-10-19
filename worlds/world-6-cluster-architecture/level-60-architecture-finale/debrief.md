# 🎓 LEVEL 60 DEBRIEF: FINALE - The Platform Handover

**Congratulations!** You finished World 6: three independent faults, found from three different status surfaces.

---

## 📊 What Was Wrong

| Component | Symptom | Where the evidence was | Fault |
|-----------|---------|------------------------|-------|
| cert-manager | Certificate never Ready | `describe certificate`, CertificateRequest | `issuerRef.name` pointed at an Issuer that does not exist |
| Gateway API | Route not attached | HTTPRoute `status.parents` | `sectionName: https`, but the Gateway only has the listener `http` |
| RBAC | `403` from the API | pod logs, `kubectl auth can-i` | Role `resources: ["configmap"]` is not a real resource name, so it granted nothing |

## 🎯 World 6 in Short

1. **Helm** keeps a revision history; recover with `helm rollback` or a corrected `helm upgrade`.
2. **Kustomize** patches select resources by target; a target that matches nothing is skipped silently.
3. **CRDs** validate custom resources with an OpenAPI schema.
4. **cert-manager** certificates need a resolvable `issuerRef` (name and kind).
5. **Gateway API** routes attach with `parentRefs` and need ReferenceGrants to cross namespaces.
6. **VPA** needs a `targetRef` that resolves to a real controller.
7. **RBAC** subjects and rules must name exactly the identity and resources in play.
8. **CRI and CSI** objects (RuntimeClass, StorageClass) must name components the cluster really has.

## 📚 Official Docs

- [Kubernetes documentation](https://kubernetes.io/docs/)
- [Helm documentation](https://helm.sh/docs/)
- [Gateway API](https://gateway-api.sigs.k8s.io/)
- [cert-manager](https://cert-manager.io/docs/)

The Linux Foundation lists kubernetes.io/docs, the Kubernetes blog, helm.sh/docs and (CKA only) gateway-api.sigs.k8s.io as the documentation available during the CKA exam. cert-manager is not on that list and is outside the CKA curriculum: it is in this world as a common example of an operator that ships CRDs.

## 🚀 What's Next

World 7 (troubleshooting on multi-node clusters) and World 8 (kubeadm on Lima VMs) are in progress.
