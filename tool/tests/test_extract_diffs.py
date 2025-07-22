from stamptool import extract_diffs
from testfixtures import compare
from .conftest import compare_dir_entries


def test_extract_diffs(testdata, tmp_path):
  out_path = tmp_path / "out"
  extract_diffs.main({
    "oci": str(testdata / "image1"),
    "outputs": {"out": str(out_path)},
  })

  [sha256_path] = compare_dir_entries(out_path, expected=["sha256"])
  [diff_path] = compare_dir_entries(sha256_path, expected=["6b40aa9e85fff948c00254614ad3e394b7232aa052d3ba7492f599bd0c01ff1b"])
  compare(diff_path.stat().st_size, expected=3072)
