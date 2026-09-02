import logging
from bs4 import BeautifulSoup
from core.security import safe_request

logger = logging.getLogger(__name__)

class TechnicalSEOScanner:
    def __init__(self, domain: str) -> None:
        self.domain = domain
        self.url = f"https://{domain}" if not domain.startswith("http") else domain
        self.issues = []

    def run(self) -> dict:
        res = {"meta_tags": {}, "robots_txt": "missing", "sitemap": "missing", "technical": 100, "content": 100, "mobile": 100}
        try:
            resp = safe_request(self.url, method="GET")
            html_text = resp.text if hasattr(resp, 'text') else resp.body.decode('utf-8', errors='ignore')
            if resp.status_code == 200:
                self._audit_html(html_text, res)
            else:
                self.issues.append({"severity": "critical", "message": f"Website returned HTTP {resp.status_code}"})
                res["technical"] -= 40
        except Exception as exc:
            self.issues.append({"severity": "critical", "message": f"Connection failed: {exc}"})
            res["technical"] = 0
            return res

        try:
            base_url = "/".join(self.url.split("/")[:3])
            robots_resp = safe_request(f"{base_url}/robots.txt", method="GET")
            r_text = robots_resp.text if hasattr(robots_resp, 'text') else robots_resp.body.decode('utf-8', errors='ignore')
            if robots_resp.status_code == 200:
                res["robots_txt"] = "valid"
                if "sitemap" in r_text.lower():
                    res["sitemap"] = "found_in_robots"
            else:
                res["robots_txt"] = "missing"
                res["technical"] -= 10
        except Exception:
            pass

        res["issues"] = self.issues
        return res

    def _audit_html(self, html: str, r: dict) -> None:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        r["meta_tags"]["title"] = title
        if not title:
            self.issues.append({"severity": "error", "message": "Missing <title> tag"})
            r["content"] -= 30
        elif len(title) > 60:
            self.issues.append({"severity": "warning", "message": "Title is too long (> 60 chars)"})
            r["content"] -= 10

        desc_tag = soup.find("meta", attrs={"name": "description"})
        desc = desc_tag.get("content", "").strip() if desc_tag else ""
        r["meta_tags"]["description"] = desc
        if not desc:
            self.issues.append({"severity": "error", "message": "Missing meta description"})
            r["content"] -= 30

        h1s = soup.find_all("h1")
        if not h1s:
            self.issues.append({"severity": "error", "message": "Missing <h1> tag"})
            r["content"] -= 15
        elif len(h1s) > 1:
            self.issues.append({"severity": "warning", "message": "Multiple <h1> tags detected"})
            r["content"] -= 5

        vp = soup.find("meta", attrs={"name": "viewport"})
        if not vp:
            self.issues.append({"severity": "error", "message": "Missing viewport meta tag for mobile"})
            r["mobile"] -= 50
