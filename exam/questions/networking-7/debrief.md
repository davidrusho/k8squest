Same as allow-client but the from entry is:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: prodns
Every namespace carries the label kubernetes.io/metadata.name automatically.
