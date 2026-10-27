# Data schema (v1)

## works.json — array of work objects
{
  "id": "genesis",                  // slug
  "title": "Genesis",
  "he_title": "בראשית",
  "also": ["Bereshit"],
  "corpus": "tanakh",               // tanakh | oral | commentary | law | philosophy | mysticism | prayer
  "division": "torah",              // torah | neviim | ketuvim | mishnah | talmud | midrash | ...
  "order": 1,
  "date": "c. 1000–500 BCE (composition); canonized by c. 200 CE",
  "date_sort": -1000,
  "language": "Biblical Hebrew",
  "summary": "2–4 sentences.",
  "why": "Why it sits where it does / why it matters. 2–4 sentences.",
  "structure": [{"name":"...", "note":"..."}],
  "themes": ["covenant","exile"],
  "people": ["abraham","moses"],
  "places": ["sinai","jerusalem"],
  "key_passages": [{"ref":"Genesis 1:1–3","text":"...","note":"..."}],
  "connections": [{"to":"talmud-bavli","why":"..."}],
  "sources": [{"label":"...","url":"..."}]
}

## people.json
{id, name, he_name, dates, era, bio, works:[work ids], places:[], themes:[], key_idea, connections:[{to,why}]}

## places.json
{id, name, he_name, region, coordinates:[lat,lng], ancient, bio, works:[], people:[], themes:[]}

## themes.json
{id, name, he_name, kind:"theme|idea|practice", short, essay, works:[], people:[], places:[], connections:[]}

## timeline.json
{year, sort, label, title, text, works:[], people:[], places:[]}

## essays.json
{id, title, dek, body (HTML-ish paragraphs), works:[], people:[], themes:[]}
