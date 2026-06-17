# Voyantra infrastructure (Terraform) — P6.3

Production-shaped AWS stack: VPC → EKS (+ managed nodes, OIDC) → RDS Postgres →
ElastiCache Redis → 3 ECR repos → an IRSA role for the app. One `highly_available`
switch separates cheap-dev from HA-prod.

## Layout
| File | Provisions |
|------|-----------|
| `versions.tf` / `providers.tf` / `variables.tf` | pins, provider+tags, all knobs |
| `vpc.tf` | VPC, public/private subnets across 3 AZs, NAT, EKS subnet tags |
| `eks.tf` | EKS cluster + managed node group + OIDC (for IRSA) |
| `rds.tf` | Postgres 16, Secrets-Manager-managed master password, node-only SG |
| `elasticache.tf` | Redis replication group, node-only SG |
| `ecr.tf` | `api` / `worker` / `web` repos, immutable tags, scan-on-push, lifecycle |
| `irsa.tf` | IAM role assumable by the `default:voyantra` ServiceAccount → read app secrets |
| `outputs.tf` | cluster endpoint, ECR URLs, RDS/Redis endpoints, IRSA ARN |

## Verify (no cost)
```bash
cd infra/terraform
terraform init                 # downloads modules + provider (local state)
terraform validate
terraform plan                 # read-only AWS calls; shows what WOULD be created
```

## Apply (P6.5 — costs money)
> ⚠️ Applied, this stack runs **~$200–400/mo** (EKS control plane, 2 nodes, NAT,
> RDS, ElastiCache). Switch to the S3 backend (`backend-s3.tf.example`) first.
```bash
cp terraform.tfvars.example terraform.tfvars   # edit env/sizing
terraform plan -out tfplan
terraform apply tfplan                         # creates real resources
terraform output configure_kubectl             # then point kubectl at EKS
# Tear down:  terraform destroy
```

Prod/staging: set `highly_available = true` and bump node/db/redis sizes in tfvars.
