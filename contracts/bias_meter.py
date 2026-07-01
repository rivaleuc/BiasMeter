# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
BiasMeter — labels the political lean of a news article by GenLayer validator consensus.

Anyone can `submit_article(headline, body, source)`; the article sits in state
`open`. `rate` then has every validator independently read the headline + body and
classify the political lean as left / center / right. The label is accepted only
when validators AGREE on the lean enum (comparative equivalence on `lean`), not on
the confidence number or the wording of the reasoning. Confidence and reasoning are
advisory; the lean is the consensus output.

The decisive field is the `lean` enum — a qualitative, natural-language judgement
that no deterministic EVM could reproduce, made reproducible by validator consensus.
"""
import json
from genlayer import *

LEANS = ("left", "center", "right")
MAX_HEADLINE = 300
MAX_BODY = 4000
MAX_SOURCE = 200
MAX_REASONING = 600


def normalize_rating(raw) -> dict:
    """Coerce any LLM output into a valid rating. Never raises; `{}` -> safe default."""
    if not isinstance(raw, dict):
        raw = {}
    lean = str(raw.get("lean", "")).strip().lower()
    if lean not in LEANS:
        lean = "center"                 # conservative default when unclear
    reasoning = raw.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        reasoning = "no reasoning"
    return {
        "lean": lean,
        "confidence": _confidence(raw.get("confidence")),
        "reasoning": reasoning.strip()[:MAX_REASONING],
    }


def _confidence(v) -> int:
    """Clamp a confidence value to an int in [0, 100]; anything unusable -> 0."""
    if isinstance(v, bool):
        return 0
    if isinstance(v, int):
        return max(0, min(100, v))
    if isinstance(v, float):
        return max(0, min(100, int(v)))
    if isinstance(v, str):
        try:
            return max(0, min(100, int(float(v.strip()))))
        except Exception:
            return 0
    return 0


def validate_rating(data) -> bool:
    """Enforce the invariants: lean in enum, confidence int 0-100, non-empty reasoning."""
    if not isinstance(data, dict):
        return False
    if data.get("lean") not in LEANS:
        return False
    c = data.get("confidence")
    if not isinstance(c, int) or isinstance(c, bool) or c < 0 or c > 100:
        return False
    r = data.get("reasoning")
    return isinstance(r, str) and bool(r.strip())


class BiasMeter(gl.Contract):
    articles: TreeMap[str, str]
    article_count: u256
    rated_count: u256

    def __init__(self):
        self.article_count = u256(0)
        self.rated_count = u256(0)

    # ----------------------------------------------------------- submit
    @gl.public.write
    def submit_article(self, headline: str, body: str, source: str) -> str:
        headline = str(headline).strip()
        body = str(body).strip()
        source = str(source).strip()
        if not headline or not body:
            raise Exception("headline and body are required")
        if not source:
            raise Exception("source is required")
        key = str(int(self.article_count))
        rec = {
            "submitter": str(gl.message.sender_address),
            "headline": headline[:MAX_HEADLINE],
            "body": body[:MAX_BODY],
            "source": source[:MAX_SOURCE],
            "state": "open",            # open -> rated
            "lean": "",
            "confidence": 0,
            "reasoning": "",
        }
        self.articles[key] = json.dumps(rec)
        self.article_count += u256(1)
        return key

    # ----------------------------------------------------------- rate
    @gl.public.write
    def rate(self, article_id: str) -> dict:
        """Consensus reads the article and labels its political lean."""
        article_id = str(article_id)
        if article_id not in self.articles:
            raise Exception("unknown article")
        a = json.loads(self.articles[article_id])
        if a["state"] != "open":
            raise Exception("article already rated")

        rating = self._rate(a["headline"], a["body"])
        a["lean"] = rating["lean"]
        a["confidence"] = rating["confidence"]
        a["reasoning"] = rating["reasoning"]
        a["state"] = "rated"
        self.articles[article_id] = json.dumps(a)
        self.rated_count += u256(1)
        return {"article": article_id, "lean": rating["lean"], "confidence": rating["confidence"]}

    def _rate(self, headline: str, body: str) -> dict:
        def do_rate() -> str:
            prompt = f"""You are a neutral media-bias analyst. Read the news article below and classify its political lean.

HEADLINE: {headline}

BODY:
{body}

Judge the lean of the article's framing and language — not whether its claims are true.
"left" = favors progressive / left-of-center framing, "right" = favors conservative / right-of-center
framing, "center" = balanced or no discernible lean.
Reply ONLY JSON: {{"lean":"left|center|right","confidence":<int 0-100>,"reasoning":"<short>"}}"""
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            return json.dumps(normalize_rating(raw))

        result = gl.eq_principle.prompt_comparative(
            do_rate,
            principle="The 'lean' enum (left / center / right) must be identical across validators; confidence and reasoning wording may differ.",
        )
        data = json.loads(result) if isinstance(result, str) else result
        if not validate_rating(data):
            data = normalize_rating(data if isinstance(data, dict) else {})
        return data

    # ----------------------------------------------------------- views
    @gl.public.view
    def get_article(self, article_id: str) -> dict:
        article_id = str(article_id)
        if article_id not in self.articles:
            return {"exists": False}
        a = json.loads(self.articles[article_id])
        a["exists"] = True
        return a

    @gl.public.view
    def stats(self) -> dict:
        return {"total_articles": int(self.article_count), "rated": int(self.rated_count)}
