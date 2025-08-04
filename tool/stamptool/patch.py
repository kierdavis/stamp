import json
import hashlib
import pathlib
from dataclasses import dataclass
from .common import load_manifest_and_config, Platform


def oci_main(deriv_attrs):
  out = pathlib.Path(deriv_attrs["outputs"]["out"])
  manifest_path = pathlib.Path(deriv_attrs["outputs"]["manifest"])
  config_path = pathlib.Path(deriv_attrs["outputs"]["config"])
  (out / "blobs/sha256").mkdir(parents=True, exist_ok=True)

  if deriv_attrs.get("base") is not None:
    base = pathlib.Path(deriv_attrs["base"])
    manifest, config = load_manifest_and_config(base)
    symlink_base_layer_blobs(base, out, manifest)
  else:
    manifest, config = EMPTY_MANIFEST, EMPTY_CONFIG

  new_layers = list(parse_new_layers(deriv_attrs.get("appendLayers", [])))
  symlink_new_layer_blobs(new_layers, out)
  patch_config(deriv_attrs, new_layers, manifest, config)

  new_config_blob = json.dumps(config, separators=(",", ":"), sort_keys=True).encode("utf-8")
  new_config_digest = "sha256:" + hashlib.sha256(new_config_blob).hexdigest()
  config_path.write_bytes(new_config_blob)
  (out / "blobs" / new_config_digest.replace(":", "/")).symlink_to(config_path)

  manifest["config"]["digest"] = new_config_digest
  manifest["config"]["size"] = len(new_config_blob)
  new_manifest_blob = json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode("utf-8")
  new_manifest_digest = "sha256:" + hashlib.sha256(new_manifest_blob).hexdigest()
  manifest_path.write_bytes(new_manifest_blob)
  (out / "blobs" / new_manifest_digest.replace(":", "/")).symlink_to(manifest_path)

  with open(out / "index.json", "w") as f:
    json.dump({
      "schemaVersion": 2,
      "mediaType": "application/vnd.oci.image.index.v1+json",
      "manifests": [{
        "mediaType": manifest["mediaType"],
        "digest": new_manifest_digest,
        "size": len(new_manifest_blob),
      }],
    }, f, separators=(",", ":"), sort_keys=True)

  (out / "oci-layout").write_text("""{"imageLayoutVersion":"1.0.0"}""")


def diffs_main(deriv_attrs):
  out = pathlib.Path(deriv_attrs["outputs"]["out"])
  (out / "sha256").mkdir(parents=True, exist_ok=True)

  if deriv_attrs.get("base") is not None:
    base_oci = pathlib.Path(deriv_attrs["base"])
    base_diffs = pathlib.Path(deriv_attrs["baseDiffs"])
    _, config = load_manifest_and_config(base_oci)
    symlink_base_layer_diffs(base_diffs, out, config)

  new_layers = list(parse_new_layers(deriv_attrs.get("appendLayers", [])))
  symlink_new_layer_diffs(new_layers, out)


def patch_config(deriv_attrs, new_layers, manifest, config):
  for new_layer in new_layers:
    append_layer(new_layer, manifest, config)
  apply_env(deriv_attrs.get("env", {}), config)
  if deriv_attrs.get("entrypoint") is not None:
    config.setdefault("config", {})["Entrypoint"] = deriv_attrs["entrypoint"]
  if deriv_attrs.get("cmd") is not None:
    config.setdefault("config", {})["Cmd"] = deriv_attrs["cmd"]
  if deriv_attrs.get("workingDir") is not None:
    config.setdefault("config", {})["WorkingDir"] = deriv_attrs["workingDir"]


def append_layer(layer, manifest, config):
  config.setdefault("rootfs", []).setdefault("diff_ids", []).append(layer.diff_digest)
  config.setdefault("history", []).append({"created_by": "stamp.patch"})
  manifest.setdefault("layers", []).append({
    "mediaType": {
      "application/vnd.oci.image.manifest.v1+json": "application/vnd.oci.image.layer.v1.tar+gzip",
      "application/vnd.docker.distribution.manifest.v2+json": "application/vnd.docker.image.rootfs.diff.tar.gzip",
    }[manifest["mediaType"]],
    "digest": layer.blob_digest,
    "size": layer.blob_size,
  })


def apply_env(new, config):
  if new:
    entries = config.get("config", {}).get("Env", [])
    for name, value in new.items():
      entries = [entry for entry in entries if not entry.startswith(name + "=")]
      entries.append(f"{name}={value}")
    config.setdefault("config", {})["Env"] = entries


def symlink_base_layer_blobs(base, out, manifest):
  for blob_ref in manifest.get("layers", []):
    rel = blob_ref["digest"].replace(":", "/")
    (out / "blobs" / rel).symlink_to(base / "blobs" / rel)


def symlink_base_layer_diffs(base, out, config):
  for diff_digest in config.get("rootfs", {}).get("diff_ids", []):
    rel = diff_digest.replace(":", "/")
    (out / rel).symlink_to(base / rel)


def symlink_new_layer_blobs(layers, out):
  for layer in layers:
    rel = layer.blob_digest.replace(":", "/")
    (out / "blobs" / rel).symlink_to(layer.blob_tarball)


def symlink_new_layer_diffs(layers, out):
  for layer in layers:
    rel = layer.diff_digest.replace(":", "/")
    (out / rel).symlink_to(layer.diff_tarball)


@dataclass(frozen=True)
class NewLayer:
  diff_dir: pathlib.Path
  blob_dir: pathlib.Path

  @property
  def diff_tarball(self):
    return self.diff_dir / "diff.tar"

  @property
  def blob_tarball(self):
    return self.blob_dir / "blob.tar.gz"

  @property
  def blob_size(self):
    return self.blob_tarball.stat().st_size

  @property
  def diff_digest(self):
    return (self.diff_dir / "digest").read_text().strip()

  @property
  def blob_digest(self):
    return (self.blob_dir / "digest").read_text().strip()


def parse_new_layers(superdirs):
  for superdir in superdirs:
    for subdir in sorted(pathlib.Path(superdir).iterdir()):
      yield NewLayer(
        diff_dir = (subdir / "diff").resolve(),
        blob_dir = (subdir / "blob").resolve(),
      )


EMPTY_CONFIG = {
  "architecture": Platform.current().arch,
  "os": Platform.current().os,
  "rootfs": {
    "type": "layers",
    "diff_ids": [],
  },
}

EMPTY_MANIFEST = {
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.manifest.v1+json",
  "config": {
    "mediaType": "application/vnd.oci.image.config.v1+json",
    "digest": None, # will be overwritten later
    "size": None,   # will be overwritten later
  },
  "layers": []
}
