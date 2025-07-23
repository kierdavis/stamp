import os
import pathlib
import subprocess


def main(deriv_attrs):
  out_path = pathlib.Path(deriv_attrs["outputs"]["out"])
  out_path.mkdir(parents=True, exist_ok=True)
  tar_path = out_path / "diff.tar"
  digest_path = out_path / "digest"

  paths = sorted(deriv_attrs["paths"])
  assert all(p.startswith("/") for p in paths)

  tar_proc = subprocess.Popen(
    [
      "tar",
      "--create",
      "--directory=/",
      "--owner=0",
      "--group=0",
      "--numeric-owner",
      f"--mtime=@{os.environ['SOURCE_DATE_EPOCH']}",
      "--sort=name",
    ] + [p.lstrip("/") for p in paths],
    stdout=subprocess.PIPE,
  )
  tee_proc = subprocess.Popen(
    ["tee", str(tar_path)],
    stdin=tar_proc.stdout,
    stdout=subprocess.PIPE,
  )
  sha256sum_proc = subprocess.Popen(
    ["sha256sum"],
    stdin=tee_proc.stdout,
    stdout=subprocess.PIPE,
  )
  for proc in [tar_proc, tee_proc, sha256sum_proc]:
    if proc.wait() != 0:
      raise subprocess.CalledProcessError(returncode=proc.returncode, cmd=repr(proc.args))

  digest_path.write_bytes(b"sha256:" + sha256sum_proc.stdout.read().split()[0])
