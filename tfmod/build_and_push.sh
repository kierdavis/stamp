#!/bin/sh
set -o errexit -o nounset -o pipefail
nix-store --realise "$drv_path"
oci_dir=$(
  nix \
  --extra-experimental-features nix-command \
  --extra-experimental-features flakes \
  derivation show \
  "$drv_path" \
  | jq --raw-output 'to_entries[0].value.outputs.out.path'
)
crane push --index "$oci_dir" "$repo_tag"
