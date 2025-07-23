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
  compare(digest_path.read_text(), expected="sha256:520c1e8da14bd3000d689ae900c8383d3516147b22b3e9101a1346a78fa21aa1")
