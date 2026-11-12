# Food ingredients made with gas solvents

[gas-solvent-food-ingredients.html](gas-solvent-food-ingredients.html) is a self-contained offline report: an exhaustive list of food ingredients made with gas solvents such as supercritical CO₂, propane, butane, dimethyl ether (DME), HFC-134a, and nitrous oxide (N₂O). It includes regulatory status, residue data, literature, and charts. Open the file in a browser; it does not need a server.

## Rebuild

`gs/build.py` reads `S.json`, `data.py`, `lit.json`, `lit_meta.py`, and `charts.py` from the current directory. It uses only the Python standard library and writes `/workspace/gas-solvent-food-ingredients.html`.

```sh
cd research/food-ingredients/gs
python3 build.py
```

That output matches the HTML page in this folder.
