"""The two scripts beside the build: the prover requests, and publishing."""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(script, *args, **kw):
    return subprocess.run([sys.executable, os.path.join(ROOT, "src", script),
                           *args], capture_output=True, text=True, **kw)


@pytest.mark.slow
def test_prover_requests_draw_the_same_sample_anywhere(tmp_path, oracle_dir):
    """A seeded sample that is only reproducible on the machine that drew it.

    The generator walks dicts and sets, so what it shuffles arrives in an
    order that depends on the process hash seed. Sorting happens before the
    shuffle for exactly this reason, and this is the test that would notice if
    somebody moved it after: the counts would be identical and the twenty
    thousand rows would be a different twenty thousand.
    """
    out = []
    for i, seed in enumerate(("0", "random")):
        path = tmp_path / f"p{i}"
        done = run("prover_requests.py",
                   "--relations", os.path.join(oracle_dir, "relations.tsv"),
                   "--out", str(path / "triples.jsonl"),
                   "--claims-out", str(path / "claims.jsonl"),
                   "--limit", "5000",
                   env=dict(os.environ, PYTHONHASHSEED=seed))
        assert done.returncode == 0, done.stderr
        out.append(path)
    assert (out[0] / "triples.jsonl").read_bytes() == \
        (out[1] / "triples.jsonl").read_bytes()
    assert (out[0] / "claims.jsonl").read_bytes() == \
        (out[1] / "claims.jsonl").read_bytes()


def test_publish_is_a_dry_run_by_default(data_dir):
    """A script that uploads because somebody ran it to see what it did.

    Publishing is not reversible in the way a local build is: the card and
    the files reach everybody who pulls the dataset. --push is the only way
    anything leaves the machine.
    """
    done = run("publish.py")
    assert done.returncode == 0, done.stderr
    assert "dry run" in done.stdout
    assert "--push" in done.stdout


def test_publish_refuses_a_card_that_does_not_declare_a_subset(tmp_path,
                                                               data_dir):
    """A subset uploaded with no config pointing at it.

    This does not fail at upload time. It produces a dataset page that loads
    and shows one subset, with the other sitting in the repository unreachable
    by load_dataset, which nobody notices until they go looking for it.
    """
    card = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    broken = tmp_path / "README.md"
    broken.write_text(card.replace("  - config_name: cpt\n", ""),
                      encoding="utf-8")
    done = run("publish.py", "--card", str(broken))
    assert done.returncode != 0
    assert "config named cpt" in done.stderr


def test_publish_refuses_a_card_with_the_wrong_counts(tmp_path, data_dir,
                                                      manifest):
    """A card quoting counts from a build that is no longer the one on disk.

    The likeliest way this happens is a rebuild against a newer oracle with
    the card left alone. Nothing about the files looks wrong, and a reader
    takes the numbers from the card because that is what a card is for.
    """
    card = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    rows = f"{manifest['cpt']['rows']:,}"
    broken = tmp_path / "README.md"
    broken.write_text(card.replace(rows, "1,234,567"), encoding="utf-8")
    done = run("publish.py", "--card", str(broken))
    assert done.returncode != 0
    assert "does not mention" in done.stderr


def test_publish_refuses_a_card_without_the_digests(tmp_path, data_dir,
                                                    manifest):
    """The reproducibility claim published without the means to check it.

    The digests are the only part of the card a reader can verify without
    rebuilding. A card that drops them still reads as confident.
    """
    card = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    broken = tmp_path / "README.md"
    broken.write_text(card.replace(manifest["triples"]["sha256"], "removed"),
                      encoding="utf-8")
    done = run("publish.py", "--card", str(broken))
    assert done.returncode != 0
    assert "does not quote the digest" in done.stderr
