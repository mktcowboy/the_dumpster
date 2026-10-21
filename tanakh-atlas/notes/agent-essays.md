# Agent: Essays
- `agents/essays.json`: 10 essays, 9,155 words total; 8–9 paragraphs each; every essay within 700–1,000 words.
- Validated with `json.load`; all 10 IDs unique; every work/person/theme reference resolves to `data/registry.json`.
- 23 unique sources across the set, 2–3 per essay (Sefaria, Stanford Encyclopedia of Philosophy, Project Gutenberg, Jewish Encyclopedia); all returned HTTP 200.
- Argument-forward coverage of canon, Oral Torah, Talmud, Rashi, codes, philosophy, Kabbalah, prayer, exile/return, and the chain; disputes over Yavneh, Zohar authorship, and Exodus historicity are flagged.
