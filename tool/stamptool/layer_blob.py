import os
import pathlib
import subprocess


def main(deriv_attrs):
  diff_path = pathlib.Path(deriv_attrs["diff"]) / "diff.tar"

  out_path = pathlib.Path(deriv_attrs["outputs"]["out"])
  out_path.mkdir(parents=True, exist_ok=True)
  blob_path = out_path / "blob.tar.gz"
  digest_path = out_path / "digest"

  pigz_proc = subprocess.Popen(
    [
      "pigz",
      "--stdout",
      "--processes", os.environ.get("NIX_BUILD_CORES", "1"),
      "--no-name",
      "--no-time",
      str(diff_path),
    ],
    stdout=subprocess.PIPE,
  )
  tee_proc = subprocess.Popen(
    ["tee", str(blob_path)],
    stdin=pigz_proc.stdout,
    stdout=subprocess.PIPE,
  )
  sha256sum_proc = subprocess.Popen(
    ["sha256sum"],
    stdin=tee_proc.stdout,
    stdout=subprocess.PIPE,
  )
  for proc in [pigz_proc, tee_proc, sha256sum_proc]:
    if proc.wait() != 0:
      raise subprocess.CalledProcessError(returncode=proc.returncode, cmd=repr(proc.args))

  digest_path.write_bytes(b"sha256:" + sha256sum_proc.stdout.read().split()[0])

