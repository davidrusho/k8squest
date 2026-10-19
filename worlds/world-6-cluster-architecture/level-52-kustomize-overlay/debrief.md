# 🎓 LEVEL 52 DEBRIEF: Kustomize - The Overlay That Did Nothing

**Congratulations!** You found a patch that was silently skipped.

---

## 📊 What Happened

The overlay's patch carried a `target` selector naming `shop-web-prod`. No resource in
the base has that name, so Kustomize skipped the patch and rendered the base values
(`replicas: 1`, `LOG_LEVEL=debug`). `kubectl apply -k` applied exactly what was rendered.

## 🔧 The Fix

```yaml
patches:
- path: replicas-and-logging.yaml
  target:
    kind: Deployment
    name: shop-web
```

```bash
cd "$HOME/.k8squest/work/level-52-kustomize-overlay"
kubectl kustomize kustomize/overlays/prod     # always read the render first
kubectl apply -k kustomize/overlays/prod
```

## 🎯 Key Takeaways

1. A base is a directory with a `kustomization.yaml`; an overlay refers to it and customizes it.
2. `kubectl kustomize <dir>` shows the result without touching the cluster; `kubectl apply -k <dir>` applies it.
3. A patch `target` selects by group, version, kind, name, namespace and selectors. A target that matches nothing is skipped without an error.
4. When an overlay "does nothing", diff the render against the base before debugging the cluster.

## 📚 Official Docs

- [Declarative Management of Kubernetes Objects Using Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)

## 🚀 Next

**Level 53:** CustomResourceDefinitions.
