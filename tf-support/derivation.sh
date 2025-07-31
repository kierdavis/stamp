#!/bin/sh
set -o errexit -o nounset -o pipefail
query=$(cat)
flake=$(jq --raw-output .flake <<<"$query")
symlink=$(jq --raw-output .symlink <<<"$query")
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
if [[ "$symlink" != null ]]; then
  mkdir -p "$(dirname "$symlink")"
  # XXX: I don't think there's a way to point a GC root at a derivation
  # through the Nix CLI right now, except with this horrible hack.
  # Create a GC root pointing at an arbitrary placeholder store path.
  nix --extra-experimental-features nix-command build --expr 'builtins.toFile "placeholder" ""' --out-link "$symlink"
  # Change the symlink to point at what we actually want.
  ln -sfT "$drv_path" "$symlink"
fi
jq --raw-input --compact-output '{drv_path:.,tag:.|ltrimstr("/nix/store/")|split("-")|.[0]}' <<<"$drv_path"
