Add `tolerations:` under the Pod's `spec:` (key dedicated, operator Equal, value gpu, effect NoSchedule). A Pod without it stays Pending with an untolerated-taint event in `k describe`.
