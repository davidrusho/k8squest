Generate with $do first, then in nano add the block directly under the top-level `spec:` line (same indent as `containers:`, two spaces).
  nodeSelector:
    disk: ssd
If no node has the label, the pod stays Pending.
