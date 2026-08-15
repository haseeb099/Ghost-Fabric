#!/usr/bin/env bash
# Bootstrap S3 + DynamoDB for Terraform remote state (run once in us-east-1).
# Requires: aws CLI credentials with admin-ish IAM for the pilot account.
# Does NOT apply the Ghost Fabric application stack.

set -euo pipefail

BUCKET="${TF_STATE_BUCKET:-ghost-fabric-terraform-state}"
TABLE="${TF_LOCK_TABLE:-ghost-fabric-terraform-locks}"
REGION="${TF_STATE_REGION:-us-east-1}"

echo "Creating state bucket s3://${BUCKET} in ${REGION}..."
if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  echo "Bucket already exists."
else
  if [[ "${REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}"
  else
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}" \
      --create-bucket-configuration LocationConstraint="${REGION}"
  fi
fi

aws s3api put-bucket-versioning \
  --bucket "${BUCKET}" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket "${BUCKET}" \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
  }'

aws s3api put-public-access-block \
  --bucket "${BUCKET}" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "Creating DynamoDB lock table ${TABLE}..."
if aws dynamodb describe-table --table-name "${TABLE}" --region "${REGION}" >/dev/null 2>&1; then
  echo "Lock table already exists."
else
  aws dynamodb create-table \
    --table-name "${TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION}"
fi

echo "Bootstrap complete. Copy backend.hcl.example -> backend.hcl and set bucket/table names."
