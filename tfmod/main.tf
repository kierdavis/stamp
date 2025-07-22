terraform {
  required_providers {
    external = {
      source = "hashicorp/external"
    }
  }
}

variable "flake" {
  type = string
  description = <<-EOT
    A reference to an output of a Nix flake, in the form accepted by 'nix build'.
    For example, 'path:path/to/myflake#myoutput'.
    The output should evaluate to a derivation that builds an OCI container image
    in the same format used by Stamp tooling.
  EOT
}

variable "repo" {
  type = string
  description = <<-EOT
    The fully qualified name of the repository to push the built image to.
    For example, 'docker.io/kierdavis/myimage'.
  EOT
}

data "external" "derivation" {
  program = ["${path.module}/derivation.sh"]
  query = { flake = var.flake }
}

locals {
  tag = data.external.derivation.result.tag
  repo_tag = "${var.repo}:${local.tag}"
}

resource "terraform_data" "build_and_push" {
  triggers_replace = local.repo_tag
  provisioner "local-exec" {
    command = "exec ${path.module}/build_and_push.sh"
    environment = merge(data.external.derivation.result, { repo_tag = local.repo_tag })
  }
}

output "tag" {
  depends_on = [terraform_data.build_and_push]
  value = local.tag
}

output "repo_tag" {
  depends_on = [terraform_data.build_and_push]
  value = local.repo_tag
}
