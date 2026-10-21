Wrote agents/tanakh_works.json: all 24 Tanakh works in canonical order, with registry ids, titles, Hebrew names, divisions, and dates.
Each entry has a 3–5 sentence summary, a why-it-sits-here essay, 3–8 structure units (12 for the Twelve; five books for Psalms), registry-only themes/people/places, four key passages, five connections, and two sources; prose runs 281–320 words.
Validated: JSON parses to 24 entries, all theme/person/place ids and connection targets resolve, all 96 verse references exist in data/tanakh_text.json, and every source URL returns HTTP 200.
Caveats: dates are approximate scholarly ranges, with date_sort set to the earlier end; references follow the project's English/Protestant versification, with Hebrew numbering noted where it differs (Genesis 32, Malachi 4).
The registry lacks Ruth/Naomi/Boaz, Daniel, and a place for Job's Uz, so those arrays are necessarily sparse; the Twelve has twelve structure units by explicit instruction.
