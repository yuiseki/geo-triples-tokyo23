#!/usr/bin/env python3
"""Ask LeanGeospatial to certify the DE-9IM readings, and vendor its answers.

The division of labour this file exists to keep: YuisekinGeoSPARQL observes,
LeanGeospatial certifies, and the build derives. The oracle reads a matrix off
two geometries and says which Simple Features predicates hold. That reading is
an observation, and an observation is not a proof. What can be proved is the
step after it: that a given matrix entails, or excludes, a given predicate.

So the prover is run over every distinct matrix the oracle produced, once, and
its verdicts are written to vendor/de9im_sf_verdicts.tsv. The build reads that
file. Lean is therefore not needed to build the dataset, and is not in its
requirements; it is needed to change what the dataset claims is proved, which
is the right place for a heavy dependency to sit.

A matrix with no verdict in the file is not an error. It produces rows marked
uncertified, which is what they are.

    python3 src/certify.py \
        --relations ../YuisekinGeoSPARQL/data/relations.tsv \
        --prover ../LeanGeospatial/.lake/build/bin/lean-geospatial-prover \
        --lean ../LeanGeospatial
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prover_requests  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDORED = os.path.join(BASE, "vendor", "de9im_sf_verdicts.tsv")

HEADER = """\
# What LeanGeospatial proves about the matrices this dataset observed.
#
# One row per (matrix, kinds, predicate). entailed means the prover derived
# the predicate from the matrix; refuted means it derived its negation. Both
# are results; neither is the oracle's opinion. A pair the prover left open
# is absent.
#
# Regenerate with src/certify.py, which needs LeanGeospatial built. Reading
# this file does not.
#
# prover: LeanGeospatial {rev}
# claims: {n}
"""


def read_vendored(path=VENDORED):
    """(matrix, a_kind, b_kind, predicate) -> "entailed" or "refuted"."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if parts[0] == "matrix":
                continue
            matrix, a_kind, b_kind, predicate, verdict = parts
            out[(matrix, a_kind, b_kind, predicate)] = verdict
    return out


def vendored_revision(path=VENDORED):
    """Which LeanGeospatial proved the verdicts beside this, from its header.

    The revision travels in the file rather than in a constant here, because
    the file is what a rebuild reads and a constant would go on saying the
    old revision after somebody regenerated it.
    """
    if not os.path.exists(path):
        return None
    for line in open(path, encoding="utf-8"):
        if line.startswith("# prover: LeanGeospatial "):
            return line.split()[-1]
        if not line.startswith("#"):
            break
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--relations", required=True)
    ap.add_argument("--prover", required=True)
    ap.add_argument("--lean", required=True, help="the LeanGeospatial checkout,"
                                                  " for the revision to record")
    ap.add_argument("--out", default=VENDORED)
    a = ap.parse_args()

    rows = prover_requests.load(a.relations)
    claims = prover_requests.claim_requests(rows)
    payload = "".join(json.dumps(c) + "\n" for c in claims)
    done = subprocess.run([a.prover], input=payload, capture_output=True,
                          text=True)
    if done.returncode != 0:
        raise SystemExit(f"the prover failed: {done.stderr.strip()[:400]}")
    verdicts = {json.loads(l)["id"]: json.loads(l)
                for l in done.stdout.splitlines() if l.strip()}

    rev = subprocess.run(["git", "-C", a.lean, "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True
                         ).stdout.strip()

    # The prover is being asked about the same matrices the oracle read. If it
    # entails a predicate the oracle did not see, or refutes one it did, one
    # of the two is wrong about this data and neither can be shipped as a
    # certificate of the other.
    lines, disagreed = [], []
    for c in claims:
        v = verdicts.get(c["id"])
        if not v or v["status"] not in ("entailed", "refuted"):
            continue
        if (v["status"] == "entailed") != bool(c["observed"]):
            disagreed.append((c["matrix"], c["claim"], c["observed"],
                              v["status"]))
        lines.append("\t".join((c["matrix"], c["a_kind"], c["b_kind"],
                                prover_requests.CLAIMS[c["claim"]],
                                v["status"])))
    if disagreed:
        raise SystemExit(
            f"{len(disagreed)} of {len(claims)} verdicts contradict the "
            f"oracle, for instance matrix {disagreed[0][0]} "
            f"{disagreed[0][1]}: observed {disagreed[0][2]}, prover "
            f"{disagreed[0][3]}")

    lines.sort()
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(HEADER.format(rev=rev, n=len(lines)))
        f.write("matrix\ta_kind\tb_kind\tpredicate\tverdict\n")
        f.write("\n".join(lines) + "\n")
    print(f"{len(lines):,} verdicts from {len({l.split(chr(9))[0] for l in lines}):,} "
          f"matrices -> {a.out}")
    print(f"   LeanGeospatial {rev}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
