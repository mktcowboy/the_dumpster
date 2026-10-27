# Land Listings — Combined

One grouped file across the state land-listing drops. The state projects stay
separate; this directory only reads them and writes a merged table.

**18,231 listings:** Colorado 999 · Texas 16,048 · Utah 1,184.

## Files

| File | Contents |
|---|---|
| `land-listings-combined.csv` | One row per listing, common schema plus state-specific fields |
| `land-listings-combined.json` | Same rows as a flat JSON array |
| `build_combined.py` | Rebuilds both files from the state projects |

Rebuild from the repository root:

```sh
python3 land-listings-combined/build_combined.py
```

The script reads:

- `colorado-land-listings/colorado-land-over-10ac.json` (or its `.part*` files)
  and `colorado-land-geocodes.json`
- `texas-triangle-land/data/listings.json`
- `utah-land-listings/utah-land-over-10ac.json`

## Columns

| Column | Notes |
|---|---|
| `state` | `CO`, `TX` or `UT` |
| `snapshot_date` | Date of that state's capture; the three drops are not simultaneous |
| `dataset` | Source project directory |
| `title` | Address/listing title as shown by Realtor.com |
| `price_usd` | Asking price as listed; blanks where the card showed none |
| `acres` | Lot size from `lot_sqft ÷ 43,560`; blanks where the card showed none |
| `price_per_acre` | Computed as `price_usd / acres` when both are present and positive |
| `county` | As listed; always blank for Colorado (Realtor.com cards omit county there) |
| `city`, `zip`, `broker` | As listed; `zip` is Utah-only, `broker` is absent from the Texas drop |
| `pending` | Utah's pending/contingent flag; Texas already drops those, Colorado does not report it |
| `list_date` | Date portion only |
| `property_type` | Texas only: Land, Farm, Single Family, Mobile, Multi Family, Apartment |
| `lat`, `lon` | Map position from the source drop or its geocode cache |
| `location_precision` | `parcel` (Realtor.com pin), `address`, `street`, `zip`, `city`, or `none` |
| `zone` | Texas only: `inside` the Dallas–San Antonio–Houston triangle or in its 50-mile `buffer` |
| `distance_to_triangle_mi` | Texas only |
| `first_seen`, `prev_price`, `realtor_id` | Texas only; history used by its page |

## Scope differences — read this

The three drops answer different questions, so the combined file is a
convenience index, not a comparable national census.

- **Colorado:** land listings, **10+ acres**, captured October 12–13, 2026.
  County is absent from the source cards. Coordinates are geocoded to
  address/street/city, not parcel pins: 703 records have a point, 295 fall back
  to their city (hollow on the original map), and 1 has no city. Price is
  missing for 17 records and acreage for 30.
- **Utah:** land listings, **10+ acres**, captured October 16, 2026. County is
  missing for 100 records. One record has no coordinates. Pending/contingent
  listings are included and flagged.
- **Texas:** **5+ acres** across land, farm/ranch, houses on acreage, mobile and
  multi-family, inside the triangle plus a 50-mile ring; captured October 18,
  2026. Pending/contingent listings and prices under $1,000 are excluded by the
  source build. Only `inside` and `buffer` records appear; `outside` records are
  dropped upstream.

Other caveats:

- Values are reproduced as listed, including a $1 placeholder and unusually
  large acreage figures in the Utah drop.
- No cross-state deduplication is needed. Each state project already dedupes
  within its own search.
- Acreage filters are inclusive: Colorado and Utah include records at exactly
  10 acres; Texas includes records at exactly 5 acres.
- `price_per_acre` is derived for this file; the Utah source also carries a
  `ppa` field, but it is not used here so all three states are computed the same
  way.
