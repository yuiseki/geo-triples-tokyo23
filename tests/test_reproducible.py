"""Whether the same input really does give the same bytes.

This is the claim the dataset is built around, so it is demonstrated rather
than asserted: the build is run twice into fresh directories and the files are
compared byte for byte. The pinned digests below are the second half of the
claim. A rebuild that is self-consistent but differs from what was published
is still a rebuild nobody can reproduce.
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The digests of the published files. Parquet bytes belong to the writer as
# much as to the data, so these hold for the pyarrow version and the codec
# the manifest records and are expected to move if either does. That is not a
# reason to stop pinning them: a digest that changed for a reason nobody can
# name is exactly what this is here to surface.
DIGESTS = {
    "triples.parquet":
        "5fdf31ceb66774981edf65cdffe4d38ac15d2165c15c7cb63ae7e23d27ee6255",
    "cpt.parquet":
        "7a0f5329df04cd0d05bd17cee7b4141fb934867bcf7712c9c446713d2cf541b3",
    "probe.parquet":
        "788dc3bdc2f38255c7cf7c313943c81ac11b6cd450ff29efb08cefbe43c3e97a",
}

WRITER = "pyarrow 20.0.0"


def digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_the_manifest_describes_the_files_beside_it(data_dir, manifest):
    """A manifest quoting a digest the file does not have.

    This is what a half-finished build leaves behind: the tables are rewritten
    and the manifest is not, or the other way round. Anyone downstream
    verifying against the manifest would then be verifying nothing.
    """
    assert digest(os.path.join(data_dir, "triples.parquet")) == \
        manifest["triples"]["sha256"]
    assert digest(os.path.join(data_dir, "cpt.parquet")) == \
        manifest["cpt"]["sha256"]
    assert digest(os.path.join(data_dir, "probe.parquet")) == \
        manifest["probe"]["sha256"]


def test_the_files_are_the_ones_that_were_pinned(data_dir, manifest):
    """The bytes moved without anybody deciding that they should.

    If the writer version below has changed too, that explains it and the
    pins should be updated together with the card. If it has not, something
    in the build changed the output without changing the counts, which is the
    case worth stopping for.
    """
    if manifest["engine"]["parquet_writer"] != WRITER:
        pytest.skip(f"built with {manifest['engine']['parquet_writer']}, "
                    f"these digests are for {WRITER}")
    for name, want in DIGESTS.items():
        assert digest(os.path.join(data_dir, name)) == want, name


@pytest.mark.slow
def test_two_builds_give_the_same_bytes(tmp_path, oracle_dir):
    """Two runs of the same input disagreeing.

    What this catches is a set or a dict iterated somewhere on the way to the
    output. Such a bug is invisible in one run and invisible again in a second
    run in the same process, so the two builds are separate processes and one
    of them gets a randomised hash seed. Counts would not move; only the order
    of rows would, and only sometimes.
    """
    out = []
    for i, seed in enumerate(("0", "random")):
        path = tmp_path / f"build{i}"
        env = dict(os.environ, PYTHONHASHSEED=seed)
        subprocess.run(
            [sys.executable, os.path.join(ROOT, "src", "build.py"),
             "--relations", os.path.join(oracle_dir, "relations.tsv"),
             "--oracle", os.path.join(oracle_dir, "manifest.json"),
             "--out", str(path)],
            check=True, env=env, capture_output=True)
        out.append(path)

    for name in ("triples.parquet", "cpt.parquet", "probe.parquet",
                 "manifest.json"):
        first = (out[0] / name).read_bytes()
        second = (out[1] / name).read_bytes()
        assert first == second, name


@pytest.mark.slow
def test_a_rebuild_matches_what_is_published(tmp_path, oracle_dir, data_dir):
    """The published files are not what this oracle produces.

    Separate from the digest pins above, because this one fails for a
    different reason: not that the writer moved, but that data/ was built
    from a different oracle run than the one on disk now.
    """
    path = tmp_path / "rebuild"
    subprocess.run(
        [sys.executable, os.path.join(ROOT, "src", "build.py"),
         "--relations", os.path.join(oracle_dir, "relations.tsv"),
         "--oracle", os.path.join(oracle_dir, "manifest.json"),
         "--out", str(path)],
        check=True, capture_output=True)
    for name in ("triples.parquet", "cpt.parquet", "probe.parquet",
                 "manifest.json"):
        assert (path / name).read_bytes() == \
            (open(os.path.join(data_dir, name), "rb").read()), name


def test_the_build_refuses_a_manifest_that_does_not_match(tmp_path,
                                                          oracle_dir):
    """A stale oracle manifest being built against without complaint.

    The oracle rewrites its graphs and its relations at different moments, so
    building while one is newer than the other is the ordinary way this goes
    wrong. Without the check the output would carry a provenance block naming
    digests that are not the bytes it was made from.
    """
    doctored = json.load(open(os.path.join(oracle_dir, "manifest.json"),
                              encoding="utf-8"))
    doctored["sources"][0]["ttl_sha256"] = "0" * 64
    path = tmp_path / "oracle.json"
    path.write_text(json.dumps(doctored), encoding="utf-8")
    done = subprocess.run(
        [sys.executable, os.path.join(ROOT, "src", "build.py"),
         "--relations", os.path.join(oracle_dir, "relations.tsv"),
         "--oracle", str(path),
         "--graphs", *[os.path.join(oracle_dir, s["ttl_file"])
                       for s in doctored["sources"]],
         "--out", str(tmp_path / "out")],
        capture_output=True, text=True)
    assert done.returncode != 0
    assert "does not describe" in done.stderr
