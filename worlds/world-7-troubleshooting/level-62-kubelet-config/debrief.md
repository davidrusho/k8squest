# 🎓 LEVEL 62 DEBRIEF: The Kubelet That Keeps Dying

**Congratulations!** You read the reason from the kubelet's own log and repaired its configuration file.

---

## 📊 What Happened

`authentication.x509.clientCAFile` in `/var/lib/kubelet/config.yaml` on `k8squest-multinode-worker2` named a file that does not exist (`ca.crtt`). The kubelet read its configuration at start-up, could not open the file and exited; systemd restarted it a second later, and the same thing happened again. `systemctl status kubelet` showed `activating (auto-restart)` rather than `inactive (dead)`, which is the difference between a service that was stopped and one that keeps failing.

## 🔧 The Fix

```bash
journalctl -u kubelet --no-pager -n 20      # failed to run Kubelet: open /etc/kubernetes/pki/ca.crtt: no such file or directory
vi /var/lib/kubelet/config.yaml              # clientCAFile: /etc/kubernetes/pki/ca.crt
systemctl restart kubelet
```

## 🎯 Key Takeaways

1. `journalctl -u kubelet` is the first stop for a kubelet that will not stay up; the error names the file or flag.
2. On a kubeadm-style node the kubelet reads `/var/lib/kubelet/config.yaml` (passed with `--config`), extra flags from `/var/lib/kubelet/kubeadm-flags.env`, and user overrides from `/etc/default/kubelet`. `systemctl cat kubelet` shows how the unit wires them together.
3. The configuration file is read at start-up. Editing it does nothing until the kubelet is restarted.
4. kubeadm also uploads the kubelet configuration to the `kubelet-config` ConfigMap in `kube-system`, which is the reference to compare a node's file against.
5. Pods already running on the node are not touched by a crash-looping kubelet. What suffers is reporting and anything new.

## 📚 Official Docs

- [Set Kubelet parameters via a config file](https://kubernetes.io/docs/tasks/administer-cluster/kubelet-config-file/)
- [Configuring each kubelet in your cluster using kubeadm](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/kubelet-integration/)
- [Troubleshooting kubeadm](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/troubleshooting-kubeadm/)

## 🚀 Next

**Level 63:** pods with no node and no events. Nobody is scheduling them.
