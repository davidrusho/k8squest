# 🎓 LEVEL 64 DEBRIEF: A Deployment That Creates Nothing

**Congratulations!** You told "no pods" apart from "Pending pods" and repaired the component that creates them.

---

## 📊 What Happened

The image in the `kube-controller-manager` static pod manifest was changed to a tag that does not exist (`v1.73.0`). The kubelet could not pull it, so the pod sat in ImagePullBackOff. The controller manager runs the Deployment controller (Deployment -> ReplicaSet) and the ReplicaSet controller (ReplicaSet -> pods), among others. With it down, the `orders` Deployment object existed but nobody acted on it: no ReplicaSet, no pods, not even Pending ones.

## 🔧 The Fix

```bash
kubectl describe pod -n kube-system kube-controller-manager-k8squest-multinode-control-plane
#   Failed to pull image "registry.k8s.io/kube-controller-manager:v1.73.0": ... not found
docker exec -it k8squest-multinode-control-plane bash
vi /etc/kubernetes/manifests/kube-controller-manager.yaml     # image: ...:v1.37.0
```

## 🎯 Key Takeaways

1. Compare level 63 and 64. A missing scheduler leaves pods that exist but are unassigned. A missing controller manager leaves objects nobody acts on at all. Which objects are missing tells you which component is down.
2. A container that never started has no log. `kubectl describe pod` and its Events are the evidence for ImagePullBackOff, on a system pod as much as on yours.
3. The controller manager is one binary running many controllers, among them the node controller, which you met in level 61.
4. Control-plane images follow the cluster version. Another static pod manifest on the same node shows the right tag (`grep image: /etc/kubernetes/manifests/*.yaml`).
5. Running pods are unaffected by a dead controller manager. Self-healing (replacing a pod that dies) is what stops.

## 📚 Official Docs

- [Kubernetes components](https://kubernetes.io/docs/concepts/overview/components/)
- [Cluster architecture: controllers](https://kubernetes.io/docs/concepts/architecture/controller/)
- [Create static Pods](https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/)
- [Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)

## 🚀 Next

**Level 65:** the API server itself stops answering, and `kubectl` cannot help you.
