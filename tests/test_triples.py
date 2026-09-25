"""The triples table: what it counts, and whether the matrix backs every row."""
import collections


import build
import vocab

# The counts of the build these tests were written against. They are here so
# that a change to the oracle, or to how negatives are chosen, cannot slip
# through as a silently different dataset: the card quotes these numbers, and
# a card quoting numbers the files do not have is worse than no card.
EXPECTED = {
    "rows": 510616,
    "pairs": 51436,
    "true": 202116,
    "false": 308500,
    "observed": 411488,
    "composition": 99128,
}

# The eight Simple Features predicates as patterns over a DE-9IM matrix, in
# the order II IB IE BI BB BE EI EB EE, for two areas.
#
# This is a second, independent transcription from the SFA spec. The oracle
# has its own in builder/rcc8.py and this file deliberately does not import
# it: the point is that two transcriptions agree, and a shared one would only
# show that a single reading is self-consistent. sfCrosses has no area/area
# case at all, which SFA answers as false rather than as an error.
SF_PATTERNS = {
    "sfEquals":     ["T*F**FFF*"],
    "sfDisjoint":   ["FF*FF****"],
    "sfIntersects": ["T********", "*T*******", "***T*****", "****T****"],
    "sfTouches":    ["FT*******", "F**T*****", "F***T****"],
    "sfWithin":     ["T*F**F***"],
    "sfContains":   ["T*****FF*"],
    "sfOverlaps":   ["T*T***T**"],
    "sfCrosses":    [],
}


def _matches(matrix, pattern):
    for got, want in zip(matrix, pattern):
        if want == "*":
            continue
        if want == "F" and got != "F":
            return False
        if want == "T" and got == "F":
            return False
    return True


def _holds(matrix, predicate):
    return any(_matches(matrix, p) for p in SF_PATTERNS[predicate])


def test_counts(triples, manifest):
    """A different number here means the dataset changed under the card.

    Either the oracle was rebuilt from different revisions, or the rule that
    picks negatives moved. Both are legitimate; neither should reach a reader
    with the old counts still printed beside them.
    """
    counts = collections.Counter(t["derivation"] for t in triples)
    assert len(triples) == EXPECTED["rows"]
    assert sum(1 for t in triples if t["truth"]) == EXPECTED["true"]
    assert sum(1 for t in triples if not t["truth"]) == EXPECTED["false"]
    assert counts["observed"] == EXPECTED["observed"]
    assert counts["composition"] == EXPECTED["composition"]
    assert manifest["triples"]["pairs"] == EXPECTED["pairs"]


def test_eight_rows_per_observed_pair(triples):
    """A pair with fewer than eight rows would be a pair with hidden negatives.

    The defence of these negatives is that no pair was sampled: every observed
    pair gets all eight predicates. A pair short of one would mean a predicate
    was dropped somewhere, and dropping the ones that are awkward is exactly
    what the design is meant to rule out.
    """
    per_pair = collections.Counter(
        (t["subject_id"], t["object_id"]) for t in triples
        if t["derivation"] == "observed")
    assert set(per_pair.values()) == {8}
    assert len(per_pair) == EXPECTED["pairs"]


def test_exactly_one_rcc8_per_pair(triples):
    """RCC8 is the exclusive reading; Simple Features is not.

    If this ever fails the two columns have come apart: the eight rows of one
    pair would be claiming different topologies of the same two shapes. Note
    that the analogous claim about the predicate column is false by design and
    is not tested here, because more than one Simple Features predicate holds
    of a pair: two equal areas are equals, intersects, within and contains.
    """
    per_pair = collections.defaultdict(set)
    for t in triples:
        if t["derivation"] == "observed":
            per_pair[(t["subject_id"], t["object_id"])].add(t["rcc8"])
    assert all(len(v) == 1 for v in per_pair.values())
    # Empty is one of the readings, and it is not a missing one. RCC8 is a
    # calculus of regions, so a pair with a point in it has no RCC8 relation
    # and its column is empty rather than holding the nearest relation.
    assert set().union(*per_pair.values()) <= set(vocab.RCC8) | {""}
    kinds = {(t["subject_id"], t["object_id"]):
             (t["subject_kind"], t["object_kind"])
             for t in triples if t["derivation"] == "observed"}
    for pair, values in per_pair.items():
        empty = next(iter(values)) == ""
        assert empty == (kinds[pair] != ("area", "area")), pair


def test_every_truth_is_the_matrix_reading(triples):
    """A false with no matrix behind it, or a matrix that says otherwise.

    Going wrong looks like a row whose truth column was decided by something
    other than de9im: a predicate list copied from a library call, or a
    negative written in by hand. Each row is re-read here from its own matrix
    with a transcription of the SFA patterns that build.py never touches.
    """
    wrong = [t for t in triples if t["derivation"] == "observed"
             and _holds(t["de9im"], t["predicate"]) != t["truth"]]
    assert not wrong, wrong[:3]


def test_matrices_are_well_formed(triples):
    """A short or empty matrix would make the reading above vacuously agree.

    zip() over a nine-character pattern and a shorter matrix stops early and
    reports a match, so a truncated matrix would pass the previous test while
    carrying no evidence at all.
    """
    for t in triples:
        if t["de9im"] is None:
            # A composed row the oracle never formed a pair for. There is no
            # matrix because nothing was measured, which the row says by
            # leaving the column empty rather than by inventing one.
            assert t["derivation"] == "composition", t
            continue
        assert len(t["de9im"]) == 9, t
        assert set(t["de9im"]) <= set("FT012"), t


def test_disjoint_pairs_are_absent_not_false(triples, manifest):
    """The table holds observed pairs only, and says where the rest went.

    23.7 million disjoint pairs are omitted. If a direct row ever carried the
    disjoint matrix it would mean the oracle started writing them, and the
    reader's rule for a missing pair would silently become wrong for some of
    them.
    """
    direct = [t for t in triples if t["derivation"] == "observed"]
    assert not [t for t in direct if t["de9im"] == build.DISJOINT_MATRIX]
    assert not [t for t in direct
                if t["predicate"] == "sfDisjoint" and t["truth"]]


def test_composition_rows_carry_their_step(triples):
    """A composed row without an intermediate cannot be checked by anyone.

    The claim about these rows is that a proved table left exactly one
    relation given two known ones. Without via_id a reader cannot find the
    two, and the derivation column becomes an assertion rather than a
    reference.
    """
    composed = [t for t in triples if t["derivation"] == "composition"]
    assert composed
    for t in composed:
        assert t["via_id"], t
        assert t["via_iri"], t
        assert t["truth"] is True, t
        assert t["via_id"] not in (t["subject_id"], t["object_id"]), t


def test_composition_agrees_with_the_vendored_table(triples, oracle_dir):
    """The entailment is re-derived from the table, not trusted from the row.

    Failure here means build.py wrote a conclusion the table does not license.
    The two premises are looked up again in the oracle's relations.tsv and the
    cell is read again, so nothing but the vendored TSV decides the answer.
    """
    import csv
    import os
    with open(os.path.join(oracle_dir, "relations.tsv"), encoding="utf-8") as f:
        rel = {(r["subject_id"], r["object_id"]): r["rcc8_raw"]
               for r in csv.DictReader(f, delimiter="\t")}
    table = build.composition_table()
    composed = [t for t in triples if t["derivation"] == "composition"]
    for t in composed:
        r = rel[(t["subject_id"], t["via_id"])]
        s = rel[(t["via_id"], t["object_id"])]
        allowed = table[(r.lower(), s.lower())]
        assert len(allowed) == 1, (r, s, allowed)
        entailed = build.CANONICAL[next(iter(allowed))]
        assert entailed == t["rcc8"], (t, entailed)
        assert vocab.RCC8_TO_SF[entailed] == t["predicate"], t


def test_composition_never_contradicts_the_geometry(triples, oracle_dir):
    """A deduction and an observation disagreeing about the same two shapes.

    A single-valued cell of a proved table leaves no room for this, so it
    would mean either the oracle mis-read a matrix or the vendored table is
    not the one the proof is about. The oracle's own run reports zero
    contradictions over a larger set of triples; this checks the ones that
    were kept.
    """
    import csv
    import os
    with open(os.path.join(oracle_dir, "relations.tsv"), encoding="utf-8") as f:
        rel = {(r["subject_id"], r["object_id"]): r["rcc8_raw"]
               for r in csv.DictReader(f, delimiter="\t")}
    for t in triples:
        if t["derivation"] != "composition":
            continue
        if t["de9im"] is None:
            # Never formed, so there is no observation to contradict. These
            # are the rows that reach past what the oracle measured: a place
            # inside a ward inside a country the place was never compared to.
            assert (t["subject_id"], t["object_id"]) not in rel, t
            continue
        observed = rel.get((t["subject_id"], t["object_id"]), "DC")
        assert observed == t["rcc8"], t


def test_composition_cells_are_named_not_assumed(manifest):
    """Coverage of the 64 cells is very uneven, and the card has to say so.

    If this ever passes with many more cells the card's paragraph about the
    concentration is out of date, which is a quieter kind of wrong than a
    count being off.

    Six of the 64, up from four when the layers were all administrative. The
    two new ones are the chain the places brought: a place inside a ward
    inside a country is NTPP x NTPP, and its converse.
    """
    cells = manifest["composition_cells_used"]
    assert set(cells) == {"EC x EQ", "EC x NTPPi", "EQ x EC", "NTPP x EC",
                          "NTPP x NTPP", "NTPPi x NTPPi"}
    assert sum(cells.values()) == EXPECTED["composition"]


def test_provenance_is_on_every_row(triples, manifest):
    """A row that cannot say which revisions produced it.

    These columns are constant, which makes them easy to drop as redundant.
    They are here so that a slice of this table pasted into a training mix
    still carries the revisions and the licence trail with it.
    """
    datasets = {t["source_dataset"] for t in triples}
    assert len(datasets) == 1
    for s in manifest["sources"]:
        assert s["revision"] in next(iter(datasets))
    assert {t["schema_version"] for t in triples} == {manifest["schema_version"]}
    assert all(t["engine_version"] for t in triples)


def test_iris_match_the_graphs(triples, labels):
    """An IRI here that names nothing in the oracle's graphs.

    The N-Triples form is only worth anything if its subjects and objects are
    the same nodes the published graphs use. A feature renamed on one side
    would give a corpus full of IRIs that resolve to nothing.
    """
    iris, _ = labels
    for t in triples:
        assert t["subject_iri"] == iris[t["subject_id"]], t
        assert t["object_iri"] == iris[t["object_id"]], t
        if t["via_id"]:
            assert t["via_iri"] == iris[t["via_id"]], t


def test_outside_ratio_is_absent_rather_than_zero(triples):
    """Zero is a reading. An unmeasured pair must not look like a nested one.

    Composed triples were never measured, so filling the column with 0.0
    would put 52,704 perfectly-nested-looking rows into any analysis of the
    border disagreement between the two Natural Earth layers.
    """
    for t in triples:
        if t["derivation"] == "composition":
            assert t["outside_ratio"] is None, t
        else:
            assert t["outside_ratio"] is not None, t


def test_every_row_says_what_certified_it(triples, manifest):
    """A certification column that stopped being filled, or filled itself in.

    Both failures look like a clean build. An empty column means the vendored
    verdicts were not found and every row quietly became uncertified; a column
    that is certified everywhere while the verdict file is missing a matrix
    means something decided to guess.
    """
    import collections
    counts = collections.Counter(t["certification"] for t in triples)
    assert manifest["triples"]["by_certification"] == dict(counts)
    assert counts["certified"] == len(triples)
    for t in triples:
        assert t["certificate"], t
        if t["derivation"] == "observed":
            assert t["certificate"].startswith("de9im:")
            assert (t["certificate"] == "de9im:entailed") == t["truth"]
        else:
            assert t["certificate"].startswith("rcc8_composition:")


def test_the_certificates_are_the_vendored_verdicts(triples):
    """A row certified by something other than what is checked in.

    The point of vendoring the verdicts is that the claim on each row can be
    read back out of a file in the repository without Lean. If the two ever
    stopped agreeing, the column would be a decoration.
    """
    import certify
    verdicts = certify.read_vendored()
    assert verdicts, "vendor/de9im_sf_verdicts.tsv is missing or empty"
    for t in triples:
        if t["derivation"] != "observed":
            continue
        want = verdicts[(t["de9im"], t["subject_kind"], t["object_kind"],
                         t["predicate"])]
        assert t["certificate"] == f"de9im:{want}"


def test_a_verdict_that_contradicts_the_oracle_stops_the_build():
    """Shipping a disagreement between the prover and the geometry.

    The two are talking about the same matrix, so one of them is wrong, and
    the worst outcome is a dataset that carries both readings in one row with
    a certification column implying they agree.
    """
    import pytest

    import build
    with pytest.raises(SystemExit) as e:
        build.certified({("FF2F11212", "area", "area", "sfTouches"):
                         "refuted"}, "FF2F11212", "sfTouches", True)
    assert "wrong about this matrix" in str(e.value)
