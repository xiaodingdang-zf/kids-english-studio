"""一句话 → episode.json。

确定性解析（主题 / 词数 / 时长 / 角色 / 画幅 / 指定单词），按固定教学结构生成台词：
引入 → 每个单词出现 3 次（含跟读停顿）→ 复习 → 结尾。
未识别的必要字段直接报错，不瞎猜。实测时长由音频步骤的 audio_timeline.json 给出。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .wordbank import CHARACTERS, THEMES

CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

DEFAULT_WORDS = 5
DEFAULT_DURATION = 60
MIN_WORDS, MAX_WORDS = 3, 8
MIN_DURATION, MAX_DURATION = 20, 180

STYLE_KEYWORDS = {
    "clay": ("黏土", "粘土", "clay"),
    "felt": ("羊毛毡", "毛毡", "felt"),
    "papercraft": ("纸艺", "剪纸", "纸雕", "papercraft", "paper"),
    "tin": ("铁皮", "发条", "tin"),
    "cardboard": ("纸箱", "纸板", "cardboard"),
    "wood": ("木偶", "木雕", "wood", "wooden"),
    "crochet": ("钩织", "毛线", "针织", "crochet"),
    "fabric": ("拼布", "布偶", "布艺", "fabric"),
}


def _detect_style(prompt: str) -> tuple[str, bool]:
    low = prompt.lower()
    for sid, kws in STYLE_KEYWORDS.items():
        if any(k in low for k in kws):
            return sid, True
    return "clay", False
ZH_MS_PER_CHAR = 240
EN_MS_PER_WORD = 520
EN_MS_BASE = 250
CUE_GAP_MS = 250


class ParseError(ValueError):
    """一句话里缺少或无法识别必要信息。"""


@dataclass
class Request:
    theme: str
    n_words: int
    duration_sec: int
    character: str
    aspect: str
    words: list[str] | None = None
    style: str = "clay"
    curriculum_key: str | None = None
    story: bool = True


DEFAULT_OPTIONS = {
    "narration": "bilingual", "en_voice": "a", "opening_closing": True,
}

STORY_SCENES = {
    "colors": ("奥利的彩虹画少了几道颜色，我们来帮他补上！", "彩虹画完成啦！"),
    "numbers": ("奥利要走过小石桥，得数清每一步！", "奥利数着石头，安全过桥啦！"),
    "animals": ("奥利发现一串脚印，想找到沿路的小伙伴！", "奥利找到小伙伴，大家一起玩啦！"),
    "fruits": ("奥利想准备野餐，篮子里还缺水果！", "野餐篮装好了，大家开动吧！"),
}


def _load_curriculum(level: str = "level1") -> dict:
    """Load curriculum data from curriculum/{level}.json."""
    p = Path(__file__).parent.parent.parent / "curriculum" / f"{level}.json"
    if not p.exists():
        raise ParseError(f"课程文件不存在：{p}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_curriculum_episode(unit_index: int, episode_index: int, level: str = "level1") -> dict:
    """Get episode words and sentence from curriculum."""
    curr = _load_curriculum(level)
    if unit_index < 1 or unit_index > len(curr["units"]):
        raise ParseError(f"单元号 {unit_index} 超出范围（1–{len(curr['units'])}）")
    unit = curr["units"][unit_index - 1]
    if episode_index < 1 or episode_index > len(unit["episodes"]):
        raise ParseError(f"集号 {episode_index} 超出范围（1–{len(unit['episodes'])}）")
    ep = unit["episodes"][episode_index - 1]
    return {
        "unit_id": unit["unit_id"],
        "unit_title_zh": unit["title_zh"],
        "unit_title_en": unit["title_en"],
        "words": ep["words"],
        "sentence": ep["sentence"],
    }


def _num(token: str) -> int:
    if token.isdigit():
        return int(token)
    if token in CN_NUM:
        return CN_NUM[token]
    if len(token) == 2 and token[0] == "十" and token[1] in CN_NUM:
        return 10 + CN_NUM[token[1]]
    raise ParseError(f"无法识别数字：{token}")


def parse_prompt(prompt: str) -> Request:
    text = prompt.strip()
    if not text:
        raise ParseError("输入为空。示例：做一集 60 秒的幼儿英语：颜色，5 个词，奥利主演")
    low = text.lower()

    # Check for curriculum-based prompt: "做 Level 1 第 3 单元第 2 集"
    curriculum_key = None
    unit_idx = None
    episode_idx = None

    m_full = re.search(r"(?:level|Level)\s*([0-9])\s*(?:第|第)\s*([0-9]+)\s*(?:单元|單元)\s*(?:第|第)\s*([0-9]+)\s*集", low)
    if m_full:
        level_num = int(m_full.group(1))
        unit_idx = int(m_full.group(2))
        episode_idx = int(m_full.group(3))
        level = f"level{level_num}"
        curriculum_key = f"{level}_{unit_idx}_{episode_idx}"
        try:
            ep_data = _get_curriculum_episode(unit_idx, episode_idx, level)
        except ParseError as e:
            raise e
        curr_duration_match = re.search(r"(\d+)\s*(?:秒|s\b|sec)", low)
        curr_duration = int(curr_duration_match.group(1)) if curr_duration_match else DEFAULT_DURATION
        if not MIN_DURATION <= curr_duration <= MAX_DURATION:
            raise ParseError(f"时长 {curr_duration} 秒超出支持范围 {MIN_DURATION}–{MAX_DURATION} 秒")
        # Return a special request that will be processed by build_episode_from_curriculum
        return Request(
            theme="curriculum",
            n_words=len(ep_data["words"]),
            duration_sec=curr_duration,
            character="ollie",
            aspect="square" if "方形" in text or "square" in low else
                   "landscape" if "横屏" in text or "landscape" in low else "portrait",
            words=ep_data["words"],
            style=_detect_style(text)[0],
            curriculum_key=curriculum_key,
        )

    theme = None
    # Prioritize built-in themes (colors, numbers, animals, fruits) over curriculum themes
    builtin_themes = ["colors", "numbers", "animals", "fruits"]
    for key in builtin_themes:
        if key in THEMES and any(k in low for k in THEMES[key]["keywords"]):
            theme = key
            break
    # If no builtin theme found, check curriculum themes
    if theme is None:
        for key, spec in THEMES.items():
            if key not in builtin_themes and any(k in low for k in spec["keywords"]):
                theme = key
                break
    if theme is None:
        names = "、".join(f"{v['zh']}({k})" for k, v in THEMES.items())
        raise ParseError(f"没有识别到主题。目前支持：{names}")

    duration = DEFAULT_DURATION
    m = re.search(r"(\d+)\s*(?:秒|s\b|sec)", low)
    m2 = re.search(r"(\d+|[一两二三四五六七八九十])\s*分(?:钟)?(?:半)?", text)
    if m:
        duration = int(m.group(1))
    elif m2:
        duration = _num(m2.group(1)) * 60 + (30 if "半" in m2.group(0) else 0)
    if not MIN_DURATION <= duration <= MAX_DURATION:
        raise ParseError(f"时长 {duration} 秒超出支持范围 {MIN_DURATION}–{MAX_DURATION} 秒")

    words = None
    mw = re.search(r"(?:单词|词汇|词)\s*[:：]\s*([A-Za-z ,，、/]+)", text)
    if mw:
        words = [w.strip().lower() for w in re.split(r"[ ,，、/]+", mw.group(1)) if w.strip()]
        bank = {w["en"] for w in THEMES[theme]["words"]}
        unknown = [w for w in words if w not in bank]
        if unknown:
            raise ParseError(f"这些词不在「{THEMES[theme]['zh']}」词库里：{', '.join(unknown)}")

    n_words = len(words) if words else DEFAULT_WORDS
    mn = re.search(r"(\d+|十[一二三四五六七八九]?|[一两二三四五六七八九十])\s*个?\s*(?:单词|词|word)", text)
    if mn and not words:
        n_words = _num(mn.group(1))
    if not MIN_WORDS <= n_words <= MAX_WORDS:
        raise ParseError(f"词数 {n_words} 超出支持范围 {MIN_WORDS}–{MAX_WORDS}")
    if n_words > len(THEMES[theme]["words"]):
        raise ParseError("词库里的词不够")

    character = "ollie"
    for key, spec in CHARACTERS.items():
        if any(k in low for k in spec["keywords"]):
            character = key

    aspect = "portrait"
    if "方形" in text or "square" in low or "正方形" in text:
        aspect = "square"
    elif "横屏" in text or "landscape" in low or "youtube" in low:
        aspect = "landscape"
    elif "竖屏" in text:
        aspect = "portrait"

    style = _detect_style(text)[0]
    story = True
    return Request(theme, n_words, duration, character, aspect, words, style, story=story)


def _estimate_ms(lang: str, text: str) -> int:
    if lang == "zh":
        chars = len(re.sub(r"[\s，。！？、：,.!?]", "", text))
        return chars * ZH_MS_PER_CHAR
    return EN_MS_BASE + len(text.split()) * EN_MS_PER_WORD


def build_episode_from_curriculum(unit_idx: int, episode_idx: int, prompt: str = "", level: str = "level1",
                                  options: dict | None = None) -> dict:
    """Build episode from curriculum data."""
    options = options or {}
    ep_data = _get_curriculum_episode(unit_idx, episode_idx, level)
    theme = "curriculum"
    char = CHARACTERS["ollie"]

    cues: list[dict] = []

    def cue(section, lang, text, pause, action="idle", word_index=None, card=False, repeat=False):
        cues.append({
            "cue_id": f"c{len(cues) + 1:03d}",
            "section": section,
            "lang": lang,
            "text": text,
            "pause_after_ms": pause,
            "action": action,
            "word_index": word_index,
            "show_card": card,
            "repeat_prompt": repeat,
        })

    # Build intro
    unit_title = ep_data["unit_title_zh"]
    if options.get("opening_closing", True):
        cue("intro", "zh", f"大家好，我是{char['zh']}！", 300, "wave")
        cue("intro", "zh", f"今天我们一起来学{unit_title}！", 200, "jump")
        cue("intro", "en", f"Let's learn {ep_data['unit_title_en']}!", 600, "clap")
    if options.get("story", True):
        cue("story", "zh", f"奥利在{unit_title}的路上遇到一个难题，要找齐线索！", 300, "point")

    # Build word cues
    words = ep_data["words"]
    for i, word in enumerate(words):
        # Find this word in wordbank to get Chinese translation
        word_obj = None
        for theme_name, theme_spec in THEMES.items():
            for w in theme_spec["words"]:
                if w["en"] == word:
                    word_obj = w
                    break
            if word_obj:
                break

        if not word_obj:
            raise ParseError(f"词 '{word}' 在词库中找不到")

        word_cap = word.capitalize()
        if options.get("story", True):
            cue("story", "zh", f"第{i + 1}条线索是{word_obj['zh']}，奥利继续向前！", 250, "point", i)
        cue("word", "zh", f"看！这是什么？", 500, "point", i)
        cue("word", "en", f"{word_cap}!", 300, "point", i, card=True)
        cue("word", "zh", f"{word_obj['zh']}，{word}。", 300, "nod", i, card=True)
        cue("word", "zh", "跟我念！", 150, "listen", i, card=True)
        cue("word", "en", f"{word_cap}.", 1800, "listen", i, card=True, repeat=True)
        cue("word", "en", f"{word_cap}! Good job!", 700, "clap", i, card=True)

    # Add review section with cumulative words from earlier episodes
    cue("review", "zh", "我们来复习一下！", 400, "jump")
    for i, word in enumerate(words):
        cue("review", "en", f"{word.capitalize()}!", 1300, "point", i, card=True, repeat=True)

    if options.get("story", True):
        cue("story", "zh", "线索找齐了，奥利解决了难题！", 300, "clap")
    if options.get("opening_closing", True):
        cue("outro", "zh", "你真棒！我们下次见！", 300, "wave")
        cue("outro", "en", "Bye-bye!", 800, "wave")

    if options.get("narration") == "english":
        for c in cues:
            if c["lang"] == "zh" and c["section"] == "story":
                c["lang"] = "en"
                c["text"] = f"A clue: {words[c['word_index']]}!" if c["word_index"] is not None else "Ollie finds the clues!"
        cues = [c for c in cues if c["lang"] == "en"]
        for i, c in enumerate(cues, 1):
            c["cue_id"] = f"c{i:03d}"

    _fit_pauses(cues, options.get("duration_sec", DEFAULT_DURATION) * 1000)

    slug = "-".join(words[:3])
    return {
        "schema_version": "1.0",
        "episode_id": f"ep_{level}_u{unit_idx:02d}e{episode_idx}_{slug}"
                      + (f"_{options['style']}" if options.get("style", "clay") != "clay" else "")
                      + ("_story" if options.get("story", True) else "")
                      + ("_square" if options.get("aspect") == "square" else "")
                      + (f"_{options['duration_sec']}s" if options.get("duration_sec", DEFAULT_DURATION) != DEFAULT_DURATION else "")
                      + ("_en" if options.get("narration") == "english" else "")
                      + ("_voice_b" if options.get("en_voice") == "b" else "")
                      + ("_no_open" if not options.get("opening_closing", True) else ""),
        "prompt": prompt,
        "theme": "curriculum",
        "theme_zh": unit_title,
        "theme_en": ep_data["unit_title_en"],
        "character": "ollie",
        "aspect": options.get("aspect", "portrait"),
        "style": options.get("style", "clay"),
        "target_duration_sec": options.get("duration_sec", DEFAULT_DURATION),
        "words": [{"en": w, "zh": next((wo["zh"] for t in THEMES.values() for wo in t["words"] if wo["en"] == w), "")} for w in words],
        "cues": cues,
        "options": {"style": options.get("style", "clay"), "duration_sec": options.get("duration_sec", DEFAULT_DURATION),
                    "aspect": options.get("aspect", "portrait"), "narration": options.get("narration", "bilingual"),
                    "en_voice": options.get("en_voice", "a"), "opening_closing": options.get("opening_closing", True),
                    "story": options.get("story", True)},
    }


def build_episode(req: Request, prompt: str = "", options: dict | None = None) -> dict:
    options = options or {}
    theme = THEMES[req.theme]
    char = CHARACTERS[req.character]
    bank = theme["words"]
    if req.words:
        chosen = [next(w for w in bank if w["en"] == en) for en in req.words]
    else:
        chosen = bank[: req.n_words]

    cues: list[dict] = []

    def cue(section, lang, text, pause, action="idle", word_index=None, card=False, repeat=False):
        cues.append({
            "cue_id": f"c{len(cues) + 1:03d}",
            "section": section,
            "lang": lang,
            "text": text,
            "pause_after_ms": pause,
            "action": action,
            "word_index": word_index,
            "show_card": card,
            "repeat_prompt": repeat,
        })

    if options.get("opening_closing", True):
        cue("intro", "zh", f"大家好，我是{char['zh']}！", 300, "wave")
        cue("intro", "zh", f"今天我们一起来学{theme['zh']}！", 200, "jump")
        cue("intro", "en", f"Let's learn {theme['en']}!", 600, "clap")

    if req.story:
        opening, closing = STORY_SCENES.get(req.theme, (
            f"奥利遇到一个难题，需要用{theme['zh']}找到线索！", "奥利解决了难题，开心地笑了！"))
        cue("story", "zh", opening, 300, "point")

    for i, w in enumerate(chosen):
        word = w["en"].capitalize()
        if req.story:
            cue("story", "zh", f"第{i + 1}条线索出现了：{w['zh']}！奥利又向前一步。", 250, "point", i)
        cue("word", "zh", f"看！{theme['question_zh']}？", 500, "point", i)
        cue("word", "en", f"{word}!", 300, "point", i, card=True)
        cue("word", "zh", f"{w['zh']}，{w['en']}。", 300, "nod", i, card=True)
        cue("word", "zh", "跟我念！", 150, "listen", i, card=True)
        cue("word", "en", f"{word}.", 1800, "listen", i, card=True, repeat=True)
        cue("word", "en", f"{word}! Good job!", 700, "clap", i, card=True)

    cue("review", "zh", "我们来复习一下！", 400, "jump")
    for i, w in enumerate(chosen):
        cue("review", "en", f"{w['en'].capitalize()}!", 1300, "point", i, card=True, repeat=True)
    if req.story:
        cue("story", "zh", closing, 300, "clap")
    if options.get("opening_closing", True):
        cue("outro", "zh", "你真棒！我们下次见！", 300, "wave")
        cue("outro", "en", "Bye-bye!", 800, "wave")

    if options.get("narration") == "english":
        # Preserve word practice/review structure while using English-only speech.
        english_story = {"colors": "Ollie's rainbow needs colors!", "numbers": "Ollie counts the stepping stones!",
                         "animals": "Ollie follows the animal footprints!", "fruits": "Ollie fills the picnic basket!"}
        for c in cues:
            if c["lang"] == "zh" and c["section"] == "story":
                c["lang"] = "en"
                c["text"] = english_story.get(req.theme, "Ollie finds a clue!") if c["word_index"] is None else f"A clue: {chosen[c['word_index']]['en']}!"
        cues = [c for c in cues if c["lang"] == "en"]
        for i, c in enumerate(cues, 1):
            c["cue_id"] = f"c{i:03d}"

    _fit_pauses(cues, req.duration_sec * 1000)

    slug = "-".join(w["en"] for w in chosen[:3])
    ep_id_suffix = ""
    if req.style != "clay":
        ep_id_suffix += f"_{req.style}"
    if req.story:
        ep_id_suffix += "_story"
    if req.aspect == "square":
        ep_id_suffix += "_square"
    if req.duration_sec != DEFAULT_DURATION:
        ep_id_suffix += f"_{req.duration_sec}s"
    if options.get("narration") == "english":
        ep_id_suffix += "_en"
    if options.get("en_voice") == "b":
        ep_id_suffix += "_voice_b"
    if not options.get("opening_closing", True):
        ep_id_suffix += "_no_open"

    ep = {
        "schema_version": "1.0",
        "episode_id": f"ep_{req.theme}_{slug}" + ep_id_suffix,
        "prompt": prompt,
        "theme": req.theme,
        "theme_zh": theme["zh"],
        "theme_en": theme["en"],
        "character": req.character,
        "aspect": req.aspect,
        "style": req.style,
        "target_duration_sec": req.duration_sec,
        "words": [dict(w) for w in chosen],
        "cues": cues,
        "options": {"style": req.style, "duration_sec": req.duration_sec, "aspect": req.aspect,
                    "narration": options.get("narration", "bilingual"), "en_voice": options.get("en_voice", "a"),
                    "opening_closing": options.get("opening_closing", True), "story": req.story},
    }

    return ep


def estimate_total_ms(cues: list[dict]) -> int:
    head, tail = 500, 800
    return head + tail + sum(_estimate_ms(c["lang"], c["text"]) + CUE_GAP_MS + c["pause_after_ms"] for c in cues)


def _fit_pauses(cues: list[dict], target_ms: int) -> None:
    """按目标时长等比缩放停顿（0.6–2.5 倍），跟读停顿不低于 1200ms。"""
    speech = estimate_total_ms([{**c, "pause_after_ms": 0} for c in cues])
    pauses = sum(c["pause_after_ms"] for c in cues)
    if pauses <= 0:
        return
    factor = max(0.6, min(2.5, (target_ms - speech) / pauses))
    for c in cues:
        p = int(round(c["pause_after_ms"] * factor / 50) * 50)
        if c["repeat_prompt"]:
            p = max(p, 1200)
        c["pause_after_ms"] = max(100, p)


def ask_questions(prompt: str) -> dict:
    """返回可直接解析的 JSON 问卷；选项第一个即默认值。"""
    req = parse_prompt(prompt)
    low = prompt.lower()
    explicit = {
        "style": _detect_style(prompt)[1],
        "duration_sec": bool(re.search(r"\d+\s*(?:秒|s\b|sec|分钟|分)|[一两二三四五六七八九十]+\s*分", low)),
        "aspect": any(x in low for x in ("竖", "横", "方形", "square", "portrait", "landscape")),
        "narration": any(x in low for x in ("纯英", "全英", "中英", "双语", "english only")),
        "en_voice": any(x in low for x in ("小何", "母语", "音色a", "音色b", "音色 a", "音色 b")),
        "opening_closing": any(x in low for x in ("片头片尾", "片头和片尾", "无片头", "无片尾")),
    }
    choices = [
        ("style", "风格", [
            "clay（黏土）", "felt（羊毛毡）", "papercraft（纸艺立体）", "tin（铁皮玩具）",
            "cardboard（纸箱涂鸦）", "wood（木偶雕刻）", "crochet（钩织玩偶）", "fabric（布偶拼布）",
        ], req.style),
        ("duration_sec", "时长", ["60 秒", "30 秒", "90 秒", "120 秒"], req.duration_sec),
        ("aspect", "画幅", ["竖屏", "横屏", "方形"], req.aspect),
        ("narration", "旁白", ["中英双语", "纯英文"], "english" if any(x in low for x in ("纯英", "全英", "english only")) else "bilingual"),
        ("en_voice", "英文音色", ["A（小何）", "B（母语）"], "b" if any(x in low for x in ("母语", "音色b", "音色 b")) else "a"),
        ("opening_closing", "片头片尾", ["有", "无"], not any(x in low for x in ("无片头", "无片尾", "片头片尾无"))),
    ]
    parsed = {"theme": req.theme, "character": req.character, "n_words": req.n_words,
              "story": req.story}
    questions, defaults = [], {}
    for key, title, labels, value in choices:
        parsed[key] = value
        if not explicit[key]:
            questions.append({"id": key, "question": title, "options": labels, "default": labels[0]})
            defaults[key] = value
    return {"parsed": parsed, "questions": questions, "defaults": defaults,
            "hint": "回复‘全部默认’，或用 --answers 传入 JSON 对象"}


def _normalize_answers(answers: dict | str | None) -> dict:
    if answers is None or answers in ("全部默认", "all"):
        return {}
    if isinstance(answers, str):
        try:
            answers = json.loads(answers)
        except json.JSONDecodeError as e:
            raise ParseError(f"--answers 需要 JSON 对象或‘全部默认’：{e}") from e
    if not isinstance(answers, dict):
        raise ParseError("--answers 需要 JSON 对象")
    allowed = {"style": tuple(STYLE_KEYWORDS), "duration_sec": (30, 60, 90, 120),
               "aspect": ("portrait", "landscape", "square"), "narration": ("bilingual", "english"),
               "en_voice": ("a", "b"), "opening_closing": (True, False), "story": (True, False)}
    for key, value in answers.items():
        if key not in allowed or value not in allowed[key] or (isinstance(value, bool) and key == "duration_sec"):
            raise ParseError(f"无效问卷答案：{key}={value!r}")
    return answers


def generate(prompt: str, answers: dict | str | None = None) -> dict:
    req = parse_prompt(prompt)
    answers = _normalize_answers(answers)
    req.style = answers.get("style", req.style)
    req.duration_sec = answers.get("duration_sec", req.duration_sec)
    req.aspect = answers.get("aspect", req.aspect)
    req.story = answers.get("story", req.story)
    options = dict(DEFAULT_OPTIONS)
    prompt_low = prompt.lower()
    if "纯英" in prompt_low or "全英" in prompt_low or "english only" in prompt_low:
        options["narration"] = "english"
    if "母语" in prompt_low or "音色b" in prompt_low or "音色 b" in prompt_low:
        options["en_voice"] = "b"
    if "无片头" in prompt_low or "无片尾" in prompt_low:
        options["opening_closing"] = False
    options.update(answers)
    if req.theme == "curriculum":
        # Extract unit and episode index from curriculum_key
        parts = req.curriculum_key.split("_")
        unit_idx = int(parts[1])
        episode_idx = int(parts[2])
        return build_episode_from_curriculum(unit_idx, episode_idx, prompt,
                                             options={"style": req.style, "duration_sec": req.duration_sec,
                                                      "aspect": req.aspect, **options,
                                                      "story": req.story})
    return build_episode(req, prompt, options)
