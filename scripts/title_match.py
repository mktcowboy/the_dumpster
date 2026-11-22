"""Fuzzy title matching for the Best-of master lists.

Variants of one work, inside one category, collapse to a single row:
case, punctuation, diacritics, curly quotes, "&" / "and", a leading
The/A/An, subtitles after ":" or " - ", parenthetical and bracketed
suffixes, season labels, creator text embedded in the title, creator
name variants, and small typos. Two works that share a title stay apart
when both creators are known and disagree.

The legacy key reproduces the previous exact normalizer so a match that
already merged still merges. Newer keys only add merges.

In the place categories the creator field is a location, so a city and its
country agree, and a trailing location on the venue name is dropped.
bestof_merges.json holds reviewed creator aliases, forced merges, and forced
splits for cases the thresholds should not decide.
"""
import collections
import difflib
import functools
import json
import os
import re
import unicodedata

# Token-sort ratio (difflib) required before two titles can fuzzy-merge.
FUZZY_RATIO = 0.92
# A token that is not identical must still look like a typo, not a different word.
TOKEN_RATIO = 0.90
# One-edit typos on a long token can sit just under TOKEN_RATIO (accordion / accordian).
EDIT_RATIO = 0.84
# Joined title shorter than this is exact-match only. Short names collide too easily.
MIN_FUZZY_CHARS = 6

ROMAN = {
    'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10',
    'xi': '11', 'xii': '12', 'xiii': '13', 'xiv': '14', 'xv': '15', 'xvi': '16', 'xvii': '17',
    'xviii': '18', 'xix': '19', 'xx': '20',
}
WORDN = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'}
ENUM_PREV = {'vol', 'volume', 'part', 'book', 'chapter'}
# Extra tokens that may appear on only one spelling of the same work.
EXTRA_OK = {'and', 'the', 'a', 'an', 'of', 'too', 'review', 'reviews'}
# Single-token stand-ins used in track titles ("U" for "you"). Applied only when the title has other words.
EQUIV = {'u': 'you', 'ur': 'your'}
ARTICLES = {'the', 'a', 'an'}
MUSIC = {'Albums', 'Songs'}
# The creator field holds a city or country here, not a person.
PLACES = {'Travel & Hotels', 'Restaurants & Food', 'Bars & Cocktails'}
# A trailing "Review" is a headline in these. In a book or podcast it can be the name.
REVIEW_KEEP = {'Books', 'Kids & YA Books', 'Comics & Graphic Novels', 'Cookbooks', 'Podcasts'}
# "<word> Edition" that names a release of the same work, not a different work.
EDITION_WORDS = {
    'deluxe', 'gold', 'base', 'standard', 'complete', 'ultimate', 'premium', 'definitive',
    'digital', 'collectors', 'goty', 'enhanced', 'anniversary', 'expanded', 'special',
}
# Trailing token runs that are packaging, not title. Longest first.
NOISE_TAILS = (
    ('original', 'motion', 'picture', 'soundtrack'), ('original', 'soundtrack'),
    ('game', 'of', 'the', 'year', 'edition'), ('nintendo', 'switch', '2', 'edition'),
    ('switch', '2', 'edition'), ('soundtrack',), ('ost',), ('remake',),
    # "Neighbors and Other Stories": _strip_decorations already took "Stories".
    ('and', 'other'),
)
# "Jury Duty Presents: Company Retreat" is "Jury Duty: Company Retreat".
PRESENTS_CATS = {'TV', 'Movies', 'Documentaries', 'Theater'}
# A maker's name in front of its own product line: "Apple iPhone 18 Pro" / "iPhone 18 Pro".
TECH_BRANDS = {'apple', 'google', 'samsung', 'valve', 'amazon', 'meta', 'microsoft', 'sony', 'nintendo'}
# Books that end in ", or <subtitle>": "Missing Persons, or My Grandmother's Secrets".
OR_SUBTITLE_CATS = {'Books', 'Kids & YA Books'}
# Song credit written at the end of the title: "Girl, so confusing featuring lorde".
# Nothing after the guest may look like a title, so "Taylor Swift feat. Post Malone,
# 'Fortnight'" keeps its song.
_FEAT_TAIL = re.compile(r'(?<=\S)\s+\(?(?:featuring|feat\.?|ft\.?)\s+[^,:;"“”‘’\-–—/|()]+\)?\s*$', re.I)
# Franchise formats whose U.K. edition lists name with a country tag.
TV_FORMATS = {'traitors', 'celebritytraitors'}
# Placeholder credits that name no artist. They agree with any creator.
COMPAT_WILDCARD = {'various artists', 'various', 'soundtrack', 'original soundtrack', 'ost', 'cast', 'original cast'}


def _names(text):
    return set(text.replace('\n', '').split('|'))


# Countries, states, and regions. A location that names only these agrees with any
# city inside it. City-states and city-or-state names (Singapore, New York,
# Washington, Victoria) are left out so they still count as a city.
# Continents, and the U.S. and U.K. with their four nations.
SUPRA = _names('''
world|europe|asia|africa|oceania|americas|north america|south america|latin america|central america|
caribbean|middle east|nordics|scandinavia|southeast asia|south asia|east asia|central asia|
indian ocean|pacific|south pacific|mediterranean|balkans|baltics|usa and canada|us and canada|
uk and ireland|british isles|usa|us|u s|united states|united states of america|america|uk|u k|
united kingdom|great britain|britain|england|scotland|wales|northern ireland|ireland
''')
COUNTRIES = _names('''
afghanistan|albania|algeria|andorra|angola|antigua|argentina|armenia|australia|austria|azerbaijan|
bahamas|bahrain|bangladesh|barbados|belarus|belgium|belize|benin|bhutan|bolivia|
bosnia and herzegovina|botswana|brazil|brunei|bulgaria|burkina faso|burundi|cambodia|cameroon|
canada|cape verde|chad|chile|china|colombia|comoros|congo|costa rica|croatia|cuba|cyprus|czechia|
czech republic|denmark|dominica|dominican republic|ecuador|egypt|el salvador|estonia|eswatini|
ethiopia|faroe islands|fiji|finland|france|french polynesia|gabon|gambia|georgia|germany|ghana|
greece|greenland|grenada|guatemala|guinea|guyana|haiti|honduras|hungary|iceland|india|indonesia|
iran|iraq|israel|italy|ivory coast|jamaica|japan|jordan|kazakhstan|kenya|kiribati|korea|south korea|
kosovo|kyrgyzstan|laos|latvia|lebanon|lesotho|liberia|libya|liechtenstein|lithuania|madagascar|
malawi|malaysia|maldives|mali|malta|mauritania|mauritius|mexico|moldova|mongolia|montenegro|morocco|
mozambique|myanmar|namibia|nepal|netherlands|new zealand|nicaragua|niger|nigeria|north macedonia|
norway|oman|pakistan|palau|panama|papua new guinea|paraguay|peru|philippines|poland|portugal|
puerto rico|qatar|romania|russia|rwanda|saint lucia|st lucia|samoa|sao tome and principe|
saudi arabia|senegal|serbia|seychelles|sierra leone|slovakia|slovenia|solomon islands|somalia|
south africa|spain|sri lanka|sudan|suriname|sweden|switzerland|syria|taiwan|tajikistan|tanzania|
thailand|timor leste|togo|tonga|trinidad and tobago|tunisia|turkey|turkiye|turkmenistan|
turks and caicos|uganda|ukraine|uae|united arab emirates|uruguay|uzbekistan|vanuatu|venezuela|
vietnam|yemen|zambia|zimbabwe
''')
# States, provinces, and regions inside one country. "Naples, Florida" is not the Naples
# a city list means, so a one-word head never loses one of these in Travel & Hotels.
SUBNATIONAL = _names('''
alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|hawaii|idaho|
illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|
mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york state|
north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|
south dakota|tennessee|texas|utah|vermont|virginia|west virginia|wisconsin|wyoming|calif|fla|tenn|
mich|ontario|quebec|british columbia|alberta|nova scotia|new south wales|queensland|tasmania|
western australia|south australia|bali|tuscany|sicily|sardinia|puglia|provence|normandy|andalusia|
catalonia|bavaria|patagonia|rajasthan|kerala|hokkaido|okinawa|cotswolds|lombok|riviera maya|
french riviera|amalfi coast|dolomites|alps|swiss alps
''')
REGIONS = SUPRA | COUNTRIES | SUBNATIONAL
# Two-letter state codes. Only after a comma: a lone "LA" is Los Angeles.
US_CODES = set('al ak az ar ca co ct de dc fl ga hi id il in ia ks ky la me md ma mi mn ms mo mt ne nv nh nj nm ny nc nd oh ok or pa ri sc sd tn tx ut vt va wa wv wi wy'.split())
# Words that do not tell two places apart ("New York" / "New Orleans").
PLACE_GENERIC = {
    'new', 'san', 'santa', 'st', 'ste', 'saint', 'sainte', 'city', 'the', 'de', 'del', 'da', 'do', 'la', 'le',
    'les', 'el', 'los', 'las', 'of', 'and', 'port', 'fort', 'north', 'south', 'east', 'west', 'island',
    'islands', 'isle', 'lake', 'mount', 'beach', 'bay', 'valley', 'national', 'park', 'province',
    'county', 'district', 'old', 'upper', 'lower', 'downtown', 'centre', 'center', 'entry',
}
# Boroughs, nicknames, and local spellings of one city ("Moebius Milano" is in Milan).
PLACE_ALIAS = {
    'nyc': 'york', 'brooklyn': 'york', 'manhattan': 'york', 'queens': 'york', 'bronx': 'york',
    'milano': 'milan', 'firenze': 'florence', 'roma': 'rome', 'venezia': 'venice', 'napoli': 'naples',
    'torino': 'turin', 'lisboa': 'lisbon', 'wien': 'vienna', 'munchen': 'munich', 'praha': 'prague',
    'sevilla': 'seville', 'kobenhavn': 'copenhagen',
}
# Words that may sit between a venue name and its city ("Astir Palace Hotel Athens").
TAIL_GENERIC = {'hotel', 'hotels', 'resort', 'resorts', 'spa', 'and', 'the', 'at'}

OVERRIDES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bestof_merges.json')

# Section labels that some lists store in the creator field.
LABELS = {
    'fiction', 'nonfiction', 'poetry', 'science', 'ideas', 'music', 'politics', 'history',
    'biography & memoir', 'memoir', 'novel', "sport & children's", 'sports', 'non-fiction',
}
STOP = {
    'a', 'an', 'the', 'of', 'and', 'or', 'to', 'in', 'on', 'for', 'with', 'from', 'into', 'about',
    'over', 'after', 'before', 'by', 'at', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'this', 'that', 'these', 'those', 'it', 'its', 'will', 'would', 'can', 'may', 'not', 'no', 'nor',
    'but', 'if', 'than', 'then', 'so', 'such', 'upon', 'per', 'via', 'across', 'against', 'among',
    'through', 'during', 'without', 'within', 'just', 'your', 'you', 'my', 'our', 'their', 'his',
    'her', 'have', 'has', 'had', 'always', 'everyone', 'everything', 'something', 'here', 'there',
    'when', 'where', 'what', 'who', 'how', 'why', 'all', 'out', 'up', 'down', 'off', 'into',
}
NAME_OK = {'the', 'and', 'of', 'de', 'da', 'di', 'van', 'von', 'la', 'le', 'el', 'y', 'bin', 'st', 'du', 'del', 'della', 'jr', 'sr'}

# Obvious category aliases. The value is the label already used in these directories.
CATEGORY_ALIASES = {
    'film': 'Movies', 'films': 'Movies', 'movie': 'Movies', 'movies': 'Movies',
    'cinema': 'Movies', 'motion picture': 'Movies', 'motion pictures': 'Movies',
    'tv': 'TV', 'television': 'TV', 'tv show': 'TV', 'tv shows': 'TV',
    'television show': 'TV', 'television shows': 'TV',
    'album': 'Albums', 'albums': 'Albums', 'record': 'Albums', 'records': 'Albums',
    'song': 'Songs', 'songs': 'Songs', 'single': 'Songs', 'singles': 'Songs',
    'book': 'Books', 'books': 'Books',
    'video game': 'Video Games', 'video games': 'Video Games',
    'videogame': 'Video Games', 'videogames': 'Video Games',
    'podcast': 'Podcasts', 'podcasts': 'Podcasts',
    'documentary': 'Documentaries', 'documentaries': 'Documentaries',
    'doc': 'Documentaries', 'docs': 'Documentaries',
    'restaurant': 'Restaurants & Food', 'restaurants': 'Restaurants & Food',
    'food': 'Restaurants & Food', 'restaurants and food': 'Restaurants & Food',
    'travel': 'Travel & Hotels', 'hotel': 'Travel & Hotels', 'hotels': 'Travel & Hotels',
    'travel and hotels': 'Travel & Hotels',
    'bar': 'Bars & Cocktails', 'bars': 'Bars & Cocktails',
    'cocktail': 'Bars & Cocktails', 'cocktails': 'Bars & Cocktails',
    'bars and cocktails': 'Bars & Cocktails',
    'tech': 'Tech & Gadgets', 'gadget': 'Tech & Gadgets', 'gadgets': 'Tech & Gadgets',
    'tech and gadgets': 'Tech & Gadgets',
    'comic': 'Comics & Graphic Novels', 'comics': 'Comics & Graphic Novels',
    'graphic novel': 'Comics & Graphic Novels', 'graphic novels': 'Comics & Graphic Novels',
    'comics and graphic novels': 'Comics & Graphic Novels',
    'kids and ya books': 'Kids & YA Books', 'kids and ya': 'Kids & YA Books',
    'ya books': 'Kids & YA Books', 'young adult': 'Kids & YA Books', 'young adult books': 'Kids & YA Books',
    'cookbook': 'Cookbooks', 'cookbooks': 'Cookbooks',
    'board game': 'Board Games', 'board games': 'Board Games',
    'theater': 'Theater', 'theatre': 'Theater', 'broadway': 'Theater',
    'wine': 'Wine & Spirits', 'spirits': 'Wine & Spirits', 'wine and spirits': 'Wine & Spirits',
    'beauty': 'Beauty',
    'photography': 'Photography', 'photo': 'Photography', 'photos': 'Photography',
    'science': 'Science',
    'sport': 'Sports', 'sports': 'Sports',
    'anime': 'Anime',
    'app': 'Apps', 'apps': 'Apps', 'application': 'Apps', 'applications': 'Apps',
}

_SEASON = re.compile(
    r'(?:[:\-–—,]\s*|\s+)\b(?:season|series)\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|[ivx]{1,4})\b',
    re.I)
_QUOTES = (
    ('\u2018', "'"), ('\u2019', "'"), ('\u201a', "'"), ('\u201b', "'"),
    ('\u201c', '"'), ('\u201d', '"'), ('\u201e', '"'), ('\u201f', '"'),
)
_LETTERS = str.maketrans({
    '\u00f8': 'o', '\u00d8': 'O', '\u00e6': 'ae', '\u00c6': 'AE', '\u0153': 'oe', '\u0152': 'OE', '\u00df': 'ss',
    '\u0142': 'l', '\u0141': 'L', '\u0111': 'd', '\u0110': 'D', '\u00fe': 'th', '\u00de': 'TH', '\u0131': 'i',
})


def fold_chars(s):
    """Straighten quotes and drop diacritics. Case is preserved."""
    for src, dst in _QUOTES:
        s = s.replace(src, dst)
    # NFKD leaves these whole, so "Nesbø" would lose its "o".
    s = s.translate(_LETTERS)
    s = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in s if not unicodedata.combining(c))


def canon_topic(topic):
    """Map an obvious category alias onto the label these lists already use."""
    folded = fold_chars(topic or '').lower().replace('&', ' and ')
    folded = re.sub(r'[^a-z0-9]+', ' ', folded).strip()
    return CATEGORY_ALIASES.get(folded, (topic or '').strip())


def _legacy_norm(title):
    """Previous exact key: case, punctuation, leading article, parens, season/part labels."""
    t = fold_chars(title)
    t = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', t)
    t = re.sub(r'[:,]?\s*(a novel|a memoir|a cookbook|stories)$', '', t.strip(), flags=re.I)
    t = re.sub(
        r"[:\s,\-–]*(season|series|part)\s+(\w+)\b",
        lambda m: ' s' + WORDN.get(m.group(2).lower(), m.group(2).lower()),
        t, flags=re.I)
    t = re.sub(r'[:\s]*limited series$', '', t, flags=re.I)
    w = re.sub(r"['’]", '', t)
    w = re.sub(r'&', ' and ', w)
    w = re.split(r'\W+', w.lower())
    w = [ROMAN.get(x, x) if i == len(w) - 1 or (i > 0 and w[i - 1] in ('vol', 'volume')) else x for i, x in enumerate(w) if x]
    if w and w[0] in ARTICLES and len(w) > 1:
        w = w[1:]
    return ''.join(w)


def _legacy_base(title):
    if ':' not in title:
        return None
    return _legacy_norm(title.split(':', 1)[0])


def is_non_creator(creator):
    """Award slots, section labels, and blurbs are not a person, artist, or place."""
    t = (creator or '').strip().lower()
    if not t:
        return True
    if t in LABELS or 'section labels' in t:
        return True
    if re.search(r'\b(best|winner|winners|nominee|nominees|outstanding|award|awards)\b', t):
        return True
    if re.search(r'\bof the year\b', t) or t.startswith(('pick for', 'game awards', 'destination')):
        return True
    if len(t) >= 60:
        return True
    return False


def known_creator(creator):
    return bool(creator and creator.strip()) and not is_non_creator(creator)


def _name_key(text):
    """Alias lookup key: folded, lowercase, letters and digits only."""
    s = fold_chars(text or '').lower().replace('&', ' and ')
    return re.sub(r'[^a-z0-9]+', '', s)


def _load_overrides(path=OVERRIDES_PATH):
    """Read bestof_merges.json once. A missing file means no overrides."""
    try:
        with open(path) as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        raw = {}
    aliases = {}
    for n, group in enumerate(raw.get('aliases') or []):
        for name in group:
            aliases[_name_key(name)] = (group[0], n)
    return {'aliases': aliases, 'alias_groups': raw.get('aliases') or [],
            'merge': raw.get('merge') or {}, 'split': raw.get('split') or {}}


OVERRIDES = _load_overrides()
# (kind, category, index) -> times an override changed a result. near_miss.py reads it.
override_hits = collections.Counter()


def alias_of(creator):
    """Canonical name for a creator in an alias group, else None."""
    hit = OVERRIDES['aliases'].get(_name_key(creator))
    return hit[0] if hit else None


@functools.lru_cache(maxsize=None)
def _people(creator):
    """Name tuples for one creator string. Order and feat. credits do not matter."""
    whole = alias_of(creator)
    if whole:
        creator = whole
    s = fold_chars(creator or '')
    # A translator or illustrator credit is not a second author.
    s = re.split(r'(?:,|;|\s)+(?:trans\.|tr\.|translated by|translation by|illus\.|illustrated by|edited by)\b', s, maxsplit=1, flags=re.I)[0]
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = s.lower().replace('&', ' and ').replace('.', '')
    s = re.sub(r'\b(?:feat|ft|featuring)\b', ',', s)
    # "e l u c i d" and "j r r tolkien" share a key with the unspaced form.
    s = re.sub(r'\b(?:[a-z]\s+){1,}[a-z]\b', lambda m: m.group(0).replace(' ', ''), s)
    people = []
    for part in re.split(r'\s+and\s+|,|;|/', s):
        # "Sturgill Simpson/Jonny Blue Skies": each alias in a group is one person.
        alias = alias_of(part)
        if alias:
            part = fold_chars(alias).lower()
        toks = [t for t in re.findall(r"[a-z0-9']+", part) if t not in ARTICLES and len(t) > 1]
        if toks and tuple(toks) not in people:
            people.append(tuple(toks))
    return tuple(people)


def _person_close(a, b):
    if a == b or set(a) <= set(b) or set(b) <= set(a):
        return True
    # A one-token name only matches a one-letter typo in a long name.
    # "Drake" / "Drakeo" is a different artist, not a typo.
    if len(a) == 1 and len(b) == 1:
        if min(len(a[0]), len(b[0])) >= 6 and not _plural_variant(a[0], b[0]) and _one_edit(a[0], b[0]):
            return True
        return False
    return difflib.SequenceMatcher(None, ' '.join(a), ' '.join(b)).ratio() >= TOKEN_RATIO


def creators_compatible(a, b):
    """True when one side is unknown, or the names are the same person or band."""
    if not known_creator(a) or not known_creator(b):
        return True
    if fold_chars(a).strip().lower() in COMPAT_WILDCARD or fold_chars(b).strip().lower() in COMPAT_WILDCARD:
        return True
    pa, pb = _people(a), _people(b)
    if not pa or not pb:
        return True
    small, large = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    used = set()
    for person in small:
        found = False
        for i, other in enumerate(large):
            if i in used:
                continue
            if _person_close(person, other):
                used.add(i)
                found = True
                break
        if not found:
            return False
    return True


@functools.lru_cache(maxsize=None)
def _place_tokens(loc):
    """(specific tokens, all tokens) for a location. Country and region segments are not specific."""
    s = fold_chars(loc or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s).replace('&', ' and ')
    specific, every = set(), set()
    segs = [seg for seg in re.split(r'[,;/|]|\s[-–—]\s|[–—]', s)]
    first = True
    for seg in segs:
        seg = re.sub(r"[.'’]", '', seg)
        seg = re.sub(r'[^a-z0-9]+', ' ', seg).strip()
        if not seg:
            continue
        toks = [PLACE_ALIAS.get(t, t) for t in seg.split()]
        every.update(toks)
        bare = re.sub(r'^(?:the|rest of the|rest of|northern|southern|eastern|western|central)\s+', '', seg)
        region = bare in REGIONS or (not first and bare in US_CODES)
        first = False
        if not region:
            specific.update(t for t in toks if t not in PLACE_GENERIC)
    return frozenset(specific), frozenset(every)


def _place_word_close(a, b):
    if a == b:
        return True
    # Marrakech / Marrakesh, Simrishamn / Simrishamng.
    return min(len(a), len(b)) >= 6 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def places_compatible(a, b):
    """Locations agree unless both name a specific place and the places differ.

    "London" and "U.K." agree: one is a country. "Miami" and "New York" do not:
    two venues with one name in two cities are two venues.
    """
    if not known_creator(a) or not known_creator(b):
        return True
    sa, sb = _place_tokens(a)[0], _place_tokens(b)[0]
    if not sa or not sb:
        return True
    return any(_place_word_close(x, y) for x in sa for y in sb)


def compat_for(category):
    """Creator agreement test for one category."""
    return places_compatible if category in PLACES else creators_compatible


def _strip_decorations(title):
    """Drop edition, year, label, and network suffixes. Keep a book or part number."""
    def repl(match):
        inner = match.group(1) if match.group(1) is not None else match.group(2)
        if re.search(r'\b(book|part|vol|volume|chapter)\b', inner or '', re.I):
            return ' ' + inner + ' '
        return ' '
    s = re.sub(r'\(([^)]*)\)|\[([^\]]*)\]', repl, title)
    s = _SEASON.sub(' ', s)
    s = re.sub(r'\blimited series\b', ' ', s, flags=re.I)
    s = re.sub(r'(?<=[A-Za-z])\$(?=[A-Za-z])', 's', s)
    s = s.replace('+', ' and ')
    s = s.replace('&', ' and ')
    prev = None
    while prev != s:
        prev = s
        s = re.sub(
            r'[\s:,\-–—]+(?:deluxe|remastered|remaster|expanded edition|anniversary edition|special edition)\b\.?\s*$',
            ' ', s, flags=re.I)
    s = re.sub(r'[\s:,\-–—]+\b(?:19|20)\d{2}\b\s*$', ' ', s)
    s = re.sub(r'[:,]?\s*\b(?:a novel|a memoir|a cookbook|stories|poems|essays)\b\s*$', ' ', s, flags=re.I)
    return re.sub(r'\s+', ' ', s).strip(' -–—:,')


def _tokens(title):
    s = fold_chars(_strip_decorations(title)).lower()
    s = s.replace("'", '')
    raw = re.findall(r'[a-z0-9]+', s)
    out = []
    i = 0
    while i < len(raw):
        t = raw[i]
        if t in ENUM_PREV and i + 1 < len(raw):
            nxt = raw[i + 1]
            nxt = WORDN.get(nxt, ROMAN.get(nxt, nxt))
            out.append(t)
            out.append(nxt)
            i += 2
            continue
        # "Diablo IV" and a trailing "Part V" are the same number. A title that is
        # only "VI" stays a word: converting a one-token title would glue it to "6".
        spell_out = t in ROMAN and (
            (len(t) >= 2 and len(raw) > 1)
            or (i == len(raw) - 1 and len(raw) > 1)
            or (out and out[-1] in ENUM_PREV))
        if spell_out:
            out.append(ROMAN[t])
        else:
            out.append(t)
        i += 1
    buf = []
    squashed = []
    for t in out:
        if len(t) == 1:
            buf.append(t)
        else:
            if buf:
                squashed.append(''.join(buf))
                buf = []
            squashed.append(t)
    if buf:
        squashed.append(''.join(buf))
    if squashed and squashed[0] in ARTICLES and len(squashed) > 1:
        squashed = squashed[1:]
    return tuple(squashed)


def _joined(tokens):
    return ''.join(tokens)


def _clean_tokens(tokens, category):
    """Drop packaging that rides on the end of a title: "Deluxe Edition", "Remake", "OST",
    "Review", a U.K. tag on a known TV format. Also a mid-title "Presents", a tech
    brand in front of its product, and an inner "Hotel" in a hotel name.

    Works on tokens, so two titles that already shared a key still share one.
    A title is never cut to nothing: "Remake" alone stays a film.
    """
    out = list(tokens)
    if category in PRESENTS_CATS and 'presents' in out[1:-1]:
        out = [t for i, t in enumerate(out) if not (t == 'presents' and 0 < i < len(out) - 1)]
    if category == 'Tech & Gadgets' and len(out) > 1:
        # "Samsung Samsung Galaxy": a doubled word is a typo.
        out = [t for i, t in enumerate(out) if i == 0 or t != out[i - 1]]
        # Keep the brand when what is left is too short to name a product ("Apple TV").
        if out[0] in TECH_BRANDS and len(_joined(out[1:])) >= 6:
            out = out[1:]
    if category == 'Travel & Hotels' and len(out) > 2:
        # "Four Seasons Hotel Firenze" / "Four Seasons Firenze". A leading or final
        # "Hotel" is part of the name ("Hotel Costes", "Grand Hotel").
        out = [t for i, t in enumerate(out) if not (t in ('hotel', 'resort') and 0 < i < len(out) - 1)]
    changed = True
    while changed and len(out) > 1:
        changed = False
        for tail in NOISE_TAILS:
            n = len(tail)
            if len(out) > n and tuple(out[-n:]) == tail:
                out = out[:-n]
                changed = True
                break
        if changed:
            continue
        if len(out) > 2 and out[-1] == 'edition' and out[-2] in EDITION_WORDS:
            out = out[:-2]
            changed = True
        elif out[-1] in ('review', 'reviews') and category not in REVIEW_KEEP and len(_joined(out[:-1])) >= 4:
            out = out[:-1]
            changed = True
        elif category == 'TV' and out[-1] == 'uk' and _joined(out[:-1]) in TV_FORMATS:
            out = out[:-1]
            changed = True
    return tuple(out)


def _title_tokens(text, category):
    """Cleaned tokens for any title text in one category."""
    if category in MUSIC:
        text = _FEAT_TAIL.sub('', text or '')
    return _clean_tokens(_tokens(text), category)


def _key(text, category):
    """Joined match key for any title text in one category."""
    return _joined(_title_tokens(text, category))


def _looks_like_name(text):
    s = re.sub(r'\([^)]*\)', ' ', fold_chars(text or '')).strip()
    if not s or len(s) > 55 or re.search(r'\d', s):
        return False
    parts = [p.strip() for p in re.split(r'\s+(?:and|&|feat\.?|featuring|ft\.?|with)\s+|,(?=\s)', s, flags=re.I) if p.strip()]
    if not parts or len(parts) > 5:
        return False
    for part in parts:
        words = [w for w in re.split(r'\s+', part) if w]
        if not 1 <= len(words) <= 5:
            return False
        for word in words:
            core = re.sub(r"[^A-Za-z'’.\-]", '', word).lower().strip('.')
            if not core:
                return False
            if core in STOP and core not in NAME_OK:
                return False
    return True


def _word_count(text):
    return len(re.findall(r"[A-Za-z0-9']+", fold_chars(text or '')))


def _split_embedded(title, creator, category, artists=frozenset()):
    """Pull a creator out of 'Artist, "Title"', 'Artist - Album (Label)', or 'Title, Author'.

    Returns (display title, display creator, alt titles). Alt titles are extra
    match keys. Display falls back to the original title when the split is only
    a guess. artists: name keys of creators other rows in the category already
    credit, so "Nourished By Time - The Passionate Ones" splits though "By"
    does not look like part of a name.
    """
    # Straighten quotes but keep accents, so the display title is not stripped.
    raw = title or ''
    for src, dst in _QUOTES:
        raw = raw.replace(src, dst)
    raw = raw.strip().rstrip(',').strip()
    alts = []
    show_t, show_c = title, creator
    field_empty = not known_creator(creator)

    quoted = re.match(r"^(?P<who>.+?)\s*[,:\-–—]\s*['\"](?P<title>.+?)['\"]?\s*$", raw)
    if quoted and _looks_like_name(quoted.group('who')) and quoted.group('title').strip():
        who, work = quoted.group('who').strip(), quoted.group('title').strip()
        alts.append(work)
        if field_empty:
            show_t, show_c = work, who
        return show_t, show_c, alts

    # "Title by Author" only. "Death by Lightning" and "Nourished By Time - Album" stay intact.
    by = re.match(r'^(?P<title>.+?)\s+by\s+(?P<who>[^()\-–—]+)$', raw, flags=re.I) if field_empty else None
    # A name does not open with an article or a small word: "The Old Man by the Sea",
    # "Hard by a Great Forest", "Hated by All the Right People" are whole titles.
    by_head = by.group('who').split()[0] if by and by.group('who').split() else ''
    if by and (by_head.lower() in ARTICLES | {'all'} or not by_head[:1].isupper()):
        by = None
    if by and _looks_like_name(by.group('who')) and 2 <= _word_count(by.group('who')) <= 4 and _word_count(by.group('title')) >= 2:
        who, work = by.group('who').strip(), by.group('title').strip()
        if not re.search(r'\bby\b', work, re.I):
            alts.append(work)
            show_t, show_c = work, who
            return show_t, show_c, alts

    if category in MUSIC and field_empty:
        dashed = re.match(r'^(?P<who>.+?)\s+[-–—]\s+(?P<title>.+)$', raw)
        if dashed and (_looks_like_name(dashed.group('who')) or _name_key(dashed.group('who')) in artists) \
                and _word_count(dashed.group('title')) >= 1:
            who, work = dashed.group('who').strip(), dashed.group('title').strip()
            labeled = bool(re.search(r'\([^)]+\)\s*$', work))
            work_core = re.sub(r'\s*\([^)]*\)\s*$', '', work).strip() or work
            if _word_count(who) <= 8 and _word_count(work_core) <= 12:
                alts.append(work_core)
                if labeled:
                    show_t, show_c = work_core, who
        colon = re.match(r'^(?P<who>.+?)\s*:\s*(?P<title>.+)$', raw)
        if colon and _looks_like_name(colon.group('who')) and 1 <= _word_count(colon.group('who')) <= 4:
            who, work = colon.group('who').strip(), colon.group('title').strip()
            if _word_count(work) >= 1 and not re.match(r'^(season|part|volume|vol|book)\b', work, re.I):
                alts.append(work)
                if show_t == title and _word_count(work) >= _word_count(who):
                    show_t, show_c = work, who

    # A comma-quote ("Artist, 'Title") was handled above. Apostrophes in
    # "Don't" or "Man's" are part of the words.
    if field_empty and not re.search(r",\s*['\"]", raw):
        # Last comma only, so "Luna, Phoenix, Queen" is not treated as a credit.
        parts = re.match(r'^(?P<left>.+),\s+(?P<right>[^,]+)$', raw)
        if parts:
            left, right = parts.group('left').strip(), parts.group('right').strip()
            left_name, right_name = _looks_like_name(left), _looks_like_name(right)
            right_orig = ''
            tail_orig = re.search(r',\s*([^,]+)$', title or '')
            if tail_orig:
                right_orig = tail_orig.group(1)
            # A space before the comma, or an accented surname, marks "Title, Author".
            # "Babylon, South Dakota" has neither: the comma is part of the title.
            credit = bool(re.search(r'\s,\s', title or '')) or bool(re.search(r'[^\x00-\x7f]', right_orig))
            # "Dua Lipa, Radical Optimism": the left side is an artist other rows credit.
            if (category in MUSIC and _name_key(left) in artists and _name_key(right) not in artists
                    and _word_count(right) >= 1):
                alts.append(right)
                show_t, show_c = right, left
            # "Artist, Album": the left side is the name and the right side is longer.
            elif (category in MUSIC and left_name and _word_count(right) >= 3
                    and _word_count(left) < _word_count(right)):
                alts.append(right)
                show_t, show_c = right, left
            elif right_name and credit and 1 <= _word_count(right) <= 6 and _word_count(left) >= 1:
                # "Title , Author" or "Album , Artist". The work is the left side.
                # Skip when the right side is the longer album title caught above.
                if not (category in MUSIC and left_name and _word_count(right) > _word_count(left)):
                    alts.append(left)
                    if _word_count(right) >= 2 or category in MUSIC:
                        show_t, show_c = left, right
    # De-dupe alts while keeping order.
    seen = set()
    clean_alts = []
    for alt in alts:
        key = _joined(_tokens(alt))
        full = _joined(_tokens(raw))
        if key and key != full and key not in seen:
            seen.add(key)
            clean_alts.append(alt)
    if show_t != title and _joined(_tokens(show_t)) == _joined(_tokens(title)):
        show_t, show_c = title, creator
    return show_t, show_c or creator, clean_alts


_SUBTITLE_SEP = re.compile(r'\s*:\s*|\s+[-–—|]\s+')
_OR_SUBTITLE_SEP = re.compile(r'\s*:\s*|\s+[-–—|]\s+|[,;]\s+or,?\s+', re.I)


def _subtitle_bases(title, category, artists=frozenset()):
    """Left-hand sides of ':', ' - ', or ' | ' subtitles, when the first side is not an artist credit.

    Every separator gives a base, so "Star Wars: Visions Presents - The Ninth Jedi"
    reaches "Star Wars: Visions Presents" as well as "Star Wars".
    """
    raw = fold_chars(title or '').strip()
    bases = []
    sep_re = _OR_SUBTITLE_SEP if category in OR_SUBTITLE_CATS else _SUBTITLE_SEP
    seps = list(sep_re.finditer(raw))
    if not seps:
        return bases
    first = raw[:seps[0].start()].strip()
    if not first or _word_count(first) < 1:
        return bases
    if category in MUSIC and ((_looks_like_name(first) and _word_count(first) <= 8) or _name_key(first) in artists):
        return bases
    full = _joined(_tokens(raw))
    for sep in seps:
        left, right = raw[:sep.start()].strip(), raw[sep.end():].strip()
        if not left or not right:
            continue
        key = _joined(_tokens(left))
        if key and key != full and len(key) >= 2 and left not in bases:
            bases.append(left)
    return bases


def _looks_like_place(text):
    """'Utah', 'Marrakesh', 'St Barths', 'Hua Hin': a few capitalized words, no digits."""
    words = re.findall(r"[^\s]+", text or '')
    if not 1 <= len(words) <= 5 or re.search(r'\d', text):
        return False
    caps = [w for w in words if w[:1].isupper()]
    return bool(caps) and all(w[:1].isupper() or w.lower() in PLACE_GENERIC for w in words)


def _place_bases(title, category):
    """Venue name without a trailing location: ', City', ': City, Country', ' at the Eaton Hotel'."""
    raw = re.sub(r'\s*\([^)]*\)\s*$', '', fold_chars(title or '').strip())
    out = []
    # A bar inside a hotel: "BKK Social Club at Four Seasons Bangkok".
    at = re.match(r'^(.+?)\s+(?:at|@)\s+(?:the\s+)?[A-Z0-9]', raw)
    if at and _word_count(at.group(1)) >= 1:
        out.append(at.group(1).strip())
    # Peel one trailing qualifier at a time: "Deer Valley, Utah, United States".
    head = raw
    while True:
        m = re.match(r'^(.+?)\s*[,:]\s*([^,:]+)$', head)
        if not m or not _looks_like_place(m.group(2).strip()):
            break
        head, qualifier = m.group(1).strip(), m.group(2).strip()
        # A destination list's bare "Naples" is not "Naples, Florida". A one-word
        # name keeps a state or province qualifier; a country can go.
        where = re.sub(r'[^a-z0-9]+', ' ', fold_chars(qualifier).lower().replace('.', '')).strip()
        if category == 'Travel & Hotels' and _word_count(head) == 1 and (where in SUBNATIONAL or where in US_CODES):
            break
        out.append(head)
    return out


def _tail_keys(texts, category):
    """(head key, tail tokens) for each way to cut 1-3 trailing words off a venue name.

    "La Mamounia Marrakech" gives ("lamamounia", ("marrakech",)). The cut is kept
    only when the tail names the other row's location, which cluster_topic checks.
    """
    out = []
    for text in texts:
        toks = _title_tokens(text, category)
        for n in range(1, 4):
            if len(toks) <= n:
                break
            head, tail = toks[:-n], toks[-n:]
            if len(_joined(head)) >= 4 and any(t not in TAIL_GENERIC for t in tail):
                out.append((_joined(head), tail))
    return out


def _tail_in_place(tail, loc):
    """True when every non-generic tail word appears in the location."""
    words = _place_tokens(loc)[1]
    return all(t in TAIL_GENERIC or any(_place_word_close(PLACE_ALIAS.get(t, t), w) for w in words) for t in tail)


def _equiv_tokens(tokens):
    if len(tokens) < 2:
        return tokens
    return tuple(EQUIV.get(t, t) for t in tokens)


def _numeric_conflict(a, b):
    def nums(tokens):
        return sorted(t for t in tokens if any(ch.isdigit() for ch in t))
    return nums(a) != nums(b)


def _plural_variant(a, b):
    """'sin' / 'sins' is a different word, not a one-letter typo."""
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return long == short + 's' or long == short + 'es'


def _one_edit(a, b):
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = j = skipped = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
        else:
            skipped += 1
            j += 1
            if skipped > 1:
                return False
    return skipped + (len(b) - j) <= 1


def _token_typo(a, b, overall):
    if a == b:
        return True
    if _plural_variant(a, b):
        return False
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if ratio >= TOKEN_RATIO:
        return True
    # accordion/accordian is one substitution and lands just under the ratio.
    if min(len(a), len(b)) >= 6 and _one_edit(a, b):
        return True
    # blacknws/blknws is two edits inside an otherwise identical title.
    if (min(len(a), len(b)) >= 6 and ratio >= EDIT_RATIO and overall >= 0.94
            and abs(len(a) - len(b)) <= 2):
        return True
    return False


def fuzzy_title(a, b):
    """Conservative token-sort match. Different numbers never match."""
    if not a or not b:
        return False
    a, b = _equiv_tokens(a), _equiv_tokens(b)
    if a == b:
        return True
    sa, sb = ' '.join(sorted(a)), ' '.join(sorted(b))
    if min(len(sa.replace(' ', '')), len(sb.replace(' ', ''))) < MIN_FUZZY_CHARS:
        return False
    if abs(len(sa) - len(sb)) > max(8, int(0.45 * max(len(sa), len(sb)))):
        return False
    if _numeric_conflict(a, b):
        return False
    overall = difflib.SequenceMatcher(None, sa, sb).ratio()
    if overall < FUZZY_RATIO:
        return False
    used = set()
    stray_a = []
    paired = []
    for tok in a:
        best_j, best_r = None, 0.0
        for j, other in enumerate(b):
            if j in used:
                continue
            ratio = 1.0 if tok == other else difflib.SequenceMatcher(None, tok, other).ratio()
            if ratio > best_r:
                best_r, best_j = ratio, j
        if best_j is not None and (best_r >= TOKEN_RATIO or _token_typo(tok, b[best_j], overall)):
            used.add(best_j)
            paired.append((tok, b[best_j]))
        else:
            stray_a.append(tok)
    stray_b = [tok for j, tok in enumerate(b) if j not in used]
    stray_a = [tok for tok in stray_a if tok not in EXTRA_OK]
    stray_b = [tok for tok in stray_b if tok not in EXTRA_OK]
    if stray_a or stray_b:
        if len(stray_a) == 1 and len(stray_b) == 1 and _token_typo(stray_a[0], stray_b[0], overall):
            return True
        return False
    # Every token paired. Reject a pure plural that squeaked through the ratio.
    for left, right in paired:
        if left != right and _plural_variant(left, right):
            return False
    return True


class _Rec:
    __slots__ = ('list_name', 'show_title', 'show_creator', 'creator', 'legacy', 'raw', 'primary', 'tokens',
                 'alts', 'bases', 'tails')

    def __init__(self, list_name, title, creator, category, artists=frozenset()):
        show_t, show_c, alt_titles = _split_embedded(title, creator, category, artists)
        self.list_name = list_name
        self.show_title = show_t or title
        # Compatibility uses the extracted creator field only. A creator guessed
        # from the title must not block the same spelling that already names one.
        self.creator = creator if known_creator(creator) else ''
        if known_creator(creator):
            self.show_creator = creator
        elif known_creator(show_c):
            self.show_creator = show_c
        else:
            self.show_creator = ''
        self.legacy = _legacy_norm(title)
        # Primary key is the full title, so a split cannot pull in a different work.
        self.tokens = _title_tokens(title, category)
        self.primary = _joined(self.tokens)
        if len(self.primary) < 2:
            self.primary = self.legacy
        # The key before suffix cleanup, so a pair that matched on it still does.
        self.raw = _joined(_tokens(title))
        # "Starburster / Favourite": a double A-side counts for its first song. Only the
        # first, so the entry cannot glue two songs that have their own rows. A known
        # creator field means the slash is not separating two artists.
        if category == 'Songs' and known_creator(creator) and ' / ' in title:
            alt_titles = list(alt_titles) + [title.split(' / ', 1)[0]]
        self.alts = []
        for alt in alt_titles:
            key = _key(alt, category)
            if key and len(key) >= 2 and key != self.primary and key not in self.alts:
                self.alts.append(key)
        legacy_base = _legacy_base(title)
        base_texts = _subtitle_bases(title, category, artists)
        if category in PLACES:
            base_texts += _place_bases(title, category)
        self.bases = []
        for base in base_texts:
            key = _key(base, category)
            if key and len(key) >= 2 and key != self.primary and key not in self.bases:
                self.bases.append(key)
        self.tails = _tail_keys([title] + base_texts, category) if category in PLACES else []
        if legacy_base and legacy_base != self.legacy and legacy_base not in self.bases and legacy_base != self.primary:
            # "Artist: Album" is a credit, not a subtitle. The bare artist name is a different row.
            head = fold_chars(title).split(':', 1)[0]
            artist_credit = category in MUSIC and _looks_like_name(head) and _word_count(head) <= 8
            if not artist_credit:
                self.bases.append(legacy_base)


class _UF:
    def __init__(self, creators, compat=creators_compatible, sides=None, on_split=None):
        n = len(creators)
        self.p = list(range(n))
        self.compat = compat
        self.known = [[] for _ in range(n)]
        for i, creator in enumerate(creators):
            if known_creator(creator):
                self.known[i].append(creator)
        # Split-override sides each record matches: {(pair index, 0 or 1)}.
        self.sides = [set(s) for s in sides] if sides else [set() for _ in range(n)]
        self.on_split = on_split

    def find(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def _ok(self, a, b):
        left, right = self.known[a], self.known[b]
        if not left or not right:
            return True
        return all(self.compat(x, y) for x in left for y in right)

    def _split(self, a, b):
        for pair, side in self.sides[a]:
            if (pair, 1 - side) in self.sides[b]:
                return pair
        return None

    def union(self, a, b, force=False):
        """Join two clusters. force skips the creator test but never a split override."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return True
        pair = self._split(ra, rb)
        if pair is not None:
            if self.on_split:
                self.on_split(pair)
            return False
        if not force and not self._ok(ra, rb):
            return False
        self.p[rb] = ra
        self.known[ra].extend(self.known[rb])
        self.sides[ra] |= self.sides[rb]
        return True


def _split_exact(records, indexes, compat=creators_compatible):
    """Group one exact key. Unknown creators join only when the known names agree."""
    known_groups = []  # list of (creator, [indexes])
    unknown = []
    for i in indexes:
        creator = records[i].creator
        if not known_creator(creator):
            unknown.append(i)
            continue
        placed = False
        for group in known_groups:
            if compat(creator, group[0]):
                group[1].append(i)
                placed = True
                break
        if not placed:
            known_groups.append((creator, [i]))
    groups = [g[1] for g in known_groups]
    if len(groups) <= 1:
        if groups:
            groups[0].extend(unknown)
        elif unknown:
            groups.append(unknown)
    elif unknown:
        groups.append(unknown)
    return groups


def _index_fuzzy(records):
    """Block fuzzy comparisons. Typos share a prefix or a first-letter length band."""
    buckets = collections.defaultdict(set)
    for i, rec in enumerate(records):
        seen = set()
        for tok in rec.tokens:
            sigs = []
            if len(tok) >= 4:
                sigs.append('t:' + tok)
            if len(tok) >= 5:
                sigs.append('p:' + tok[:4])
            if len(tok) >= 6:
                # Off-by-one and off-by-two lengths catch a missing or extra letter.
                for delta in range(-2, 3):
                    sigs.append('b:%s%d' % (tok[0], len(tok) + delta))
            for sig in sigs:
                if sig in seen:
                    continue
                seen.add(sig)
                buckets[sig].add(i)
    return buckets


def cluster_topic(lists, category):
    """Merge items from one category.

    lists: [{'list': name, 'items': [(title, creator), ...]}, ...]
    Returns {key: {list name: (display title, creator)}} in first-seen order.
    One list contributes at most one row per work.
    Overrides in bestof_merges.json apply last for merges and throughout for splits.
    """
    raw = []
    for entry in lists:
        name = entry['list']
        for item in entry.get('items') or []:
            if not item:
                continue
            title = item[0] if len(item) > 0 else ''
            creator = item[1] if len(item) > 1 else ''
            if not title or not str(title).strip():
                continue
            raw.append((name, str(title), str(creator or '')))
    if not raw:
        return {}
    compat = compat_for(category)
    # Artist names the category already credits, for "Artist - Album" with an odd name.
    artists = frozenset(_name_key(c) for _n, _t, c in raw if category in MUSIC and known_creator(c))
    records = [_Rec(name, title, creator, category, artists) for name, title, creator in raw]
    for rec in records:
        hit = OVERRIDES['aliases'].get(_name_key(rec.creator)) if rec.creator else None
        if hit:
            override_hits[('alias', '', hit[1])] += 1

    def side_match(rec, side):
        """A split or merge side is a title, or [title, creator]."""
        title, who = (side, None) if isinstance(side, str) else (side[0], side[1])
        key = _key(title, category)
        # An alt is the extracted work: "Lily Allen, 'P–sy Palace'" is "P–sy Palace".
        if key not in (rec.primary, rec.legacy) and key not in rec.alts:
            return False
        return who is None or (known_creator(rec.creator) and compat(rec.creator, who))

    splits = OVERRIDES['split'].get(category) or []
    sides = [set() for _ in records]
    for n, pair in enumerate(splits):
        for s, side in enumerate(pair):
            for i, rec in enumerate(records):
                if side_match(rec, side):
                    sides[i].add((n, s))
    uf = _UF([rec.creator for rec in records], compat, sides,
             lambda n: override_hits.update([('split', category, n)]))
    by_primary = collections.defaultdict(list)
    by_legacy = collections.defaultdict(list)
    for i, rec in enumerate(records):
        if rec.primary:
            by_primary[rec.primary].append(i)
        if rec.legacy and len(rec.legacy) >= 2:
            by_legacy[rec.legacy].append(i)
    for indexes in by_primary.values():
        for group in _split_exact(records, indexes, compat):
            for i in group[1:]:
                uf.union(group[0], i)
    by_raw = collections.defaultdict(list)
    for i, rec in enumerate(records):
        if rec.raw != rec.primary and len(rec.raw) >= 2:
            by_raw[rec.raw].append(i)
    for i, rec in enumerate(records):
        if rec.raw in by_raw and rec.raw == rec.primary:
            by_raw[rec.raw].append(i)
    for groups in (by_legacy, by_raw):
        for indexes in groups.values():
            for group in _split_exact(records, indexes, compat):
                for i in group[1:]:
                    uf.union(group[0], i)

    ambiguous = set()
    for key, indexes in by_primary.items():
        people = []
        conflict = False
        for i in indexes:
            creator = records[i].creator
            if not known_creator(creator):
                continue
            if any(not compat(creator, other) for other in people):
                conflict = True
                break
            people.append(creator)
        if conflict:
            ambiguous.add(key)

    def blocked(i, j):
        """Don't attach a bare title to one creator when another creator has it too."""
        for rec, other in ((records[i], records[j]), (records[j], records[i])):
            if not known_creator(rec.creator) and rec.primary in ambiguous and known_creator(other.creator):
                return True
        return False

    def link(i, j):
        if i == j or blocked(i, j):
            return
        uf.union(i, j)

    for i, rec in enumerate(records):
        for key in rec.alts:
            for j in by_primary.get(key, ()):
                link(i, j)
            for j in by_legacy.get(key, ()):
                link(i, j)
        for key in rec.bases:
            for j in by_primary.get(key, ()):
                link(i, j)
            for j in by_legacy.get(key, ()):
                link(i, j)
        # "Eden Rock St Barths" joins "Eden Rock" only when that row is in St. Barths.
        # A bare "Capella" never collects Capella Sydney and Capella Bangkok.
        for key, tail in rec.tails:
            for j in by_primary.get(key, ()):
                if known_creator(records[j].creator) and _tail_in_place(tail, records[j].creator):
                    link(i, j)
    # Wrappers that share an extracted title but no clean primary.
    by_alt = collections.defaultdict(list)
    for i, rec in enumerate(records):
        for key in rec.alts:
            by_alt[key].append(i)
    for indexes in by_alt.values():
        for group in _split_exact(records, indexes, compat):
            for i in group[1:]:
                link(group[0], i)

    buckets = _index_fuzzy(records)
    seen_pairs = set()
    for indexes in buckets.values():
        group = [i for i in indexes]
        if len(group) < 2 or len(group) > 250:
            continue
        for a_i in range(len(group)):
            for b_i in range(a_i + 1, len(group)):
                i, j = group[a_i], group[b_i]
                if i > j:
                    i, j = j, i
                if (i, j) in seen_pairs or uf.find(i) == uf.find(j):
                    continue
                seen_pairs.add((i, j))
                if fuzzy_title(records[i].tokens, records[j].tokens):
                    link(i, j)

    # Reviewed merges run last and skip the creator test: "Voaara" in Ste.-Marie and
    # in Ambatorao is one lodge, which no location rule can tell.
    for n, pair in enumerate(OVERRIDES['merge'].get(category) or []):
        left = [i for i, rec in enumerate(records) if side_match(rec, pair[0])]
        right = [i for i, rec in enumerate(records) if side_match(rec, pair[1])]
        if not left or not right:
            continue
        for i in left[1:] + right:
            uf.union(left[0], i, force=True)
        if all(uf.find(i) == uf.find(left[0]) for i in right):
            override_hits[('merge', category, n)] += 1

    clusters = collections.OrderedDict()
    for i, rec in enumerate(records):
        root = uf.find(i)
        bucket = clusters.get(root)
        if bucket is None:
            bucket = collections.OrderedDict()
            clusters[root] = bucket
        # First spelling from a list wins the slot. The count is unique lists.
        bucket.setdefault(rec.list_name, (rec.show_title, rec.show_creator))
    return clusters


def title_penalty(title):
    """Lower is cleaner. Used only to break a tie between equally common spellings."""
    penalty = 0
    if title.isupper() and len(title) > 3:
        penalty += 3
    if re.search(u'[\u2018\u2019\u201c\u201d]', title):
        penalty += 2
    if title.rstrip().endswith((',', ':', ';', "'", '"', '\u2018', '\u201c')):
        penalty += 3
    if re.search(r'\s[-–—]\s', title):
        penalty += 1
    if re.search(r'\([^)]*(?:deluxe|remaster|19\d\d|20\d\d)[^)]*\)', title, re.I):
        penalty += 2
    return penalty
