# 🎓 LEVEL 73 DEBRIEF: Join the Worker

**Congratulations!** You added a worker to a kubeadm cluster with a token you created yourself, and checked the cluster's identity while you did it.

---

## 📊 What Happened

`kubeadm join` needs two things from you, and they answer two different questions:

- **A bootstrap token** (`<id>.<secret>`) says to the cluster: this machine is allowed to ask to join. Tokens expire after 24 hours by default, which is why the one `kubeadm init` printed was useless by the time you needed it.
- **The CA certificate hash** (`--discovery-token-ca-cert-hash sha256:...`) says to the machine: the API server I am talking to belongs to the right cluster. The joining node downloads the cluster information over a connection it cannot yet verify, and the hash is what lets it check the CA in that information before it trusts anything else.

`kubeadm token create --print-join-command` prints both in one line, ready to paste. On the worker, `kubeadm join` fetched the cluster information, started the kubelet with a bootstrap credential, and the kubelet requested its own long-term client certificate. A few seconds later the node object appeared, the kube-proxy and Flannel DaemonSets scheduled their pods onto it, and it turned Ready.

## 🔧 The Fix

```bash
# on k8squest-cp
sudo kubeadm token list                              # nothing
sudo kubeadm token create --print-join-command
#   kubeadm join <control-plane-ip>:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>

# on k8squest-worker, with sudo
sudo kubeadm join <control-plane-ip>:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>

kubectl get nodes -w                                 # both Ready
```

## 🎯 Key Takeaways

1. The documentation: "By default, node join tokens expire after 24 hours." A new one is one command away.
2. The hash can be recomputed from the CA at any time: `openssl x509 -pubkey -in /etc/kubernetes/pki/ca.crt | openssl rsa -pubin -outform der 2>/dev/null | openssl dgst -sha256 -hex | sed 's/^.* //'`.
3. `--discovery-token-unsafe-skip-ca-verification` makes the join work without the hash, and gives up the check that you are joining the right cluster. kubeadm's own reference tells you to consider that carefully.
4. A node is ready for work only when the kubelet is running **and** the pod network reached it. A worker that has just joined is NotReady for a short while; its Flannel pod is what finishes the job.
5. Anyone who holds a valid token can add a node to your cluster. Tokens are secrets; delete the ones you do not need (`kubeadm token delete`).

## 📚 Official Docs

- [Adding Linux worker nodes](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/adding-linux-nodes/)
- [kubeadm join: discovery, tokens and the CA hash](https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-join/)
- [kubeadm token](https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-token/)

## 🚀 Next

**Level 74:** a cluster at Kubernetes v1.36 and a minor upgrade to do, in the right order, without losing the workload.
