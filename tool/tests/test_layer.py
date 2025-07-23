from stamptool import layer
from tarfile import DIRTYPE, REGTYPE, SYMTYPE
from testfixtures import compare
from .conftest import compare_dir_entries, compare_tar_entries, environment


def test_layer(testdata, tmp_path):
  blob_out_path = tmp_path / "blob"
  diff_out_path = tmp_path / "diff"
  with environment(SOURCE_DATE_EPOCH="1001"):
    layer.main({
      "copy": [
        {"src": str(testdata / "copysrc1"), "dest": "/copy/root", "owner": 0},
        {"src": str(testdata / "copysrc1"), "dest": "/copy/nonroot", "owner": 123},
      ],
      "runOnHost": "mkdir runonhost",
      "outputs": {
        "out": str(blob_out_path),
        "diff": str(diff_out_path),
      },
    })

  expected_entries = [
    dict(name="copy/root", size=0, mtime=1001, type=DIRTYPE, uid=0, gid=0, uname="", gname=""),
    dict(name="copy/root/hello.txt", size=14, mtime=1001, mode=0o644, type=REGTYPE, uid=0, gid=0, uname="", gname=""),
    dict(name="copy/root/world.txt", size=0, mtime=1001, type=SYMTYPE, linkname="hello.txt", uid=0, gid=0, uname="", gname=""),
    dict(name="copy/nonroot", size=0, mtime=1001, type=DIRTYPE, uid=123, gid=123, uname="", gname=""),
    dict(name="copy/nonroot/hello.txt", size=14, mtime=1001, mode=0o644, type=REGTYPE, uid=123, gid=123, uname="", gname=""),
    dict(name="copy/nonroot/world.txt", size=0, mtime=1001, type=SYMTYPE, linkname="hello.txt", uid=123, gid=123, uname="", gname=""),
    dict(name="runonhost", size=0, mtime=1001, type=DIRTYPE, uid=0, gid=0, uname="", gname=""),
  ]

  [diff_data_path, diff_digest_path] = compare_dir_entries(diff_out_path, expected=["diff.tar", "digest"])
  compare_tar_entries(diff_data_path, expected=expected_entries)
  compare(diff_digest_path.read_text(), expected="sha256:4983abca8eaf9fb3fafc39d5c3b2dbb7a6d5677e503b73ede3f1773ba8f94852")
  [blob_data_path, blob_digest_path] = compare_dir_entries(blob_out_path, expected=["blob.tar.gz", "digest"])
  compare_tar_entries(blob_data_path, expected=expected_entries)
  compare(blob_digest_path.read_text(), expected="sha256:966b39b3c6a9352e2245959b9dca8dd1d1f57d0d3fa6ff3f6b1a798444d315d4")
