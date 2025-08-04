{ e2fsprogs
, gnutar
, lib
, pigz
, python3
, rsync
, stdenvNoCC
, util-linux
, vmTools
}:

let
  self = python3.pkgs.buildPythonApplication rec {
    pname = "stamptool";
    version = "0.1";
    pyproject = true;
    src = builtins.filterSource (path: type: baseNameOf path != "default.nix") ./.;
    build-system = with python3.pkgs; [ setuptools ];
    nativeCheckInputs = with python3.pkgs; [ gnutar pigz pytestCheckHook rsync testfixtures ];

    passthru = {
      extractDiffs =
        { name ? "stamp-extract-diffs"
        , oci
        , passthru ? {}
        }:
        stdenvNoCC.mkDerivation {
          inherit name oci passthru;
          __structuredAttrs = true;
          nativeBuildInputs = [ self pigz ];
          buildCommand = "stamptool extract-diffs";
          # diffs may contain Nix store paths, but they refer to the image's
          # Nix store, not the host system's.
          unsafeDiscardReferences.out = true;
        };

      layerBlob =
        { name ? "stamp-layer-blob"
        , diff
        , passthru ? {}
        }:
        stdenvNoCC.mkDerivation {
          inherit name diff passthru;
          __structuredAttrs = true;
          nativeBuildInputs = [ self pigz ];
          buildCommand = "stamptool layer-blob";
        };

      layerDiff =
        { name ? "stamp-layer-diff"
        , copy ? []
        , runOnHost ? ""
        , runOnHostUID ? 0
        , runOnHostGID ? runOnHostUID
        , runInContainer ? ""
        , runInContainerBase ? null
        , vmDiskSize ? 2048 # MB
        , vmMemory ? 512    # MB
        , hash ? null
        , passthru ? {}
        }:
        let
          allUIDsEqual = lib.all (x: (x.uid or 0) == runOnHostUID) copy;
          allGIDsEqual = lib.all (x: (x.gid or (x.uid or 0)) == runOnHostGID) copy;
          needVM = runInContainer != "" || !allUIDsEqual || !allGIDsEqual;
          drv = stdenvNoCC.mkDerivation ({
            inherit name copy runOnHost runOnHostUID runOnHostGID runInContainer runInContainerBase passthru;
            __structuredAttrs = true;
            nativeBuildInputs = [ self gnutar rsync ];
            buildCommand = "stamptool layer-diff";
            runInContainerBaseDiffs = if runInContainerBase != null then runInContainerBase.diffs else null;
            # diffs may contain Nix store paths, but they refer to the image's
            # Nix store, not the host system's.
            unsafeDiscardReferences.out = true;
          } // lib.optionalAttrs (hash != null) {
            outputHash = hash;
            outputHashMode = "recursive";
          });
        in
          if needVM
          then vmTools.runInLinuxVM (drv.overrideAttrs (oldAttrs: {
            preVM = vmTools.createEmptyImage {
              size = vmDiskSize;
              fullName = "disk";
              destination = "disk";
            };
            memSize = vmMemory;
            nativeBuildInputs = oldAttrs.nativeBuildInputs ++ [ e2fsprogs util-linux ];
            buildCommand = ''
              mkdir mnt
              mkfs /dev/${vmTools.hd}
              mount /dev/${vmTools.hd} mnt
              cd mnt
            '' + oldAttrs.buildCommand;
          }))
          else drv;

      nixPackingPlan =
        { name ? "stamp-nix-packing-plan"
        , closureInfo
        , targetLayerSize
        , passthru ? {}
        }:
        stdenvNoCC.mkDerivation {
          inherit name closureInfo targetLayerSize passthru;
          __structuredAttrs = true;
          nativeBuildInputs = [ self ];
          buildCommand = "stamptool nix-packing-plan";
        };

      nixStoreLayerDiff =
        { name ? "stamp-nix-store-layer-diff"
        , paths
        , passthru ? {}
        }:
        stdenvNoCC.mkDerivation {
          inherit name paths passthru;
          __structuredAttrs = true;
          nativeBuildInputs = [ self gnutar ];
          buildCommand = "stamptool nix-store-layer-diff";
          # diffs may contain Nix store paths, but they refer to the image's
          # Nix store, not the host system's.
          unsafeDiscardReferences.diff = true;
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
          preferLocalBuild = true;
        };

      patchOCI =
        { name ? "stamp-patch-oci"
        , base ? null
        , appendLayers ? []
        , env ? {}
        , entrypoint ? null
        , cmd ? null
        , workingDir ? null
        , passthru ? {}
        }:
        stdenvNoCC.mkDerivation {
          inherit name base appendLayers env entrypoint cmd workingDir passthru;
          __structuredAttrs = true;
          outputs = [ "out" "manifest" "config" ];
          nativeBuildInputs = [ self ];
          buildCommand = "stamptool patch-oci";
          preferLocalBuild = true;
          # Env/Entrypoint/Cmd etc may contain Nix store paths, but they refer
          # to the image's Nix store, not the host system's.
          unsafeDiscardReferences.config = true;
        };
    };
  };
in self
