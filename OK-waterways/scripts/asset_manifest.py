#!/usr/bin/env python3
"""Write the Workers Static Assets manifest ({"/path": {hash, size}}) for site/ — used for
direct-API uploads (wrangler deploy does this automatically)."""
import os, sys, json, hashlib
site = sys.argv[1] if len(sys.argv) > 1 else "site"
man, paths = {}, {}
for root, _, files in os.walk(site):
    for f in files:
        p = os.path.join(root, f); rel = "/" + os.path.relpath(p, site)
        data = open(p, "rb").read()
        h = hashlib.sha256(data + os.path.splitext(f)[1].encode()).hexdigest()[:32]
        man[rel] = {"hash": h, "size": len(data)}; paths[h] = p
json.dump(man, open("build/asset_manifest.json", "w"))
json.dump(paths, open("build/asset_paths.json", "w"))
print(len(man), "files", sum(v["size"] for v in man.values()) / 1e6, "MB")
