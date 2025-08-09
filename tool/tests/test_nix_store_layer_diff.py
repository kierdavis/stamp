import hashlib
from stamptool import nix_store_layer_diff
from tarfile import DIRTYPE, REGTYPE, SYMTYPE
from testfixtures import compare
from .conftest import compare_dir_entries, compare_tar_entries, environment


def test_nix_store_layer_diff(testdata, tmp_path):
  src_path = (testdata / "copysrc1").absolute()
  out_path = tmp_path / "out"
  with environment(SOURCE_DATE_EPOCH="1001"):
    nix_store_layer_diff.main({
      "paths": [str(src_path)],
      "outputs": {"out": str(out_path)},
    })

  path_in_tar = src_path.relative_to("/")

  [tar_path, digest_path] = compare_dir_entries(out_path, expected=["diff.tar", "digest"])
  compare_tar_entries(tar_path, expected=[
    dict(name=str(path_in_tar), size=0, mtime=1001, type=DIRTYPE, uid=0, gid=0, uname="", gname=""),
    dict(name=str(path_in_tar / "hello.txt"), size=14, mtime=1001, mode=0o644, type=REGTYPE, uid=0, gid=0, uname="", gname=""),
    dict(name=str(path_in_tar / "world.txt"), size=0, mtime=1001, type=SYMTYPE, linkname="hello.txt", uid=0, gid=0, uname="", gname=""),
  ])

  # We can't hardcode the expected digest here because the filenames in the
  # archive are based on the location of testdata on the build host.
  h = hashlib.sha256()
  with open(tar_path, "rb") as f:
    while True:
      chunk = f.read(4096)
      if not chunk:
        break
      h.update(chunk)
  compare(digest_path.read_text(), expected="sha256:" + h.hexdigest())
