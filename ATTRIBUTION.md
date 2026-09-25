# Attribution and licence

## The short version

This dataset is a Derivative Database of OpenStreetMap. Everything in it
carries ODbL-1.0, including the English and Japanese sentences, and so does
any corpus that contains them.

| what | licence | share-alike | attribution |
|---|---|---|---|
| `data/triples.parquet` | ODbL-1.0 | yes | required |
| `data/cpt.parquet`, all three forms | ODbL-1.0 | yes | required |
| `data/manifest.json` | ODbL-1.0 | yes | required |
| the code in `src/` and `tests/` | MIT | no | as MIT requires |
| `vendor/rcc8_known_table.tsv` | see below | | |

Share-alike is contagious. Two of the three sources are public domain and
that changes nothing: one ODbL source makes the whole derived database ODbL,
so there is no combination in which Natural Earth's terms soften
OpenStreetMap's. The oracle's manifest computes this and this one carries the
answer through rather than deciding it again.

## Why the sentences are covered too

This is the part that is easy to get wrong, so it is stated plainly.

A sentence here is a template filled with two names, and which template is
chosen is decided by a DE-9IM matrix computed from OpenStreetMap geometry.
The text is therefore not a description of the database sitting alongside it.
It is an extraction from it: every sentence is a Substantial extraction in
ODbL's sense, because the relation it states was read off the polygons.

Three consequences.

- A corpus that includes `cpt.parquet`, in any of its three forms, is a
  Derivative Database and carries ODbL-1.0.
- The same holds for the N-Triples form, which is the same content with the
  IRIs spelled out rather than the names.
- Training a model on it is where the law is genuinely unsettled, and this
  file does not pretend otherwise. What is not unsettled is the corpus: if
  you redistribute the text, you redistribute it under ODbL.

The safe way to mix sources is to keep this apart from CC0 and public-domain
material rather than to discover later that a whole corpus went ODbL.
Wikidata's P131 asserts a containment and is CC0; a containment *computed
from these polygons* is not.

## OpenStreetMap

> (c) OpenStreetMap contributors, available under the Open Database License.
> https://www.openstreetmap.org/copyright

The 23 Tokyo wards come from
[`yuiseki/osm-tokyo23-src-2026-08`](https://huggingface.co/datasets/yuiseki/osm-tokyo23-src-2026-08)
at revision `e60e017f6a77fa81014b11ca953ae0b2b177edaf`, cut from
`planet-260831.osm.pbf` (md5 `c67437924cf55de40e8708c7192f354d`). That
snapshot is the only OpenStreetMap source.

The Open Database License is at
https://opendatacommons.org/licenses/odbl/1-0/ . ODbL-1.0 section 4.2 allows
the notice requirement to be met with the licence's URI rather than its text,
which is what this file does.

## Natural Earth

Natural Earth places its data in the public domain. No permission is needed
and no attribution is required, though the project asks for credit where
practical:

> Made with Natural Earth. Free vector and raster map data @
> naturalearthdata.com

The 258 countries and 4,596 states come from
[`yuiseki/ne-admin0-10m`](https://huggingface.co/datasets/yuiseki/ne-admin0-10m)
at version 5.1.1, revision `d1d37a11992230933819fdb3f363dc919bb547a5`.

## The oracle

The relations were computed by
[YuisekinGeoSPARQL](https://github.com/yuiseki/YuisekinGeoSPARQL), which loads
the sources into Apache Jena Fuseki 6.2.0 (Apache License 2.0, not modified)
and compares GEOS through shapely against JTS inside Jena, pair by pair.

## The composition table

`vendor/rcc8_known_table.tsv` is copied from
[LeanGeospatial](https://github.com/yuiseki/LeanGeospatial), where it is
`data/rcc8_known_table.tsv`. Its own header records what it is: the RCC8
composition table as stated on
[Wikipedia](https://en.wikipedia.org/wiki/Region_connection_calculus), revid
1366466711 of 2026-07-28.

It is used here as a premise rather than as a citation because
LeanGeospatial's theorem `table_eq_published` shows that the table derived
from its own definitions agrees with this one on all 64 cells. Reading the
TSV is therefore reading the proved table, and is far less likely to go wrong
than transcribing 64 cells by hand a second time.

Wikipedia's text is CC BY-SA 4.0. A 64-row table of which relations are
possible is a statement of mathematical fact rather than an expressive work,
and the same table appears in Randell, Cui and Cohn (1992) and in every
survey since; it is reproduced here with its source named.

## The code

MIT. See LICENSE. It does not cover the data, and the data does not cover it.
