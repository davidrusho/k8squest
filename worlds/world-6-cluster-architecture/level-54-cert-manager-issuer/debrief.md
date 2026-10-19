# 🎓 LEVEL 54 DEBRIEF: cert-manager - The Certificate That Never Gets Ready

**Congratulations!** You traced a stuck Certificate back to its issuerRef.

---

## 📊 What Happened

`web-cert` named `kind: ClusterIssuer`, but the only issuer was a namespaced `Issuer`
called `selfsigned-issuer`. cert-manager looked for a ClusterIssuer with that name,
found nothing, and the Certificate stayed not Ready, so no TLS Secret was written.

## 🔧 The Fix

```yaml
issuerRef:
  name: selfsigned-issuer
  kind: Issuer
```

## 🎯 Key Takeaways

1. cert-manager adds `Issuer`, `ClusterIssuer`, `Certificate`, `CertificateRequest` and more as CRDs.
2. An `Issuer` is namespaced and cannot be used across namespaces; a `ClusterIssuer` is not namespaced.
3. `issuerRef` needs the right `name` and the right `kind`.
4. Debug in order: Certificate, CertificateRequest, issuer, events.
5. A `SelfSigned` issuer is useful for bootstrapping a private PKI, not for public trust.

## 📚 Official Docs

- [cert-manager: Certificate resource](https://cert-manager.io/docs/usage/certificate/)
- [cert-manager: Issuers](https://cert-manager.io/docs/concepts/issuer/)
- [cert-manager: SelfSigned](https://cert-manager.io/docs/configuration/selfsigned/)

## 🚀 Next

**Level 55:** Gateway API HTTPRoute.
