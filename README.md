# BiasMeter

**Labels the political lean of a news article by GenLayer validator consensus.**

[![GenLayer](https://img.shields.io/badge/GenLayer-Bradbury-ff4d6d)](https://genlayer.com) [![chainId](https://img.shields.io/badge/chainId-4221-4dd0e1)](https://docs.genlayer.com) [![contract](https://img.shields.io/badge/contract-Python%20GenVM-8a63d2)](https://docs.genlayer.com) [![tests](https://img.shields.io/badge/tests-5%2F5%20passing-3fb950)](tests) [![License](https://img.shields.io/badge/license-MIT-2dd4bf)](LICENSE)

Anyone can `submit_article(headline, body, source)`; the article sits in state `open`. `rate` then has
every validator independently read the headline + body and classify the political lean as **left /
center / right**. The label is accepted only when validators **agree on the lean enum** (comparative
equivalence on `lean`), not on the confidence number or the wording of the reasoning. Confidence and
reasoning are advisory; the lean is the consensus output.

- **Contract (Bradbury, chain 4221):** `DEPLOY_PENDING`
- **Explorer:** https://explorer-bradbury.genlayer.com/contract/DEPLOY_PENDING

---

## Why GenLayer is essential

Classifying the political lean of an article is qualitative judgement over natural language — there is no
formula, no oracle feed, and no way for a deterministic EVM to reproduce it. A single off-chain API call
would be an unverifiable black box. GenLayer instead has **every validator independently read the same
article** and accept a label only when they **agree on the lean enum**, turning a subjective media-bias
call into a reproducible, tamper-resistant on-chain outcome.

## Workflow

| Step | Method | What happens |
| --- | --- | --- |
| Submit | `submit_article(headline, body, source)` | Stores the article in state `open`; returns its id. |
| Rate | `rate(id)` | Consensus reads headline + body → `lean` (left / center / right) + confidence + reasoning; state → `rated`. |
| Read | `get_article(id)` | Full record: submitter, text, source, state, lean, confidence, reasoning. |
| Stats | `stats()` | `total_articles` and `rated` counters. |

### Correctness check

`_rate` wraps the local `do_rate` in **`gl.eq_principle.prompt_comparative`** with the principle
*"the 'lean' enum (left / center / right) must be identical across validators; confidence and reasoning
wording may differ."* This is the crux: validators catch a **wrong label** because they must converge on
the *decisive `lean` field* itself — not merely on the shape of the JSON. A validator that returns a
different lean breaks equivalence and the result is rejected. `validate_rating` enforces the invariants
(lean in enum, integer confidence in 0–100, non-empty reasoning) and `normalize_rating` maps any unclear
or malformed output to a conservative default (`center`, confidence `0`) so a degenerate response can
never corrupt state. State is guarded on-chain: an article can only be rated once, and unknown ids raise.

## Architecture

```
BiasMeter/
├── contracts/bias_meter.py   ← GenLayer Intelligent Contract (submit + consensus lean rating)
└── tests/                    ← pytest: normalize/validate guards + full submit → rate flow
```

Contract-only — **no frontend, no `app/` directory.** The contract is the whole product: storage
(`TreeMap[str, str]` + `u256` counters), deterministic helpers, and a consensus-backed `rate` method.

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install pytest -q
.venv/bin/python -m pytest tests -q
```

Covers `normalize_rating` / `validate_rating` on good and adversarial inputs (bad lean → `center`,
confidence `999` → `100`, `-5` → `0`, non-dict input) plus a full **submit → rate** integration run
asserting the state transition (`open` → `rated`) and that the finalized `lean` is within the enum and
`confidence` within `[0, 100]`. Under the test shim the consensus returns the normalized default.

## Deploy

```bash
genlayer deploy --contract contracts/bias_meter.py
```

After deployment, set `CONTRACT_ADDRESS` in `.env` (replace the `DEPLOY_PENDING` placeholder).
