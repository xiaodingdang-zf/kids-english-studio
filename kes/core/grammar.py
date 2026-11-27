"""小学语法系列（G1–G10）解析与脚本生成。"""
from __future__ import annotations

import re

from ..core.common import ROOT, load_json

GRAMMAR_PATH = ROOT / "curriculum" / "grammar.json"


def load_grammar() -> dict:
    return load_json(GRAMMAR_PATH)


def find_grammar_unit(prompt: str) -> dict | None:
    low = prompt.lower()
    if not re.search(r"语法|grammar|\bg\d+\b", low):
        return None
    units = load_grammar()["units"]
    m = re.search(r"\bg(\d+)\b", low) or re.search(r"第\s*(\d+)\s*集", prompt) or re.search(r"grammar\s*(\d+)", low)
    if m:
        ep = int(m.group(1))
        for u in units:
            if u["episode"] == ep:
                return u
        raise ValueError(f"语法系列共有 {len(units)} 集，没有第 {ep} 集")
    for u in units:
        if u["id"].lower() in low or any(k in low for k in u["title_en"].lower().split() if len(k) > 2):
            return u
    return units[0]


def build_grammar_episode(unit: dict, prompt: str, style: str = "clay", aspect: str = "portrait",
                          duration_sec: int = 75) -> dict:
    words = [{"en": ex["en"], "zh": ex["zh"], "card_en": ex["phrase"], "asset_rel": ex["asset"]}
             for ex in unit["examples"]]
    cues: list[dict] = []

    def cue(section, lang, text, pause, action="idle", word_index=None, card=False, repeat=False):
        cues.append({
            "cue_id": f"c{len(cues) + 1:03d}", "section": section, "lang": lang, "text": text,
            "pause_after_ms": pause, "action": action, "word_index": word_index,
            "show_card": card, "repeat_prompt": repeat,
        })

    cue("intro", "zh", f"大家好，我是奥利！今天学小学语法：{unit['title_zh']}。", 300, "wave")
    cue("story", "zh", unit["intro_zh"], 300, "curious" if False else "listen")
    cue("intro", "zh", f"记住口诀：{unit['rule_zh']}", 450, "nod")
    cue("intro", "en", f"Let's learn: {unit['title_en']}!", 500, "clap")

    for i, ex in enumerate(unit["examples"]):
        phrase = ex["phrase"]
        p_dot = phrase if phrase[-1:] in ".!?" else f"{phrase}."
        p_bang = phrase if phrase[-1:] in "!?" else f"{phrase.rstrip('.')}!"
        cue("word", "zh", f"来看第 {i + 1} 组：{ex['zh']}。", 350, "point", i, card=True)
        cue("word", "en", p_dot, 350, "point", i, card=True)
        cue("word", "zh", "跟我念！", 150, "listen", i, card=True)
        cue("word", "en", p_dot, 1500, "listen", i, card=True, repeat=True)
        cue("word", "en", f"{p_bang} Good job!", 500, "clap", i, card=True)

    cue("review", "zh", "闯关时间到！看看你学会了吗？", 400, "jump")
    for qi, q in enumerate(unit["quiz"], 1):
        wi = next((idx for idx, w in enumerate(words) if w["en"] == q.get("en")), None)
        cue("review", "zh", f"第 {qi} 题：{q['prompt_zh']}", 200, "listen", wi)
        cue("review", "en", q["prompt_en"].replace("___", "hmm"), 1600, "listen", wi, repeat=True)
        cue("review", "zh", f"答案是：", 150, "point", wi)
        cue("review", "en", f"{q['answer']}!", 600, "clap", wi)

    cue("outro", "zh", f"今天记住啦：{unit['rule_zh']}你真棒！", 300, "wave")
    cue("outro", "en", "Bye-bye!", 700, "wave")

    slug = re.sub(r"[^a-z0-9]+", "-", unit["title_en"].split(":")[0].lower()).strip("-")
    ep_id = f"ep_grammar_{unit['id'].lower()}e{unit['episode']}_{slug}"
    if style != "clay":
        ep_id += f"_{style}"
    return {
        "schema_version": "1.0",
        "episode_id": ep_id,
        "prompt": prompt,
        "theme": "grammar",
        "theme_zh": unit["title_zh"],
        "theme_en": unit["title_en"],
        "character": "ollie",
        "aspect": aspect,
        "style": style,
        "target_duration_sec": duration_sec,
        "options": {"style": style, "duration_sec": duration_sec, "aspect": aspect,
                    "narration": "bilingual", "en_voice": "a", "opening_closing": True, "story": True},
        "words": words,
        "cues": cues,
    }
