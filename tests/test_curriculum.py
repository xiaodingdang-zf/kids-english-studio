import pytest

from kes.core.common import validate
from kes.core.script_generator import ParseError, generate, parse_prompt, _get_curriculum_episode


def test_load_curriculum_episode():
    """Test loading curriculum episode data."""
    ep = _get_curriculum_episode(1, 1)
    assert ep["unit_id"] == "U1"
    assert ep["unit_title_zh"] == "问候与姓名"
    assert ep["unit_title_en"] == "Greetings & Names"
    assert len(ep["words"]) == 3
    assert ep["words"][0] == "hello"
    assert ep["sentence"] == "Hello, I'm ____."


def test_parse_curriculum_prompt():
    """Test parsing curriculum-based prompts."""
    # Test full format: Level 1 Unit 1 Episode 1
    r = parse_prompt("做 Level 1 第 1 单元第 1 集")
    assert r.theme == "curriculum"
    assert r.curriculum_key == "level1_1_1"

    # Test Level 1 Unit 3 Episode 2
    r = parse_prompt("做 Level 1 第 3 单元第 2 集")
    assert r.theme == "curriculum"
    assert r.curriculum_key == "level1_3_2"

    # Test Unit 8 Episode 4
    r = parse_prompt("做 Level 1 第 8 单元第 4 集")
    assert r.theme == "curriculum"
    assert r.curriculum_key == "level1_8_4"


def test_invalid_curriculum_prompts():
    """Test invalid curriculum prompts."""
    # Invalid unit number
    with pytest.raises(ParseError) as exc:
        parse_prompt("做 Level 1 第 9 单元第 1 集")
    assert "单元号 9 超出范围" in str(exc.value)

    # Invalid episode number
    with pytest.raises(ParseError) as exc:
        parse_prompt("做 Level 1 第 1 单元第 5 集")
    assert "集号 5 超出范围" in str(exc.value)


def test_generate_curriculum_episode():
    """Test generating curriculum episode."""
    ep = generate("做 Level 1 第 3 单元第 2 集")

    # Validate schema
    validate(ep, "episode")

    # Check episode structure
    assert ep["theme"] == "curriculum"
    assert ep["theme_zh"] == "身体部位"
    assert ep["theme_en"] == "Body"
    assert len(ep["words"]) == 3
    assert [w["en"] for w in ep["words"]] == ["eye", "ear", "nose"]

    # Check word structure
    for w in ep["words"]:
        assert "en" in w
        assert "zh" in w
        assert w["zh"]  # Non-empty Chinese translation

    # Check cue structure
    sections = [c["section"] for c in ep["cues"]]
    assert sections[0] == "intro"
    assert sections[-1] == "outro"
    assert "word" in sections
    assert "review" in sections

    # Check that all words appear at least 3 times in word section
    for i, w in enumerate(ep["words"]):
        en_cues = [c for c in ep["cues"] if c["word_index"] == i and c["section"] == "word" and c["lang"] == "en"]
        assert len(en_cues) >= 3
        # Check for repeat prompt with pause >= 1200ms
        assert any(c["repeat_prompt"] and c["pause_after_ms"] >= 1200 for c in en_cues)

    # Check episode ID format
    assert ep["episode_id"].startswith("ep_level1_u03e2_")


def test_curriculum_episode_different_units():
    """Test generating episodes from different units."""
    ep1 = generate("做 Level 1 第 1 单元第 1 集")
    assert [w["en"] for w in ep1["words"]] == ["hello", "hi", "goodbye"]

    ep2 = generate("做 Level 1 第 2 单元第 3 集")
    assert [w["en"] for w in ep2["words"]] == ["grandpa", "family", "love"]

    ep3 = generate("做 Level 1 第 5 单元第 2 集")
    assert [w["en"] for w in ep3["words"]] == ["book", "pen", "pencil"]


def test_curriculum_cue_structure():
    """Test that curriculum episodes have proper cue structure."""
    ep = generate("做 Level 1 第 1 单元第 2 集")

    # Check all cues have required fields
    for c in ep["cues"]:
        assert "cue_id" in c
        assert "section" in c
        assert "lang" in c
        assert "text" in c
        assert "pause_after_ms" in c
        assert "action" in c
        assert "word_index" in c or c["word_index"] is None
        assert "show_card" in c
        assert "repeat_prompt" in c

    # Check cue_id uniqueness
    cue_ids = [c["cue_id"] for c in ep["cues"]]
    assert len(cue_ids) == len(set(cue_ids))


def test_curriculum_backward_compatibility():
    """Test that original theme-based prompts still work."""
    # This should use the colors theme, not curriculum
    ep = generate("做一集 60 秒的幼儿英语：颜色，5 个词，奥利主演")
    assert ep["theme"] == "colors"
    assert len(ep["words"]) == 5
