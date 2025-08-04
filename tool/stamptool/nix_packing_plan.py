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
    subtree_root_id = dep_graph.best_node(minimise=lambda m: abs(m.closure_size - avail_space))

    # Remove it from the dependency graph and add it to the layer.
    layer.path_metas += dep_graph.pop_subtree(subtree_root_id)

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
class PathMeta:
  path: str
  size: int # bytes
  closure_size: int
  refs: set = field(default_factory=set)


@dataclass
class Layer:
  path_metas: list = field(default_factory=list)

  @property
  def is_empty(self):
    return not self.path_metas

  @property
  def paths(self):
    return (m.path for m in self.path_metas)

  @property
  def size(self):
    return sum(m.size for m in self.path_metas)


class DepGraph:
  def __init__(self, closure_info_path):
    """
    `closure_info_path` should be the path to a directory containing a file
    named `registration`, which should be formed of one or more instances of
    the following sequence of lines:
      [store path]
      [arbitrary]
      [size occupied by path, in bytes]
      [arbitrary]
      [number of store paths referred to by this path]
      [referenced path 0]
      [referenced path 1]
      ...
    For example:
      /nix/store/0dqmgjr0jsc2s75sbgdvkk7d08zx5g61-libgcrypt-1.10.3-lib
      sha256:18irhz8220sy6x34mlyjvp5sqa8fw0jrcxxdivkgl01ps7nhqh5a
      1463016

      3
      /nix/store/0dqmgjr0jsc2s75sbgdvkk7d08zx5g61-libgcrypt-1.10.3-lib
      /nix/store/9z7wv6k9i38k83xpbgqcapaxhdkbaqhz-libgpg-error-1.51
      /nix/store/cg9s562sa33k78m63njfn1rw47dp9z0i-glibc-2.40-66
    """

    metas = []
    with open(pathlib.Path(closure_info_path) / "registration") as f:
      while True:
        path = f.readline().rstrip("\n")
        if not path:
          break
        f.readline()
        size = int(f.readline().rstrip("\n"))
        f.readline()
        n_refs = int(f.readline().rstrip("\n"))
        refs = {f.readline().rstrip("\n") for _ in range(n_refs)}
        metas.append(PathMeta(path=path, size=size, closure_size=None, refs=refs))

    # For some efficiency, let's memoize the store paths by assigning a unique
    # identifying integer to each one. We'll assume that Nix will never give us
    # two dicts for the same `path`, and simply use the path's position in the
    # input file as the identifying integer.
    self._id_to_meta = metas

    # Set up a mapping from path strings to their corresponding integers.
    self._path_to_id = {m.path: i for i, m in enumerate(self._id_to_meta)}

    # Map each `refs` from a collection of path strings to a collection of
    # identifying integers. Also, sometimes a path declares a dependency on
    # itself - we'll go ahead and remove these self-loops from the dependency
    # graph now.
    for m in self._id_to_meta:
      m.refs = {self._path_to_id[p] for p in m.refs if p != m.path}

    # Calculate a topological order of the dependency graph.
    tsort = graphlib.TopologicalSorter()
    for i, m in enumerate(self._id_to_meta):
      tsort.add(i, *m.refs)
    self._ids_depth_first = list(tsort.static_order())

    self._recompute_closure_sizes()

  @property
  def _ids_depth_last(self):
    return reversed(self._ids_depth_first)

  @property
  def is_empty(self):
    return all(m is None for m in self._id_to_meta)

  def best_node(self, *, minimise):
    return min(
      filter(
        lambda tup: tup[1] is not None,
        enumerate(self._id_to_meta),
      ),
      key=lambda tup: minimise(tup[1]),
    )[0]

  def pop_subtree(self, root_id):
    node_ids = {root_id}
    for i in self._ids_depth_last:
      if i in node_ids:
        node_ids |= self._id_to_meta[i].refs
    return self.pop(*node_ids)

  def pop(self, *node_ids):
    metas = [self._id_to_meta[i] for i in node_ids]
    for i in node_ids:
      self._id_to_meta[i] = None
    for m in self._id_to_meta:
      if m is not None:
        m.refs.difference_update(node_ids)
    self._recompute_closure_sizes()
    return metas

  def _recompute_closure_sizes(self):
    for i in self._ids_depth_first:
      m = self._id_to_meta[i]
      if m is not None:
        m.closure_size = m.size + sum(
          self._id_to_meta[ii].closure_size
          for ii in m.refs
        )
