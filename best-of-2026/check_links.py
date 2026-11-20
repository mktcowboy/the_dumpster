import csv,subprocess,sys
rows=[l.rstrip('\n').split('\t') for l in open('candidates.tsv') if l.strip()]
out=[]
for r in rows:
    u=r[4]
    p=subprocess.run(['curl','-s','-o','/tmp/body','-w','%{http_code} %{url_effective}','-L','--max-time','25','-A','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36','-H','Accept-Language: en-US',u],capture_output=True,text=True)
    code,eff=(p.stdout.split(' ',1)+[''])[:2]
    body=open('/tmp/body','rb').read().decode('utf8','ignore') if code else ''
    has2026='2026' in body
    print(code, has2026, r[0][:60], '' if eff==u else '-> '+eff, flush=True)
    out.append(r+[code,str(has2026),eff])
csv.writer(open('check.csv','w')).writerows(out)
