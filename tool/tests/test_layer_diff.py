from pytest import raises
from stamptool import layer_diff
from stamptool.common import StampInternalError
from tarfile import DIRTYPE, REGTYPE, SYMTYPE
from testfixtures import compare
from .conftest import chdir, compare_dir_entries, compare_tar_entries, environment


def test_layer_diff(testdata, tmp_path):
  out_path = tmp_path / "out"
  with chdir(tmp_path / "workdir", mkdir=True):
    with environment(SOURCE_DATE_EPOCH="1001"):
      layer_diff.main({
        "copy": [
          {"src": str(testdata / "copysrc1"), "dest": "/copy"},
        ],
        "runOnHost": "ln -sfT my/link/target runonhost",
        "outputs": {"out": str(out_path)},
      })

  [tar_path, digest_path] = compare_dir_entries(out_path, expected=["diff.tar", "digest"])
  compare_tar_entries(tar_path, expected=[
    dict(name="copy", size=0, mtime=1001, type=DIRTYPE, uid=0, gid=0, uname="", gname=""),
    dict(name="copy/hello.txt", size=14, mtime=1001, mode=0o644, type=REGTYPE, uid=0, gid=0, uname="", gname=""),
    dict(name="copy/world.txt", size=0, mtime=1001, type=SYMTYPE, linkname="hello.txt", uid=0, gid=0, uname="", gname=""),
    dict(name="runonhost", size=0, mtime=1001, type=SYMTYPE, linkname="my/link/target", uid=0, gid=0, uname="", gname=""),
  ])
  compare(digest_path.read_text(), expected="sha256:dddf50b4b4a4feab2b3bb56c476e33e0efc0804b8ee66e1a2116bd9640d96c59")


def test_layer_diff_uid(testdata, tmp_path):
  out_path = tmp_path / "out"
  with chdir(tmp_path / "workdir", mkdir=True):
    with environment(SOURCE_DATE_EPOCH="1001"):
      layer_diff.main({
        "copy": [
          {"src": str(testdata / "copysrc1"), "dest": "/copy", "uid": 52},
        ],
        "runOnHost": "ln -sfT my/link/target runonhost",
        "runOnHostUID": 52,
        "outputs": {"out": str(out_path)},
      })

  [tar_path, digest_path] = compare_dir_entries(out_path, expected=["diff.tar", "digest"])
  compare_tar_entries(tar_path, expected=[
    dict(name="copy", size=0, mtime=1001, type=DIRTYPE, uid=52, gid=52, uname="", gname=""),
    dict(name="copy/hello.txt", size=14, mtime=1001, mode=0o644, type=REGTYPE, uid=52, gid=52, uname="", gname=""),
    dict(name="copy/world.txt", size=0, mtime=1001, type=SYMTYPE, linkname="hello.txt", uid=52, gid=52, uname="", gname=""),
    dict(name="runonhost", size=0, mtime=1001, type=SYMTYPE, linkname="my/link/target", uid=52, gid=52, uname="", gname=""),
  ])
  compare(digest_path.read_text(), expected="sha256:3362ee933c40adfc7dd39459c52ab97a2946bc05a0d316ed6cce239846eed6d2")


def test_layer_diff_uid_gid(testdata, tmp_path):
  out_path = tmp_path / "out"
  with chdir(tmp_path / "workdir", mkdir=True):
    with environment(SOURCE_DATE_EPOCH="1001"):
      layer_diff.main({
        "copy": [
          {"src": str(testdata / "copysrc1"), "dest": "/copy", "uid": 52, "gid": 59},
        ],
        "runOnHost": "ln -sfT my/link/target runonhost",
        "runOnHostUID": 52,
        "runOnHostGID": 59,
        "outputs": {"out": str(out_path)},
      })

  [tar_path, digest_path] = compare_dir_entries(out_path, expected=["diff.tar", "digest"])
  compare_tar_entries(tar_path, expected=[
    dict(name="copy", size=0, mtime=1001, type=DIRTYPE, uid=52, gid=59, uname="", gname=""),
    dict(name="copy/hello.txt", size=14, mtime=1001, mode=0o644, type=REGTYPE, uid=52, gid=59, uname="", gname=""),
    dict(name="copy/world.txt", size=0, mtime=1001, type=SYMTYPE, linkname="hello.txt", uid=52, gid=59, uname="", gname=""),
    dict(name="runonhost", size=0, mtime=1001, type=SYMTYPE, linkname="my/link/target", uid=52, gid=59, uname="", gname=""),
  ])
  compare(digest_path.read_text(), expected="sha256:8eda6c5bb71404ae4a6e4a2c3b7869b446650e4facf417e8448a96ec97d8bfbb")


def test_layer_diff_multiple_uids(testdata, tmp_path):
  out_path = tmp_path / "out"
  with chdir(tmp_path / "workdir", mkdir=True):
    with environment(SOURCE_DATE_EPOCH="1001"):
      with raises(StampInternalError):
        layer_diff.main({
          "copy": [
            {"src": str(testdata / "copysrc1"), "dest": "/copy", "uid": 52},
          ],
          "runOnHost": "ln -sfT my/link/target runonhost",
          "runOnHostUID": 53,
          "outputs": {"out": str(out_path)},
        })
