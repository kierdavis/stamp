variable "flake_output" {
  type        = string
  description = <<-EOT
    A reference to an output of a Nix flake, in the form accepted by 'nix build'.
    For example, 'path:path/to/myflake#myoutput'.
    This output will be evaluated during the Terraform plan phase.
    The result of evaluation should be derivation for an OCI image directory,
    which will be realised and pushed during the Terraform apply phase.
  EOT
}

variable "repo" {
  type        = string
  description = <<-EOT
    The fully qualified name of the repository to push the built image to.
    For example, 'docker.io/kierdavis/myimage'.
  EOT
}

variable "eval_options" {
  type    = list(string)
  default = []
}

variable "create_derivation_gc_root" {
  type        = bool
  default     = true
  description = <<-EOT
    If true, a Nix garbage collector root will be created for the derivation.
    This can speed up the Terraform plan phase, particularly if evaluating the
    derivation requires realising store paths (i.e. import-from-derivation),
    at the of increase Nix store disk usage.
  EOT
}

variable "gc_root_id" {
  type    = string
  default = null
}

variable "gc_root_dir" {
  type    = string
  default = null
}

module "build" {
  source                    = "github.com/kierdavis/nix-realisation?ref=c031a4c46e77b68b3e19a8cd640908f844673bfb"
  flake_output              = var.flake_output
  eval_options              = var.eval_options
  create_derivation_gc_root = var.create_derivation_gc_root
  gc_root_id                = var.gc_root_id
  gc_root_dir               = var.gc_root_dir
}

locals {
  tag      = split("-", basename(module.build.derivation))[0]
  repo_tag = "${var.repo}:${local.tag}"
}

resource "terraform_data" "push" {
  triggers_replace = local.repo_tag
  provisioner "local-exec" {
    command = <<-EOT
      exec crane push --index "$oci_dir" "$repo_tag"
    EOT
    environment = {
      oci_dir  = module.build.outputs.out
      repo_tag = local.repo_tag
    }
  }
}

output "derivation" {
  value       = module.build.derivation
  description = <<-EOT
    The Nix derivation for building the image, i.e. the result of evaluating
    the specified flake output. This is a filename of the form '/nix/store/*.drv'.
  EOT
}

output "oci_dir" {
  value       = module.build.outputs.out
  description = <<-EOT
    The Nix derivation for building the image, i.e. the result of evaluating
    the specified flake output. This is a filename of the form '/nix/store/*.drv'.
  EOT
}

output "tag" {
  depends_on = [terraform_data.push]
  value      = local.tag
}

output "repo_tag" {
  depends_on = [terraform_data.push]
  value      = local.repo_tag
}
