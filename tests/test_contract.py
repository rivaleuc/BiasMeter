"""BiasMeter tests: rating normalize/validate guards + full submit -> rate flow."""

A = "0xAAa0000000000000000000000000000000000001"
B = "0xBBb0000000000000000000000000000000000002"


def test_normalize_rating(contract):
    n = contract.normalize_rating
    # good input passes through, lean lowercased
    assert n({"lean": "left", "confidence": 80, "reasoning": "clear framing"})["lean"] == "left"
    assert n({"lean": "RIGHT", "confidence": 60, "reasoning": "x"})["lean"] == "right"
    # bad / unknown lean -> conservative default 'center'
    assert n({"lean": "socialist", "confidence": 50, "reasoning": "x"})["lean"] == "center"
    assert n({})["lean"] == "center"
    assert n({})["confidence"] == 0
    # confidence clamping
    assert n({"lean": "left", "confidence": 999, "reasoning": "x"})["confidence"] == 100
    assert n({"lean": "left", "confidence": -5, "reasoning": "x"})["confidence"] == 0
    # numeric string / float confidence coerced then clamped
    assert n({"lean": "right", "confidence": "77", "reasoning": "x"})["confidence"] == 77
    assert n({"lean": "right", "confidence": 42.9, "reasoning": "x"})["confidence"] == 42
    # non-dict input never raises -> valid default
    assert n("garbage")["lean"] == "center"
    assert n(None)["confidence"] == 0
    assert n(123)["reasoning"] == "no reasoning"
    # empty / non-string reasoning -> default
    assert n({"lean": "left", "confidence": 10, "reasoning": "   "})["reasoning"] == "no reasoning"


def test_validate_rating(contract):
    v = contract.validate_rating
    assert v({"lean": "center", "confidence": 50, "reasoning": "balanced"})
    assert v({"lean": "left", "confidence": 0, "reasoning": "x"})
    assert v({"lean": "right", "confidence": 100, "reasoning": "x"})
    # bad lean
    assert not v({"lean": "blue", "confidence": 50, "reasoning": "x"})
    # confidence not an int
    assert not v({"lean": "left", "confidence": "50", "reasoning": "x"})
    # bool is not a valid confidence
    assert not v({"lean": "left", "confidence": True, "reasoning": "x"})
    # out of range
    assert not v({"lean": "left", "confidence": 101, "reasoning": "x"})
    assert not v({"lean": "left", "confidence": -1, "reasoning": "x"})
    # empty reasoning
    assert not v({"lean": "left", "confidence": 50, "reasoning": "  "})
    # non-dict
    assert not v("nope")
    assert not v(None)


def _new(contract):
    return contract, contract.BiasMeter()


def test_submit_requires_fields(contract):
    mod, c = _new(contract)
    mod.gl.message.sender_address = A
    for bad in (("", "body", "src"), ("head", "", "src"), ("head", "body", "")):
        try:
            c.submit_article(*bad)
            assert False, "empty field should be rejected"
        except Exception:
            pass


def test_missing_article_view(contract):
    mod, c = _new(contract)
    assert c.get_article("999") == {"exists": False}


def test_full_flow(contract):
    mod, c = _new(contract)
    mod.gl.message.sender_address = A
    aid = c.submit_article(
        "Senate passes sweeping climate bill",
        "Lawmakers approved a landmark package expanding clean-energy subsidies amid partisan debate.",
        "example-news.com",
    )
    # freshly submitted -> open, no lean yet
    art = c.get_article(aid)
    assert art["exists"] is True
    assert art["state"] == "open"
    assert art["lean"] == ""
    assert art["submitter"] == A

    # rate: consensus (shim) returns the normalized default
    mod.gl.message.sender_address = B
    out = c.rate(aid)
    assert out["lean"] in ("left", "center", "right")
    assert 0 <= out["confidence"] <= 100

    art = c.get_article(aid)
    assert art["state"] == "rated"
    assert art["lean"] in ("left", "center", "right")
    assert 0 <= art["confidence"] <= 100
    assert isinstance(art["reasoning"], str) and art["reasoning"]

    # cannot rate twice
    try:
        c.rate(aid)
        assert False, "already-rated article should be rejected"
    except Exception:
        pass

    # rating an unknown article is rejected
    try:
        c.rate("12345")
        assert False, "unknown article should be rejected"
    except Exception:
        pass

    st = c.stats()
    assert st["total_articles"] == 1 and st["rated"] == 1
    mod.gl.message.sender_address = A
