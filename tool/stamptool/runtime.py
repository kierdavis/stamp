import contextlib
import itertools
import os
import pathlib
import shlex
import subprocess
import sys


class Runtime:
  def __init__(self):
    tmp_root = pathlib.Path("rt")
    tmp_root.mkdir()
    self.tmp_dirs = (tmp_root / str(i) for i in itertools.count())
    self.diff_extract_dirs = {}


  def extract_diff(self, img_diffs_dir, digest):
    try:
      return self.diff_extract_dirs[digest]
    except KeyError:
      pass
    tarball_path = img_diffs_dir / digest.replace(":", "/")
    self.diff_extract_dirs[digest] = extract_dir = next(self.tmp_dirs)
    extract_dir.mkdir(parents=True, exist_ok=True)
    print(f"extracting {tarball_path} to {extract_dir}...", file=sys.stderr)
    subprocess.run(
      ["tar", "--extract", f"--file={tarball_path}", f"--directory={extract_dir}"],
      stdin=subprocess.DEVNULL,
      stdout=sys.stderr,
      check=True,
    )
    return extract_dir


  @contextlib.contextmanager
  def overlay_mounted(self, *, lowerdirs, upperdir=None, options=[]):
    all_options = [f"lowerdir={':'.join(map(str, lowerdirs))}"]
    if upperdir is not None:
      workdir = next(self.tmp_dirs)
      workdir.mkdir(parents=True, exist_ok=True)
      all_options += [f"upperdir={upperdir}", f"workdir={workdir}"]
    if options:
      all_options.extend(options)
    mountpoint = next(self.tmp_dirs)
    mountpoint.mkdir(parents=True, exist_ok=True)
    mount_cmd = ["mount", "-toverlay", "-o" + ",".join(all_options), "overlay", str(mountpoint)]
    print(" ".join(mount_cmd), file=sys.stderr)
    try:
      subprocess.run(mount_cmd, stdin=subprocess.DEVNULL, stdout=sys.stderr, check=True)
    except subprocess.CalledProcessError:
      subprocess.run(["dmesg"], stdout=sys.stderr)
      raise
    try:
      yield mountpoint
    finally:
      subprocess.run(["umount", str(mountpoint)], stdin=subprocess.DEVNULL, stdout=sys.stderr)


  def mount_image(self, *, ctx, config, diffs_dir, upperdir=None):
    # lowerdirs[0] is the topmost layer, lowerdirs[-1] is the bottommost layer - same order as required by overlayfs mount option.
    curr_tier_lowerdirs = [
      self.extract_diff(diffs_dir, digest)
      for digest in reversed(config["rootfs"]["diff_ids"])
    ]

    max_lowerdirs_per_overlay = 28  # by experimentation
    next_tier_lowerdirs = []
    while len(curr_tier_lowerdirs) + len(next_tier_lowerdirs) > max_lowerdirs_per_overlay:
      group_size = min(max_lowerdirs_per_overlay + 1, len(curr_tier_lowerdirs))
      group_mountpoint = ctx.enter_context(self.overlay_mounted(
        lowerdirs = curr_tier_lowerdirs[-group_size+1:],
        upperdir = curr_tier_lowerdirs[-group_size],
        options = ["ro"],
      ))
      curr_tier_lowerdirs = curr_tier_lowerdirs[:-group_size]
      next_tier_lowerdirs.insert(0, group_mountpoint)
      if not curr_tier_lowerdirs:
        curr_tier_lowerdirs = next_tier_lowerdirs
        next_tier_lowerdirs = []

    return ctx.enter_context(self.overlay_mounted(
      lowerdirs = curr_tier_lowerdirs + next_tier_lowerdirs,
      upperdir = upperdir,
      options = ["volatile"] if upperdir is not None else ["ro"],
    ))


  def run(self, *, script, layer_content_dir, img_config=None, img_diffs_dir=None):
    with contextlib.ExitStack() as ctx:
      if img_config is not None:
        assert img_diffs_dir is not None
        root_fs = self.mount_image(
          ctx=ctx,
          config=img_config,
          diffs_dir=img_diffs_dir,
          upperdir=layer_content_dir,
        )
      else:
        root_fs = layer_content_dir

      for subdir in ["dev", "proc", "sys"]:
        ctx.enter_context(ephemeral_dir(root_fs / subdir))

      env = list(img_config.get("config", {}).get("Env", []))
      for var_name in ["SOURCE_DATE_EPOCH"]:
        if var_name in os.environ:
          env.insert(0, f"{var_name}={os.environ[var_name]}")

      cmd = [
        "unshare", "-imnpuf", "--mount-proc",
        "sh", "-euc",
        f"""
          for x in dev proc sys; do
            mount --rbind /$x {quote(root_fs)}/$x;
          done
          exec env --ignore-environment {' '.join(map(quote, env))} "$(type -p chroot)" {quote(root_fs)} sh -euc {quote(script)}
        """,
      ]
      print(" ".join(quote(word) for word in cmd), file=sys.stderr)
      subprocess.run(cmd, check=True)


@contextlib.contextmanager
def ephemeral_dir(path):
  path = pathlib.Path(path)
  if path.exists():
    yield
  else:
    path.mkdir(parents=True, exist_ok=True)
    try:
      yield
    finally:
      try:
        path.rmdir()
      except:
        pass


def quote(x):
  return shlex.quote(str(x))
