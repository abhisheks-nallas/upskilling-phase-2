#!/bin/bash
# Runs on the box. Installs k3s, Helm and Fission (with its CRDs). Safe to re-run.
set -e
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
VERSION=v1.27.0   # Fission chart/app version. Needs Kubernetes 1.32 or newer, k3s stable is newer than that.

command -v k3s >/dev/null || curl -sfL https://get.k3s.io | sudo INSTALL_K3S_EXEC='--write-kubeconfig-mode 644' sh -
for i in $(seq 1 40); do kubectl get nodes 2>/dev/null | grep -q ' Ready' && break; sleep 4; done

command -v helm >/dev/null || curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
command -v git >/dev/null || sudo dnf install -y -q git   # kubectl -k needs git to fetch the CRDs

# This chart version does not install the Fission CRDs itself. Without them the executor and router crash-loop.
kubectl apply --server-side -k "github.com/fission/fission/crds/v1?ref=$VERSION" >/dev/null

helm repo add fission-charts https://fission.github.io/fission-charts/ >/dev/null 2>&1 || true
helm repo update >/dev/null
# NodePort router (31314). mqt_keda off: we don't use message queue triggers and it needs extra components.
helm upgrade --install fission fission-charts/fission-all --version "${VERSION#v}" --namespace fission --create-namespace \
  --set serviceType=NodePort --set routerServiceType=NodePort --set mqt_keda.enabled=false --wait --timeout 10m
kubectl get pods -n fission
