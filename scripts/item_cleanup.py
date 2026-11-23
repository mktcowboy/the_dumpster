"""Source-data fixes applied to items.json before the master lists are built.

clean_items(d, year) takes the list records from items.json and returns them
with extraction mistakes repaired. items.json itself is never rewritten.

Every rule names its list (the exact `list` value) and matches the extracted
(title, creator) text exactly, so a rule that no longer matches does nothing.
The one general rule is META: page text that is never a title in any list.
"""
import re

ALL = '*'

# Page furniture read as items: aggregator counts, tag footers, newsletter
# boxes, staff credits, and the lead-in to a quote.
META = re.compile(
    r'^(?:\d+ lists?:|List of Lists Surveyed:|Tagged:|GET THE \w+ DIGEST|YOUR INBOX IS LIT'
    r'|Writers, Editors, and Contributors)$|\b(?:said|says|adds|winners are):$')

# (title, creator) -> (title, creator). Titles split at "by", a subtitle or
# location left in the creator field, censored or cut-off titles, and typos
# whose correct spelling another list in the same year and category uses.
REWRITE = {
    # 2024
    'Pitchfork: The 100 Best Songs of 2024': {
        ('Nourished', 'Time: “Hell of a Ride'): ('Hell of a Ride', 'Nourished By Time')},
    'NPR: Books We Love 2024': {('Hard', 'a Great Forest'): ('Hard by a Great Forest', '')},
    'Sight and Sound: The 50 Best Films of 2024': {('Caught', 'the Tides'): ('Caught by the Tides', '')},
    'Electric Lit: Best Nonfiction of 2024': {
        ('Bone of the Bone: Essays on America', 'a Daughter of the Working Class by Sarah Smarsh'):
            ('Bone of the Bone: Essays on America by a Daughter of the Working Class', 'Sarah Smarsh')},
    'Barnes & Noble: Best Cookbooks of 2024': {
        ('Bodega Bakes: Recipes for Sweets and Treats Inspired', 'My Corner Store - A Baking Cookbook'):
            ('Bodega Bakes: Recipes for Sweets and Treats Inspired by My Corner Store - A Baking Cookbook', '')},
    'CBS Sports: 24 Biggest Sports Stories of 2024': {
        ('Caitlin Clark takes WNBA', 'storm in rookie season'): ('Caitlin Clark takes WNBA by storm in rookie season', '')},
    'Bon Appétit: The Best New Restaurants of 2024': {('Oro', 'Nixta'): ('Oro by Nixta', '')},
    'Condé Nast Traveller: The Gold List 2024': {
        ('Miavana', 'Time + Tide – Madagascar'): ('Miavana by Time + Tide', 'Madagascar')},
    'Condé Nast Traveler: Hot List 2024': {
        ('Shinta Mani Mustang', 'A Bensley Collection, Jomsom'): ('Shinta Mani Mustang – A Bensley Collection', 'Jomsom')},
    # The rest of this list keeps the city in the creator field.
    'Condé Nast Traveller: The Best New Restaurants in the World (Hot List 2024)': {
        ("Maty's – Miami", ''): ("Maty's", 'Miami'), ('Yess – Los Angeles', ''): ('Yess', 'Los Angeles'),
        ('Chishuru – London', ''): ('Chishuru', 'London'), ('Kiln – San Francisco', ''): ('Kiln', 'San Francisco')},
    'Vulture: The Best Movies of 2024': {
        ('Horizon: An American Saga', 'Chapter One'): ('Horizon: An American Saga – Chapter One', '')},
    'The Game Awards 2024: All Winners (NPR)': {
        ('Metaphor: ReFantanzio', 'Best Narrative'): ('Metaphor: ReFantazio', 'Best Narrative')},
    'TIME: The 10 Best Fiction Books of 2024': {
        ('Ghostroots , ’Pemi Aguda', ''): ('Ghostroots', 'Pemi Aguda')},
    # 2025
    'Pitchfork: The 100 Best Songs of 2025': {('Nourished', 'Time: “9 2 5'): ('9 2 5', 'Nourished By Time')},
    'Pitchfork: The 50 Best Albums of 2025': {
        ('Nourished', 'Time: The Passionate Ones'): ('The Passionate Ones', 'Nourished By Time')},
    # The matcher reads "by" as a stop word, so it cannot split "Nourished By Time - Album" itself.
    'Stereogum: The 50 Best Albums of 2025': {
        ('Nourished By Time - The Passionate Ones (XL)', ''): ('The Passionate Ones', 'Nourished By Time')},
    'BrooklynVegan: Top 55 Albums of 2025': {
        ('Nourished By Time - The Passionate Ones', ''): ('The Passionate Ones', 'Nourished By Time')},
    'The Guardian: The 50 Best Albums of 2025': {
        ('Nourished', 'Time – The Passionate Ones'): ('The Passionate Ones', 'Nourished By Time')},
    'NME: The 50 Best Albums of 2025': {
        ('Nourished', 'Time – ‘The Passionate Ones'): ('The Passionate Ones', 'Nourished By Time')},
    'Consequence: The 50 Best Albums of 2025': {('Nourished', 'Time'): ('Nourished By Time', '')},
    'The New Yorker: The Best Books of 2025': {('The Old Man', 'the Sea'): ('The Old Man by the Sea', '')},
    'NPR: Books We Love 2025': {('Hard', 'a Great Forest'): ('Hard by a Great Forest', '')},
    'Vulture: The Best Movies of 2025': {('Caught', 'the Tides'): ('Caught by the Tides', '')},
    'Rolling Stone: The 20 Best Movies of 2025': {('Caught', 'the Tides'): ('Caught by the Tides', '')},
    'Metacritic: The 30 Best Movies of 2025': {('Caught', 'the Tides'): ('Caught by the Tides', '')},
    'IndieWire: The Best Movies of 2025': {('Caught', 'the Tides'): ('Caught by the Tides', '')},
    'Vulture: The Best TV Shows and Series of 2025': {('Death', 'Lightning'): ('Death by Lightning', '')},
    'Metacritic: The 20 Best New TV Shows of 2025': {('Death', 'Lightning'): ('Death by Lightning', '')},
    'Condé Nast Traveler: Hot List 2025': {
        ('The Pig', 'in the Cotswolds — Barnsley'): ('The Pig in the Cotswolds', 'Barnsley')},
    # Part I, as Esquire and Metacritic spell it, so the two documentary lists still match.
    'Variety: The Best Documentaries of 2025': {
        ('My Undesirable Friends', 'Part 1: Last Air in Moscow'): ('My Undesirable Friends: Part I – Last Air in Moscow', '')},
    'Esquire: The 23 Best Documentaries of 2025': {
        ('My Undesirable Friends: Part I', 'Last Air in Moscow'): ('My Undesirable Friends: Part I – Last Air in Moscow', '')},
    'Billboard: The 100 Best Songs of 2025': {('Lily Allen, “P–sy Palace', ''): ('Lily Allen, “Pussy Palace', '')},
    'iHeartRewind 2025: Top Artists & Songs of the Year': {
        ('Sorry I’m Here For Someone…', 'Benson Boone'): ('Sorry I’m Here For Someone Else', 'Benson Boone')},
    '/Film: The 10 Best Movies of 2025, Ranked': {('The Testament of Anne Lee', ''): ('The Testament of Ann Lee', '')},
    # 2026
    'The New Yorker: The Best Books of 2026 So Far': {
        ('Hated', 'All the Right People'): ('Hated by All the Right People', '')},
    'Rotten Tomatoes: Best New Documentaries of 2026': {
        ('Paralyzed', 'Hope: The Maria Bamford Story'): ('Paralyzed by Hope: The Maria Bamford Story', ''),
        ('Marc', 'Sofia'): ('Marc by Sofia', '')},
    'The A.V. Club: The Best Films of 2026 So Far': {
        ('28 Days Later: The Bone Temple', ''): ('28 Years Later: The Bone Temple', '')},
    'NME: The Best Albums of 2026... So Far': {
        ('You Look Pretty Sad For A Girl So In Love', 'Olivia Rodrigo'):
            ('You Seem Pretty Sad For A Girl So In Love', 'Olivia Rodrigo')},
    'Rolling Stone: Best Albums of 2026 So Far': {
        ('Paul McCartney,’The Boys of Dungeon Lane', ''): ('The Boys of Dungeon Lane', 'Paul McCartney')},
    'Esquire: Best TV Shows of 2026 So Far': {
        ('Star Wars: Visions Presents', 'The Ninth Jedi'): ('Star Wars: Visions Presents – The Ninth Jedi', '')},
    'PUNCH: Cocktail Recipes From the Best New Bars of 2026': {('Vandell', 'Los Angeles. Everyone'): ('Vandell', 'Los Angeles')},
}

# Lists whose extracted rows hold no titles at all. The reason becomes the list's note.
EMPTY = {
    'Lit Hub: The Ultimate Best Books of 2024 List (aggregate)': 'the extracted rows were site headings and article links',
    'Lit Hub: The Ultimate Best Books of 2025 List (aggregate)': 'the extracted rows were the "N lists:" headings',
    'Publishers Weekly: Best Books 2025 (all)': 'the extracted rows were authors and publishers, not book titles',
    'Apple Music: Top Songs of 2024 – Global': 'the extracted rows were artist names, not song titles',
    'Apple Music: Top Songs of 2025 – Global': 'the extracted rows were artist names, not song titles',
    'NPR: The 25 Best Songs of 2025': 'the extracted rows were artist names, not song titles',
    'Consequence: The 50 Best Albums of 2024': 'the extracted rows were artist names, not album titles',
    'Consequence: The 50 Best Albums of 2025': 'the extracted rows were artist names, not album titles',
}

# Titles to drop: headings, bylines, article links, and works from another
# category (albums and audiobooks on a songs list, TV series on a movies list).
DROP = {
    'Slate: The 10 Best Books of 2024': {'The 10 Best Books of 2024'},
    'Book Riot: The Best Comics and Graphic Novels of 2024': {'Rachel Brittain'},
    'Book Riot: The Best Comic Books and Graphic Novels of 2025': {'Eileen Gonzalez'},
    "Popular Science: Best of What's New 2024": {
        'How to use your phone if the grid goes down', '20 Fiona the hippo photos to celebrate her short time on Earth'},
    'The Telegraph: The Greatest Books of 2025': {'Contributors', 'Editors'},
    'Booker Prize 2025 Winner': {
        'David Szalay’s comments on his Booker Prize-winning book', 'Reaction to Flesh in the media',
        'The Booker effect', 'The ceremony', 'Booker Prize week', 'Media enquiries'},
    'Spotify Wrapped 2024: Top Artists, Songs, Albums and Podcasts': {
        'THE TORTURED POETS DEPARTMENT: THE ANTHOLOGY', 'HIT ME HARD AND SOFT', 'Short n’ Sweet',
        'MAÑANA SERÁ BONITO', 'eternal sunshine', '1989 (Taylor’s Version)', 'SOS', 'Lover',
        'Fireworks & Rollerblades', 'Starboy',
        'A Court of Thorns and Roses', 'The Fellowship of the Ring', 'I’m Glad My Mom Died',
        'A Court of Mist and Fury', 'It Ends with Us', 'The 48 Laws of Power', 'A Court of Wings and Ruin',
        'A Game of Thrones: A Song of Ice and Fire: Book One', 'Icebreaker: A Novel', 'Fourth Wing'},
    'Spotify Wrapped 2025: Top Artists, Songs, Albums and Podcasts': {
        'DeBÍ TiRAR MáS FOToS', 'KPop Demon Hunters (Soundtrack from the Netflix Film)', 'HIT ME HARD AND SOFT',
        'SOS Deluxe: LANA', 'Short n’ Sweet', 'MAYHEM', 'You’ll Be Alright, Kid', 'I’m The Problem', 'GNX',
        'Un Verano Sin Ti',
        'Fourth Wing', 'Lights Out', 'Iron Flame', 'A Court of Thorns and Roses by Sarah J. Maas',
        'A Court of Mist and Fury', 'The House of My Mother', 'The Wedding People', 'A Court of Wings and Ruin',
        'Quicksilver', 'Great Big Beautiful Life'},
    'Rotten Tomatoes: Golden Tomato Awards 2024 Winners': {
        'Shōgun', 'The Penguin', 'X-Men ’97', 'Wise Guy: David Chase and the Sopranos', 'Dead Boy Detectvies', 'Fallout'},
    'Rotten Tomatoes: Golden Tomato Awards 2025 Winners': {
        'Andor: Season 2', 'Pluribus: Season 1', 'Adolescence', 'Long Story Short: Season 1', 'Reacher: Season 3',
        'The Studio: Season 1', 'Wolf Hall: Season 2', 'Alien: Earth: Season 1', 'Task: Season 1'},
    # The composer's award. The game is already on the list.
    'The Game Awards 2025: Every Winner (Game Informer)': {'Lorien Testard - Clair Obscur: Expédition 33'},
}

# Award lists keep the award in the creator field. Drop the rows whose award
# goes to a person, team, show, or film rather than a work of the list's kind.
NON_GAME = re.compile(r'Performance|Performer|Content Creator|Esports (?:Athlete|Team)|Adaptation|User Creation|Movie|TV|Anime|Comic')
BAR_PEOPLE = re.compile(r'Judges|Committee|Bartender of the Year|Mentor|Brand Ambassador|Publication|Broadcast|Writing|Book|Ingredient|Lifetime|Visionary')
TONY_PEOPLE = re.compile(r'Actor|Actress|Direction|Choreography|Special Tony|Isabelle Stevenson|Regional Theatre|Tony Honors')
DROP_AWARD = {
    'The Game Awards 2024: All Winners (NPR)': NON_GAME,
    'The Game Awards 2025: Every Winner (Game Informer)': NON_GAME,
    'IGN Awards 2025: The Winners': NON_GAME,
    'Polygon: Game of the Year 2026': NON_GAME,
    'Tales of the Cocktail: 2024 Spirited Awards Winners': BAR_PEOPLE,
    'Tales of the Cocktail: 2025 Spirited Awards Winners': BAR_PEOPLE,
    'Tony Awards 2024 Winners': TONY_PEOPLE,
    'Tony Awards 2025 Winners': TONY_PEOPLE,
    'Tony Awards 2026 Winners': TONY_PEOPLE,
    'Crunchyroll: Anime Awards 2025 Winners': re.compile(r'Director|Character|Opening|Ending'),
}

# Award slots and section headings in the creator field that read as a name.
# Labels such as "Best ..." are already ignored downstream.
BLANK = {
    'The Game Awards 2024: All Winners (NPR)': {'Games for Impact', 'Innovation in Accessibility', 'Most Anticipated Game', "Player's Voice"},
    'The Game Awards 2025: Every Winner (Game Informer)': {'Games For Impact', 'Innovation in Accessibility', 'Most Anticipated Game', "Player's Voice"},
    'PC Gamer: Game of the Year Awards 2024': {'Creative Achievement', 'Spirit of the PC'},
    'James Beard Awards 2024 Winners': {'Emerging Chef'},
    'James Beard Awards 2025 Winners': {'Emerging Chef'},
    "Tom's Guide Awards 2025": {'Most efficient'},
    "Tom's Guide Awards 2026": {'Sustainability in tech', 'Travel'},
    'Apple: 2026 App Store Award Finalists': {'Cultural Impact App', 'Cultural Impact Game'},
    'The Planetary Society: Best of 2024': {'Most exciting moment in planetary science', 'Most exciting upcoming mission'},
    'The Guardian: The Best Theatre, Comedy and Dance of 2024': ALL,  # Theatre / Comedy / Dance
    'The Guardian: The Best Theatre, Comedy and Dance of 2025': ALL,
    "The Telegraph: The Best Books of 2026 (critics' picks)": ALL,  # genre sections
    # Award regions and categories. A plain city or country stays.
    "CN Traveller (UK): 2026 Readers' Choice Awards Winners": re.compile(
        r'^(?:rest of |the )|\band\b|&|^(?:Europe|Asia|Africa|North America|Nordics|Southeast Asia|Northern Africa'
        r'|Indian Ocean|world)$|ships\b|tour operators|travel specialists'),
}

# Creator text that leads with the award. Keep the name after the dash.
CREATOR_SUB = {
    'Spiel des Jahres: Award Winners 2024': r'^\w*[Ss]piel des Jahres \d{4} – ',
    'Spiel des Jahres: Award Winners 2025': r'^\w*[Ss]piel des Jahres \d{4} – ',
    'Tony Awards 2024 Winners': r'^Best [^–]+ – ',
    'Tony Awards 2025 Winners': r'^Best [^–]+ – ',
}


def _award_hit(rx, label):
    """A Game Awards nominee line can list several awards. Drop only when every one matches."""
    if label.startswith('Game Awards nominee:'):
        cats = [c for c in label.split(':', 1)[1].split(',') if c.strip()]
        return bool(cats) and all(rx.search(c) for c in cats)
    return bool(rx.search(label))


def _blank(rule, creator):
    if rule is ALL:
        return True
    if isinstance(rule, re.Pattern):
        return bool(rule.search(creator))
    return creator in rule


def _fix_list(x):
    name = x['list']
    if name in EMPTY:
        return []
    rewrite, drop = REWRITE.get(name, {}), DROP.get(name, ())
    award, blank, sub = DROP_AWARD.get(name), BLANK.get(name), CREATOR_SUB.get(name)
    out = []
    for a, b in x['items']:
        a, b = rewrite.get((a, b), (a, b))
        if a in drop or META.search(a.strip()):
            continue
        if award and b and _award_hit(award, b):
            continue
        if sub and b:
            b = re.sub(sub, '', b)
        if blank and b and _blank(blank, b):
            b = ''
        out.append([a, b])
    return out


def clean_items(d, year):
    # Every list name carries its year, so the rule tables need no year key.
    out = [dict(x, items=_fix_list(x)) for x in d]
    # An emptied list would otherwise read as "items not retrievable" with no reason.
    for x, old in zip(out, d):
        if old['items'] and not x['items'] and not x.get('note'):
            x['note'] = 'items dropped in cleanup: ' + EMPTY.get(x['list'], 'no row was a title')
    return out
