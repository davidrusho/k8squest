`--field-selector=status.phase!=Running` filters on the server; `k get po -A | grep -v Running` gives a similar list (plus the header). The list has to come from all namespaces (`-A`), not only one.
