"""Converte l'export markdown della tier list HSReplay in data/comps.json.

Uso: python tools/parse_hsreplay_comps.py export.md [--out data/comps.json]

Formato atteso per ogni comp:
    ### Mechs - APM Magnetic (Tier 1)
    - **Difficulty**: 1/5 | **Tier Rank**: 0 (Previous: Tier 2)
    - **Summary**: ...
    - **When to Commit**: ...
    - **Common Enablers**: ...
    - **Core Cards**: Nome (T7), Altro Nome (T6)
    - **Add-on / Tech Cards**: ...
    - **How to Play & Strategy**:
      testo...
Le righe di continuazione (senza "- **") vengono accodate al campo precedente.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HEADER = re.compile(r"^###\s+(.*?)\s*\(Tier\s+(\d)\)\s*$")
FIELD = re.compile(r"^-\s+\*\*(.+?)\*\*:\s*(.*)$")
SOURCE = re.compile(r"Source:\s*\[(.*?)\]\((.*?)\)")
SCRAPED = re.compile(r"Scraped:\s*(\S+)")
CARD = re.compile(r"\s*(.*?)\s*\(T(\d)\)\s*,?")


def parse_cards(text):
    """'Malchezaar, Prince of Dance (T3), Wrath Weaver (T1)' -> [{name, tavern_tier}, ...]
    Funziona anche con nomi che contengono virgole perche' ogni carta termina con (Tn)."""
    return [{"name": n.strip(), "tavern_tier": int(t)} for n, t in CARD.findall(text) if n.strip()]


def parse(md):
    meta = {}
    m = SOURCE.search(md)
    if m:
        meta["_source"] = f"{m.group(1)} - {m.group(2)}"
    m = SCRAPED.search(md)
    if m:
        meta["_scraped"] = m.group(1)

    comps, cur, field = [], None, None
    for raw in md.splitlines():
        line = raw.rstrip()
        h = HEADER.match(line)
        if h:
            title, tier = h.group(1), int(h.group(2))
            tribe = title.split(" - ", 1)[0].strip()
            cur = {"tribe": tribe, "name": title, "tier": tier, "core": [], "addons": []}
            comps.append(cur)
            field = None
            continue
        if cur is None:
            continue
        if line.strip() == "---" or line.startswith("## "):
            field = None
            continue
        f = FIELD.match(line)
        if f:
            key, val = f.group(1), f.group(2).strip()
            field = key
            if key == "Difficulty":
                d = re.search(r"(\d)/5", val)
                r = re.search(r"Tier Rank\*\*:\s*(\d+)", line)
                cur["difficulty"] = int(d.group(1)) if d else None
                cur["rank"] = int(r.group(1)) if r else None
            elif key == "Summary":
                cur["summary"] = val
            elif key == "When to Commit":
                cur["commit"] = val
            elif key == "Common Enablers":
                cur["enablers"] = val
            elif key == "Core Cards":
                cur["core"] = parse_cards(val)
            elif key.startswith("Add-on"):
                cur["addons"] = parse_cards(val)
            elif key.startswith("How to Play"):
                cur["strategy"] = val
            continue
        if line.strip() and field:  # riga di continuazione del campo precedente
            text = line.strip()
            if field == "When to Commit":
                cur["commit"] = f"{cur.get('commit', '')}; {text}".strip("; ")
            elif field == "Common Enablers":
                cur["enablers"] = f"{cur.get('enablers', '')}; {text}".strip("; ")
            elif field.startswith("How to Play"):
                cur["strategy"] = f"{cur.get('strategy', '')} {text}".strip()
            elif field == "Core Cards":
                cur["core"] += parse_cards(text)
            elif field.startswith("Add-on"):
                cur["addons"] += parse_cards(text)
    return meta, comps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "comps.json"))
    args = ap.parse_args()

    md = Path(args.export).read_text(encoding="utf-8")
    meta, comps = parse(md)
    if not comps:
        sys.exit("Nessuna comp trovata: formato del file cambiato?")
    bad = [c["name"] for c in comps if not c["core"]]
    if bad:
        print(f"ATTENZIONE: comp senza carte core: {bad}", file=sys.stderr)
    out = dict(meta, comps=comps)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"Scritte {len(comps)} comp in {args.out}")


if __name__ == "__main__":
    main()
