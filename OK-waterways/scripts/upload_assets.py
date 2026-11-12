#!/usr/bin/env python3
"""Upload asset buckets returned by POST .../assets-upload-session.
Usage: upload_assets.py ACCOUNT_ID SESSION_JSON   (SESSION_JSON = {"jwt":..., "buckets":[[hash,...],...]})
Prints the completion JWT."""
import sys, json, base64, mimetypes, urllib.request, uuid
acct, sess = sys.argv[1], json.load(open(sys.argv[2]))
paths = json.load(open("build/asset_paths.json"))
url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/workers/assets/upload?base64=true"
done = None
for bucket in sess["buckets"]:
    bnd = uuid.uuid4().hex; body = b""
    for h in bucket:
        p = paths[h]; ct = mimetypes.guess_type(p)[0] or "application/octet-stream"
        body += (f"--{bnd}\r\nContent-Disposition: form-data; name=\"{h}\"; filename=\"{h}\"\r\nContent-Type: {ct}\r\n\r\n").encode()
        body += base64.b64encode(open(p, "rb").read()) + b"\r\n"
    body += f"--{bnd}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={"Authorization": "Bearer " + sess["jwt"], "Content-Type": f"multipart/form-data; boundary={bnd}"})
    r = json.load(urllib.request.urlopen(req, timeout=600))
    print("bucket", len(bucket), r.get("success"), file=sys.stderr)
    if r.get("result", {}).get("jwt"): done = r["result"]["jwt"]
print(done or sess["jwt"])
