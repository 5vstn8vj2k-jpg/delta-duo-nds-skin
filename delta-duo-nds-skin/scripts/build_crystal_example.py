#!/usr/bin/env python3
"""Build an original Abra-style crystal Delta NDS skin example.

This is intentionally an example for the Casey/Abra crystal aesthetic, not a
universal theme generator. It accepts a Delta .deltaskin archive or info.json,
keeps only iPhone inner/outer/splitView/cover representations, and writes all
artwork, previews, metadata, and the final archive beneath --output-dir.
"""
from __future__ import annotations

import argparse
import copy
import html
import io
import json
import math
import re
import tempfile
import zipfile
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

KEEP_REPRESENTATIONS = ("inner", "outer", "splitView", "cover")
FRAMES = {
    "a": {"x": 823, "y": 550, "width": 48, "height": 48},
    "b": {"x": 775, "y": 598, "width": 48, "height": 48},
    "x": {"x": 775, "y": 502, "width": 48, "height": 48},
    "y": {"x": 727, "y": 550, "width": 48, "height": 48},
    "l": {"x": 26, "y": 448, "width": 150, "height": 44},
    "r": {"x": 775, "y": 448, "width": 150, "height": 44},
    "menu": {"x": 325, "y": 565, "width": 24, "height": 24},
    "select": {"x": 445, "y": 565, "width": 24, "height": 24},
    "start": {"x": 565, "y": 565, "width": 24, "height": 24},
}
FACE_EDGES = {
    "a": {"top": 0, "bottom": 0, "left": 0, "right": 20},
    "b": {"top": 0, "bottom": 8, "left": 0, "right": 0},
    "x": {"top": 3, "bottom": 0, "left": 0, "right": 0},
    "y": {"top": 0, "bottom": 0, "left": 15, "right": 0},
}
FONT = "DejaVu Sans, Helvetica, Arial, sans-serif"
PALETTE = {"#1b2a38":"#fbe69e", "#111b26":"#eec85e", "#080e16":"#d8a93f", "#263847":"#f9da7f", "#141f2a":"#c19340", "#080f17":"#795337", "#607c87":"#dbb676", "#060b12":"#684632", "#0a121a":"#56392d", "#49606b":"#f4d18b", "#111d27":"#8b664a", "#172a35":"#674736", "#050b10":"#53372b", "#9cb4ba":"#fce6bd", "#7be2c5":"#ffe58e", "#f4c581":"#f8dba6", "#9fc6f3":"#e5d3fa", "#c6b7f4":"#ead2f5", "#070e14":"#644334", "#334b57":"#b58c62", "#78919a":"#d2ae7d", "#9fb5bb":"#634535", "#638a98":"#947143", "#433044":"#4b315d", "#2a202d":"#33232e"}


def fnum(v): return str(round(float(v), 3))
def esc(s): return html.escape(str(s), quote=True)
def txt(x, y, s, size=11, fill="#b6c5cf", weight=700, anchor="middle", spacing=0):
    return f'<text x="{fnum(x)}" y="{fnum(y)}" text-anchor="{anchor}" dominant-baseline="middle" font-family="{FONT}" font-size="{size}" font-weight="{weight}" letter-spacing="{spacing}" fill="{fill}">{esc(s)}</text>'
def rect(x,y,w,h,r=0,fill="none",stroke="none",sw=0,opacity=1):
    return f'<rect x="{fnum(x)}" y="{fnum(y)}" width="{fnum(w)}" height="{fnum(h)}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"/>'
def circle(cx,cy,r,fill,stroke="none",sw=0,opacity=1):
    return f'<circle cx="{fnum(cx)}" cy="{fnum(cy)}" r="{fnum(r)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"/>'
def line(x1,y1,x2,y2,color,width=1,opacity=1):
    return f'<line x1="{fnum(x1)}" y1="{fnum(y1)}" x2="{fnum(x2)}" y2="{fnum(y2)}" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>'
def abra_head(x,y,scale):
    return f'''<g transform="translate({x},{y}) scale({scale})" stroke-linecap="round" stroke-linejoin="round"><path d="M -20 -12 L -26 -29 Q -17 -30 -9 -21 Q 0 -24 9 -21 Q 17 -30 26 -29 L 20 -12 Q 22 -3 15 3 L 4 10 Q 0 13 -4 10 L -15 3 Q -22 -3 -20 -12 Z" fill="#ffdb62" stroke="#75502f" stroke-width="1.8"/><path d="M -21 -24 L -17 -14 L -11 -19 Z M 21 -24 L 17 -14 L 11 -19 Z" fill="#ffeeb0"/><path d="M -15 -10 Q -12 -5 -7 -4 M 15 -10 Q 12 -5 7 -4" fill="none" stroke="#63432b" stroke-width="2"/><path d="M -2 4 Q 0 6 2 4" fill="none" stroke="#63432b" stroke-width="1.4"/></g>'''


def load_template(path: Path):
    tmp = None
    if path.suffix.lower() == ".deltaskin":
        tmp = tempfile.TemporaryDirectory(prefix="delta-skin-")
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if "info.json" not in names:
                raise ValueError(".deltaskin must contain top-level info.json")
            z.extract("info.json", tmp.name)
            raw = json.loads((Path(tmp.name) / "info.json").read_text(encoding="utf-8"))
        base = Path(tmp.name)
    elif path.name == "info.json" or path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        base = path.parent
    else:
        raise ValueError("--template must be a Delta .deltaskin archive or info.json")
    try:
        phone = raw["representations"]["iphone"]
    except (KeyError, TypeError) as e:
        if tmp: tmp.cleanup()
        raise ValueError("template info.json lacks representations.iphone") from e
    return raw, phone, tmp


def prepare_phone(phone, layout):
    keep = {k: copy.deepcopy(phone[k]) for k in KEEP_REPRESENTATIONS if k in phone}
    if not keep:
        raise ValueError("template has no iPhone Duo representations")
    if layout == "big-main" and "inner" not in keep:
        raise ValueError("big-main layout requires an inner representation")
    if layout == "big-main" and "inner" in keep:
        inner = keep["inner"]
        expected = {"portrait": {"width": 669, "height": 951}, "landscape": {"width": 951, "height": 669}}
        for direction, mapping in expected.items():
            if direction in inner and inner[direction].get("mappingSize") != mapping:
                raise ValueError(f"big-main layout needs official inner/{direction} mappingSize {mapping}")
            for i, expected_y in enumerate((0, 192)):
                if direction in inner:
                    screens = inner[direction].get("screens", [])
                    if len(screens) <= i or screens[i].get("inputFrame") != {"x": 0, "y": expected_y, "width": 256, "height": 192}:
                        raise ValueError(f"big-main layout needs the official NDS screen order in inner/{direction}")
        if "portrait" in inner and inner["portrait"].get("screens"):
            inner["portrait"]["screens"][0]["outputFrame"] = {"x":46.5,"y":22,"width":576,"height":432}
        if "landscape" in inner and len(inner["landscape"].get("screens", [])) > 1:
            land = inner["landscape"]
            land["screens"][0]["outputFrame"] = {"x":30,"y":30,"width":536,"height":402}
            land["screens"][1]["outputFrame"] = {"x":620,"y":117,"width":300,"height":225}
        # The replacement hitboxes are designed only for the landscape canvas.
        # Preserve the portrait controls and its unchanged lower touch frame.
        for rep in [inner["landscape"]] if "landscape" in inner else []:
            for item in rep.get("items", []):
                inp = item.get("inputs")
                if isinstance(inp, dict) and "up" in inp:
                    item["frame"] = {"x":78,"y":505,"width":136,"height":136}
                    item["extendedEdges"] = {"left":78,"right":12,"top":8,"bottom":8}
                elif isinstance(inp, dict) and inp.get("x") == "touchScreenX":
                    screens = [s for s in rep.get("screens", []) if s.get("outputFrame") and s.get("placement") != "app"]
                    if len(screens) > 1: item["frame"] = copy.deepcopy(screens[1]["outputFrame"])
                elif isinstance(inp, list) and inp and inp[0] in FRAMES:
                    n = inp[0]; item["frame"] = copy.deepcopy(FRAMES[n])
                    item["extendedEdges"] = ({"top":4,"bottom":4,"left":10,"right":10} if n in ("l","r") else {"top":12,"bottom":12,"left":18,"right":55} if n in ("menu","select","start") else copy.deepcopy(FACE_EDGES[n]))
    return keep


def render(mode, ori, rep, overlay):
    w, h = rep["mappingSize"]["width"], rep["mappingSize"]["height"]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">', '<defs><linearGradient id="body" x1="0" y1="0" x2=".65" y2="1"><stop stop-color="#1b2a38"/><stop offset=".47" stop-color="#111b26"/><stop offset="1" stop-color="#080e16"/></linearGradient><linearGradient id="metal" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#fff2e2"/><stop offset=".3" stop-color="#776379"/><stop offset=".7" stop-color="#514052"/><stop offset="1" stop-color="#a992a5"/></linearGradient><linearGradient id="button" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#e4c8f5"/><stop offset=".5" stop-color="#765094"/><stop offset="1" stop-color="#4b315d"/></linearGradient></defs>', rect(0,0,w,h,0,"url(#body)"), rect(3,3,w-6,h-6,21,"none","#765667",3,.8), rect(5,5,w-10,h-10,19,"none","#fce6cf",1.2,.95)]
    if mode == "cover": s += [circle(w/2,h/2-4,60,"#f3deab","#bb8d51",1), abra_head(w/2,h/2+3,1.65), txt(w/2,h/2+83,"ABRA DREAM",13,"#704737",700,spacing=3)]
    elif mode == "inner" and ori == "portrait": s += [rect(0,466,w,13,0,"#080f17"), abra_head(w/2,552,1.05), txt(w/2,583,"ABRA / 063",9,"#684232",700,spacing=1.4)]
    elif mode == "inner" and ori == "landscape": s += [abra_head(w/2,490,1.1), txt(w/2,523,"ABRA / 063",9,"#684232",700,spacing=1.4)]
    elif mode in ("outer", "splitView"): s += [abra_head(w/2, h*.48, .5)]
    for sc in rep.get("screens", []):
        q = sc.get("outputFrame")
        if sc.get("placement") == "app" or not q: continue
        x,y,sw,sh = [q[k] for k in ("x","y","width","height")]
        s += [rect(x-8,y-8,sw+16,sh+16,8,"#392c3f","#62485e",1), rect(x-3,y-3,sw+6,sh+6,3,"#483642","#d9b6ce",.7), rect(x,y,sw,sh,0,"#000")]
    for item in rep.get("items", []):
        inp, frame = item.get("inputs"), item.get("frame")
        if not frame: continue
        x,y,bw,bh = [frame[k] for k in ("x","y","width","height")]; cx,cy=x+bw/2,y+bh/2
        if isinstance(inp, dict):
            if "up" not in inp: continue
            size=min(bw,bh); u=size/3; s += [circle(cx,cy,size*.52,"#0a121a","#49606b",1), circle(cx,cy,size*.49,"#111d27","#172a35",1)]
            pts=[(x+u,y+3),(x+2*u,y+3),(x+2*u,y+u),(x+size-3,y+u),(x+size-3,y+2*u),(x+2*u,y+2*u),(x+2*u,y+size-3),(x+u,y+size-3),(x+u,y+2*u),(x+3,y+2*u),(x+3,y+u),(x+u,y+u)]
            s.append('<path d="'+' '.join(('M' if i==0 else 'L')+f'{a:.2f},{b:.2f}' for i,(a,b) in enumerate(pts))+' Z" fill="url(#metal)" stroke="#e0c9de" stroke-width="1.6"/>'); continue
        if not isinstance(inp,list) or not inp: continue
        n=inp[0]
        if n in "abxy": s += [circle(cx,cy+2,min(bw,bh)/2-1,"#433044"), circle(cx,cy,min(bw,bh)/2-3,"url(#button)","#eee0f7",.8), txt(cx,cy,n.upper(),16,"#ffe5b0",700)]
        elif n in ("l","r"): s += [rect(x+2,y+3,bw-4,bh-8,8,"url(#metal)","#f7e5f1",1), txt(cx,cy,n.upper(),14,"#fff1db",700)]
        elif n in ("menu","start","select"): s += [circle(cx,cy,8,"url(#button)","#78919a",.8), txt(x+bw+7,cy,n.upper(),8,"#9fb5bb",700,"start",.4)]
    s.append('</svg>')
    svg = re.sub(r"#[0-9a-fA-F]{6}", lambda m: PALETTE.get(m.group(0).lower(), m.group(0)), ''.join(s))
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=int(w*3), output_height=int(h*3))
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    alpha = im.getchannel("A"); draw = ImageDraw.Draw(alpha)
    for sc in rep.get("screens", []):
        q=sc.get("outputFrame")
        if sc.get("placement") == "app" or not q: continue
        draw.rectangle((round(q["x"]*3), round(q["y"]*3), round((q["x"]+q["width"])*3)-1, round((q["y"]+q["height"])*3)-1), fill=0)
    im.putalpha(alpha)
    if overlay == "psychic":
        for sc in rep.get("screens", []):
            q=sc.get("outputFrame"); inp=sc.get("inputFrame", {})
            if not q or sc.get("placement") == "app" or inp.get("y") != 192: continue
            im.alpha_composite(psychic_pattern(q["width"],q["height"],round(q["width"]*3),round(q["height"]*3)), (round(q["x"]*3),round(q["y"]*3)))
    return im


def psychic_pattern(w,h,outw,outh):
    cx,cy=w/2,h/2; unit=min(w,h); r=unit*.405; p=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"><g fill="none" stroke="#e2c0ff" stroke-linecap="round">']
    for radius,sw,op,dash in [(r,1.15,.22,""),(r*.91,.55,.14,"3 5"),(r*.75,1.1,.23,""),(r*.58,.7,.16,"5 5"),(r*.42,.9,.20,"")]: p.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" stroke-width="{sw}" opacity="{op}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>' )
    pts=[f'{cx+r*(.72 if i%2==0 else .51)*math.cos(-math.pi/2+i*math.pi/8):.3f},{cy+r*(.72 if i%2==0 else .51)*math.sin(-math.pi/2+i*math.pi/8):.3f}' for i in range(16)]
    p += [f'<polygon points="{" ".join(pts)}" stroke-width=".9" opacity=".16"/>', f'<circle cx="{cx}" cy="{cy}" r="{unit*.024}" stroke-width=".9" opacity=".18"/>', '</g></svg>']
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=''.join(p).encode(),output_width=outw,output_height=outh))).convert("RGBA")


def preview(rep, skin, out):
    scale=3; w,h=rep["mappingSize"]["width"],rep["mappingSize"]["height"]; bg=Image.new("RGBA",(w*scale,h*scale),"#302742"); d=ImageDraw.Draw(bg)
    for i,sc in enumerate(rep.get("screens", [])):
        q=sc.get("outputFrame")
        if not q: continue
        x,y,sw,sh=[round(q[k]*scale) for k in ("x","y","width","height")]; d.rectangle((x,y,x+sw,y+sh),fill="#3b3152" if i==0 else "#3d3151")
        for k in range(7): d.line((x+sw*.12,y+sh*(.42+k*.075),x+sw*.88,y+sh*(.42+k*.075)),fill=(170,144,177,110),width=3)
        d.ellipse((x+sw*.66,y+sh*.16,x+sw*.78,y+sh*.32),fill="#ffe7a2")
        label="GAME SCREEN" if i==0 else "TOUCH SCREEN"
        try: font=ImageFont.truetype("DejaVuSans-Bold.ttf", max(20, round(sh*.05)))
        except OSError: font=ImageFont.load_default()
        d.text((x+sw/2,y+sh*.86),label,font=font,fill="#fff2d0",anchor="mm")
    result=Image.alpha_composite(bg,skin).convert("RGB"); result.thumbnail((840,1300),Image.Resampling.LANCZOS); result.save(out,optimize=True)


def main():
    ap=argparse.ArgumentParser(description="Casey-style crystal NDS skin example (not a universal theme generator).")
    ap.add_argument("--template", required=True, type=Path, help="Delta .deltaskin or info.json")
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--identifier", required=True)
    ap.add_argument("--layout", choices=("big-main","official"), default="official")
    ap.add_argument("--overlay", choices=("psychic","none"), default="none")
    args=ap.parse_args(); args.output_dir.mkdir(parents=True,exist_ok=True)
    if not args.name.strip() or not args.identifier.strip():
        ap.error("--name and --identifier cannot be blank")
    slug=re.sub(r"[^A-Za-z0-9._-]+","-",args.name).strip("-") or "crystal-example"
    archive=args.output_dir/f"{slug}.deltaskin"
    if args.template.resolve() in ((args.output_dir/"info.json").resolve(), archive.resolve()):
        ap.error("choose a different output directory to avoid overwriting the input template")
    raw, phone, tmp = load_template(args.template)
    try:
        if raw.get("gameTypeIdentifier") != "com.rileytestut.delta.game.ds":
            raise ValueError("template must use the Delta NDS gameTypeIdentifier")
        reps=prepare_phone(phone,args.layout); info={k:v for k,v in raw.items() if k not in ("name","identifier","representations")}; info.update(name=args.name,identifier=args.identifier,representations={"iphone":reps})
        assets=[]
        for mode,variants in reps.items():
            for ori,rep in variants.items():
                filename=f"crystal_{mode}_{ori}.png"; render(mode,ori,rep,args.overlay).save(args.output_dir/filename,optimize=True); rep["assets"]={"large":filename}; assets.append(filename)
        (args.output_dir/"info.json").write_text(json.dumps(info,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        for ori in ("portrait","landscape"):
            if ori in reps.get("inner",{}): preview(reps["inner"][ori],Image.open(args.output_dir/f"crystal_inner_{ori}.png").convert("RGBA"),args.output_dir/f"preview_inner_{ori}.png")
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            z.write(args.output_dir/"info.json","info.json")
            for filename in sorted(assets): z.write(args.output_dir/filename,filename)
        print(archive)
    finally:
        if tmp: tmp.cleanup()

if __name__ == "__main__": main()
