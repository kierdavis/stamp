import hashlib
import json
import os
import pytest
from stamptool import patch
from testfixtures import compare
from .conftest import compare_dir_entries


@pytest.fixture
def append_layers(testdata):
  return [{
    "diffTarball": testdata / "layer1/diff.tar",
    "diffDigest": testdata / "layer1/diff.tar.digest",
    "blobTarball": testdata / "layer1/blob.tar.gz",
    "blobDigest": testdata / "layer1/blob.tar.gz.digest",
  }]


def test_patch_oci(testdata, append_layers, tmp_path):
  out_path = tmp_path / "out"
  manifest_path = tmp_path / "manifest.json"
  config_path = tmp_path / "config.json"
  patch.oci_main({
    "base": str(testdata / "image1"),
    "appendLayers": append_layers,
    "env": {
      "NEWKEY": "mockvalue",
      "PATH": "mockpath",
    },
    "entrypoint": ["mockentrypoint"],
    "cmd": ["mockcmd"],
    "workingDir": "/mock/working/dir",
    "outputs": {
      "out": str(out_path),
      "manifest": str(manifest_path),
      "config": str(config_path),
    },
  })

  config_bytes = config_path.read_bytes()
  config_sha256 = hashlib.sha256(config_bytes).hexdigest()
  compare(json.loads(config_bytes), expected={
    "architecture": "amd64",
    "config": {
      "Cmd": ["mockcmd"],
      "Entrypoint": ["mockentrypoint"],
      "Env": [
        "NEWKEY=mockvalue",
        "PATH=mockpath"
      ],
      "Labels": {
        "io.buildah.version": "1.37.3"
      },
      "WorkingDir": "/mock/working/dir",
    },
    "created": "2025-07-12T17:51:20.151387201Z",
    "history": [
      {
        "created": "2025-07-12T17:51:20.152025793Z",
        "created_by": "/bin/sh -c #(nop) ADD dir:7b78277f3138ff3699db830af6ebc94871bf82b0a88b53571098b73865e68c74 in /etc "
      },
      {
        "created_by": "stamp.patch"
      }
    ],
    "os": "linux",
    "rootfs": {
      "diff_ids": [
        "sha256:6b40aa9e85fff948c00254614ad3e394b7232aa052d3ba7492f599bd0c01ff1b",
        "sha256:9280d2bae700a4d81f87bf46be48a145d2a5465f3e09c9c99708cf765bf7a243"
      ],
      "type": "layers"
    }
  })
  compare(config_sha256, expected="e05f8a98593f434361df1a00351790211e6d49a9c3f218ce4eab19da44e1b2fe")
  compare(len(config_bytes), expected=647)

  manifest_bytes = manifest_path.read_bytes()
  manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
  compare(json.loads(manifest_bytes), expected={
    "schemaVersion": 2,
    "mediaType": "application/vnd.oci.image.manifest.v1+json",
    "config": {
      "mediaType": "application/vnd.oci.image.config.v1+json",
      "digest": f"sha256:{config_sha256}",
      "size": len(config_bytes),
    },
    "layers": [
      {
        "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
        "digest": "sha256:680548d6538925f29b19de954184c7d1f86ef3fb22b90ee3a24eb26143c093fe",
        "size": 192
      },
      {
        "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
        "digest": "sha256:c23ae081fe7ff8d83d714694c9f579a159cce67807e473c24e0709bb65a8d1a4",
        "size": 135
      }
    ],
    "annotations": {
      "org.opencontainers.image.base.digest": "",
      "org.opencontainers.image.base.name": ""
    }
  })
  compare(manifest_sha256, expected="3cb500edc295f65525d1cdf217ee5a1bc060dfe8a1fc0c1d6de78c6c601535ed")
  compare(len(manifest_bytes), expected=653)

  [blobs_path, index_path, oci_layout_path] = compare_dir_entries(out_path, expected=["blobs", "index.json", "oci-layout"])

  with open(oci_layout_path) as f:
    compare(json.load(f), expected={"imageLayoutVersion": "1.0.0"})

  with open(index_path) as f:
    compare(json.load(f), expected={
      "schemaVersion": 2,
      "mediaType": "application/vnd.oci.image.index.v1+json",
      "manifests": [{
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "digest": f"sha256:{manifest_sha256}",
        "size": len(manifest_bytes),
      }],
    })

  [sha256_path] = compare_dir_entries(blobs_path, expected=["sha256"])
  [config_link_path, manifest_link_path, base_layer_link_path, new_layer_link_path] = compare_dir_entries(sha256_path, [
    config_sha256,
    manifest_sha256,
    "680548d6538925f29b19de954184c7d1f86ef3fb22b90ee3a24eb26143c093fe", # layer blob from base image
    "c23ae081fe7ff8d83d714694c9f579a159cce67807e473c24e0709bb65a8d1a4", # layer blob from appendLayers
  ])

  compare(os.readlink(config_link_path), expected=str(config_path))
  compare(os.readlink(manifest_link_path), expected=str(manifest_path))
  compare(os.readlink(base_layer_link_path), expected=str(testdata / "image1/blobs/sha256/680548d6538925f29b19de954184c7d1f86ef3fb22b90ee3a24eb26143c093fe"))
  compare(os.readlink(new_layer_link_path), expected=str(testdata / "layer1/blob.tar.gz"))


def test_patch_diffs(testdata, append_layers, tmp_path):
  out_path = tmp_path / "out"
  patch.diffs_main({
    "base": str(testdata / "image1"),
    "baseDiffs": str(testdata / "image1-diffs"),
    "appendLayers": append_layers,
    "outputs": {"out": str(out_path)},
  })

  [sha256_path] = compare_dir_entries(out_path, expected=["sha256"])
  [base_layer_link_path, new_layer_link_path] = compare_dir_entries(sha256_path, [
    "6b40aa9e85fff948c00254614ad3e394b7232aa052d3ba7492f599bd0c01ff1b",
    "9280d2bae700a4d81f87bf46be48a145d2a5465f3e09c9c99708cf765bf7a243",
  ])

  compare(os.readlink(base_layer_link_path), expected=str(testdata / "image1-diffs/sha256/6b40aa9e85fff948c00254614ad3e394b7232aa052d3ba7492f599bd0c01ff1b"))
  compare(os.readlink(new_layer_link_path), expected=str(testdata / "layer1/diff.tar"))


def test_patch_oci_no_base(testdata, append_layers, tmp_path):
  out_path = tmp_path / "out"
  manifest_path = tmp_path / "manifest.json"
  config_path = tmp_path / "config.json"
  patch.oci_main({
    "base": None,
    "appendLayers": append_layers,
    "env": {
      "NEWKEY": "mockvalue",
      "PATH": "mockpath",
    },
    "entrypoint": ["mockentrypoint"],
    "cmd": ["mockcmd"],
    "workingDir": "/mock/working/dir",
    "outputs": {
      "out": str(out_path),
      "manifest": str(manifest_path),
      "config": str(config_path),
    },
  })

  config_bytes = config_path.read_bytes()
  config_sha256 = hashlib.sha256(config_bytes).hexdigest()
  compare(json.loads(config_bytes), expected={
    "architecture": "amd64",
    "config": {
      "Cmd": ["mockcmd"],
      "Entrypoint": ["mockentrypoint"],
      "Env": [
        "NEWKEY=mockvalue",
        "PATH=mockpath"
      ],
      "WorkingDir": "/mock/working/dir",
    },
    "history": [
      {
        "created_by": "stamp.patch"
      }
    ],
    "os": "linux",
    "rootfs": {
      "diff_ids": [
        "sha256:9280d2bae700a4d81f87bf46be48a145d2a5465f3e09c9c99708cf765bf7a243"
      ],
      "type": "layers"
    }
  })
  compare(config_sha256, expected="a7ad8bade6fe0adc9783533678890b16fc103ac9ff618c4836c78f6ad71b229b")
  compare(len(config_bytes), expected=329)

  manifest_bytes = manifest_path.read_bytes()
  manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
  compare(json.loads(manifest_bytes), expected={
    "schemaVersion": 2,
    "mediaType": "application/vnd.oci.image.manifest.v1+json",
    "config": {
      "mediaType": "application/vnd.oci.image.config.v1+json",
      "digest": f"sha256:{config_sha256}",
      "size": len(config_bytes),
    },
    "layers": [
      {
        "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
        "digest": "sha256:c23ae081fe7ff8d83d714694c9f579a159cce67807e473c24e0709bb65a8d1a4",
        "size": 135
      }
    ]
  })
  compare(manifest_sha256, expected="e1900c2198c8e3adbdf6e053e244c3d93d6bbfab04d8c138180b4754ff380dd4")
  compare(len(manifest_bytes), expected=401)

  [blobs_path, index_path, oci_layout_path] = compare_dir_entries(out_path, expected=["blobs", "index.json", "oci-layout"])

  with open(oci_layout_path) as f:
    compare(json.load(f), expected={"imageLayoutVersion": "1.0.0"})

  with open(index_path) as f:
    compare(json.load(f), expected={
      "schemaVersion": 2,
      "mediaType": "application/vnd.oci.image.index.v1+json",
      "manifests": [{
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "digest": f"sha256:{manifest_sha256}",
        "size": len(manifest_bytes),
      }],
    })

  [sha256_path] = compare_dir_entries(blobs_path, expected=["sha256"])
  [config_link_path, manifest_link_path, new_layer_link_path] = compare_dir_entries(sha256_path, [
    config_sha256,
    manifest_sha256,
    "c23ae081fe7ff8d83d714694c9f579a159cce67807e473c24e0709bb65a8d1a4", # layer blob from appendLayers
  ])

  compare(os.readlink(config_link_path), expected=str(config_path))
  compare(os.readlink(manifest_link_path), expected=str(manifest_path))
  compare(os.readlink(new_layer_link_path), expected=str(testdata / "layer1/blob.tar.gz"))


def test_patch_diffs_no_base(testdata, append_layers, tmp_path):
  out_path = tmp_path / "out"
  patch.diffs_main({
    "appendLayers": append_layers,
    "outputs": {"out": str(out_path)},
  })

  [sha256_path] = compare_dir_entries(out_path, expected=["sha256"])
  [new_layer_link_path] = compare_dir_entries(sha256_path, [
    "9280d2bae700a4d81f87bf46be48a145d2a5465f3e09c9c99708cf765bf7a243",
  ])

  compare(os.readlink(new_layer_link_path), expected=str(testdata / "layer1/diff.tar"))
