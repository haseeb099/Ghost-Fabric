# Ghost Fabric — AWS pilot Terraform

Three-region pilot foundation (`us-east-1`, `eu-west-1`, `ap-southeast-1`).

See [docs/AWS_PILOT_DEPLOYMENT.md](../../docs/AWS_PILOT_DEPLOYMENT.md).

```bash
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
# Manual only:
# terraform plan -out=pilot.tfplan
# terraform apply pilot.tfplan
```
