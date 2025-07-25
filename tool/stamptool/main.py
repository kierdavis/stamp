import json
import os
import sys
from . import extract_diffs, layer_blob, layer_diff, nix_packing_plan, nix_store_layer_diff, patch


CMD_FUNCS = {
  "extract-diffs": extract_diffs.main,
  "layer-blob": layer_blob.main,
  "layer-diff": layer_diff.main,
  "nix-packing-plan": nix_packing_plan.main,
  "nix-store-layer-diff": nix_store_layer_diff.main,
  "patch-diffs": patch.diffs_main,
  "patch-oci": patch.oci_main,
}


def main():
  cmd = sys.argv[1]
  cmd_func = CMD_FUNCS[cmd]
  with open(os.environ["NIX_ATTRS_JSON_FILE"]) as f:
    deriv_attrs = json.load(f)
  return cmd_func(deriv_attrs)
