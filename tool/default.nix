{ bash
, coreutils
, gnutar
, pigz
, python3
, stdenvNoCC
}:

let
  self = python3.pkgs.buildPythonApplication rec {
    pname = "stamptool";
    version = "0.1";
    pyproject = true;
    src = builtins.filterSource (path: type: baseNameOf path != "default.nix") ./.;
    build-system = with python3.pkgs; [ setuptools ];
    nativeCheckInputs = with python3.pkgs; [ pytestCheckHook testfixtures ] ++ propagatedBuildInputs;
    propagatedBuildInputs = [ bash coreutils gnutar pigz ];

    passthru = {
      extractDiffs =
        { name ? "stamp-extract-diffs"
        , oci
        , passthru ? {}
        }:
        stdenvNoCC.mkDerivation {
          inherit name oci passthru;
          __structuredAttrs = true;
          nativeBuildInputs = [ self ];
          buildCommand = "stamptool extract-diffs";
          # diffs may contain Nix store paths, but they refer to the image's
          # Nix store, not the host system's.
          unsafeDiscardReferences.out = true;
        };

      layer =
        { name ? "stamp-layer"
        , copy ? []
        , runOnHost ? ""
        , passthru ? {}
        }:
        stdenvNoCC.mkDerivation {
          inherit name copy runOnHost passthru;
          __structuredAttrs = true;
          outputs = [ "out" "diff" ];
          nativeBuildInputs = [ self ];
          buildCommand = "stamptool layer";
          # diffs may contain Nix store paths, but they refer to the image's
          # Nix store, not the host system's.
          unsafeDiscardReferences.diff = true;
        };

      nixPackingPlan =
        { name ? "stamp-nix-packing-plan"
        , roots
        , targetLayerSize
        , passthru ? {}
        }:
        stdenvNoCC.mkDerivation {
          inherit name targetLayerSize passthru;
          __structuredAttrs = true;
          nativeBuildInputs = [ self ];
          buildCommand = "stamptool nix-packing-plan";
          exportReferencesGraph.closureInfo = roots;
        };

      patchDiffs =
        { name ? "stamp-patch-diffs"
        , base ? null
        , appendLayers ? []
        , passthru ? {}
        }:
        stdenvNoCC.mkDerivation {
          inherit name base appendLayers passthru;
          __structuredAttrs = true;
          nativeBuildInputs = [ self ];
          buildCommand = "stamptool patch-diffs";
          baseDiffs = if base != null then base.diffs else null;
        };

      patchOCI =
        { name ? "stamp-patch-oci"
        , base ? null
        , appendLayers ? []
        , env ? {}
        , entrypoint ? {}
        , cmd ? {}
        , passthru ? {}
        }:
        stdenvNoCC.mkDerivation {
          inherit name base appendLayers env entrypoint cmd passthru;
          __structuredAttrs = true;
          outputs = [ "out" "manifest" "config" ];
          nativeBuildInputs = [ self ];
          buildCommand = "stamptool patch-oci";
          # Env/Entrypoint/Cmd etc may contain Nix store paths, but they refer
          # to the image's Nix store, not the host system's.
          unsafeDiscardReferences.config = true;
        };
    };
  };
in self
