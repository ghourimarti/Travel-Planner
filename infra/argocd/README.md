# ArgoCD GitOps (P6.4c)

ArgoCD reconciles the Helm chart in `infra/helm/voyantra` into the cluster from
git. CI never `kubectl apply`s — it bumps an image tag in `values-<env>.yaml`
(see `.github/workflows/cd.yml` / `promote.yml`) and ArgoCD converges. Rollback
is `git revert` of the bump (or `argocd app rollback`).

| Env | Sync | Driven by |
|-----|------|-----------|
| dev | automated (prune + selfHeal) | every merge to `main` (cd.yml) |
| staging | automated | promotion after the eval gate (promote.yml) |
| prod | **manual** | promotion PR + human `argocd app sync` |

## One-time bootstrap (on the EKS cluster — P6.5)

1. **Set your repo URL** in `project.yaml` and the three `application-*.yaml`
   (`https://github.com/OWNER/REPO.git`), and the `ACCOUNT/REGION/endpoint`
   placeholders in `values-<env>.yaml` from the Terraform outputs.

2. **Install ArgoCD**

   ```bash
   kubectl create namespace argocd
   kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
   ```

3. **Install External Secrets Operator** and create the `cluster-secret-store`
   (AWS provider) authenticated via the IRSA `voyantra` ServiceAccount:

   ```bash
   helm repo add external-secrets https://charts.external-secrets.io
   helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace
   ```

   ```yaml
   # cluster-secret-store.yaml — provider auth via the IRSA SA (jwt)
   apiVersion: external-secrets.io/v1
   kind: ClusterSecretStore
   metadata:
     name: cluster-secret-store
   spec:
     provider:
       aws:
         service: SecretsManager
         region: REGION
         auth:
           jwt:
             serviceAccountRef:
               name: voyantra
               namespace: voyantra-dev
   ```

   Store the app secret JSON in AWS Secrets Manager per env, e.g.
   `voyantra-dev/app` holding `OPENAI_API_KEY`, `DATABASE_URL` (assembled from the
   RDS master secret), `SESSION_SECRET`, `DEV_LOGIN_PASSWORD`.

4. **Register the project + apps**

   ```bash
   kubectl apply -f infra/argocd/project.yaml
   kubectl apply -f infra/argocd/application-dev.yaml
   kubectl apply -f infra/argocd/application-staging.yaml
   kubectl apply -f infra/argocd/application-prod.yaml
   ```

## Rollback

- **dev/staging:** revert the deploy PR — ArgoCD self-heals back.
- **prod:** `argocd app rollback voyantra-prod <revision>` (or revert the
  promotion PR, then `argocd app sync voyantra-prod`).
