from pathlib import Path
import math
from PIL import Image, ImageDraw

out = Path(__file__).parent
frames = []
for i in range(48):
    im = Image.new('RGB', (600, 400), '#151923')
    d = ImageDraw.Draw(im)
    t = i / 48 * math.tau
    d.ellipse((135, 325, 465, 351), fill='#0b0e15')
    for x, phase in [(235, 0), (285, 2), (335, 4), (375, 1)]:
        sway = math.sin(t + phase) * 13
        height = 55 + 22 * math.sin(t * 2 + phase)
        d.polygon([(x-24, 211), (x-16, 167), (x+sway, 151-height), (x+13, 172), (x+29, 211)], fill='#ff7845')
        d.polygon([(x-13, 211), (x+sway/2, 149-height/2), (x+15, 211)], fill='#ffd166')
    d.rounded_rectangle((178, 200, 422, 324), radius=12, fill='#3ab795', outline='#76e1bd', width=4)
    for x in (200, 239, 278, 317, 356, 395):
        d.line((x, 223, x, 300), fill='#25876f', width=5)
    d.rounded_rectangle((164, 188, 436, 211), radius=6, fill='#76e1bd')
    d.ellipse((195, 315, 221, 342), fill='#a1adbb')
    d.ellipse((379, 315, 405, 342), fill='#a1adbb')
    d.rounded_rectangle((253, 240, 347, 284), radius=8, fill='#151923')
    d.ellipse((273, 251, 281, 259), fill='#76e1bd')
    d.ellipse((319, 251, 327, 259), fill='#76e1bd')
    d.arc((282, 250, 319, 274), 0, 180, fill='#76e1bd', width=3)
    for j in range(5):
        y = 175 - ((i * 3 + j * 31) % 120)
        x = 220 + j * 39 + math.sin(t+j) * 9
        d.ellipse((x, y, x+5, y+5), fill='#ffd166')
    frames.append(im)
frames[0].save(out / 'dumpster.gif', save_all=True, append_images=frames[1:], duration=60, loop=0, optimize=True)
