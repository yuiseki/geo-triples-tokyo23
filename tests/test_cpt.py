"""The cpt table: the three forms, and whether the text follows the triple."""
import collections

import build
import vocab

EXPECTED = {
    "rows": 483922,
    "ntriples": 202116,
    "en": 131140,
    "ja": 150666,
}


def test_counts(cpt, manifest):
    """The text changed without the card that quotes its size changing.

    The three numbers are not independent: ntriples is every true triple, and
    en and ja are equal only because the seven Natural Earth features with no
    label at all are the same seven in both languages. A build where they
    stopped being equal would be a build where one language lost labels.
    """
    by_form = collections.Counter(r["form"] for r in cpt)
    assert len(cpt) == EXPECTED["rows"]
    for form in vocab.FORMS:
        assert by_form[form] == EXPECTED[form], form
    assert manifest["cpt"]["by_form"] == dict(by_form)


def test_every_true_triple_has_exactly_one_ntriples_row(cpt, triples):
    """A missing line would hide the label gap the form column exists to show.

    N-Triples is unconditional so that a feature without a Japanese label
    appears as a ja row that is absent beside an ntriples row that is
    present. If ntriples were itself conditional, counting rows per form
    would measure nothing.
    """
    keys = collections.Counter(
        (r["subject_id"], r["predicate"], r["object_id"], r["derivation"],
         r["via_id"] or "")
        for r in cpt if r["form"] == "ntriples")
    expected = collections.Counter(
        (t["subject_id"], t["predicate"], t["object_id"], t["derivation"],
         t["via_id"] or "")
        for t in triples if t["truth"])
    assert keys == expected


def test_a_sentence_never_appears_without_its_line(cpt):
    """An en or ja row with no ntriples row above it.

    That would mean a sentence exists for a triple the canonical form does
    not, which inverts the layering: the sentence would be the primary record
    and nothing would tie it back to an IRI.
    """
    lines = {(r["subject_id"], r["predicate"], r["object_id"],
              r["derivation"], r["via_id"] or "")
             for r in cpt if r["form"] == "ntriples"}
    for r in cpt:
        if r["form"] == "ntriples":
            continue
        key = (r["subject_id"], r["predicate"], r["object_id"],
               r["derivation"], r["via_id"] or "")
        assert key in lines, r


def test_ntriples_is_well_formed(cpt):
    """Text that a triple store would refuse to load.

    The whole reason for carrying this form is that it is the ordinary
    serialisation. A line missing its trailing full stop, or with a bare id
    where an IRI belongs, would be a corpus that teaches a shape nothing
    accepts.
    """
    for r in cpt:
        if r["form"] != "ntriples":
            continue
        lines = r["text"].split("\n")
        assert len(lines) == (3 if r["derivation"] == "composition" else 1), r
        for line in lines:
            assert line.endswith(" ."), line
            parts = line[:-2].split(" ")
            assert len(parts) == 3, line
            for p in parts:
                assert p.startswith("<") and p.endswith(">"), line
                assert "://" in p, line


def test_the_conclusion_is_the_last_line(cpt, triples):
    """A chain whose final statement is not the row's own triple.

    A composed row carries its two premises so the deduction can be read. If
    the conclusion were not last, or were a different triple, the columns
    beside the text would describe something the text does not say.
    """
    index = {(t["subject_id"], t["predicate"], t["object_id"], t["via_id"]): t
             for t in triples if t["truth"]}
    for r in cpt:
        if r["form"] != "ntriples" or r["derivation"] != "composition":
            continue
        t = index[(r["subject_id"], r["predicate"], r["object_id"],
                   r["via_id"])]
        assert r["text"].split("\n")[-1] == vocab.nt_line(t), r


def test_sentences_are_reproducible_from_their_triple(cpt, triples, labels):
    """Text that cannot be regenerated from the row it sits beside.

    Every sentence is a template and two labels, so re-rendering must give
    back the same string. A failure means something got into the text that is
    not in the triple: a hand edit, a stale label, or a template applied to
    the wrong pair.
    """
    iris, names = labels
    index = {(t["subject_id"], t["predicate"], t["object_id"], t["via_id"]): t
             for t in triples if t["truth"]}
    # The premise predicates are not columns of the triples table: they are
    # recoverable from the rcc8 of the two observed pairs a composed row went
    # through, so carrying them would be two more columns saying what another
    # row already says.
    # Only the pairs that have an RCC8 relation at all. A composed row's two
    # premises always do, because composition is defined over regions, so
    # skipping the rest loses nothing and keeps a point out of a table that
    # has no row for it.
    observed = {(t["subject_id"], t["object_id"]): vocab.RCC8_TO_SF[t["rcc8"]]
                for t in triples
                if t["derivation"] == "observed" and t["rcc8"]}
    checked = 0
    for r in cpt:
        if r["form"] == "ntriples":
            continue
        t = dict(index[(r["subject_id"], r["predicate"], r["object_id"],
                        r["via_id"])])
        if t["derivation"] == "composition":
            t["premise_a_predicate"] = observed[(t["subject_id"], t["via_id"])]
            t["premise_b_predicate"] = observed[(t["via_id"], t["object_id"])]
        parts = build.statements(t, iris)
        assert vocab.sentence_text(parts, names, r["form"]) == r["text"], r
        checked += 1
    assert checked == EXPECTED["en"] + EXPECTED["ja"]


def test_no_sentence_borrows_a_name_from_another_language(cpt, labels):
    """A romanised name sitting in a Japanese sentence.

    This is what a fallback looks like when it is added for coverage: the ja
    row count goes up and the text quietly becomes half English. Checked
    against the labels directly rather than by re-rendering, because a
    fallback in the renderer would reproduce itself perfectly.
    """
    _, names = labels
    other = {"en": "ja", "ja": "en"}
    for r in cpt:
        if r["form"] not in vocab.LANGS:
            continue
        for side in ("subject_id", "object_id"):
            mine = names.get((r[side], r["form"]))
            theirs = names.get((r[side], other[r["form"]]))
            assert mine, r
            assert mine in r["text"], r
            if theirs and theirs != mine and not inside_a_label(theirs, r,
                                                                names):
                assert theirs not in r["text"], (r, theirs)


def inside_a_label(text, row, names):
    """Whether this string is part of a label the sentence legitimately uses.

    An editor may put both languages in one name tag: name:en of
    渋谷区立松濤中学校 is "渋谷区立松濤中学校 Shoto Junior High School". The
    ward's Japanese name is then inside the English sentence because the
    school's own English label contains it, which says nothing about a
    fallback in the renderer.
    """
    for side in ("subject_id", "object_id"):
        for lang in vocab.LANGS:
            label = names.get((row[side], lang))
            if label and text in label and text != label:
                return True
    return False


def test_only_spoken_predicates_become_sentences(cpt):
    """sfIntersects or sfCrosses turning up as text.

    sfIntersects holds of every observed pair and says almost nothing;
    sfCrosses is never true between two areas. Both belong in the triples
    table. A sentence saying one of them would be filler that a model would
    learn to produce.
    """
    for r in cpt:
        if r["form"] in vocab.LANGS:
            assert r["predicate"] in vocab.SPOKEN, r


def test_the_label_gap_is_visible_in_the_counts(cpt, triples):
    """The gap between the forms should be explainable, not just present.

    If the difference stops being accounted for by unspoken predicates plus
    unlabelled features, sentences are being dropped for some other reason
    and nobody would notice from the counts alone.
    """
    unspoken = sum(1 for t in triples
                   if t["truth"] and not vocab.wording(t))
    by_form = collections.Counter(r["form"] for r in cpt)
    gaps = {lang: by_form["ntriples"] - unspoken - by_form[lang]
            for lang in vocab.LANGS}

    # sfIntersects, true of every observed pair and saying almost nothing.
    # It is the whole of the unspoken set: the predicates a point and an area
    # have no wording for are also the ones that are never true of them, so
    # adding the places moved this number by exactly the number of new pairs.
    assert unspoken == 51436

    # The two languages part company here, and the direction is the useful
    # part. Seven Natural Earth features carry no label in any language and
    # account for the Japanese gap entirely. The English gap is four orders
    # larger because a place in OpenStreetMap usually has name:ja and often
    # has no name:en, which is a fact about the source rather than about this
    # build.
    assert gaps["ja"] == 14
    assert gaps["en"] == 19540
