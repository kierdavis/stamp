import os
import pathlib
import shutil
import subprocess
from .common import StampInternalError, load_manifest_and_config
from .runtime import Runtime


def main(deriv_attrs):
  if os.getuid() == 0:
    uid_handling = FullUIDHandling()
  else:
    uid_handling = HomogeneousUIDHandling(deriv_attrs)
  rt = Runtime()

  content_dir = pathlib.Path("content")
  content_dir.mkdir()
  do_copy(deriv_attrs.get("copy", []), content_dir, uid_handling)
  if deriv_attrs.get("runOnHost"):
    do_run_on_host(deriv_attrs["runOnHost"], content_dir)
  if deriv_attrs.get("runInContainer"):
    do_run_in_container(deriv_attrs, content_dir, rt)

  out_dir = pathlib.Path(deriv_attrs["outputs"]["out"])
  pack(content_dir, out_dir, uid_handling)


def do_copy(elems, content_dir, uid_handling):
  for elem in elems:
    src = pathlib.Path(elem["src"])
    dest = pathlib.PurePath(elem["dest"])
    assert dest.is_absolute()
    dest = content_dir / dest.relative_to("/")
    uid = elem.get("uid", 0)
    gid = elem.get("gid", uid)

    if src.is_dir() and not src.is_symlink():
      cmd = ["rsync", "--archive", "--mkpath"] + uid_handling.rsync_chown_opts(uid, gid) + [f"{src}/", f"{dest}/"]
      subprocess.run(cmd, check=True)
    else:
      dest.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(src, dest, follow_symlinks=False)
      uid_handling.chown(dest, uid, gid)


def do_run_on_host(script, content_dir):
  subprocess.run(
    ["bash", "-e"],
    input=script.encode("utf-8"),
    cwd=content_dir,
    check=True,
  )


def do_run_in_container(deriv_attrs, content_dir, rt):
  script = deriv_attrs["runInContainer"]
  if deriv_attrs.get("runInContainerBase"):
    img_oci_dir = pathlib.Path(deriv_attrs["runInContainerBase"])
    img_diffs_dir = pathlib.Path(deriv_attrs["runInContainerBaseDiffs"])
    _, img_config = load_manifest_and_config(img_oci_dir)
  else:
    img_config, img_diffs_dir = None, None
  rt.run(
    script=script,
    layer_content_dir=content_dir,
    img_config=img_config,
    img_diffs_dir=img_diffs_dir,
  )


def pack(content_dir, out_dir, uid_handling):
  out_dir.mkdir(parents=True, exist_ok=True)
  tar_path = out_dir / "diff.tar"
  digest_path = out_dir / "digest"

  tar_args = sorted(x.name for x in content_dir.iterdir())
  tar_proc = subprocess.Popen(
    [
      "tar",
      "--create",
      f"--directory={content_dir}",
      "--numeric-owner",
      f"--mtime=@{os.environ['SOURCE_DATE_EPOCH']}",
      "--sort=name",
    ] + uid_handling.pack_opts + tar_args,
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


def is_root():
  return os.getuid() == 0


class UIDHandling:
  pass


class FullUIDHandling(UIDHandling):
  def rsync_chown_opts(self, uid, gid):
    return [f"--chown={uid}:{gid}"]

  def chown(self, path, uid, gid):
    os.chown(path, uid, gid, follow_symlinks=False)

  @property
  def pack_opts(self):
    return []


class HomogeneousUIDHandling(UIDHandling):
  def __init__(self, deriv_attrs):
    uids_requested = set()
    gids_requested = set()
    for copy_elem in deriv_attrs.get("copy", []):
      uid = copy_elem.get("uid", 0)
      gid = copy_elem.get("gid", uid)
      uids_requested.add(uid)
      gids_requested.add(gid)
    if deriv_attrs.get("runOnHost"):
      uid = deriv_attrs.get("runOnHostUID", 0)
      gid = deriv_attrs.get("runOnHostGID", uid)
      uids_requested.add(uid)
      gids_requested.add(gid)
    if len(uids_requested) > 1:
      raise StampInternalError(f"Multiple UIDs referenced in copy/runOnHost arguments ({uids_requested!r}), but I am not running as root. This is an error in Stamp's Nix logic.")
    if len(gids_requested) > 1:
      raise StampInternalError(f"Multiple GIDs referenced in copy/runOnHost arguments ({gids_requested!r}), but I am not running as root. This is an error in Stamp's Nix logic.")
    [self.uid] = list(uids_requested)
    [self.gid] = list(gids_requested)

  def rsync_chown_opts(self, uid, gid):
    assert uid == self.uid
    assert gid == self.gid
    return []

  def chown(self, path, uid, gid):
    assert uid == self.uid
    assert gid == self.gid

  @property
  def pack_opts(self):
    return [f"--owner={self.uid}", f"--group={self.gid}"]
