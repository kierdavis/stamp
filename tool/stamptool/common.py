import json
import platform
from dataclasses import dataclass


@dataclass(frozen=True)
class Platform:
  arch: str
  os: str

  @classmethod
  def current(cls):
    return cls(
      arch={
        "x86_64": "amd64",
      }[platform.machine()],
      os={
        "Linux": "linux",
      }[platform.system()],
    )


class InvalidImageError(Exception):
  pass


class PlatformMismatch(Exception):
  pass


class StampInternalError(Exception):
  pass


def iter_index_recursive(oci_dir, index_path=None):
  if index_path is None:
    index_path = oci_dir / "index.json"
  with open(index_path, "r") as f:
    index = json.load(f)
  if index.get("mediaType") not in (None, "application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json"):
    raise InvalidImageError(f"document at {index_path} has unrecognised mediaType {index['mediaType']!r} (expected an index)")
  for manifest_ref in index["manifests"]:
    if manifest_ref["mediaType"] in ("application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json"):
      nested_index_path = oci_dir / "blobs" / manifest_ref["digest"].replace(":", "/")
      yield from iter_index_recursive(oci_dir, nested_index_path)
    elif manifest_ref["mediaType"] in ("application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"):
      yield manifest_ref
    else:
      raise InvalidImageError(f"blob {manifest_ref['digest']} referenced by index at {index_path} has unrecognised mediaType {manifest_ref['mediaType']!r}")


def manifest_matches_platform(manifest_ref, desired_plat):
  arch = manifest_ref.get("platform", {}).get("architecture")
  arch_ok = arch is None or arch == desired_plat.arch
  os = manifest_ref.get("platform", {}).get("os")
  os_ok = os is None or os == desired_plat.os
  return arch_ok and os_ok


def load_manifest_and_config(oci_dir, desired_plat=Platform.current()):
  manifest_refs = [ref for ref in iter_index_recursive(oci_dir) if manifest_matches_platform(ref, desired_plat)]
  if not manifest_refs:
    raise PlatformMismatch("no manifest is suitable for desired platform")
  if len(manifest_refs) > 1:
    raise PlatformMismatch("multiple manifests are suitable for desired platform")
  [manifest_ref] = manifest_refs

  manifest_path = oci_dir / "blobs" / manifest_ref["digest"].replace(":", "/")
  with open(manifest_path, "r") as f:
    manifest = json.load(f)
  if manifest["mediaType"] not in ("application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"):
    raise InvalidImageError(f"manifest {manifest_path} has unrecognised mediaType: {manifest['mediaType']}")

  config_path = oci_dir / "blobs" / manifest["config"]["digest"].replace(":", "/")
  with open(config_path, "r") as f:
    config = json.load(f)
  if config["rootfs"]["type"] != "layers":
    raise InvalidImageError(f"expected rootfs.type to be 'layers' in {config_path}")

  return manifest, config
