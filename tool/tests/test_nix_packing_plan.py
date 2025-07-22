from stamptool import nix_packing_plan
from testfixtures import compare
from textwrap import dedent
from .conftest import compare_dir_entries


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
closure_info = [
  {
    "path": "/mockstore/aaa",
    "narSize": 266,
    "closureSize": 266,
    "references": [],
  },
  {
    "path": "/mockstore/bbb",
    "narSize": 100,
    "closureSize": 405,
    "references": ["/mockstore/aaa", "/mockstore/bbb", "/mockstore/ccc"],
  },
  {
    "path": "/mockstore/ccc",
    "narSize": 39,
    "closureSize": 39,
    "references": [],
  },
  {
    "path": "/mockstore/ddd",
    "narSize": 45,
    "closureSize": 1660,
    "references": ["/mockstore/bbb", "/mockstore/fff"],
  },
  {
    "path": "/mockstore/eee",
    "narSize": 221,
    "closureSize": 221,
    "references": [],
  },
  {
    "path": "/mockstore/fff",
    "narSize": 901,
    "closureSize": 1210,
    "references": ["/mockstore/eee", "/mockstore/ggg"],
  },
  {
    "path": "/mockstore/ggg",
    "narSize": 88,
    "closureSize": 88,
    "references": [],
  },
]


expected_plan = {
  "0000": "/mockstore/aaa\n/mockstore/bbb\n/mockstore/ccc\n",
  "0001": "/mockstore/eee\n/mockstore/ggg\n",
  "0002": "/mockstore/fff\n",
  "0003": "/mockstore/ddd\n",
}


def test_nix_packing_plan(tmp_path):
  out_dir = tmp_path / "out"
  nix_packing_plan.main({
    "closureInfo": closure_info,
    "targetLayerSize": 500,
    "outputs": {"out": str(out_dir)},
  })

  compare_dir_entries(out_dir, expected=expected_plan.keys())
  for filename, expected_content in expected_plan.items():
    compare((out_dir / filename).read_text(), expected=expected_content)
