#!/bin/sh
set -o errexit -o nounset -o pipefail
flake=$(jq --raw-output .flake)
stamp_dir=$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")
drv_path=$(
  nix \
  --extra-experimental-features nix-command \
  --extra-experimental-features flakes \
  path-info \
  --derivation \
  --override-input stamp "path:$stamp_dir" \
  --show-trace \
  "$flake"
)
jq --raw-input --compact-output '{drv_path:.,tag:.|ltrimstr("/nix/store/")|split("-")|.[0]}' <<<"$drv_path"
