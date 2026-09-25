"""Where the tests get the dataset and the oracle from.

The tables are read from data/, built by src/build.py, rather than rebuilt
per test: most of these tests are about what the published files contain, and
a test that builds its own copy would pass while the published files were
wrong. The one test that does rebuild says so in its name.
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

# Where the oracle lives when the two repositories are checked out side by
# side, which is how they are developed. ORACLE overrides it.
ORACLE = os.environ.get(
    "ORACLE", os.path.join(ROOT, "..", "YuisekinGeoSPARQL", "data"))


@pytest.fixture(scope="session")
def data_dir():
    path = os.path.join(ROOT, "data")
    if not os.path.exists(os.path.join(path, "manifest.json")):
        pytest.skip(f"no dataset in {path}; run src/build.py first")
    return path


@pytest.fixture(scope="session")
def manifest(data_dir):
    with open(os.path.join(data_dir, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def triples(data_dir):
    import pyarrow.parquet as pq
    return pq.read_table(os.path.join(data_dir, "triples.parquet")).to_pylist()


@pytest.fixture(scope="session")
def cpt(data_dir):
    import pyarrow.parquet as pq
    return pq.read_table(os.path.join(data_dir, "cpt.parquet")).to_pylist()


@pytest.fixture(scope="session")
def oracle_dir():
    if not os.path.exists(os.path.join(ORACLE, "relations.tsv")):
        pytest.skip(f"no oracle output in {ORACLE}; set ORACLE to point at it")
    return ORACLE


@pytest.fixture(scope="session")
def labels(oracle_dir):
    import build
    with open(os.path.join(oracle_dir, "manifest.json"), encoding="utf-8") as f:
        oracle = json.load(f)
    graphs = [os.path.join(oracle_dir, s["ttl_file"]) for s in oracle["sources"]]
    return build.feature_labels(graphs)


@pytest.fixture(scope="session")
def probe(data_dir):
    import pyarrow.parquet as pq
    return pq.read_table(os.path.join(data_dir, "probe.parquet")).to_pylist()
