# Least-privilege policy: read ONLY this app's secrets, nothing else.
resource "aws_iam_policy" "secrets_read" {
  name        = "${local.name}-secrets-read"
  description = "Read ${local.name} app secrets from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret",
      ]
      Resource = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${local.name}/*"
    }]
  })
}

# IRSA: an IAM role assumable ONLY by the `voyantra` ServiceAccount in `default`,
# via the cluster's OIDC provider — pods get AWS creds without node-wide access.
module "irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.44"

  role_name = "${local.name}-app"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["default:voyantra"]
    }
  }

  role_policy_arns = {
    secrets = aws_iam_policy.secrets_read.arn
  }
}
