#!/usr/bin/env python3
"""SEO/AEO/GEO validator for the Di Dee Designers static site (stdlib only).

Usage: python scripts/validate_seo.py [repo_root]
Prints PASS/FAIL per check and exits 1 if any critical check fails.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
SITE = "https://dideedesigners.in"
PRICES = {"Box folding (pressed pleats)": 250, "Semi-fluffy pleats": 300, "Full-fluffy pleats with hanger": 400}
# Claims the owner has not verified; must never appear in schema or visible text of indexable pages.
FORBIDDEN_TEXT = [r"\bAggregateRating\b", r"\bstar rating", r"★", r"\bcustomer reviews?\b", r"\bcertified\b", r"\baward[- ]winning\b",
                  r"\bopen (daily|24)", r"\bopening hours\b", r"\bsince (19|20)\d\d\b", r"\bfounded in\b", r"\byears of experience\b",
                  r"\bwe sell sarees\b",
                  # unverified service promises / quality claims (owner review before re-adding)
                  r"\bpick-?up\b", r"\bdoorstep\b", r"\bdeliver(y|ies)\b", r"\bexpress\b", r"\bbulk\b", r"\bsilk\b", r"\bbridal\b",
                  r"\bappointments?\b", r"\bpersonal care\b", r"\bgentle\b", r"\beven pleats\b"]
FORBIDDEN_SCHEMA_KEYS = {"aggregateRating", "review", "geo", "openingHours", "openingHoursSpecification", "streetAddress",
                         "postalCode", "foundingDate", "latitude", "longitude", "speakable"}
FORBIDDEN_SCHEMA_TYPES = {"HowTo", "HowToStep", "AggregateRating", "Review", "GeoCoordinates", "SpeakableSpecification"}

results = []  # (ok, critical, message)


def check(ok, msg, critical=True):
    results.append((bool(ok), critical, msg))


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""; self.meta = {}; self.canonical = None; self.h1 = []; self.ld = []; self.links = []
        self.imgs = []; self.text = []; self.faq = []; self._cur = None; self._buf = []; self._skip = 0

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "meta":
            k = a.get("name") or a.get("property")
            if k:
                self.meta[k.lower()] = a.get("content", "")
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        elif tag == "a" and a.get("href") is not None:
            self.links.append(a["href"])
        elif tag == "img" and a.get("src"):
            self.imgs.append(a["src"])
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._cur = "ld"; self._buf = []; self._skip += 1
        elif tag in ("script", "style"):
            self._skip += 1
        elif tag in ("title", "h1", "summary"):
            self._cur = tag; self._buf = []
        elif tag == "details":
            self.faq.append([None, None])
        elif tag == "p" and self.faq and self.faq[-1][0] and self.faq[-1][1] is None:
            self._cur = "faq_p"; self._buf = []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            if self._cur == "ld":
                self.ld.append("".join(self._buf)); self._cur = None
            self._skip -= 1
        elif tag in ("title", "h1", "summary") and self._cur == tag:
            t = " ".join("".join(self._buf).split())
            if tag == "title": self.title = t
            elif tag == "h1": self.h1.append(t)
            else: self.faq[-1][0] = t
            self._cur = None
        elif tag == "p" and self._cur == "faq_p":
            self.faq[-1][1] = " ".join("".join(self._buf).split()); self._cur = None

    def handle_data(self, d):
        if self._cur:
            self._buf.append(d)
        if not self._skip:
            self.text.append(d)


def route(path: Path):
    rel = path.relative_to(ROOT).as_posix()
    if rel == "index.html": return "/"
    if rel.endswith("/index.html"): return "/" + rel[:-10]
    if rel.endswith(".html"): return "/" + rel[:-5]
    return None


def resolve(href):
    """Map an internal href to an existing file, or None."""
    p = urlparse(href)
    if p.scheme in ("mailto", "tel", "javascript", "data") or (p.netloc and p.netloc != "dideedesigners.in"):
        return True
    path = p.path
    if not path:  # pure fragment
        return True
    t = (ROOT / path.lstrip("/")) if path.startswith("/") else (ROOT / path)
    return t.is_file() or (t.is_dir() and (t / "index.html").is_file()) or t.with_suffix(".html").is_file()


pages = {}
for f in sorted(ROOT.rglob("*.html")):
    if ".git" in f.parts or "scripts" in f.parts:
        continue
    p = Page(); p.feed(f.read_text(encoding="utf-8")); p.path = f; p.route = route(f)
    p.noindex = "noindex" in p.meta.get("robots", "").lower()
    pages[f] = p
indexable = {f: p for f, p in pages.items() if not p.noindex and f.name != "404.html"}

# --- titles / descriptions / h1 / canonical
for kind, get in (("title", lambda p: p.title), ("meta description", lambda p: p.meta.get("description", ""))):
    seen = {}
    for f, p in indexable.items():
        v = get(p)
        check(v, f"{kind} present: {p.route}")
        if v in seen: check(False, f"{kind} duplicated: {p.route} == {seen[v]}")
        seen[v] = p.route
    check(len(seen) == len(indexable), f"unique {kind}s across {len(indexable)} indexable pages")
for f, p in indexable.items():
    check(len(p.h1) == 1, f"exactly one H1 on {p.route} (found {len(p.h1)})")
    want = SITE + p.route
    check(p.canonical == want, f"canonical on {p.route} is {want} (found {p.canonical})")
    check(p.meta.get("og:url") == want, f"og:url matches canonical on {p.route}", False)
    for k in ("og:title", "og:description", "og:image", "twitter:title", "twitter:description", "twitter:image"):
        check(p.meta.get(k), f"{k} present on {p.route}", False)
    check(len(p.title) <= 70, f"title length <= 70 on {p.route} ({len(p.title)})", False)
    check(len(p.meta.get("description", "")) <= 170, f"description length <= 170 on {p.route}", False)
for f, p in pages.items():
    if p.noindex:
        check("noindex" in p.meta["robots"], f"{p.route} keeps noindex", False)

# --- JSON-LD
for f, p in indexable.items():
    r = p.route
    check(len(p.ld) == 1, f"one JSON-LD block on {r} (found {len(p.ld)})")
    if not p.ld: continue
    try:
        data = json.loads(p.ld[0])
    except ValueError as e:
        check(False, f"JSON-LD parses on {r}: {e}"); continue
    check(True, f"JSON-LD parses on {r}")
    nodes = data.get("@graph", [data])
    defined, refs, types = set(), [], set()

    def walk(o, top=False):
        if isinstance(o, dict):
            keys = set(o) - {"@context"}
            if "@id" in o and keys == {"@id"}:
                refs.append(o["@id"])
            elif "@id" in o:
                defined.add(o["@id"])
            t = o.get("@type")
            for x in ([t] if isinstance(t, str) else t or []): types.add(x)
            for k, v in o.items():
                if k in FORBIDDEN_SCHEMA_KEYS: check(False, f"forbidden schema key '{k}' on {r}")
                walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(nodes)
    check(not [x for x in refs if x not in defined], f"all @id references resolve on {r}" +
          (f" (missing: {[x for x in refs if x not in defined]})" if [x for x in refs if x not in defined] else ""))
    check(not (types & FORBIDDEN_SCHEMA_TYPES), f"no forbidden schema types on {r}: {sorted(types & FORBIDDEN_SCHEMA_TYPES)}")
    check(SITE + "/#organization" in defined, f"Organization @id defined on {r}")
    check({"Organization", "WebSite", "WebPage"} <= (types | ({"WebPage"} if "FAQPage" in types else set())), f"Organization/WebSite/WebPage present on {r}")
    if r != "/": check("BreadcrumbList" in types, f"BreadcrumbList on {r}")
    check(("FAQPage" in types) == (r == "/faq"), f"FAQPage only on /faq (page {r})")
    vis = " ".join(p.text)
    # offers must match visible prices
    for m in re.finditer(r'"name": "([^"]+?)(?:, per saree)?",\s*"price": "(\d+)"', json.dumps(data, indent=2, ensure_ascii=False)):
        name, price = m.group(1), int(m.group(2))
        check(PRICES.get(name) == price, f"offer '{name}' = ₹{price} matches verified price on {r}")
        check(f"₹{price}" in vis, f"₹{price} for '{name}' visible on {r}")
    if r == "/faq":  # FAQ schema must equal visible FAQ
        qa = [(n["name"], n["acceptedAnswer"]["text"]) for x in nodes if x.get("@type") == "FAQPage" for n in x["mainEntity"]]
        check(qa == [tuple(x) for x in p.faq], f"FAQ schema exactly matches {len(p.faq)} visible Q&As")
    schema_text = p.ld[0]
    for pat in FORBIDDEN_TEXT:
        check(not re.search(pat, schema_text, re.I), f"no forbidden claim /{pat}/ in schema on {r}")

# --- visible-text claims + price consistency
for f, p in indexable.items():
    vis = " ".join(p.text)
    for pat in FORBIDDEN_TEXT:
        check(not re.search(pat, vis, re.I), f"no forbidden claim /{pat}/ in visible text of {p.route}")
    if p.route == "/saree-draping/":
        check("₹" not in vis, "draping page lists no invented price")
    if p.route == "/saree-pre-pleating/":
        check(all(f"₹{v}" in vis for v in PRICES.values()), "pre-pleating page shows ₹250/₹300/₹400")
home = next((p for p in indexable.values() if p.route == "/"), None)
if home:
    hv = " ".join(home.text)
    check(all(f"₹{v}" in hv for v in PRICES.values()), "homepage shows ₹250/₹300/₹400")
    check("pre-pleating" in home.h1[0].lower() and "draping" in home.h1[0].lower(), "homepage H1 names both services")

# --- links / images
for f, p in pages.items():
    bad = [h for h in p.links if not resolve(h)]
    check(not bad, f"internal links resolve in {p.route or f.name}" + (f" (broken: {bad})" if bad else ""))
    base = f.parent
    badi = []
    for s in p.imgs:
        if s.startswith("data:") or s.startswith("http"): continue
        t = ROOT / s.lstrip("/") if s.startswith("/") else base / s
        if not t.is_file(): badi.append(s)
    check(not badi, f"image paths resolve in {p.route or f.name}" + (f" (missing: {badi})" if badi else ""))
# --- sitemap
sm = ROOT / "sitemap.xml"
try:
    tree = ET.parse(sm); check(True, "sitemap.xml is well-formed XML")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "i": "http://www.google.com/schemas/sitemap-image/1.1"}
    locs = [u.findtext("s:loc", namespaces=ns) for u in tree.getroot().findall("s:url", ns)]
    want = sorted(SITE + p.route for p in indexable.values())
    check(sorted(locs) == want, f"sitemap URLs == indexable canonicals (sitemap: {sorted(locs)})")
    check(len(set(locs)) == len(locs), "sitemap has no duplicate URLs")
    for u in tree.getroot().findall("s:url", ns):
        lm = u.findtext("s:lastmod", namespaces=ns)
        check(lm and re.fullmatch(r"\d{4}-\d{2}-\d{2}", lm), f"valid lastmod for {u.findtext('s:loc', namespaces=ns)}")
        for il in u.findall("i:image/i:loc", ns):
            check((ROOT / il.text.replace(SITE + "/", "")).is_file(), f"sitemap image exists: {il.text}")
except (ET.ParseError, OSError) as e:
    check(False, f"sitemap.xml valid: {e}")

# --- robots.txt
rb = (ROOT / "robots.txt").read_text(encoding="utf-8")
check(f"Sitemap: {SITE}/sitemap.xml" in rb, "robots.txt declares the sitemap")
check(not re.search(r"^\s*Disallow:\s*/\s*$", rb, re.M), "robots.txt does not block the whole site")

# --- llms.txt
ll = (ROOT / "llms.txt").read_text(encoding="utf-8")
for u in ("/", "/saree-pre-pleating/", "/saree-draping/", "/faq"):
    check(SITE + u in ll, f"llms.txt links {SITE}{u}", False)
check(all(f"₹{v}" in ll for v in PRICES.values()), "llms.txt has the three verified prices")

fails = [r for r in results if not r[0]]
for ok, crit, msg in results:
    print(("PASS " if ok else ("FAIL " if crit else "WARN ")) + msg)
crit_fail = [r for r in fails if r[1]]
print(f"\n{len(results) - len(fails)} passed, {len(crit_fail)} critical failures, {len(fails) - len(crit_fail)} warnings")
sys.exit(1 if crit_fail else 0)
