import hashlib
import json
import os
from stamptool import patch
from testfixtures import compare
from .conftest import compare_dir_entries


def test_patch_oci(testdata, tmp_path):
  out_path = tmp_path / "out"
  manifest_path = tmp_path / "manifest.json"
  config_path = tmp_path / "config.json"
  patch.oci_main({
    "base": str(testdata / "image1"),
    "appendLayers": [{
      "blob": str(testdata / "layer1/blob"),
      "diff": str(testdata / "layer1/diff"),
    }],
    "env": {
      "NEWKEY": "mockvalue",
      "PATH": "mockpath",
    },
    "entrypoint": ["mockentrypoint"],
    "cmd": ["mockcmd"],
    "outputs": {
      "out": str(out_path),
      "manifest": str(manifest_path),
      "config": str(config_path),
    },
  })

  config_bytes = config_path.read_bytes()
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
      }
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
  compare(hashlib.sha256(config_bytes).hexdigest(), expected="7b22a011e9e5566be22a1a68fa6c7af68d533dd1b602e7a31d940e1d7a443519")
  compare(len(config_bytes), expected=614)

  manifest_bytes = manifest_path.read_bytes()
  compare(json.loads(manifest_bytes), expected={
    "schemaVersion": 2,
    "mediaType": "application/vnd.oci.image.manifest.v1+json",
    "config": {
      "mediaType": "application/vnd.oci.image.config.v1+json",
      "digest": "sha256:7b22a011e9e5566be22a1a68fa6c7af68d533dd1b602e7a31d940e1d7a443519",
      "size": 614,
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
  compare(hashlib.sha256(manifest_bytes).hexdigest(), expected="8b466ccba104a1e17219a741860efae3e8257d2e6aeddf684d7f59d10b77d62a")
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
        "digest": "sha256:8b466ccba104a1e17219a741860efae3e8257d2e6aeddf684d7f59d10b77d62a",
        "size": 653,
      }],
    })

  [sha256_path] = compare_dir_entries(blobs_path, expected=["sha256"])
  [config_link_path, manifest_link_path, base_layer_link_path, new_layer_link_path] = compare_dir_entries(sha256_path, [
    "7b22a011e9e5566be22a1a68fa6c7af68d533dd1b602e7a31d940e1d7a443519", # config
    "8b466ccba104a1e17219a741860efae3e8257d2e6aeddf684d7f59d10b77d62a", # manifest
    "680548d6538925f29b19de954184c7d1f86ef3fb22b90ee3a24eb26143c093fe", # layer blob from base image
    "c23ae081fe7ff8d83d714694c9f579a159cce67807e473c24e0709bb65a8d1a4", # layer blob from appendLayers
  ])

  compare(os.readlink(config_link_path), expected=str(config_path))
  compare(os.readlink(manifest_link_path), expected=str(manifest_path))
  compare(os.readlink(base_layer_link_path), expected=str(testdata / "image1/blobs/sha256/680548d6538925f29b19de954184c7d1f86ef3fb22b90ee3a24eb26143c093fe"))
  compare(os.readlink(new_layer_link_path), expected=str(testdata / "layer1/blob/blob.tar.gz"))


def test_patch_diffs(testdata, tmp_path):
  out_path = tmp_path / "out"
  patch.diffs_main({
    "base": str(testdata / "image1"),
    "baseDiffs": str(testdata / "image1-diffs"),
    "appendLayers": [{
      "diff": str(testdata / "layer1/diff"),
    }],
    "outputs": {"out": str(out_path)},
  })

  [sha256_path] = compare_dir_entries(out_path, expected=["sha256"])
  [base_layer_link_path, new_layer_link_path] = compare_dir_entries(sha256_path, [
    "6b40aa9e85fff948c00254614ad3e394b7232aa052d3ba7492f599bd0c01ff1b",
    "9280d2bae700a4d81f87bf46be48a145d2a5465f3e09c9c99708cf765bf7a243",
  ])

  compare(os.readlink(base_layer_link_path), expected=str(testdata / "image1-diffs/sha256/6b40aa9e85fff948c00254614ad3e394b7232aa052d3ba7492f599bd0c01ff1b"))
  compare(os.readlink(new_layer_link_path), expected=str(testdata / "layer1/diff/diff.tar"))


def test_patch_oci_no_base(testdata, tmp_path):
  out_path = tmp_path / "out"
  manifest_path = tmp_path / "manifest.json"
  config_path = tmp_path / "config.json"
  patch.oci_main({
    "base": None,
    "appendLayers": [{
      "blob": str(testdata / "layer1/blob"),
      "diff": str(testdata / "layer1/diff"),
    }],
    "env": {
      "NEWKEY": "mockvalue",
      "PATH": "mockpath",
    },
    "entrypoint": ["mockentrypoint"],
    "cmd": ["mockcmd"],
    "outputs": {
      "out": str(out_path),
      "manifest": str(manifest_path),
      "config": str(config_path),
    },
  })

  config_bytes = config_path.read_bytes()
  compare(json.loads(config_bytes), expected={
    "architecture": "amd64",
    "config": {
      "Cmd": ["mockcmd"],
      "Entrypoint": ["mockentrypoint"],
      "Env": [
        "NEWKEY=mockvalue",
        "PATH=mockpath"
      ]
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
  compare(hashlib.sha256(config_bytes).hexdigest(), expected="d27856def4e73db924921419bf20510684f2f9b67b979b296dba3f3936b8772c")
  compare(len(config_bytes), expected=296)

  manifest_bytes = manifest_path.read_bytes()
  compare(json.loads(manifest_bytes), expected={
    "schemaVersion": 2,
    "mediaType": "application/vnd.oci.image.manifest.v1+json",
    "config": {
      "mediaType": "application/vnd.oci.image.config.v1+json",
      "digest": "sha256:d27856def4e73db924921419bf20510684f2f9b67b979b296dba3f3936b8772c",
      "size": 296,
    },
    "layers": [
      {
        "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
        "digest": "sha256:c23ae081fe7ff8d83d714694c9f579a159cce67807e473c24e0709bb65a8d1a4",
        "size": 135
      }
    ]
  })
  compare(hashlib.sha256(manifest_bytes).hexdigest(), expected="7963d10db2ff37d0a01987e3ac63fdad88583150f2ab24838191f1e6cc9b6b8e")
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
        "digest": "sha256:7963d10db2ff37d0a01987e3ac63fdad88583150f2ab24838191f1e6cc9b6b8e",
        "size": 401,
      }],
    })

  [sha256_path] = compare_dir_entries(blobs_path, expected=["sha256"])
  [config_link_path, manifest_link_path, new_layer_link_path] = compare_dir_entries(sha256_path, [
    "d27856def4e73db924921419bf20510684f2f9b67b979b296dba3f3936b8772c", # config
    "7963d10db2ff37d0a01987e3ac63fdad88583150f2ab24838191f1e6cc9b6b8e", # manifest
    "c23ae081fe7ff8d83d714694c9f579a159cce67807e473c24e0709bb65a8d1a4", # layer blob from appendLayers
  ])

  compare(os.readlink(config_link_path), expected=str(config_path))
  compare(os.readlink(manifest_link_path), expected=str(manifest_path))
  compare(os.readlink(new_layer_link_path), expected=str(testdata / "layer1/blob/blob.tar.gz"))


def test_patch_diffs_no_base(testdata, tmp_path):
  out_path = tmp_path / "out"
  patch.diffs_main({
    "appendLayers": [{
      "diff": str(testdata / "layer1/diff"),
    }],
    "outputs": {"out": str(out_path)},
  })

  [sha256_path] = compare_dir_entries(out_path, expected=["sha256"])
  [new_layer_link_path] = compare_dir_entries(sha256_path, [
    "9280d2bae700a4d81f87bf46be48a145d2a5465f3e09c9c99708cf765bf7a243",
  ])

  compare(os.readlink(new_layer_link_path), expected=str(testdata / "layer1/diff/diff.tar"))
