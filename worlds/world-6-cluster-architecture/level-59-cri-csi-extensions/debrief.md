# 🎓 LEVEL 59 DEBRIEF: CRI and CSI - Extensions That Point at Nothing

**Congratulations!** You matched two extension objects to components that really exist.

---

## 📊 What Happened

1. The `fast-local` StorageClass named a provisioner (`csi.fastdisk.example.com`) that is not installed, so the PVC stayed `Pending` and the pod, waiting for its volume, never started.
2. Once storage worked, the pod was scheduled but its sandbox failed: the `sandboxed` RuntimeClass named a handler (`runsc`) that kind's containerd does not have (`no runtime for "runsc" is configured`).

## 🔧 The Fix

```yaml
handler: runc                         # RuntimeClass
provisioner: rancher.io/local-path    # StorageClass
```

Both fields are immutable, so the objects are deleted and recreated.

## 🎯 Key Takeaways

1. Kubernetes talks to pluggable interfaces: **CRI** (container runtime), **CNI** (networking), **CSI** (storage).
2. A `RuntimeClass` is a name plus a `handler`; the handler must exist in the node's CRI runtime configuration.
3. A `StorageClass` names the `provisioner` that creates volumes; with `WaitForFirstConsumer` binding happens when a pod is scheduled.
4. Read events on the PVC for storage problems and on the pod for runtime problems; they appear at different stages.
5. Discover what a cluster provides before copying manifests from another one.

## 📚 Official Docs

- [Runtime Class](https://kubernetes.io/docs/concepts/containers/runtime-class/)
- [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [Extending Kubernetes](https://kubernetes.io/docs/concepts/extend-kubernetes/)

## 🚀 Next

**Level 60:** The World 6 finale.
