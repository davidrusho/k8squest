kubectl create svc nodeport takes --node-port to pin the node port; without it one is allocated from 30000-32767. Check it with `k get svc np1`.
