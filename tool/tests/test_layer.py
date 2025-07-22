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
        {"src": str(testdata / "copysrc1"), "dest": "/data/root", "owner": 0},
        {"src": str(testdata / "copysrc1"), "dest": "/data/nonroot", "owner": 123},
      ],
      "outputs": {
        "out": str(blob_out_path),
        "diff": str(diff_out_path),
      },
    })

  expected_entries = [
    dict(name="data/root", size=0, mtime=1001, type=DIRTYPE, uid=0, gid=0, uname="", gname=""),
    dict(name="data/root/hello.txt", size=14, mtime=1001, mode=0o644, type=REGTYPE, uid=0, gid=0, uname="", gname=""),
    dict(name="data/root/world.txt", size=0, mtime=1001, type=SYMTYPE, linkname="hello.txt", uid=0, gid=0, uname="", gname=""),
    dict(name="data/nonroot", size=0, mtime=1001, type=DIRTYPE, uid=123, gid=123, uname="", gname=""),
    dict(name="data/nonroot/hello.txt", size=14, mtime=1001, mode=0o644, type=REGTYPE, uid=123, gid=123, uname="", gname=""),
    dict(name="data/nonroot/world.txt", size=0, mtime=1001, type=SYMTYPE, linkname="hello.txt", uid=123, gid=123, uname="", gname=""),
  ]

  [diff_data_path, diff_digest_path] = compare_dir_entries(diff_out_path, expected=["diff.tar", "digest"])
  compare_tar_entries(diff_data_path, expected=expected_entries)
  compare(diff_digest_path.read_text(), expected="sha256:6c3f6a1afc46b112c77dcc5aa2bf52324540d0e4cfdbbe8082e381145c03af99")
  [blob_data_path, blob_digest_path] = compare_dir_entries(blob_out_path, expected=["blob.tar.gz", "digest"])
  compare_tar_entries(blob_data_path, expected=expected_entries)
  compare(blob_digest_path.read_text(), expected="sha256:c6227c139487484a49156254449fde77d7c4462575d89c88939dafedbb03ac62")
