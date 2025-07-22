import os
import pathlib
import subprocess


def main(deriv_attrs):
  blob_dir = pathlib.Path(deriv_attrs["outputs"]["out"])
  blob_dir.mkdir(parents=True, exist_ok=True)
  tar_gz_path = blob_dir / "blob.tar.gz"

  diff_dir = pathlib.Path(deriv_attrs["outputs"]["diff"])
  diff_dir.mkdir(parents=True, exist_ok=True)
  tar_path = diff_dir / "diff.tar"

  source_date_epoch = os.environ["SOURCE_DATE_EPOCH"]

  for entry in deriv_attrs.get("copy", []):
    src = pathlib.Path(entry["src"]).absolute()
    dest = pathlib.PurePath(entry["dest"])
    assert dest.is_absolute()
    owner = entry.get("owner", 0)
    group = entry.get("group", owner)
    opts = [
      "--append",
      "--directory=/",
      f"--file={tar_path}",
      f"--owner={owner}",
      f"--group={group}",
      f"--mtime=@{source_date_epoch}",
      "--sort=name",
    ]
    if _is_numeric(owner):
      opts.append("--numeric-owner")
    if src != dest:
      opts.append("--transform=s|^" + str(src.relative_to("/")).replace("|", "\\|") + "|" + str(dest.relative_to("/")).replace("|", "\\|") + "|")
    subprocess.run(
      ["tar"] + opts + [str(src.relative_to("/"))],
      check=True,
    )

  n_cores = os.environ.get("NIX_BUILD_CORES", "1")
  diff_digest_proc = subprocess.Popen(
    ["sha256sum", str(tar_path)],
    stdout=subprocess.PIPE,
  )
  gzip_proc = subprocess.Popen(
    [
      "pigz",
      "--stdout",
      "--processes", n_cores,
      "--no-name",
      "--no-time",
      str(tar_path),
    ],
    stdout=subprocess.PIPE,
  )
  tee_proc = subprocess.Popen(
    ["tee", str(tar_gz_path)],
    stdin=gzip_proc.stdout,
    stdout=subprocess.PIPE,
  )
  blob_digest_proc = subprocess.Popen(
    ["sha256sum"],
    stdin=tee_proc.stdout,
    stdout=subprocess.PIPE,
  )

  for proc in [diff_digest_proc, gzip_proc, tee_proc, blob_digest_proc]:
    if proc.wait() != 0:
      raise subprocess.CalledProcessError(returncode=proc.returncode, cmd=repr(proc.args))

  blob_digest = b"sha256:" + blob_digest_proc.stdout.read().split()[0]
  (blob_dir / "digest").write_bytes(blob_digest)

  diff_digest = b"sha256:" + diff_digest_proc.stdout.read().split()[0]
  (diff_dir / "digest").write_bytes(diff_digest)


def _is_numeric(val):
  try:
    int(val)
    return True
  except ValueError:
    return False
