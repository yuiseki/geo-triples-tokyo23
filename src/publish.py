#!/usr/bin/env python3
"""Push the built dataset to the Hub.

Data first, card last, so the repository is never in a state where the card
describes files that have not arrived.

What this refuses to do is more of the point than what it does. The card is
not documentation that happens to sit beside the data: it is what the Hub
reads to find the Parquet at all, and it is where a reader gets the counts
and the digests from. A subset the card does not declare uploads cleanly and
stays invisible; a count the card is wrong about is worse, because it looks
right. So the card is checked against the manifest before anything moves, and
a mismatch stops the push rather than being reported afterwards.

    python3 src/publish.py             # dry run
    python3 src/publish.py --push
"""
import argparse
import hashlib
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "yuiseki/geo-triples-tokyo23"

# The published path of each subset, and the key in the manifest that counts
# its rows. The Hub config name is the same word in both places on purpose:
# a config named one thing and counted under another is how the two drift.
SUBSETS = {
    "triples": "data/triples.parquet",
    "cpt": "data/cpt.parquet",
    "probe": "data/probe.parquet",
}

# Goes up with the tables. Without it a reader has the digests only from the
# card, and a card is a thing somebody can edit.
EXTRA = ["data/manifest.json", "vendor/de9im_sf_verdicts.tsv"]


def digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--card", default=os.path.join(BASE, "README.md"))
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    members = list(SUBSETS.values()) + EXTRA
    paths = []
    for m in members:
        p = os.path.join(BASE, m)
        if not os.path.exists(p):
            raise SystemExit(f"missing {p}; run src/build.py first")
        paths.append((m, p))

    manifest = json.load(open(os.path.join(BASE, "data", "manifest.json"),
                              encoding="utf-8"))
    card = open(a.card, encoding="utf-8").read()

    for subset, path in SUBSETS.items():
        # The Hub needs both the config name and the path it points at. A
        # config declared without its file, or a file with no config, is the
        # failure that produces a dataset page with nothing on it.
        if not re.search(r"^\s+- config_name: %s$" % re.escape(subset),
                         card, re.M):
            raise SystemExit(f"the card declares no config named {subset}")
        if not re.search(r"^\s+path: %s$" % re.escape(path), card, re.M):
            raise SystemExit(f"the card's data_files do not point at {path}")

        rows = manifest[subset]["rows"]
        if f"{rows:,}" not in card:
            raise SystemExit(f"the card does not mention {rows:,} rows "
                             f"for {subset}")

        # The digest is the whole reproducibility claim. Publishing a card
        # that quotes a digest the file does not have would make the claim
        # unfalsifiable in the one direction that matters.
        actual = digest(os.path.join(BASE, path))
        if actual != manifest[subset]["sha256"]:
            raise SystemExit(f"{path} is {actual}, but the manifest says "
                             f"{manifest[subset]['sha256']}; rebuild")
        if actual not in card:
            raise SystemExit(f"the card does not quote the digest of {path}")

    if manifest["licence"]["id"] not in card and "odbl" not in card.lower():
        raise SystemExit("the card does not state the licence")

    total = sum(os.path.getsize(p) for _, p in paths)
    print(f"{a.repo}  schema {manifest['schema_version']}")
    for subset in SUBSETS:
        print(f"   {subset:10} {manifest[subset]['rows']:10,} rows")
    for m, p in paths:
        print(f"   {m:30} {os.path.getsize(p)/1e6:8.2f} MB")
    print(f"   {'total':30} {total/1e6:8.2f} MB")
    print(f"   licence {manifest['licence']['id']}, share-alike "
          f"{manifest['licence']['share_alike']}")
    print("card declares every subset, its row count and its digest")

    if not a.push:
        print("dry run. pass --push to upload")
        return 0

    from huggingface_hub import HfApi
    api = HfApi()
    api.create_repo(a.repo, repo_type="dataset", exist_ok=True)
    for m, p in paths:
        print(f"uploading {m} ...", flush=True)
        api.upload_file(path_or_fileobj=p, path_in_repo=m,
                        repo_id=a.repo, repo_type="dataset")
    for name in ("LICENSE", "ATTRIBUTION.md"):
        api.upload_file(path_or_fileobj=os.path.join(BASE, name),
                        path_in_repo=name, repo_id=a.repo, repo_type="dataset")
    api.upload_file(path_or_fileobj=a.card, path_in_repo="README.md",
                    repo_id=a.repo, repo_type="dataset")
    print(f"pushed to https://huggingface.co/datasets/{a.repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
