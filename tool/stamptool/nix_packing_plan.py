import graphlib
import pathlib
from dataclasses import dataclass, field


def main(deriv_attrs):
  dep_graph = DepGraph(deriv_attrs["closureInfo"])

  # The overall approach is to iteratively remove subtrees from the dependency
  # graph, assigning each one to a layer.
  layers = []
  layer = Layer()
  target_layer_size = deriv_attrs["targetLayerSize"]
  while not dep_graph.is_empty:

    # Select the subtree that would best satisfy the available space in the current layer.
    avail_space = target_layer_size - layer.size
    assert avail_space > 0
    subtree_root_id = dep_graph.best_node(minimise=lambda d: abs(d["closureSize"] - avail_space))

    # Remove it from the dependency graph and add it to the layer.
    layer.path_dicts += dep_graph.pop_subtree(subtree_root_id)

    # If the layer is over half full (w.r.t. targetLayerSize), it's done.
    if layer.size >= target_layer_size // 2:
      layers.append(layer)
      layer = Layer()

  if not layer.is_empty:
    layers.append(layer)

  out_dir = pathlib.Path(deriv_attrs["outputs"]["out"])
  out_dir.mkdir(parents=True, exist_ok=True)
  for i, layer in enumerate(layers):
    with open(out_dir / f"{i:04d}", "w") as f:
      for p in sorted(layer.paths):
        print(p, file=f)


@dataclass
class Layer:
  path_dicts: list = field(default_factory=list)

  @property
  def is_empty(self):
    return not self.path_dicts

  @property
  def paths(self):
    return (d["path"] for d in self.path_dicts)

  @property
  def size(self):
    return sum(d["narSize"] for d in self.path_dicts)


class DepGraph:
  def __init__(self, path_dicts):
    """
    `path_dicts` should be of the form:
      [
        {
          "path": "/nix/store/0046rn5sgi6l38zl81bg2r02zlzxqqbc-libXext-1.3.6",
          "narSize": 96504,         # size occupied by path, in bytes
          "closureSize": 37164352,  # sum of narSizes of all paths in this path's closure
          "references": [
            "/nix/store/0046rn5sgi6l38zl81bg2r02zlzxqqbc-libXext-1.3.6",
            "/nix/store/1nsvsrqp5zm96r9p3rrq3yhlyw8jiy91-libX11-1.8.12",
            "/nix/store/zdpby3l6azi78sl83cpad2qjpfj25aqx-glibc-2.40-66",
          ],
        },
        ...
      ]
    """

    # For some efficiency, let's memoize the store paths by assigning a unique
    # identifying integer to each one. We'll assume that Nix will never give us
    # two dicts for the same `path`, and simply use the dict's position in the
    # provided list as the identifying integer.
    self._id_to_dict = list(path_dicts)

    # Set up a mapping from path strings to their corresponding integers.
    self._path_to_id = {d["path"]: i for i, d in enumerate(self._id_to_dict)}

    # Map the `references` member of each dict from a collection of path
    # strings to a collection of identifying integers. Also, sometimes a
    # path declares a dependency on itself - we'll go ahead and remove these
    # self-loops from the dependency graph now.
    for d in self._id_to_dict:
      d["references"] = {self._path_to_id[p] for p in d["references"] if p != d["path"]}

    # Calculate a topological order of the dependency graph.
    tsort = graphlib.TopologicalSorter()
    for i, d in enumerate(self._id_to_dict):
      tsort.add(i, *d["references"])
    self._ids_depth_first = list(tsort.static_order())

  @property
  def _ids_depth_last(self):
    return reversed(self._ids_depth_first)

  @property
  def is_empty(self):
    return all(d is None for d in self._id_to_dict)

  def best_node(self, *, minimise):
    return min(
      filter(
        lambda tup: tup[1] is not None,
        enumerate(self._id_to_dict),
      ),
      key=lambda tup: minimise(tup[1]),
    )[0]

  def pop_subtree(self, root_id):
    node_ids = {root_id}
    for i in self._ids_depth_last:
      if i in node_ids:
        node_ids |= self._id_to_dict[i]["references"]
    return self.pop(*node_ids)

  def pop(self, *node_ids):
    node_dicts = [self._id_to_dict[i] for i in node_ids]
    for i in node_ids:
      self._id_to_dict[i] = None
    for d in self._id_to_dict:
      if d is not None:
        d["references"].difference_update(node_ids)
    self._recompute_closure_sizes()
    return node_dicts

  def _recompute_closure_sizes(self):
    for i in self._ids_depth_first:
      d = self._id_to_dict[i]
      if d is not None:
        d["closureSize"] = d["narSize"] + sum(
          self._id_to_dict[ii]["closureSize"]
          for ii in d["references"]
        )
