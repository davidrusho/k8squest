# 🎓 LEVEL 75 DEBRIEF: Lose the Ledger, Restore etcd

**Congratulations!** You saved a snapshot of a live cluster's data store, deleted the application it protected, and brought the application back by restoring etcd.

---

## 📊 What Happened

etcd holds every object in the cluster. A snapshot is a single file containing all of it at one moment, and a restore turns that file back into a data directory.

1. **The snapshot.** `etcdctl snapshot save` talks to the running etcd over TLS, so it needs the endpoint and the three certificate paths, which the etcd static pod's manifest lists. `etcdutl snapshot status` then read the file itself and reported its hash, revision and key count. (The documentation marks `etcdctl snapshot status` as deprecated in favour of `etcdutl`.)
2. **The accident.** Deleting the Deployment and ConfigMap removed their keys from etcd. Nothing about that is recoverable from inside Kubernetes.
3. **The restore.** The documentation's caution: if any API servers are running, do not restore; "stop all API server instances, restore state in all etcd instances, restart all API server instances". Both are static pods, so moving their manifests out of `/etc/kubernetes/manifests` stops them. `etcdutl snapshot restore --data-dir /var/lib/etcd-restored` wrote a fresh data directory, and changing the `etcd-data` volume's `hostPath` in `etcd.yaml` made etcd use it. When the manifests came back, the API server read the old state: the Deployment with its original UID, and the ConfigMap.

A restore gives the member a new identity: the etcd cluster ID differs from before. That is why the check can tell a real restore from re-creating the objects by hand.

## 🔧 The Fix

```bash
limactl shell k8squest-cp
sudo -i
export KUBECONFIG=/etc/kubernetes/admin.conf
E="--endpoints=https://127.0.0.1:2379 --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/server.crt --key=/etc/kubernetes/pki/etcd/server.key"

etcdctl $E snapshot save /var/backups/etcd/k8squest-snapshot.db
etcdutl snapshot status /var/backups/etcd/k8squest-snapshot.db -w table

kubectl -n k8squest delete deployment ledger
kubectl -n k8squest delete configmap ledger-config

mkdir /root/parked
mv /etc/kubernetes/manifests/kube-apiserver.yaml /etc/kubernetes/manifests/etcd.yaml /root/parked/
crictl ps                                    # wait until etcd and kube-apiserver are gone
etcdutl --data-dir /var/lib/etcd-restored snapshot restore /var/backups/etcd/k8squest-snapshot.db
sed -i 's|path: /var/lib/etcd$|path: /var/lib/etcd-restored|' /root/parked/etcd.yaml
mv /root/parked/etcd.yaml /root/parked/kube-apiserver.yaml /etc/kubernetes/manifests/
kubectl get deployment,cm -n k8squest
```

## 🎯 Key Takeaways

1. A backup you have not restored is a hope. This is the whole drill, in a lab, with nothing to lose.
2. `etcdctl` is a client of a running etcd; `etcdutl` works on files. Saving needs the former, checking and restoring need the latter.
3. Restore into a new directory and point etcd at it. The alternative is to delete the old data directory first and restore into the same path; both are in the documentation.
4. A restore rolls the whole cluster back to the snapshot's moment. Anything created after the snapshot is gone, and the kubelets reconcile to the restored state.
5. A kubeadm control plane runs from static pod manifests, so "stop etcd" means "move its manifest" rather than `systemctl stop`.
6. Keep snapshots off the machine they protect. This level stores one on the control plane only because it is a lab.

## 📚 Official Docs

- [Operating etcd clusters for Kubernetes: backing up and restoring](https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd/#backing-up-an-etcd-cluster)
- [etcd disaster recovery](https://etcd.io/docs/current/op-guide/recovery/)
- [etcdutl](https://github.com/etcd-io/etcd/blob/main/etcdutl/README.md)

## 🚀 Next

**Level 76 (the finale):** take the worker out of service for maintenance without taking the application down.
