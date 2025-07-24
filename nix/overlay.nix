self: super:

with self;

{
  stamp = {
    defaultTargetLayerSize = 128 * 1024 * 1024; # bytes

    fetch =
      { name ? "stamp-img-${lib.strings.sanitizeDerivationName repository}"
      , repository
      , digest
      , hash
      , passthru ? {}
      }:
      let
        passthru' = { inherit oci diffs; } // passthru;
        oci = stdenvNoCC.mkDerivation {
          inherit name repository digest;
          nativeBuildInputs = [ crane ];
          buildCommand = ''crane pull --format=oci "$repository@$digest" "$out"'';
          outputHash = hash;
          outputHashMode = "recursive";
          passthru = passthru';
        };
        diffs = stamp.internal.tool.extractDiffs {
          inherit oci;
          name = "${name}-diffs";
          passthru = passthru';
        };
      in oci;

    patch =
      { name ? stamp.internal.defaultPatchDrvName base
      , base ? null
      , appendLayers ? []
      , copy ? []
      , runOnHost ? ""
      , runOnHostUID ? 0
      , runOnHostGID ? runOnHostUID
      , runInContainer ? ""
      , env ? {}
      , entrypoint ? null
      , cmd ? null
      , workingDir ? null
      , vmDiskSize ? 2048 # MB
      , vmMemory ? 512    # MB
      , layerHash ? null
      , passthru ? {}
      }:
      let
        implicitLayer = if copy != [] || runOnHost != "" || runInContainer != ""
          then stamp.internal.layer {
            inherit copy runOnHost runOnHostUID runOnHostGID runInContainer vmDiskSize vmMemory;
            name = "${name}-layer";
            runInContainerBase = if runInContainer != "" then base else null;
            hash = layerHash;
          }
          else null;
        appendLayers' = builtins.map (lay: { inherit (lay) blob diff; })
          (appendLayers ++ lib.optional (implicitLayer != null) implicitLayer);
        passthru' = { inherit oci diffs implicitLayer; } // passthru;
        oci = stamp.internal.tool.patchOCI {
          inherit name base env entrypoint cmd workingDir;
          appendLayers = appendLayers';
          passthru = passthru';
        };
        diffs = stamp.internal.tool.patchDiffs {
          inherit base;
          name = "${name}-diffs";
          appendLayers = appendLayers';
          passthru = passthru';
        };
      in oci;

    fromNix =
      { name ? "stamp-img-nix"
      , runOnHost ? ""
      , runInContainer ? ""
      , env ? {}
      , entrypoint ? null
      , cmd ? null
      , workingDir ? null
      , targetLayerSize ? stamp.defaultTargetLayerSize # bytes
      , withRegistration ? false
      , withConveniences ? true
      , vmDiskSize ? 2048 # MB
      , vmMemory ? 512    # MB
      , passthru ? {}
      }:
      let
        runOnHost' = lib.optionalString withConveniences ''
          mkdir -p bin etc/pki/tls/certs etc/ssl/certs tmp usr
          ln -sfT "${bash}/bin/bash" bin/bash
          ln -sfT "${bash}/bin/bash" bin/sh
          ln -sfT "${busybox}/bin/env" bin/env
          for x in etc/{ssl/certs/ca-{bundle,certificates}.crt,pki/tls/certs/ca-bundle.crt}; do
            ln -sfT "${cacert}/etc/ssl/certs/ca-bundle.crt" "$x"
          done
          ln -sfT ../bin usr/bin
        '' + runOnHost;
        env' = env // lib.optionalAttrs withConveniences {
          PATH =
            let default = lib.makeBinPath [ bash busybox ];
            in if env ? PATH then "${env.PATH}:${default}" else default;
        };
        storeRoots = lib.concatMap stamp.internal.findStorePaths (
          [ runOnHost' runInContainer ]
          ++ lib.mapAttrsToList (_: val: val) env'
          ++ (if entrypoint != null then entrypoint else [])
          ++ (if cmd != null then cmd else [])
        );
        packingPlan = stamp.internal.tool.nixPackingPlan {
          inherit targetLayerSize;
          name = "${name}-packing-plan";
          roots = storeRoots;
        };
        mkStoreLayer = fileName: _: let
          pathsFile = "${packingPlan}/${fileName}";
        in stamp.internal.nixStoreLayer {
          paths = builtins.filter (x: x != "") (lib.splitString "\n" (builtins.readFile pathsFile));
          passthru = { inherit pathsFile; };
        };
        storeLayers = lib.mapAttrsToList mkStoreLayer (builtins.readDir packingPlan);
        copy = lib.optional withRegistration {
          src = "${closureInfo { rootPaths = storeRoots; }}/registration";
          dest = "/nix-path-registration";
        };
      in stamp.patch {
        inherit name copy runInContainer entrypoint cmd workingDir vmDiskSize vmMemory;
        appendLayers = storeLayers;
        runOnHost = runOnHost';
        env = env';
        passthru = { inherit storeRoots packingPlan storeLayers; } // passthru;
      };

    installDebianPkgs =
      { name ? stamp.internal.defaultPatchDrvName base
      , base
      , pkgs
      , vmDiskSize ? 2048 # MB
      , vmMemory ? 512    # MB
      , layerHash ? null
      , passthru ? {}
      }:
      stamp.patch {
        inherit name base vmDiskSize vmMemory layerHash passthru;
        copy = builtins.map (src: { inherit src; dest = "/imgbuild/${src.name}"; }) pkgs;
        runInContainer = ''
          apt install -y /imgbuild/*
          truncate --size=0 /var/cache/ldconfig/aux-cache /var/log/apt/history.log /var/log/apt/term.log /var/log/dpkg.log
          rm -rf /imgbuild
        '';
      };

    internal = {
      tool = callPackage ../tool {};

      defaultPatchDrvName = base: if base != null then "${base.name}-patch" else "stamp-img";

      # Given a string, return a (non unique) list of all the top-level Nix
      # store paths mentioned in the string.
      findStorePaths = str: let
        str' = builtins.toString str;
        ctx = builtins.getContext str';
        # "foo /nix/store/aaa-foo/bar" -> [ "foo " [ "/nix/store/aaa-foo" ] "/bar" ]
        split = builtins.split "(${builtins.storeDir}/[0-9a-z]{32}-[-.+_?=0-9a-zA-Z]+)" str';
        # -> [ "/nix/store/aaa-foo" ]
        paths = builtins.map (groups: builtins.elemAt groups 0) (builtins.filter builtins.isList split);
      in builtins.map (path: builtins.appendContext path ctx) paths;

      layer =
        { name ? "stamp-layer"
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
          passthru' = { inherit diff blob; } // passthru;
          diff = stamp.internal.tool.layerDiff {
            inherit copy runOnHost runOnHostUID runOnHostGID runInContainer runInContainerBase vmDiskSize vmMemory hash;
            name = "${name}-diff";
            passthru = passthru';
          };
          blob = stamp.internal.tool.layerBlob {
            inherit diff;
            name = "${name}-blob";
            passthru = passthru';
          };
        in diff;

      nixStoreLayer =
        { paths
        , passthru ? {}
        }:
        let
          passthru' = { inherit paths diff blob; } // passthru;
          diff = stamp.internal.tool.nixStoreLayerDiff {
            inherit paths;
            name = "stamp-layer-nix-store-diff";
            passthru = passthru';
          };
          blob = stamp.internal.tool.layerBlob {
            inherit diff;
            name = "stamp-layer-nix-store-blob";
            passthru = passthru';
          };
        in diff;
    };
  };
}
