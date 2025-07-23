from stamptool import layer_blob
from tarfile import DIRTYPE, REGTYPE, SYMTYPE
from testfixtures import compare
from .conftest import compare_dir_entries, compare_tar_entries, environment


def test_layer_blob(testdata, tmp_path):
  out_path = tmp_path / "out"
  layer_blob.main({
    "diff": str(testdata / "layer1/diff"),
    "outputs": {"out": str(out_path)},
  })

  [tar_path, digest_path] = compare_dir_entries(out_path, expected=["blob.tar.gz", "digest"])
  compare_tar_entries(tar_path, expected=[
    dict(name="bin", size=0, mtime=1753201736, type=DIRTYPE, uid=0, gid=0, uname="", gname=""),
    dict(name="bin/sh", size=0, mtime=1753201736, type=SYMTYPE, linkname="bash", uid=0, gid=0, uname="", gname=""),
  ])
  compare(digest_path.read_text(), expected="sha256:d425f61ceda903c7d845908ac3289b251677810955dabb4b01ecb266d2e6bf94")
