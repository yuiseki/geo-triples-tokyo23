"""The evaluation set: one parent per place, and the contamination it admits.

The set exists because the first evaluation written for this work could not
be used: it asked which prefecture each of 1,134 Japanese municipalities is
in, and exactly one of those places appears in this corpus. A probe the
corpus says nothing about measures the model that was there before.

What replaced it asks the same shape of question about places the corpus does
talk about, which makes it a recall test rather than a generalisation test.
The tests below hold that line in both directions: every answer must appear in
cpt, and the set must not silently become something else.
"""
import collections

EXPECTED = {
    "place-in-ward": 6162,
    "ward-in-state": 17,
    "state-in-country": 2711,
}


def test_counts(probe, manifest):
    by_level = collections.Counter(r["level"] for r in probe)
    assert dict(by_level) == EXPECTED
    assert manifest["probe"]["by_level"] == dict(by_level)
    assert manifest["probe"]["rows"] == len(probe)


def test_one_row_per_child(probe):
    """A place with two answers, both scored, both counted.

    The parent comes from a pair of layers rather than from a relation, and
    nothing in the geometry stops a ward meeting two states. Six of the 23
    wards meet Chiba as well as Tokyo. Those are dropped at build time; this
    is the check that they were.
    """
    seen = collections.Counter(r["child_id"] for r in probe)
    assert [c for c, n in seen.items() if n > 1] == []


def test_every_answer_is_stated_in_the_corpus(probe, cpt):
    """The claim on the card, as a test rather than as a sentence.

    If an answer were absent from cpt, a model scoring on it would be scoring
    on something it was never shown, and the number would mean the opposite of
    what the card says it means.
    """
    stated = {(r["subject_id"], r["object_id"]) for r in cpt}
    missing = [r for r in probe
               if (r["child_id"], r["parent_id"]) not in stated]
    assert missing == []


def test_the_japanese_half_is_a_subset_not_a_translation(probe, manifest):
    """Scoring Japanese on rows whose labels were quietly filled from English.

    Seven Natural Earth features carry no label in either language, and many
    more carry one only in English. A row without both labels is not asked in
    Japanese; it must not be asked with an English string standing in.
    """
    both = [r for r in probe if r["child_ja"] and r["parent_ja"]]
    assert manifest["probe"]["answerable_ja"] == len(both)
    assert len(both) < len(probe)
    # Not that the two are always different strings: a place whose Japanese
    # name is written in Latin script has the same label in both, and Torch
    # Tower is one. What must not happen is a row counted as answerable in
    # Japanese with no Japanese label at all, which the filter above is.
    assert all(r["child_ja"] and r["parent_ja"] for r in both)


def test_the_chance_rate_is_the_generous_one(probe, manifest):
    """A denominator that flattered the result.

    Chance is quoted per level, and the two levels are not choosing among the
    same things. Getting this wrong in the other direction would make 94% at
    the ward level look like nothing.
    """
    c = manifest["probe"]["candidates"]
    assert c["state-in-country"] == 258
    assert c["ward-in-state"] == 47
    assert c["place-in-ward"] == 23
    parents = {r["level"]: set() for r in probe}
    for r in probe:
        parents[r["level"]].add(r["parent_id"])
    for level, seen in parents.items():
        assert len(seen) <= c[level], level


def test_the_answer_is_not_read_off_the_relation(probe):
    """Rebuilding the parent from the geometry instead of the attribute.

    Natural Earth draws each coastline twice, once per layer, and the
    vertices do not agree: 40.7% of the states merely overlap the country
    they belong to, and only 21 of Japan's 47 prefectures are within Japan.
    A probe built on within would be scoring the model against that artefact,
    so most of these rows are deliberately not within.
    """
    by_rcc8 = collections.Counter(r["rcc8"] for r in probe)
    assert by_rcc8["PO"] > 0
    assert by_rcc8["NTPP"] + by_rcc8["TPP"] < len(probe)
    # And a place mapped as a node has no RCC8 relation at all.
    assert by_rcc8[""] > 0
