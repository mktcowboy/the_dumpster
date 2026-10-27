# Agent report: people.json
Wrote `agents/people.json`: 43 entries in exact registry order — 21 Biblical, 2 Second Temple, 5 Tannaitic, 5 Amoraic, 1 Geonic, 7 Rishonim, 2 Acharonim.
Bios range 140–165 words; each entry has 1–4 works, 3–5 themes, 3–5 people connections, and 1–2 sources.
Validated with `python3 json.load`; all work, place, theme, and connection ids resolve against `data/registry.json`; every source URL returned HTTP 200.
Note: Job, Ibn Ezra, and Isserles have empty `places` arrays because Uz, Tudela, and Kraków are absent from the place registry; no false locations were substituted.
