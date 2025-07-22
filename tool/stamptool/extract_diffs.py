import json
import os
import pathlib
import subprocess
from .common import iter_index_recursive, InvalidImageError


def main(deriv_attrs):
  oci_dir = pathlib.Path(deriv_attrs["oci"])
  out_dir = pathlib.Path(deriv_attrs["outputs"]["out"])

  layers_to_unpack = {
    blob_digest: compression_algo
    for manifest_ref in iter_index_recursive(oci_dir)
    for blob_digest, compression_algo in iter_manifest_layers(oci_dir, manifest_ref)
  }

  (out_dir / "sha256").mkdir(parents=True, exist_ok=True)
  for blob_digest, compression_algo in layers_to_unpack.items():
    blob_path = oci_dir / "blobs" / blob_digest.replace(":", "/")
    diff_staging_path = out_dir / "staging"
    diff_digest = decompress_and_digest(blob_path, diff_staging_path, compression_algo)
    diff_staging_path.rename(out_dir / diff_digest.replace(":", "/"))


def iter_manifest_layers(oci_dir, manifest_ref):
  manifest_path = oci_dir / "blobs" / manifest_ref["digest"].replace(":", "/")
  with open(manifest_path, "r") as f:
    manifest = json.load(f)
  if manifest["mediaType"] not in ("application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"):
    raise InvalidImageError(f"document at {manifest_path} has unrecognised mediaType: {manifest['mediaType']!r} (expected a manifest)")
  for layer_ref in manifest["layers"]:
    if layer_ref["mediaType"] in ("application/vnd.oci.image.layer.v1.tar+gzip", "application/vnd.docker.image.rootfs.diff.tar.gzip"):
      yield layer_ref["digest"], "gzip"
    elif layer_ref["mediaType"] in ("application/vnd.in-toto+json",):
      pass # This "layer" is some kind of metadata, not a diff. Do nothing.
    else:
      raise InvalidImageError(f"blob {layer_ref['digest']} referenced by manifest at {manifest_path} has unrecognised mediaType {layer_ref['mediaType']!r}")


def decompress_and_digest(in_path, out_path, compression_algo):
  n_cores = os.environ.get("NIX_BUILD_CORES", "1")
  decompress_proc = subprocess.Popen(
    {
      "gzip": ["unpigz", "--stdout", "--processes", n_cores, str(in_path)],
    }[compression_algo],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
  )
  tee_proc = subprocess.Popen(
    ["tee", str(out_path)],
    stdin=decompress_proc.stdout,
    stdout=subprocess.PIPE,
  )
  sha256sum_proc = subprocess.Popen(
    ["sha256sum"],
    stdin=tee_proc.stdout,
    stdout=subprocess.PIPE,
  )
  for proc in [decompress_proc, tee_proc, sha256sum_proc]:
    if proc.wait() != 0:
      raise subprocess.CalledProcessError(returncode=proc.returncode, cmd=repr(proc.args))
  return "sha256:" + sha256sum_proc.stdout.read().decode("ascii").split()[0]
