# 🎓 LEVEL 53 DEBRIEF: CRD - The Schema That Rejects Everything

**Congratulations!** You diagnosed a validation failure at the API server.

---

## 📊 What Happened

The CRD declared `spec.replicas` as `type: string`. The Website in `website.yaml` sent the
integer `3`, so the API server answered with a validation error such as
`spec.replicas: Invalid value: "integer": spec.replicas in body must be of type string`.
No controller was involved: the CRD's schema alone accepts or rejects custom resources.

## 🔧 The Fix

```yaml
replicas:
  type: integer
  minimum: 1
  maximum: 10
```

## 🎯 Key Takeaways

1. A CRD adds a new API type; its `openAPIV3Schema` validates every instance.
2. With `apiextensions.k8s.io/v1` a structural schema is mandatory.
3. `kubectl explain <kind>.spec.<field>` reads the schema from the cluster.
4. Constraints such as `minimum`, `maximum`, `enum` and `required` are enforced on create and update.
5. Existing objects are not re-validated when a CRD changes, so fix schemas before adoption.

## 📚 Official Docs

- [Extend the Kubernetes API with CustomResourceDefinitions](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/)

## 🚀 Next

**Level 54:** cert-manager Issuers.
