let
  defaultTargetLayerSize = 128 * 1024 * 1024; # bytes

  # Given a string, return a (non unique) list of all the top-level Nix
  # store paths mentioned in the string.
  findStorePaths = str:
    builtins.map (groups: builtins.elemAt groups 0)
      (builtins.filter builtins.isList
        (builtins.split "(${builtins.storeDir}/[0-9a-z]{32}-[-.+_?=0-9a-zA-Z]+)" str));
in

self: super: with self; {
  stamp = {
    tool = callPackage ../tool {};

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
      , env ? {}
      , entrypoint ? null
      , cmd ? null
      , passthru ? {}
      }:
      let
        implicitLayer = if builtins.length copy != 0
          then stamp.tool.layer { inherit copy; name = "${name}-newlayer"; }
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
      , symlink ? []
      , env ? {}
      , entrypoint ? null
      , cmd ? null
      , targetLayerSize ? defaultTargetLayerSize # bytes
      , withRegistration ? false
      , withConveniences ? true
      , passthru ? {}
      }:
      let
        symlink' = symlink ++ lib.optionals withConveniences [
          { link = "/bin/bash"; target = "sh"; }
          { link = "/bin/sh"; target = "${bash}/bin/sh"; }
          { link = "/etc/ssl/certs/ca-bundle.crt"; target = "${cacert}/etc/ssl/certs/ca-bundle.crt"; }
        ];
        storeRoots = lib.concatMap findStorePaths (
          builtins.map (x: x.target) symlink'
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
          paths = builtins.filter (x: x != "") (lib.strings.splitString "\n" (builtins.readFile pathsFile));
        in stamp.tool.layer {
          name = "stamp-layer-nix-store";
          copy = builtins.map (p: { src = p; dest = p; owner = 0; group = 0; }) paths;
          passthru = { inherit pathsFile paths; };
        };
        storeLayers = lib.attrsets.mapAttrsToList mkStoreLayer (builtins.readDir packingPlan);
        copySymlinks = map (x: {
          src = runCommand "symlink" { inherit (x) target; } ''ln -sfT "$target" "$out"'';
          dest = x.link;
          owner = x.owner or 0;
          group = x.group or 0;
        }) symlink';
        copyRegistration = lib.optional withRegistration {
          src = "${closureInfo { rootPaths = storeRoots; }}/registration";
          dest = "/nix-path-registration";
          owner = 0;
          group = 0;
        };
      in stamp.patch {
        inherit name env entrypoint cmd;
        appendLayers = storeLayers;
        copy = copySymlinks ++ copyRegistration;
        passthru = { inherit storeRoots packingPlan storeLayers; } // passthru;
      };
  };
}
