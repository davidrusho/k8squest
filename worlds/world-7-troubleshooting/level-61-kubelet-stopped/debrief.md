# 🎓 LEVEL 61 DEBRIEF: A Worker That Went Quiet

**Congratulations!** You found a node that was NotReady because its kubelet was not running, and brought it back for good.

---

## 📊 What Happened

The kubelet on `k8squest-multinode-worker` had been stopped and disabled. The kubelet is the node agent: it reports the node's health to the API server. Once those reports stopped, the node controller set the node's `Ready` condition to `Unknown` and added the `node.kubernetes.io/unreachable` taint. The `inventory` pods were pinned to that node with a `nodeSelector`, and the scheduler does not place pods on a node with an untolerated taint, so they stayed `Pending`.

## 🔧 The Fix

On the node (`docker exec -it k8squest-multinode-worker bash`):

```bash
systemctl status kubelet            # inactive (dead)
systemctl is-enabled kubelet        # disabled
systemctl enable --now kubelet      # start now AND at every boot
```

`systemctl start` alone would have passed the first check and failed the second: the node would have come back, then vanished again at the next reboot.

## 🎯 Key Takeaways

1. A NotReady node is almost always a node-side problem. `kubectl describe node` gives the condition and the taints; the cause is on the node.
2. The unreachable taint is why the pods are Pending: scheduling looks at taints, and the workload itself was fine.
3. Pods already running on an unreachable node are not removed at once. The documented default is to wait five minutes before evicting them.
4. `systemctl start` and `systemctl enable` are different things. Use `enable --now` when you mean both.
5. On kind, a node is a Docker container: `docker exec -it <node> bash` is your "SSH to the node". It has `systemctl`, `journalctl` and `crictl`.

## 📚 Official Docs

- [Debugging Kubernetes clusters: a down/unreachable node](https://kubernetes.io/docs/tasks/debug/debug-cluster/#example-debugging-a-down-unreachable-node)
- [Nodes: node status and heartbeats](https://kubernetes.io/docs/concepts/architecture/nodes/)
- [Taints and tolerations: taint based evictions](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
- [kind quick start: working with a node (docker exec)](https://kind.sigs.k8s.io/docs/user/quick-start/)

## 🚀 Next

**Level 62:** the kubelet is running, then exiting again and again. Why?
