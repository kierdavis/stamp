import copy
import os
import pathlib
import pytest
import tarfile
from testfixtures import compare


@pytest.fixture
def testdata():
  return pathlib.Path(__file__).parents[1] / "testdata"


def compare_dir_entries(dir_path, expected):
  """
  Assert that a filesystem directory contains files/subdirs with the given
  names, and no others.

  If it does, a list of the same length of `expected` is returned,
  in which each element is a `pathlib.Path` representing the file/subdir that
  was proven to exist. Paired with list unpacking syntax, this makes it
  easy to make assertions about nested filesystems.

  For example, the following directory structure:

    base/
      dir1/
        file1
      dir2/
        file2
        file3

  can be verified with the following sequence of calls to this function:

    [dir1_path, dir2_path] = compare_dir_entries("base", expected=["dir1", "dir2"])
    [file1_path] = compare_dir_entries(dir1_path, expected=["file1"])
    [file2_path, file3_path] = compare_dir_entries(dir2_path, expected=["file2", "file3"])

  `expected` should only include entries that would be returned by
  `Path.iterdir`; i.e. it should not include the standard "." and ".." entries.
  """

  entries = {x.name: x for x in pathlib.Path(dir_path).iterdir()}
  compare(frozenset(entries), expected=frozenset(expected))
  return [entries[name] for name in expected]


def compare_tar_entries(tar_path, expected):
  """
  Assert that a tar archive contains the given entries, and no others.

  `expected` should be an iterable of dictionaries whose keys/values correspond
  to attributes of tarfile.TarInfo.
  """

  expected = {x.pop("name"): x for x in copy.deepcopy(expected)}
  with tarfile.open(tar_path) as tar:
    got = {}
    while True:
      info = tar.next()
      if info is None:
        break
      try:
        attrs_to_compare = expected[info.name].keys()
      except KeyError:
        attrs_to_compare = ["size", "mtime", "mode", "type", "linkname", "uid", "gid", "uname", "gname", "pax_headers"]
      got[info.name] = {attr: getattr(info, attr, None) for attr in attrs_to_compare}
  compare(got, expected=expected)


class chdir:
  """
  Context manager for temporarily overriding the current working directory.
  """

  def __init__(self, value, mkdir=False):
    self._value = value
    self._mkdir = mkdir
    self._saved = None

  def __enter__(self):
    assert self._saved is None
    if self._mkdir:
      pathlib.Path(self._value).mkdir(parents=True, exist_ok=True)
    self._saved = pathlib.Path.cwd()
    os.chdir(self._value)
    return self._value

  def __exit__(self, *exc_info):
    assert self._saved is not None
    os.chdir(self._saved)
    self._saved = None


class environment:
  """
  Context manager for temporarily overriding the current process's environment
  variables.
  """

  def __init__(self, **values):
    self._values = values
    self._saved = None

  def __enter__(self):
    assert self._saved is None
    self._saved = {}
    for name, value in self._values.items():
      self._saved[name] = os.environ[name]
      os.environ[name] = str(value)
    return self

  def __exit__(self, *exc_info):
    assert self._saved is not None
    for name, value in self._saved.items():
      os.environ[name] = value
    self._saved = None
