"""Display-only title fixes for the master ranking. Matching is unaffected.

Kirkus prints book titles in ALL CAPS. An all-caps title in a book
category is recased to English title case. Music and other categories
keep caps, which there is usually the artist's own styling.
"""
import re

BOOKS = {'Books', 'Kids & YA Books', 'Cookbooks', 'Comics & Graphic Novels'}
# Lowercase mid-title: articles, coordinating conjunctions, short prepositions.
# Not "up": it is usually a verb particle ("Growing Up Under a Red Flag").
SMALL = {
    'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'for', 'so', 'yet', 'as', 'at', 'by', 'in', 'of',
    'off', 'on', 'per', 'to', 'via', 'from', 'into', 'with', 'over', 'vs',
}
# Stay caps. Kept short: "US", "IT", "LA" are usually ordinary words in a title.
ACRONYMS = {
    'AI', 'USA', 'UK', 'EU', 'NYC', 'FBI', 'CIA', 'DC', 'TV', 'NASA', 'DNA', 'HIV', 'AIDS', 'LGBT',
    'LGBTQ', 'CEO', 'DJ', 'UFO', 'MLK', 'NFL', 'NBA', 'WWI', 'WWII', 'ABC', 'DIY', 'BBQ', 'OK', 'USSR',
}
# A trailing period on these does not end a sentence ("Mr. and Mrs.").
ABBREV = {'MR.', 'MRS.', 'MS.', 'DR.', 'ST.', 'JR.', 'SR.', 'VOL.', 'NO.', 'VS.'}
ROMAN = re.compile(r'(?=[IVX]{2,}$)X{0,3}(IX|IV|V?I{0,3})$')
INITIALS = re.compile(r'([A-Z]\.){2,}$')
# One word inside a space-separated token. Hyphens, slashes and brackets split words, except "(S)KIN".
WORD = re.compile(r"[\w'’]+(?:\)[\w'’]+)?")
STOPS = (':', '.', '!', '?', '—', '–')


def _word(w, small):
    if w in ACRONYMS or ROMAN.match(w): return w
    lw = w.lower()
    if small and lw in SMALL: return lw
    if re.match(r"O['’]\w\w", w): return w[:2] + lw[2:].capitalize()
    if re.match(r'MC[A-Z]{2}', w): return 'Mc' + lw[2:].capitalize()
    i = next(i for i, c in enumerate(lw) if c.isalnum())
    return lw[:i] + lw[i].upper() + lw[i + 1:] if lw[i].isalpha() else lw


def _token(tok, first, last):
    if INITIALS.match(tok.rstrip(',;:!?')): return tok
    ms = list(WORD.finditer(tok))
    out, pos = [], 0
    for n, m in enumerate(ms):
        # Inner hyphen words lowercase too ("Mother-in-Law"); a word just after "(" or a quote does not.
        edge = (first and n == 0) or (last and n == len(ms) - 1) or tok[:m.start()].endswith(('(', '[', '"', '“', '‘'))
        out += [tok[pos:m.start()], _word(m.group(), not edge)]
        pos = m.end()
    return ''.join(out) + tok[pos:]


def title_case(title):
    """Recase an ALL-CAPS title: capitalize each word, lowercase small words mid-title.

    The first and last word, and the first word after a colon, dash or
    sentence stop, stay capitalized. Roman numerals, dotted initials and a
    short acronym list stay caps.
    """
    toks = title.split(' ')
    alpha = [i for i, t in enumerate(toks) if any(c.isalnum() for c in t)]
    out, start = [], True
    for i, t in enumerate(toks):
        if t == 'A' and re.match(r'TO [A-Z]\b', ' '.join(toks[i + 1:i + 3])):
            out.append(t)  # "A to Z"
            start = False
        elif i in alpha:
            out.append(_token(t, start, i == alpha[-1]))
            start = False
        else:
            out.append(t)
        if t in ('-', '—', '–') or t.endswith(STOPS) and t not in ABBREV and not INITIALS.match(t): start = True
    return ' '.join(out)


def display_title(title, category):
    """Title-case an ALL-CAPS book title. Other titles and categories pass through."""
    letters = [c for c in title if c.isalpha()]
    if category not in BOOKS or len(letters) < 3 or not all(c.isupper() for c in letters): return title
    return title_case(title)
