# 🎓 LEVEL 57 DEBRIEF: VPA - The Autoscaler Watching Nothing

**Congratulations!** You pointed a VerticalPodAutoscaler at the workload it was meant to watch.

---

## 📊 What Happened

`hamster-vpa` had `targetRef.name: hamster-app`, but the Deployment is called `hamster`.
A VPA takes its pod set from its target controller, so it matched no pods and the
recommender never produced a recommendation.

## 🔧 The Fix

```yaml
targetRef:
  apiVersion: apps/v1
  kind: Deployment
  name: hamster
```

## 🎯 Key Takeaways

1. HPA changes how many pods run; VPA recommends (or sets) how much CPU and memory each pod requests.
2. A VPA is built from three components: recommender, updater and admission controller.
3. `updateMode: "Off"` only publishes recommendations in `status.recommendation`; other modes evict or recreate pods to apply them.
4. `targetRef` identifies the controller whose pods are managed; a wrong one means nothing is measured.
5. VPA needs metrics-server in the cluster.
6. Do not point an HPA and a VPA at the same CPU or memory metric.

## 📚 Official Docs

- [Kubernetes: Vertical Pod Autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/vertical-pod-autoscale/)
- [VPA installation](https://github.com/kubernetes/autoscaler/blob/vertical-pod-autoscaler-1.8.0/vertical-pod-autoscaler/docs/installation.md)
- [VPA API reference](https://github.com/kubernetes/autoscaler/blob/vertical-pod-autoscaler-1.8.0/vertical-pod-autoscaler/docs/api.md)

## 🚀 Next

**Level 58:** ServiceAccount RBAC.
