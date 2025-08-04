from stamptool import nix_packing_plan
from testfixtures import compare
from .conftest import compare_dir_entries


# Rationale for the closure structure used in this test:
#
#       ddd
#      /   \
#   bbb     fff
#   / \     / \
# aaa ccc eee ggg
#
# Expected analysis:
#   * The subtree with closureSize closest to 500 is the one rooted at bbb.
#     Since this closureSize is more than half the target layer size, the
#     algorithm should _not_ pull further subtrees into this layer.
#   * The first layer emitted should be aaa,bbb,ccc.
#   * Now, eee has the closest closureSize to 500, but it's not enough to fill
#     a layer to half the target, so the algorithm should pull more
#     subtrees into this layer.
#   * The subtree with the next closest closureSize to 500 is ggg.
#     Together with eee, this fills a layer to half the target.
#   * The second layer emitted should be eee,ggg.
#   * The third layer emitted should be fff.
#   * The fourth and final layer emitted should be ddd.
#


expected_plan = {
  "0000": "/mockstore/aaa\n/mockstore/bbb\n/mockstore/ccc\n",
  "0001": "/mockstore/eee\n/mockstore/ggg\n",
  "0002": "/mockstore/fff\n",
  "0003": "/mockstore/ddd\n",
}


def test_nix_packing_plan(testdata, tmp_path):
  out_dir = tmp_path / "out"
  nix_packing_plan.main({
    "closureInfo": str(testdata / "closureinfo1"),
    "targetLayerSize": 500,
    "outputs": {"out": str(out_dir)},
  })

  compare_dir_entries(out_dir, expected=expected_plan.keys())
  for filename, expected_content in expected_plan.items():
    compare((out_dir / filename).read_text(), expected=expected_content)
