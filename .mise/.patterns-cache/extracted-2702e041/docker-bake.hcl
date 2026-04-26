variable "TAG" {
  default = "0.1.0"
}

variable "REGISTRY" {
  default = "ghcr.io/orchestras"
}

group "default" {
  targets = ["package"]
}

target "package" {
  dockerfile = "Dockerfile.package"
  tags = [
    "${REGISTRY}/python-template:${TAG}",
    "${REGISTRY}/python-template:latest",
  ]
  args = {
    TAG = TAG
  }
  platforms = ["linux/amd64", "linux/arm64"]
  cache-from = ["type=gha"]
  cache-to   = ["type=gha,mode=max"]
}
