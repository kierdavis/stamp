let
  defaultTargetLayerSize = 128 * 1024 * 1024; # bytes

  # Given a string, return a (non unique) list of all the top-level Nix
  # store paths mentioned in the string.
  findStorePaths = str: let
    ctx = builtins.getContext str;
    # "foo /nix/store/aaa-foo/bar" -> [ "foo " [ "/nix/store/aaa-foo" ] "/bar" ]
    split = builtins.split "(${builtins.storeDir}/[0-9a-z]{32}-[-.+_?=0-9a-zA-Z]+)" str;
    # -> [ "/nix/store/aaa-foo" ]
    paths = builtins.map (groups: builtins.elemAt groups 0) (builtins.filter builtins.isList split);
  in builtins.map (path: builtins.appendContext path ctx) paths;

in

self: super: with self; {
  stamp = {
    tool = callPackage ../tool {};

    fetch =
      { name ? "stamp-img-${lib.sanitizeDerivationName repository}"
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
        diffs = stamp.tool.extractDiffs {
          inherit oci;
          name = "${name}-diffs";
          passthru = passthru';
        };
      in oci;

    patch =
      { name ? (if base != null then "${base.name}-patch" else "stamp-img")
      , base ? null
      , appendLayers ? []
      , copy ? []
      , runOnHost ? ""
      , env ? {}
      , entrypoint ? null
      , cmd ? null
      , passthru ? {}
      }:
      let
        implicitLayer = if copy != [] || runOnHost != ""
          then stamp.tool.layer { inherit copy runOnHost; name = "${name}-newlayer"; }
          else null;
        appendLayers' = builtins.map (lay: { blob = lay.out; diff = lay.diff; })
          (appendLayers ++ lib.optional (implicitLayer != null) implicitLayer);
        passthru' = { inherit oci diffs implicitLayer; } // passthru;
        oci = stamp.tool.patchOCI {
          inherit name base env entrypoint cmd;
          appendLayers = appendLayers';
          passthru = passthru';
        };
        diffs = stamp.tool.patchDiffs {
          inherit base;
          name = "${name}-diffs";
          appendLayers = appendLayers';
          passthru = passthru';
        };
      in oci;

    fromNix =
      { name ? "stamp-img-nix"
      , runOnHost ? ""
      , env ? {}
      , entrypoint ? null
      , cmd ? null
      , targetLayerSize ? defaultTargetLayerSize # bytes
      , withRegistration ? false
      , withConveniences ? true
      , passthru ? {}
      }:
      let
        runOnHost' = lib.optionalString withConveniences ''
          mkdir -p bin etc/ssl/certs tmp
          ln -sfT sh bin/bash
          ln -sfT "${bash}/bin/sh" bin/sh
          ln -sfT "${cacert}/etc/ssl/certs/ca-bundle.crt" etc/ssl/certs/ca-bundle.crt
        '' + runOnHost;
        storeRoots = lib.concatMap findStorePaths (
          [ runOnHost' ]
          ++ lib.mapAttrsToList (_: val: val) env
          ++ (if entrypoint != null then entrypoint else [])
          ++ (if cmd != null then cmd else [])
        );
        packingPlan = stamp.tool.nixPackingPlan {
          inherit targetLayerSize;
          name = "${name}-packing-plan";
          roots = storeRoots;
        };
        mkStoreLayer = fileName: _: let
          pathsFile = "${packingPlan}/${fileName}";
          paths = builtins.filter (x: x != "") (lib.splitString "\n" (builtins.readFile pathsFile));
        in stamp.tool.layer {
          name = "stamp-layer-nix-store";
          copy = builtins.map (p: { src = p; dest = p; }) paths;
          passthru = { inherit pathsFile paths; };
        };
        storeLayers = lib.mapAttrsToList mkStoreLayer (builtins.readDir packingPlan);
        registrationCopy = lib.optional withRegistration {
          src = "${closureInfo { rootPaths = storeRoots; }}/registration";
          dest = "/nix-path-registration";
        };
      in stamp.patch {
        inherit name env entrypoint cmd;
        appendLayers = storeLayers;
        copy = registrationCopy;
        runOnHost = runOnHost';
        passthru = { inherit storeRoots packingPlan storeLayers; } // passthru;
      };
  };
}
