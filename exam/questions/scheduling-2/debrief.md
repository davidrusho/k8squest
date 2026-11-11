Generate with $do first, then in nano add the block directly under the top-level `spec:` line (same indent as `containers:`, two spaces).
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: disk
            operator: In
            values:
            - ssd
