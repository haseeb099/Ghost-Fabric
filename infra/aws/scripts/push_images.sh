# Push local Docker images to each regional ECR repository after terraform apply.
# Usage:
#   ./scripts/push_images.sh us-east-1 <api_repo_url> <web_repo_url> [tag]
set -euo pipefail

REGION="${1:?region required}"
API_REPO="${2:?api repository URL required}"
WEB_REPO="${3:?web repository URL required}"
TAG="${4:-latest}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "$(echo "${API_REPO}" | cut -d/ -f1)"

docker build -t "${API_REPO}:${TAG}" "${ROOT}/backend"
docker build -t "${WEB_REPO}:${TAG}" "${ROOT}/frontend"
docker push "${API_REPO}:${TAG}"
docker push "${WEB_REPO}:${TAG}"

echo "Pushed ${API_REPO}:${TAG} and ${WEB_REPO}:${TAG}"
