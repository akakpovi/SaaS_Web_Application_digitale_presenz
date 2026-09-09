from __future__ import annotations
import json
import re
import time
from typing import Any
from urllib.parse import urlparse
from core.security import SafeRequestSession


class SeoScanner:
    TITLE_MIN = 30
    TITLE_MAX = 60
    META_MIN = 120
    META_MAX = 160

    def __init__(self, domain: str):
        self.domain = domain.strip().lower().rstrip(".")
        self.base_url = f"https://{self.domain}"
        self._s = SafeRequestSession()

    def run(self) -> dict[str, Any]:
        try:
            html, url, code, ms, sz = self._fetch(self.base_url)
        except Exception as e:
            return {
                "status": "failed",
                "seo_score": 0.0,
                "error": str(e),
                "issues": [{"code": "FETCH_ERROR", "severity": "critical", "message": str(e)}],
                "warnings": [],
                "passed": [],
            }
        r: dict[str, Any] = {
            "status": "completed",
            "final_url": url,
            "status_code": code,
            "load_time_ms": ms,
            "page_size_bytes": sz,
            "issues": [],
            "warnings": [],
            "passed": [],
        }
        for p in [
            self._title(html),
            self._meta(html),
            self._canonical(html, url),
            self._robots(html),
            self._og(html),
            self._tc(html),
            self._headings(html),
            self._images(html),
            self._links(html, url),
            self._schema(html),
            self._indexable(html),
            self._sitemap(url),
            self._robotstxt(url),
        ]:
            r["issues"].extend(p.pop("_i", []))
            r["warnings"].extend(p.pop("_w", []))
            r["passed"].extend(p.pop("_p", []))
            r.update(p)
        r["seo_score"] = self._score(r)
        return r

    def _fetch(self, url: str):
        t = time.monotonic()
        resp = self._s.get(url, timeout=15, allow_redirects=True)
        ms = int((time.monotonic() - t) * 1000)
        return resp.text, str(resp.url), resp.status_code, ms, len(resp.content)

    def _title(self, html: str):
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        t = re.sub(r"\s+", " ", m.group(1).strip()) if m else ""
        n = len(t)
        i, w, p = [], [], []
        if not t:
            i.append({"code": "MISSING_TITLE", "severity": "critical", "message": "No title."})
        elif n < self.TITLE_MIN:
            w.append({"code": "TITLE_TOO_SHORT", "severity": "warning", "message": f"Title {n}ch."})
        elif n > self.TITLE_MAX:
            w.append({"code": "TITLE_TOO_LONG", "severity": "warning", "message": f"Title {n}ch."})
        else:
            p.append({"code": "TITLE_OK", "message": f"Title {n}ch."})
        return {"title": t, "title_length": n, "_i": i, "_w": w, "_p": p}

    def _meta(self, html: str):
        m = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']'
            r'|<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']description["\']',
            html,
            re.I,
        )
        d = ((m.group(1) or m.group(2) or "").strip()) if m else ""
        n = len(d)
        i, w, p = [], [], []
        if not d:
            i.append({"code": "MISSING_META_DESC", "severity": "high", "message": "No meta desc."})
        elif n < self.META_MIN:
            w.append({"code": "META_DESC_TOO_SHORT", "severity": "warning", "message": f"Meta {n}ch."})
        elif n > self.META_MAX:
            w.append({"code": "META_DESC_TOO_LONG", "severity": "warning", "message": f"Meta {n}ch."})
        else:
            p.append({"code": "META_DESC_OK", "message": f"Meta {n}ch."})
        return {"meta_description": d, "meta_description_length": n, "_i": i, "_w": w, "_p": p}

    def _canonical(self, html: str, url: str):
        m = re.search(
            r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']*)["\']'
            r'|<link[^>]+href=["\']([^"\']*)["\'][^>]+rel=["\']canonical["\']',
            html,
            re.I,
        )
        c = ((m.group(1) or m.group(2) or "").strip()) if m else ""
        has = bool(c)
        i = [] if has else [{"code": "MISSING_CANONICAL", "severity": "medium", "message": "No canonical."}]
        p = [{"code": "CANONICAL_OK", "message": "Canonical set."}] if has else []
        return {"has_canonical": has, "canonical_url": c, "_i": i, "_w": [], "_p": p}

    def _robots(self, html: str):
        m = re.search(
            r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)["\']'
            r'|<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']robots["\']',
            html,
            re.I,
        )
        v = ((m.group(1) or m.group(2) or "").lower()) if m else ""
        ni = "noindex" in v
        nf = "nofollow" in v
        i = [{"code": "NOINDEX_DETECTED", "severity": "critical", "message": "Noindex found."}] if ni else []
        p = [] if ni else [{"code": "INDEXABLE", "message": "Page indexable."}]
        return {"robots_meta": v, "noindex_detected": ni, "nofollow_detected": nf, "_i": i, "_w": [], "_p": p}

    def _og(self, html: str):
        def g(prop: str):
            m = re.search(rf'<meta[^>]+property=["\']og:{prop}["\'][^>]+content=["\']([^"\']*)["\']', html, re.I)
            return m.group(1).strip() if m else ""
        t, d, img, tp = g("title"), g("description"), g("image"), g("type")
        has = bool(t or d or img)
        w, p = [], []
        if not has:
            w.append({"code": "MISSING_OG", "severity": "warning", "message": "No OG tags."})
        else:
            if not img:
                w.append({"code": "MISSING_OG_IMAGE", "severity": "warning", "message": "No OG image."})
            p.append({"code": "OG_OK", "message": "OG tags present."})
        return {"og_title": t, "og_description": d, "og_image": img, "og_type": tp, "has_og": has, "_i": [], "_w": w, "_p": p}

    def _tc(self, html: str):
        def g(n: str):
            m = re.search(rf'<meta[^>]+name=["\']twitter:{n}["\'][^>]+content=["\']([^"\']*)["\']', html, re.I)
            return m.group(1).strip() if m else ""
        c, t = g("card"), g("title")
        has = bool(c)
        w = [] if has else [{"code": "MISSING_TWITTER_CARD", "severity": "info", "message": "No Twitter Card."}]
        p = [{"code": "TWITTER_CARD_OK", "message": "Twitter Card present."}] if has else []
        return {"twitter_card": c, "twitter_title": t, "has_twitter_card": has, "_i": [], "_w": w, "_p": p}

    def _headings(self, html: str):
        h1t = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        h1x = [re.sub(r"<[^>]+>", "", x).strip() for x in h1t]
        h1, h2, h3 = len(h1t), len(re.findall(r"<h2[^>]*>", html, re.I)), len(re.findall(r"<h3[^>]*>", html, re.I))
        i, w, p = [], [], []
        if h1 == 0:
            i.append({"code": "MISSING_H1", "severity": "high", "message": "No h1."})
        elif h1 > 1:
            w.append({"code": "MULTIPLE_H1", "severity": "warning", "message": f"{h1} h1 tags."})
        else:
            p.append({"code": "H1_OK", "message": "One h1."})
        if h2 == 0:
            w.append({"code": "MISSING_H2", "severity": "info", "message": "No h2."})
        else:
            p.append({"code": "HEADINGS_OK", "message": f"h2={h2} h3={h3}."})
        return {"h1_count": h1, "h1_texts": h1x, "h2_count": h2, "h3_count": h3, "_i": i, "_w": w, "_p": p}

    def _images(self, html: str):
        imgs = re.findall(r"<img[^>]*>", html, re.I)
        tot = len(imgs)
        na = sum(1 for x in imgs if not re.search(r'alt=["\'][^"\']+["\']', x))
        i, w, p = [], [], []
        if na > 0:
            bkt = i if na > 5 else w
            bkt.append({"code": "IMAGES_MISSING_ALT", "severity": "high" if na > 5 else "warning", "message": f"{na}/{tot} no alt."})
        elif tot > 0:
            p.append({"code": "IMAGES_ALT_OK", "message": f"All {tot} have alt."})
        return {"img_total": tot, "img_without_alt": na, "_i": i, "_w": w, "_p": p}

    def _links(self, html: str, url: str):
        base = urlparse(url)
        hrefs = re.findall(r'<a[^>]+href=["\']([^"\'#][^"\']*)["\']', html, re.I)
        inn = ext = 0
        for h in hrefs:
            if h.startswith(("http://", "https://")):
                if urlparse(h).netloc == base.netloc:
                    inn += 1
                else:
                    ext += 1
            elif not h.startswith(("mailto:", "tel:", "javascript:")):
                inn += 1
        w = [] if inn else [{"code": "NO_INTERNAL_LINKS", "severity": "warning", "message": "No internal links."}]
        p = [{"code": "LINKS_OK", "message": f"{inn} int, {ext} ext."}] if inn else []
        return {"internal_links": inn, "external_links": ext, "_i": [], "_w": w, "_p": p}

    def _schema(self, html: str):
        scripts = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I | re.S)
        types = []
        for raw in scripts:
            try:
                d = json.loads(raw)
                t = d.get("@type", "")
                types.extend(t if isinstance(t, list) else ([t] if t else []))
            except Exception:
                pass
        has = bool(types)
        w = [] if has else [{"code": "NO_STRUCTURED_DATA", "severity": "info", "message": "No JSON-LD."}]
        p = [{"code": "SCHEMA_OK", "message": f"Types: {','.join(set(types))}"}] if has else []
        return {"has_structured_data": has, "structured_data_types": types, "_i": [], "_w": w, "_p": p}

    def _indexable(self, html: str):
        ni = "noindex" in html.lower()
        nf = "nofollow" in html.lower()
        p = [{"code": "INDEXABLE", "message": "Page indexable."}] if not ni else []
        return {"is_indexable": not ni, "noindex_detected": ni, "nofollow_detected": nf, "_i": [], "_w": [], "_p": p}

    def _sitemap(self, url: str):
        p2 = urlparse(url)
        u = f"{p2.scheme}://{p2.netloc}/sitemap.xml"
        try:
            has = self._s.get(u, timeout=10).status_code == 200
        except Exception:
            has = False
            u = ""
        i = [] if has else [{"code": "MISSING_SITEMAP", "severity": "medium", "message": "No sitemap.xml."}]
        p = [{"code": "SITEMAP_OK", "message": "sitemap.xml found."}] if has else []
        return {"has_sitemap": has, "sitemap_url": u if has else "", "_i": i, "_w": [], "_p": p}

    def _robotstxt(self, url: str):
        p2 = urlparse(url)
        u = f"{p2.scheme}://{p2.netloc}/robots.txt"
        try:
            has = self._s.get(u, timeout=10).status_code == 200
        except Exception:
            has = False
        i = [] if has else [{"code": "MISSING_ROBOTS_TXT", "severity": "medium", "message": "No robots.txt."}]
        p = [{"code": "ROBOTS_TXT_OK", "message": "robots.txt found."}] if has else []
        return {"has_robots_txt": has, "_i": i, "_w": [], "_p": p}

    def _score(self, r: dict[str, Any]):
        W = {
            "MISSING_TITLE": 15, "TITLE_TOO_SHORT": 5, "TITLE_TOO_LONG": 5,
            "MISSING_META_DESC": 10, "META_DESC_TOO_SHORT": 4, "META_DESC_TOO_LONG": 4,
            "MISSING_CANONICAL": 8, "NOINDEX_DETECTED": 20, "MISSING_H1": 10,
            "MULTIPLE_H1": 4, "MISSING_SITEMAP": 8, "MISSING_ROBOTS_TXT": 5,
            "IMAGES_MISSING_ALT": 6, "MISSING_OG": 3, "MISSING_OG_IMAGE": 2,
        }
        codes = {x.get("code", "") for x in r.get("issues", []) + r.get("warnings", [])}
        return max(0.0, round(100.0 - sum(v for k, v in W.items() if k in codes), 1))
