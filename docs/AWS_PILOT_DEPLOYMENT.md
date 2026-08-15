# Ghost Fabric — AWS Pilot Deployment (GF-29)

Bounded **pilot** infrastructure for three independent regional footprints. This is **not** multi-region mesh failover or consensus — those are later CHAMELEON work (GF-32+).

## Safety boundary

- Synthetic or approved training data only
- Human approval required for simulated recovery
- No targeting, weapons assignment, autonomous action, or operational deception
- `terraform apply` is **manual**; CI only validates configuration

## Architecture (per region)

```
Internet
   |
  ALB (HTTP :80)  ---- path /api/*, /ws/* ----> ECS Fargate API :8000
   |                                           |
   +------------- default / ----------------> ECS Fargate Web :80
                                               |
                                          private subnets
                                               |
                                          RDS PostgreSQL 16
                                          (storage_encrypted, private,
                                           automated backups)
```

**TLS gate:** the pilot ALB is HTTP-only today. Production internet exposure
requires ACM certificates, an HTTPS :443 listener (TLS 1.3 policy after
sign-off), and verification recorded in
[SECURITY_FOUNDATION_REVIEW.md](SECURITY_FOUNDATION_REVIEW.md). Do not claim
TLS 1.3 or mTLS from this scaffold alone.

Secrets Manager holds:

- `DATABASE_URL` (full connection string)
- `AUTH_TOKENS` (viewer/operator bearer map)

Rotate those secrets through the manager; never commit production values.
CHAMELEON service mTLS remains blocked on
[architecture/CHAMELEON_TRANSPORT_REVIEW.md](architecture/CHAMELEON_TRANSPORT_REVIEW.md).

Regions: `us-east-1`, `eu-west-1`, `ap-southeast-1` (non-overlapping VPC CIDRs).

## Prerequisites

1. AWS account with admin (or scoped) IAM for VPC, ECS, ECR, RDS, Secrets Manager, IAM, CloudWatch, ELB
2. [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.6
3. AWS CLI v2 configured (`aws sts get-caller-identity`)
4. Docker (to build/push images)

## Bootstrap remote state (once)

```bash
cd infra/aws
export TF_STATE_BUCKET="ghost-fabric-terraform-state-<unique>"
export TF_LOCK_TABLE="ghost-fabric-terraform-locks"
export TF_STATE_REGION="us-east-1"
bash scripts/bootstrap_state.sh

cp backend.hcl.example backend.hcl
# Edit bucket / table names in backend.hcl

# Uncomment the backend "s3" {} block in versions.tf, then:
terraform init -backend-config=backend.hcl
```

Until the backend block is enabled, local state is fine for dry-runs:

```bash
terraform init
```

## Plan (no cloud changes until you apply)

```bash
cd infra/aws
cp terraform.tfvars.example terraform.tfvars
terraform fmt -recursive
terraform validate
terraform plan -out=pilot.tfplan
```

Review the plan carefully (NAT gateways and RDS incur cost in **each** of three regions).

## Apply (manual only)

```bash
terraform apply pilot.tfplan
terraform output
```

Capture:

- `pilot_endpoints` — ALB DNS per region
- `ecr_repositories` — push targets
- `secret_arns` — never print secret values to tickets/chat

## Push container images

```bash
# Example for us-east-1 after reading terraform output
API_REPO="$(terraform output -json ecr_repositories | jq -r '.["us-east-1"].api')"
WEB_REPO="$(terraform output -json ecr_repositories | jq -r '.["us-east-1"].web')"
bash scripts/push_images.sh us-east-1 "$API_REPO" "$WEB_REPO" latest

# Force new ECS deployment
aws ecs update-service --region us-east-1 \
  --cluster "$(terraform output -json | jq -r '.')" \
  --force-new-deployment
```

Repeat for `eu-west-1` and `ap-southeast-1`, or script a loop over `terraform output -json ecr_repositories`.

After first image push, force ECS service redeploy if tasks were started with a missing image:

```bash
CLUSTER=$(terraform output -raw ... )  # use region module outputs via JSON
```

Practical pattern:

```bash
for region in us-east-1 eu-west-1 ap-southeast-1; do
  api=$(terraform output -json ecr_repositories | jq -r --arg r "$region" '.[$r].api')
  web=$(terraform output -json ecr_repositories | jq -r --arg r "$region" '.[$r].web')
  bash scripts/push_images.sh "$region" "$api" "$web" latest
done
```

Then in each region, update the ECS services named `${project}-${environment}-${region}-api|web`.

## Secret injection

Terraform creates and rotates initial secrets. ECS task definitions inject:

| Env var | Source |
|---------|--------|
| `DATABASE_URL` | Secrets Manager `.../database-url` |
| `AUTH_TOKENS` | Secrets Manager `.../auth-tokens` |
| `AUTH_MODE` | Terraform var (default `required`) |
| `AUDIT_BACKEND` | `postgres` |
| `CORS_ORIGINS` | ALB DNS (`http://...`) |

Retrieve pilot tokens (operators only):

```bash
aws secretsmanager get-secret-value \
  --secret-id ghost-fabric-pilot/<region>/auth-tokens \
  --query SecretString --output text
```

Rotate tokens before any external pilot audience.

## Post-deploy smoke checks

```bash
ALB="http://$(terraform output -json pilot_endpoints | jq -r '.["us-east-1"]')"
curl -fsS "$ALB/api/health"
# Expect persistence.backend == postgres when healthy

# Operator mutation (use rotated token)
curl -fsS -X POST "$ALB/api/v1/scenario/reset" \
  -H "Authorization: Bearer <operator-token>" \
  -H "X-Command-ID: $(uuidgen)"
curl -fsS "$ALB/api/v1/audit/export" \
  -H "Authorization: Bearer <operator-token>"
```

Open `$ALB/` for the console. ALB path rules send `/api/*` and `/ws/*` to the API service.

## Backup and restore

### Automated

RDS: 7-day automated backups (configurable via `db_backup_retention_days`), storage encryption on, deletion protection on.

### Logical export (application)

```bash
curl -fsS "$ALB/api/v1/audit/export" -H "Authorization: Bearer <operator-token>" \
  > audit-export.json
```

### RDS snapshot restore

1. Create snapshot (or use automated snapshot) in the AWS console / CLI  
2. Restore to a new instance in the same VPC/subnet group  
3. Update Secrets Manager `database-url` and force ECS redeploy  
4. Do **not** expose RDS publicly

## Rollback

1. **Application:** redeploy previous ECR image tag; `aws ecs update-service --force-new-deployment`  
2. **Terraform:** `terraform plan` / targeted destroy is high risk — prefer image rollback  
3. **Full teardown (destroys pilot data):**

```bash
# Disable deletion protection first if required
terraform destroy
```

## Cost notes

Three regions × (NAT Gateway + ALB + Fargate + RDS) is intentional for pilot geography rehearsal and will incur non-trivial AWS spend. For a cheaper dry-run, temporarily set `enable_nat_gateway = false` is **not** recommended with Fargate private subnets unless you add VPC endpoints.

## What this does **not** provide yet

- Cross-region VPC peering / Transit Gateway  
- Raft / consensus mesh implementation (GF-33; GF-32 design awaits architect approval)  
- Global traffic manager / failover DNS  
- ACM HTTPS certificates (add before external pilots)  
- FedRAMP / SOC 2 certification  

## Related

- Local Compose path: [DEPLOYMENT.md](DEPLOYMENT.md)  
- OpenAPI: `contracts/openapi.json`  
- Terraform root: `infra/aws/`  
