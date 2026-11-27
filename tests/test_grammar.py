import pytest

from kes.core.common import validate
from kes.core.grammar import load_grammar
from kes.core.script_generator import ParseError, generate


def test_grammar_curriculum_has_10_units():
    g = load_grammar()
    assert len(g["units"]) >= 10
    assert g["units"][0]["id"] == "G1"


def test_generate_grammar_episode():
    ep = generate("做语法第 1 集")
    validate(ep, "episode")
    assert ep["theme"] == "grammar"
    assert ep["words"][0]["card_en"] == "an apple"
    for i in range(len(ep["words"])):
        en = [c for c in ep["cues"] if c["word_index"] == i and c["section"] == "word" and c["lang"] == "en"]
        assert len(en) >= 3
    assert any(c["section"] == "review" and c["repeat_prompt"] for c in ep["cues"])


def test_all_10_grammar_episodes_valid():
    for i in range(1, 11):
        ep = generate(f"做语法第 {i} 集")
        validate(ep, "episode")


def test_invalid_grammar_episode():
    with pytest.raises(ParseError):
        generate("做语法第 99 集")
