import json

import pytest

from kes.core.common import validate
from kes.core.script_generator import ParseError, generate, parse_prompt, ask_questions

CASES = [
    ("做一集 60 秒的幼儿英语：颜色，5 个词，奥利主演", "colors", 5, 60, "portrait"),
    ("做一集90秒的数字儿歌，6个单词", "numbers", 6, 90, "portrait"),
    ("动物主题，三个词，1分钟，横屏", "animals", 3, 60, "landscape"),
    ("水果 fruits 8 words 120s", "fruits", 8, 120, "portrait"),
    ("一分半的颜色视频，四个词", "colors", 4, 90, "portrait"),
    ("颜色，单词：red, blue, green", "colors", 3, 60, "portrait"),
]


@pytest.mark.parametrize("prompt,theme,n,dur,aspect", CASES)
def test_parse(prompt, theme, n, dur, aspect):
    r = parse_prompt(prompt)
    assert (r.theme, r.n_words, r.duration_sec, r.aspect) == (theme, n, dur, aspect)


@pytest.mark.parametrize("prompt", ["做一集关于恐龙的视频", "", "颜色 20 个词", "颜色 5 秒", "颜色，单词：red, dinosaur"])
def test_invalid(prompt):
    with pytest.raises(ParseError):
        parse_prompt(prompt)


def test_episode_structure_and_schema():
    ep = generate("做一集 60 秒的幼儿英语：颜色，5 个词，奥利主演")
    validate(ep, "episode")
    assert [w["en"] for w in ep["words"]] == ["red", "blue", "yellow", "green", "orange"]
    sections = [c["section"] for c in ep["cues"]]
    assert sections[0] == "intro" and sections[-1] == "outro" and "review" in sections
    for i in range(5):
        en = [c for c in ep["cues"] if c["word_index"] == i and c["section"] == "word" and c["lang"] == "en"]
        assert len(en) >= 3
        assert any(c["repeat_prompt"] and c["pause_after_ms"] >= 1200 for c in en)
    assert len({c["cue_id"] for c in ep["cues"]}) == len(ep["cues"])


def test_explicit_words():
    ep = generate("颜色，单词：purple, pink, brown")
    assert [w["en"] for w in ep["words"]] == ["purple", "pink", "brown"]


def test_square_aspect():
    ep = generate("做一集方形的颜色")
    validate(ep, "episode")
    assert ep["aspect"] == "square"
    assert "square" in ep["episode_id"]


def test_story_mode():
    ep = generate("做一集故事化的颜色")
    validate(ep, "episode")
    assert ep.get("options", {}).get("story") is True
    assert "story" in ep["episode_id"]
    story_cues = [c for c in ep["cues"] if c["section"] == "story"]
    assert len(story_cues) > 0
    assert any("奥利" in c["text"] for c in story_cues)


def test_story_and_square_combined():
    ep = generate("做一集故事化的颜色，方形")
    validate(ep, "episode")
    assert ep["aspect"] == "square"
    assert ep.get("options", {}).get("story") is True
    assert "_story_square" in ep["episode_id"]


def test_ask_questions_basic():
    result = ask_questions("做一集动物")
    assert "parsed" in result
    assert "questions" in result
    assert "defaults" in result

    parsed = result["parsed"]
    assert parsed["theme"] == "animals"
    assert parsed["character"] == "ollie"
    assert parsed["duration_sec"] == 60
    assert parsed["n_words"] == 5
    assert parsed["aspect"] == "portrait"

    # Check that all questions have required fields
    for q in result["questions"]:
        assert "id" in q
        assert "question" in q
        assert "options" in q
        assert "default" in q
        assert isinstance(q["options"], list)
        assert len(q["options"]) > 0


def test_ask_questions_with_explicit_values():
    # When all fields are specified, should have fewer questions
    result = ask_questions("做一集 60 秒的羊毛毡风格动物，竖屏，3 个词")
    parsed = result["parsed"]
    assert parsed["duration_sec"] == 60
    assert parsed["style"] == "felt"
    assert parsed["aspect"] == "portrait"
    assert parsed["n_words"] == 3

    # Defaults should still be populated for unspecified fields
    assert "defaults" in result
    assert len(result["defaults"]) > 0


def test_ask_questions_story_recognized():
    result = ask_questions("做一集故事化的颜色")
    parsed = result["parsed"]
    assert parsed["story"] is True


def test_questions_defaults_first_and_cli_json(capsys):
    from kes.cli import main
    main(["questions", "做一集动物"])
    result = json.loads(capsys.readouterr().out)
    assert {q["id"] for q in result["questions"]} == {
        "style", "duration_sec", "aspect", "narration", "en_voice", "opening_closing"
    }
    assert all(q["options"][0] == q["default"] for q in result["questions"])
    assert result["parsed"]["story"] is True


def test_answers_change_script_and_are_saved():
    ep = generate("做一集动物", {"style": "felt", "duration_sec": 90, "aspect": "square",
                              "narration": "english", "en_voice": "b", "opening_closing": False})
    validate(ep, "episode")
    assert ep["options"] == {"style": "felt", "duration_sec": 90, "aspect": "square",
                             "narration": "english", "en_voice": "b", "opening_closing": False, "story": True}
    assert (ep["style"], ep["target_duration_sec"], ep["aspect"]) == ("felt", 90, "square")
    assert all(c["lang"] == "en" for c in ep["cues"])
    assert all(c["section"] not in ("intro", "outro") for c in ep["cues"])
    assert any(c["section"] == "story" for c in ep["cues"])
    for i in range(len(ep["words"])):
        practice = [c for c in ep["cues"] if c["section"] == "word" and c["word_index"] == i]
        assert len(practice) >= 3
        assert any(c["repeat_prompt"] and c["pause_after_ms"] >= 1200 for c in practice)


def test_all_defaults_and_invalid_answers():
    assert generate("做一集动物", "全部默认")["options"]["story"] is True
    with pytest.raises(ParseError, match="无效问卷答案"):
        generate("做一集动物", {"duration_sec": 17})


def test_story_is_specific_problem_and_resolution():
    ep = generate("做一集动物")
    story = [c["text"] for c in ep["cues"] if c["section"] == "story"]
    assert "脚印" in story[0]
    assert "小伙伴" in story[-1]
    assert len(story) == len(ep["words"]) + 2


def test_curriculum_explicit_square_and_answers():
    ep = generate("做 Level 1 第 8 单元第 4 集，方形", {"narration": "english"})
    validate(ep, "episode")
    assert ep["aspect"] == "square"
    assert ep["options"]["narration"] == "english"
    assert all(c["lang"] == "en" for c in ep["cues"])
    assert any(c["section"] == "story" for c in ep["cues"])
