#!/usr/bin/env python3
"""Turn relations.tsv into requests LeanGeospatial's prover can answer.

This was builder/triples.py in YuisekinGeoSPARQL. It moved here because it is
the only part of that builder that reads relations.tsv rather than helping to
write it: the oracle needs build_rdf.py, sources.py and rcc8.py to produce the
graph, and nothing there needs this. Keeping it beside the oracle meant the
image that builds the data also carried a consumer of it.

Two kinds of request, both in the JSON Lines shape ProverJSON.lean documents.

An RCC8 request states A r B and B s C and asks what holds between A and C.
The prover answers from the composition table it has proved; the observed
A-C relation goes in `observed` so a checker can compare without the prover
being told the answer.

    {"id":"...","facts":[{"a":"A","relation":"NTPP","b":"B"},
                         {"a":"B","relation":"NTPP","b":"C"}],
     "query":{"a":"A","b":"C"},"observed":"NTPP", ...}

A DE-9IM claim states a matrix and a Simple Features predicate:

    {"id":"...","matrix":"FF2F11212","claim":"touches"}

A pair absent from relations.tsv is DC. That is how triples through a
disjoint pair are built without writing 23.7 million rows: the reader fills
them in, and --include-dc says whether to.

    python3 src/prover_requests.py \
        --relations ../YuisekinGeoSPARQL/data/relations.tsv \
        --out data/prover/triples.jsonl \
        --claims-out data/prover/claims.jsonl --limit 0

    lean-geospatial-prover < data/prover/triples.jsonl > verdicts.jsonl
"""
import argparse
import csv
import json
import os
import random
import sys

RELS = ("DC", "EC", "PO", "EQ", "TPP", "NTPP", "TPPi", "NTPPi")

# The Simple Features predicates the prover's Claim.ofString? accepts, and the
# column in relations.tsv that says whether each holds.
CLAIMS = {"equals": "sfEquals", "disjoint": "sfDisjoint",
          "intersects": "sfIntersects", "touches": "sfTouches",
          "within": "sfWithin", "contains": "sfContains",
          "overlaps": "sfOverlaps", "crosses": "sfCrosses"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def index(rows, column="rcc8_raw"):
    """(a, b) -> relation, and a -> the b it relates to."""
    rel, out = {}, {}
    for r in rows:
        a, b = r["subject_id"], r["object_id"]
        value = r[column]
        if not value:
            continue
        rel[(a, b)] = value
        out.setdefault(a, set()).add(b)
    return rel, out


def triples(rel, out, features, include_dc, limit, seed):
    """Every A-B-C where A-B and B-C are known, optionally through DC too."""
    found = []
    # Sorted at every level. These are dicts and sets, so the order they
    # iterate in is the order Python happened to build them, and with string
    # keys that depends on the hash seed of the process.
    for a in sorted(out):
        for b in sorted(out[a]):
            r = rel[(a, b)]
            cs = out.get(b, set())
            if include_dc:
                cs = cs | (features - {a, b})
            for c in sorted(cs):
                if c == a or c == b:
                    continue
                s = rel.get((b, c), "DC")
                if not include_dc and s == "DC":
                    continue
                found.append((a, r, b, s, c, rel.get((a, c), "DC")))
    # Sort before shuffling, not after. Sorting first gives the shuffle a
    # fixed input, so a seed draws the same subset everywhere rather than only
    # on a machine that built the same dictionaries in the same order, and
    # sorting again afterwards makes the output order independent of which
    # subset was drawn.
    found.sort()
    if limit and len(found) > limit:
        random.Random(seed).shuffle(found)
        found = found[:limit]
        found.sort()
    return found


def claim_requests(rows):
    """One request per distinct matrix and predicate, with what was observed.

    Distinct in the matrix, not in the pair: the prover is being asked what a
    matrix entails, which is a question about the matrix alone. 36,694 pairs
    reduce to 18 matrices, and 144 requests answer for all of them.

    Separated out because src/certify.py asks the same question for a
    different purpose: this writes a file for a person to run the prover on,
    and that runs the prover and keeps the answers.
    """
    seen, out = set(), []
    for r in rows:
        held = set(r["sf_raw"].split(",")) if r["sf_raw"] else set()
        for claim, column in sorted(CLAIMS.items()):
            key = (r["de9im_raw"], claim)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "id": f"c{len(out):07d}",
                "matrix": r["de9im_raw"],
                "claim": claim,
                # sfOverlaps and sfCrosses are defined by cases on the
                # dimensions of the operands, so the prover asks which kinds
                # these are rather than guessing. Everything in this file is
                # an administrative area.
                "a_kind": "area",
                "b_kind": "area",
                "observed": column in held,
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--relations", required=True,
                    help="the oracle's relations.tsv")
    ap.add_argument("--out", default="data/prover/triples.jsonl")
    ap.add_argument("--claims-out", default="data/prover/claims.jsonl")
    ap.add_argument("--column", default="rcc8_raw",
                    choices=["rcc8_raw", "rcc8_norm"],
                    help="which reading to state as fact. The raw one is the "
                         "observation; the normalized one is a judgement and "
                         "says so in the output")
    ap.add_argument("--include-dc", action="store_true",
                    help="also build triples through a disjoint pair. A pair "
                         "absent from relations.tsv is DC")
    ap.add_argument("--limit", type=int, default=20000,
                    help="0 for all. 699,002 triples exist without --include-dc")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    rows = load(a.relations)
    rel, out = index(rows, a.column)
    features = {r["subject_id"] for r in rows} | {r["object_id"] for r in rows}
    found = triples(rel, out, features, a.include_dc, a.limit, a.seed)

    for path in (a.out, a.claims_out):
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)

    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        for i, (x, r, y, s, z, observed) in enumerate(found):
            f.write(json.dumps({
                "id": f"t{i:07d}",
                "facts": [{"a": x, "relation": r, "b": y},
                          {"a": y, "relation": s, "b": z}],
                "query": {"a": x, "b": z},
                # Not part of the request. The prover ignores unknown keys,
                # and a checker needs the observation to compare against.
                "observed": observed,
                "reading": a.column,
            }, ensure_ascii=False) + "\n")

    claims = claim_requests(rows)
    with open(a.claims_out, "w", encoding="utf-8", newline="\n") as f:
        for c in claims:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    n = len(claims)

    print(f"{len(found):,} triples -> {a.out}  (reading {a.column})")
    print(f"{n:,} distinct matrix/claim pairs -> {a.claims_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
