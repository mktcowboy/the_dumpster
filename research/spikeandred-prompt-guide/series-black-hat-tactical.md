# Black Hat Tactical — 6-post series

Built with the Spikeandred field guide (`index.html`). The setting changes from Rio to Jerusalem and Bnei Brak. The film language stays the same.

**Concept:** Haredi men in their usual black-and-white dress, with military surplus and tactical gear worn as streetwear. It is a fashion story, not a war story.

**Guardrails:** No weapons. No flags, unit patches, or insignia. No caricature. Faces stay real and dignified. Label every post as AI.

---

## Style lock (paste at the start of every prompt)

```
16mm documentary, Jerusalem, 35mm lens, Kodak Vision3 250D,
hard natural sun, warm highlights, crushed blacks, muted greens,
visible grain, slight halation, unposed framing, 4:5.
```

## Wardrobe lock (keep the same in every frame)

- **Base:** black felt hat, long black coat (bekishe), white shirt, tzitzit fringes, full beard, payot.
- **Gear:** MultiCam plate carrier (no plates, no patches), coyote-brown chest rig, olive MA-1 bomber, tan suede combat boots, ripstop cargo trousers, fingerless tactical gloves, black carabiners.
- **Palette:** black, white, coyote brown, olive, MultiCam.

## Negative prompt

```
plastic skin, waxy, CGI, 3D render, video game, HDR, oversaturated, airbrushed,
perfect teeth, symmetrical composition, stock photo, studio lighting, watermark,
text, logo, readable signage, flags, insignia, patches, weapons, rifles, guns,
caricature, exaggerated facial features, costume, cartoon
```

---

## Post 1 / Establishing — "Where are we?"

**Ratio:** 4:5 + 9:16

```
Film still from a 16mm documentary, three Haredi men walking away down a narrow
stone alley in Mea Shearim, Jerusalem, at midday, black felt hats and long black
coats with MultiCam plate carriers strapped over them, tan combat boots, laundry
lines strung between balconies, faded wall posters with no readable text, rusted
blue window shutters, hard overhead sun and deep shadows, 35mm lens from waist
height, Kodak Vision3 250D, heavy natural grain, slight halation, imperfect
framing, candid unposed moment, warm highlights, crushed blacks, 4:5
```

**Caption:** Midday in Mea Shearim. Same coats. New layers. 🎞️ #AIart

---

## Post 2 / Hero — "Who is this?"

**Ratio:** 4:5

```
Candid close-up portrait of a young Haredi man on a night street in Geula,
Jerusalem, direct on-camera flash, long curled payot, thin gold-rim glasses,
black felt hat, white shirt under a MultiCam plate carrier, tzitzit fringes
hanging below the carrier, olive MA-1 bomber open over it, sweat on his skin,
blurred shop lights and wet asphalt behind him, 35mm lens, Kodak Portra 400
pushed two stops, visible grain, slight red-eye, small motion blur, unposed,
raw street photography, 4:5
```

**Caption:** Geula, 11:40 pm. Fit check passed. #AIart

---

## Post 3 / Action — "What's happening?"

**Ratio:** 9:16

```
Documentary photograph of a Haredi man running to catch a city bus on Malchei
Yisrael Street, Jerusalem, at golden hour, long black coat flying open behind him,
coyote-brown chest rig, black hat held down with one hand, tan combat boots
mid-stride, other passengers watching from the bus door, dust and exhaust in the
air, motion blur in the coat and legs, 35mm lens, Kodak Vision3 500T, gritty
grain, lens flare, imperfect focus, 9:16, subject in the upper third, empty
street in the lower third
```

**Caption:** Never late. Always loaded with pockets. #AIart

---

## Post 4 / Detail — "What is it?"

**Ratio:** 4:5 + 1:1

```
Tight detail photograph, the chest of a Haredi man in Jerusalem, white tzitzit
fringes hanging over worn coyote-brown MOLLE webbing, a black carabiner holding a
key ring, a hand in a fingerless tactical glove holding a small worn prayer book,
long black coat edge in the frame, hard afternoon sun from the side, 50mm lens,
Kodak Vision3 250D, visible grain, dust on the nylon, frayed stitching,
unretouched skin on the knuckles, shallow focus, 4:5
```

**Caption:** Wool, nylon, and 3,000 years of layering. #AIart

---

## Post 5 / Crowd — "Who's it for?"

**Ratio:** 3:2

```
Flash photograph of a group of young Haredi men laughing at a late-night
falafel kiosk on Rabbi Akiva Street, Bnei Brak, black hats and long coats mixed
with olive bombers, MultiCam carriers, and chest rigs, one man leaning on the
counter, sodium streetlight and fluorescent kiosk light, steam from the fryer,
plastic stools and stacked crates, 28mm lens, Kodak Ultramax 400, direct flash,
blur, grain, red-eye, candid, 3:2
```

**Caption:** The whole unit, off duty. Bnei Brak after dark. #AIart

---

## Post 6 / Surreal — "What will they remember?"

**Ratio:** 16:9

```
Documentary-style photograph of a massive matte-olive military surplus blimp
floating low over the stone rooftops of Mea Shearim, Jerusalem, at golden hour,
no markings on the blimp, small Haredi men in black hats and plate carriers on
balconies and rooftops looking up, water tanks, solar heaters, and tangled
antennas in the foreground, 35mm lens, Kodak Vision3 250D, grain, slight
atmospheric haze, realistic scale, deadpan composition, 16:9
```

**Caption:** Air support arrived. Nobody looked surprised. #AIart

---

## Carousel option (guide structure A)

Post 1 → Post 2 → Post 4 → Post 6. World, hero, detail, end card.

## Model settings

| Model | Settings |
|---|---|
| Midjourney | `--style raw --s 50 --ar 4:5` (change `--ar` per post). Use Post 2 as `--sref` for posts 3–6. |
| Flux | Paste as written. Guidance 3–4, 28–40 steps. Add "amateur documentary photograph, not retouched." |
| Nano Banana / Imagen | Generate Post 2 first. Then say "keep the man, the gear, and the grade; change only the scene." |

## Workflow

1. Generate Post 2 (hero) first. Do not continue until the face, hat, and carrier read correctly.
2. Use the hero as the style and character reference for the other five.
3. Make 4–6 variations per post. Pick the least perfect one.
4. Check hands, tzitzit, and the hat brim hardest. Models often merge them.
5. Grade all six together. Add grain last.
