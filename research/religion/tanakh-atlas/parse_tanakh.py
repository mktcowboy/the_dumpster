import re, json, os, glob, html

FILES = {
 'GEN':('genesis','Genesis','בְּרֵאשִׁית','torah',1,['Genesis']),
 'EXO':('exodus','Exodus','שְׁמוֹת','torah',2,['Exodus']),
 'LEV':('leviticus','Leviticus','וַיִּקְרָא','torah',3,['Leviticus']),
 'NUM':('numbers','Numbers','בְּמִדְבַּר','torah',4,['Numbers']),
 'DEU':('deuteronomy','Deuteronomy','דְּבָרִים','torah',5,['Deuteronomy']),
 'JOS':('joshua','Joshua','יְהוֹשֻׁעַ','neviim',6,['Joshua']),
 'JDG':('judges','Judges','שׁוֹפְטִים','neviim',7,['Judges']),
 '1SA':('samuel','Samuel','שְׁמוּאֵל','neviim',8,['1 Samuel','2 Samuel']),
 '2SA':('samuel','Samuel','שְׁמוּאֵל','neviim',8,['1 Samuel','2 Samuel']),
 '1KI':('kings','Kings','מְלָכִים','neviim',9,['1 Kings','2 Kings']),
 '2KI':('kings','Kings','מְלָכִים','neviim',9,['1 Kings','2 Kings']),
 'ISA':('isaiah','Isaiah','יְשַׁעְיָהוּ','neviim',10,['Isaiah']),
 'JER':('jeremiah','Jeremiah','יִרְמְיָהוּ','neviim',11,['Jeremiah']),
 'EZK':('ezekiel','Ezekiel','יְחֶזְקֵאל','neviim',12,['Ezekiel']),
 'HOS':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'JOL':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'AMO':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'OBA':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'JON':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'MIC':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'NAM':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'HAB':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'ZEP':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'HAG':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'ZEC':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'MAL':('twelve','The Twelve','תְּרֵי עָשָׂר','neviim',13,['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']),
 'PSA':('psalms','Psalms','תְּהִלִּים','ketuvim',14,['Psalms']),
 'PRO':('proverbs','Proverbs','מִשְׁלֵי','ketuvim',15,['Proverbs']),
 'JOB':('job','Job','אִיּוֹב','ketuvim',16,['Job']),
 'SNG':('song','Song of Songs','שִׁיר הַשִּׁירִים','ketuvim',17,['Song of Songs']),
 'RUT':('ruth','Ruth','רוּת','ketuvim',18,['Ruth']),
 'LAM':('lamentations','Lamentations','אֵיכָה','ketuvim',19,['Lamentations']),
 'ECC':('ecclesiastes','Ecclesiastes','קֹהֶלֶת','ketuvim',20,['Ecclesiastes']),
 'EST':('esther','Esther','אֶסְתֵּר','ketuvim',21,['Esther']),
 'DAN':('daniel','Daniel','דָּנִיֵּאל','ketuvim',22,['Daniel']),
 'EZR':('ezra','Ezra–Nehemiah','עֶזְרָא־נְחֶמְיָה','ketuvim',23,['Ezra','Nehemiah']),
 'NEH':('ezra','Ezra–Nehemiah','עֶזְרָא־נְחֶמְיָה','ketuvim',23,['Ezra','Nehemiah']),
 '1CH':('chronicles','Chronicles','דִּבְרֵי הַיָּמִים','ketuvim',24,['1 Chronicles','2 Chronicles']),
 '2CH':('chronicles','Chronicles','דִּבְרֵי הַיָּמִים','ketuvim',24,['1 Chronicles','2 Chronicles']),
}
order_files = ['GEN','EXO','LEV','NUM','DEU','JOS','JDG','1SA','2SA','1KI','2KI','ISA','JER','EZK','HOS','JOL','AMO','OBA','JON','MIC','NAM','HAB','ZEP','HAG','ZEC','MAL','PSA','PRO','JOB','SNG','RUT','LAM','ECC','EST','DAN','EZR','NEH','1CH','2CH']

def clean(s):
    s = s.replace('\\f ', '\\f').replace('\\x ', '\\x')
    s = re.sub(r'\\f\b.*?\\f\*', '', s, flags=re.S)
    s = re.sub(r'\\x\b.*?\\x\*', '', s, flags=re.S)
    s = re.sub(r'\\[a-z0-9]+\*?', ' ', s)
    s = re.sub(r'\{[^}]*\}', '', s)
    s = s.replace('//', '')
    s = html.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

books = {}
for code in order_files:
    path = glob.glob(f'sources/usfm/*-{code}engjps.usfm')
    if not path: print('MISSING', code); continue
    raw = open(path[0], encoding='utf-8-sig').read()
    bid, title, he, div, num, parts = FILES[code]
    if bid not in books:
        books[bid] = {'id':bid,'title':title,'he':he,'division':div,'order':num,'parts':parts,'chapters':[],'verses':0}
    cur = None
    for line in raw.splitlines():
        line=line.strip()
        if line.startswith('\\c '):
            m=re.match(r'\\c\s+(\d+)',line)
            if m:
                cur={'n':int(m.group(1)),'verses':[]}
                books[bid]['chapters'].append(cur)
        elif line.startswith('\\v ') and cur is not None:
            m=re.match(r'\\v\s+([0-9]+(?:-[0-9]+)?)\s*(.*)',line)
            if m:
                txt=clean(m.group(2))
                if txt:
                    cur['verses'].append({'n':m.group(1),'t':txt})
                    books[bid]['verses']+=1
        elif cur is not None and line and not line.startswith('\\'):
            # continuation of verse
            if cur['verses']:
                cur['verses'][-1]['t'] = (cur['verses'][-1]['t']+' '+clean(line)).strip()

out={'books':[], 'stats':{}}
for bid,b in sorted(books.items(), key=lambda kv: kv[1]['order']):
    out['books'].append(b)
out['stats']={'books':len(out['books']),'chapters':sum(len(b['chapters']) for b in out['books']),'verses':sum(b['verses'] for b in out['books'])}
json.dump(out,open('data/tanakh_text.json','w'),ensure_ascii=False,separators=(',',':'))
print(out['stats'])
for b in out['books']:
    print(b['order'], b['id'], len(b['chapters']), b['verses'])
