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
          preferLocalBuild = true;
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
      , cmd ? null
      , entrypoint ? null
      , env ? {}
      , user ? null
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
        appendLayers' = appendLayers ++ lib.optional (implicitLayer != null) implicitLayer;
        passthru' = { inherit oci diffs implicitLayer; } // passthru;
        oci = stamp.internal.tool.patchOCI {
          inherit name base cmd entrypoint env user workingDir;
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
      , cmd ? null
      , entrypoint ? null
      , env ? {}
      , user ? null
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
            let default = lib.makeBinPath [ bash procps busybox ];
            in if env ? PATH then "${env.PATH}:${default}" else default;
        };
        storeRoots = lib.concatMap stamp.internal.findStorePaths (
          [ runOnHost' runInContainer ]
          ++ lib.mapAttrsToList (_: val: val) env'
          ++ (if entrypoint != null then entrypoint else [])
          ++ (if cmd != null then cmd else [])
        );
        closureInfo' = closureInfo { rootPaths = storeRoots; };
        packingPlan = stamp.internal.tool.nixPackingPlan {
          inherit targetLayerSize;
          name = "${name}-packing-plan";
          closureInfo = closureInfo';
        };
        mkStoreLayer = fileName: _: let
          pathsFile = "${packingPlan}/${fileName}";
        in stamp.internal.nixStoreLayer {
          paths = builtins.filter (x: x != "") (lib.splitString "\n" (builtins.readFile pathsFile));
          passthru = { inherit pathsFile; };
        };
        storeLayers = lib.mapAttrsToList mkStoreLayer (builtins.readDir packingPlan);
        copy = lib.optional withRegistration {
          src = "${closureInfo'}/registration";
          dest = "/nix-path-registration";
        };
      in stamp.patch {
        inherit name copy runInContainer cmd entrypoint user workingDir vmDiskSize vmMemory;
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

      digest =
        { name ? "${src.name}-digest"
        , src
        , passthru ? {}
        }:
        stdenvNoCC.mkDerivation {
          inherit name src passthru;
          buildCommand = ''( echo -n sha256: && sha256sum "$src" | cut -d ' ' -f 1 ) > "$out"'';
          preferLocalBuild = true;
        };

      layerFromDiffTarball =
        { name ? lib.strings.removeSuffix "-diff.tar" diffTarball.name
        , src
        , passthru ? {}
        }:
        let
          passthru' = { inherit diffTarball blobTarball diffDigest blobDigest; } // passthru;
          diffTarball = if src ? overrideAttrs
            then src.overrideAttrs (oldAttrs: { passthru = passthru' // (oldAttrs.passthru or {}); })
            else src;
          blobTarball = stdenvNoCC.mkDerivation {
            inherit diffTarball;
            name = "${name}-blob.tar.gz";
            nativeBuildInputs = [ pigz ];
            buildCommand = ''pigz --stdout --processes ''${NIX_BUILD_CORES:-1} --no-name --no-time "$diffTarball" > "$out"'';
            passthru = passthru';
          };
          diffDigest = stamp.internal.digest {
            src = diffTarball;
            passthru = passthru';
          };
          blobDigest = stamp.internal.digest {
            src = blobTarball;
            passthru = passthru';
          };
        in blobTarball;

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
        stamp.internal.layerFromDiffTarball {
          inherit name passthru;
          src = stamp.internal.tool.layerDiff {
            inherit copy runOnHost runOnHostUID runOnHostGID runInContainer runInContainerBase vmDiskSize vmMemory hash;
            name = "${name}-diff.tar";
          };
        };

      nixStoreLayer =
        { name ? "stamp-layer-nix-store"
        , paths
        , passthru ? {}
        }:
        stamp.internal.layerFromDiffTarball {
          inherit name;
          src = stdenvNoCC.mkDerivation {
            inherit paths;
            name = "${name}-diff.tar";
            buildCommand = ''tar --create --directory=/ --file="$out" --owner=0 --group=0 --numeric-owner --mtime="@$SOURCE_DATE_EPOCH" --sort=name "''${paths[@]#/}"'';
            preferLocalBuild = true;
            # diffs may contain Nix store paths, but they refer to the image's
            # Nix store, not the host system's.
            unsafeDiscardReferences.out = true;
            # required by unsafeDiscardReferences
            __structuredAttrs = true;
          };
          passthru = { inherit paths; } // passthru;
        };
    };
  };
}
