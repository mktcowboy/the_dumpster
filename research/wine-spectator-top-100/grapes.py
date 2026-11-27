"""Infer a grape or style for red and white wines from the wine's name.

The source records carry no grape field. New World wines usually name the
grape ("Cabernet Sauvignon Napa Valley"); Old World wines name the place
("Pauillac", "Barolo"), so those map to the place's main grape or blend.
The rule whose match starts earliest in the name wins, so the grape or place
named first decides; ties go to the earlier rule. Anything unmatched falls to
"Proprietary & other reds" or "Other whites". This is an inference, labeled as such in the
report.
"""
import re
import unicodedata


def _fold(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _rules(pairs):
    return [(g, re.compile(p)) for g, p in pairs]


# Each pattern is matched against "<wine name> | <region> | <country>", folded
# to lowercase ASCII.
RED = _rules([
    # grape named outright
    ("Cabernet Franc", r"cabernet franc|chinon|bourgueil|saumur-champigny"),
    ("Syrah / Shiraz", r"\bshiraz|\bsyrah|\bsirah\b"),
    ("Cabernet Sauvignon", r"cabernet sauvignon|\bcabernet\b"),
    ("Pinot Noir", r"pinot noir|spatburgunder"),
    ("Merlot", r"\bmerlot"),
    ("Zinfandel / Primitivo", r"zinfandel|primitivo"),
    ("Malbec", r"malbec|\bcahors"),
    ("Grenache & Rhône blends", r"grenache|garnacha|cannonau|chateauneuf|gigondas|vacqueyras|cotes du rhone|"
     r"cotes-du-rhone|rasteau|cairanne|lirac|vinsobres|beaumes|ventoux|luberon|priorat|montsant|"
     r"costieres|coteaux du languedoc|languedoc|roussillon|minervois|corbieres|faugeres|st.-chinian|"
     r"pic st.-loup|terrasses du larzac|campo de borja|calatayud|\bgsm\b"),
    ("Syrah / Shiraz", r"hermitage|cote-rotie|cote rotie|cornas|st.-joseph|saint-joseph|collines rhodaniennes"),
    ("Petite Sirah", r"petite sirah"),
    ("Tempranillo", r"tempranillo|tinto fino|\brioja|ribera del duero|\btoro\b|tinta de toro"),
    ("Sangiovese", r"sangiovese|brunello|chianti|vino nobile|rosso di montalcino|morellino|carmignano|"
     r"montecucco|rosso di montepulciano"),
    ("Nebbiolo", r"nebbiolo|barolo|barbaresco|gattinara|ghemme|\broero|valtellina|sforzato|langhe"),
    ("Barbera", r"barbera"),
    ("Dolcetto", r"dolcetto|dogliani"),
    ("Corvina (Amarone)", r"amarone|valpolicella|ripasso|\bverona\b|corvina"),
    ("Aglianico", r"aglianico|taurasi"),
    ("Nerello Mascalese (Etna)", r"\betna\b|nerello"),
    ("Nero d'Avola", r"nero d.avola"),
    ("Montepulciano", r"montepulciano d.abruzzo"),
    ("Gamay (Beaujolais)", r"gamay|beaujolais|moulin-a-vent|morgon|fleurie|julienas|chenas|brouilly|"
     r"chiroubles|regnie|st.-amour"),
    ("Mourvèdre", r"mourvedre|monastrell|bandol|jumilla"),
    ("Mencía", r"mencia|bierzo|ribeira sacra"),
    ("Carmenère", r"carmenere"),
    ("Pinotage", r"pinotage"),
    ("Touriga & Douro blends", r"touriga|\bdouro\b|\bdao\b|alentejo|bairrada"),
    ("Tannat", r"tannat|madiran"),
    ("Carignan", r"carignan|carinena"),
    ("Port", r"\bport\b"),
    # place-based blends
    ("Bordeaux blend", r"pauillac|st.-julien|st.-estephe|margaux|pessac|graves|medoc|pomerol|st.-emilion|"
     r"fronsac|bordeaux|listrac|moulis|castillon|lalande|\| (left|right) bank|meritage"),
    ("Pinot Noir", r"\| (burgundy|cote de nuits|cote de beaune|chalonnaise)|bourgogne|chambertin|"
     r"richebourg|romanee|vosne|nuits|musigny|clos de vougeot|echezeaux|volnay|pommard|\bcorton\b|"
     r"beaune|savigny|chambolle|morey|gevrey|marsannay|santenay|mercurey|givry|monthelie|"
     r"clos de la roche|clos st.-denis|clos de tart|la tache|grands-echezeaux|\| central otago|"
     r"\| willamette"),
    ("Super Tuscan & Tuscan blends", r"toscana|bolgheri|\| tuscany|maremma|colli della toscana|"
     r"sassicaia|ornellaia|tignanello"),
])

WHITE = _rules([
    ("Sauvignon Blanc", r"sauvignon blanc|fume blanc|sancerre|pouilly-fume|menetou|quincy|reuilly|"
     r"touraine|sauvignon\b"),
    ("Chardonnay", r"chardonnay|chablis|meursault|montrachet|corton-charlemagne|pouilly-fuisse|"
     r"pouilly-vinzelles|st.-veran|macon|vire-clesse|bourgogne|saint-aubin|st.-aubin|"
     r"\| (burgundy|cote de beaune|chalonnaise|macon|chablis)"),
    ("Riesling", r"riesling|kabinett|spatlese|auslese|\bqba\b|grosses gewachs|\bgg\b|"
     r"smaragd(?!.*gruner)|federspiel(?!.*gruner)"),
    ("Grüner Veltliner", r"gruner|veltliner"),
    ("Chenin Blanc", r"chenin|vouvray|savennieres|montlouis|anjou|saumur|steen"),
    ("Pinot Gris / Grigio", r"pinot gris|pinot grigio|grauburgunder|tokay pinot gris"),
    ("Gewürztraminer", r"gewurz|traminer"),
    ("Pinot Blanc", r"pinot blanc|pinot bianco|weissburgunder"),
    ("Viognier & Rhône whites", r"viognier|condrieu|marsanne|roussanne|hermitage|chateauneuf|"
     r"st.-joseph|crozes|cotes du rhone|grenache blanc|\| (northern|southern) rhone|\| rhone"),
    ("Sémillon & white Bordeaux", r"semillon|pessac|graves|bordeaux|entre-deux-mers"),
    ("Albariño", r"albarino|alvarinho|rias baixas"),
    ("Godello", r"godello|valdeorras"),
    ("Champagne & sparkling", r"champagne|prosecco|\bbrut\b"),
    ("Italian whites", r"soave|garganega|fiano|greco di tufo|verdicchio|vermentino|friulano|"
     r"ribolla|falanghina|arneis|gavi|cortese|trebbiano|pecorino|catarratto|grillo|carricante|"
     r"etna|timorasso|kerner|manzoni|vernaccia|orvieto|lugana|collio|\| (veneto|campania|marche|"
     r"friuli/venezia-giulia|trentino/alto adige|sicily|umbria|calabria|liguria)"),
    ("Sherry", r"manzanilla|amontillado|oloroso|\bfino\b|jerez|sherry"),
    ("Viura (white Rioja)", r"viura|rioja white|white rioja"),
    ("Greek whites", r"assyrtiko|malagouzia|moschofilero|\| greece"),
    ("Other whites", r"muscadet|melon|torrontes|furmint|tokaji|jacquere|apremont|savoie|jura|"
     r"txakoli|verdejo|rueda|vinho verde|muscat|moscato|silvaner|scheurebe|chasselas"),
    ("Riesling", r"\| germany|\| finger lakes"),
    ("Chardonnay", r"\| (carneros|sonoma|napa)"),
])


def grape(color, name, region, country):
    rules = RED if color == "Red" else WHITE if color == "White" else None
    if rules is None:
        return ""
    text = _fold(f"{name} | {region} | {country}")
    best = None
    for i, (g, rx) in enumerate(rules):
        m = rx.search(text)
        if m and (best is None or (m.start(), i) < best[0]):
            best = ((m.start(), i), g)
    if best:
        return best[1]
    return "Proprietary & other reds" if color == "Red" else "Other whites"
