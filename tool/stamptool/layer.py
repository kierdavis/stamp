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
    append_to_tar(
      tar_path=tar_path,
      src_path=pathlib.Path(entry["src"]).absolute(),
      dest_path=pathlib.PurePath(entry["dest"]),
      owner=entry.get("owner"),
      group=entry.get("group"),
      mtime=entry.get("mtime"),
    )

  if deriv_attrs.get("runOnHost"):
    run_on_host(tar_path, deriv_attrs["runOnHost"])

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


def run_on_host(
  tar_path,
  script,
):
  workdir = pathlib.Path("run-on-host")
  workdir.mkdir(parents=True, exist_ok=True)
  subprocess.run(
    ["bash", "-e"],
    cwd=workdir,
    input=script,
    encoding="utf-8",
    check=True,
  )
  append_to_tar(
    tar_path=tar_path,
    src_path=workdir,
    dest_path=pathlib.PurePath("/"),
  )


def append_to_tar(
  tar_path,
  src_path,
  dest_path,
  owner=None,
  group=None,
  mtime=None,
):
  if owner is None:
    owner = 0
  if group is None:
    group = owner
  if mtime is None:
    mtime = int(os.environ["SOURCE_DATE_EPOCH"])
  cmd = [
    "tar",
    "--append",
    f"--file={tar_path}",
    f"--owner={owner}",
    f"--group={group}",
    f"--mtime=@{mtime}",
    "--sort=name",
  ]
  if _is_numeric(owner):
    cmd.append("--numeric-owner")

  assert dest_path.is_absolute()
  if dest_path == pathlib.PurePath("/"):
    cmd += [f"--directory={src_path}"] + [x.name for x in src_path.iterdir()]
  else:
    cmd += [
      "--directory=/",
      "--transform=s|^" + str(src_path.relative_to("/")).replace("|", "\\|") + "|" + str(dest_path.relative_to("/")).replace("|", "\\|") + "|",
      str(src_path.relative_to("/")),
    ]
  subprocess.run(cmd, check=True)


def _is_numeric(val):
  try:
    int(val)
    return True
  except ValueError:
    return False
