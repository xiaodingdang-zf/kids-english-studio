"""TTS adapters.

mock: macOS `say`（本机离线、零计费；音色仅供开发预览，不可用于发布）。
live: 调用现有 wanwu-pipeline 的 `wanwu tts`（火山引擎 seed-tts-2.0，计费）。
      本模块从不读取密钥文件，密钥由 wanwu 自己在计费请求路径中读取。
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Protocol

from ..core.common import run


class PaidCallBlocked(RuntimeError):
    pass


class EnglishNativeAdapter(Protocol):
    """B 方案注入接口：实现方须显式传英文语言并遵守 allow_paid。"""

    def synthesize(self, cues: list[dict], voice: dict, work_dir: Path,
                   allow_paid: bool) -> dict[str, tuple[Path, str]]: ...


class VolcEnglishAdapter:
    """火山引擎 seed-tts-2.0 英文母语适配器（explicit_language='en'），带缓存与计费门禁。"""

    URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
    KEY_FILE = Path.home() / ".config/sweety-handdraw-video/volcengine.env"

    def _headers(self, resource_id: str) -> dict[str, str]:
        import os, shlex, uuid
        creds = {}
        if self.KEY_FILE.exists():
            for line in self.KEY_FILE.read_text(encoding="utf-8").splitlines():
                parts = shlex.split(line, comments=True)
                if parts and parts[0] == "export":
                    parts = parts[1:]
                if len(parts) == 1 and "=" in parts[0]:
                    k, val = parts[0].split("=", 1)
                    if k in ("VOLC_TTS_API_KEY", "VOLC_TTS_APP_ID", "VOLC_TTS_ACCESS_KEY"):
                        creds[k] = val
        for k in ("VOLC_TTS_API_KEY", "VOLC_TTS_APP_ID", "VOLC_TTS_ACCESS_KEY"):
            if os.environ.get(k):
                creds[k] = os.environ[k]
        if creds.get("VOLC_TTS_API_KEY"):
            auth = {"X-Api-Key": creds["VOLC_TTS_API_KEY"]}
        elif creds.get("VOLC_TTS_APP_ID") and creds.get("VOLC_TTS_ACCESS_KEY"):
            auth = {"X-Api-App-Id": creds["VOLC_TTS_APP_ID"], "X-Api-Access-Key": creds["VOLC_TTS_ACCESS_KEY"]}
        else:
            raise RuntimeError("TTS credentials missing")
        return {**auth, "X-Api-Resource-Id": resource_id,
                "X-Api-Request-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

    def build_body(self, text: str, voice: dict) -> dict:
        additions = {"explicit_language": voice.get("explicit_language", "en"),
                     "aigc_metadata": {"enable": True, "content_producer": ""}}
        return {"user": {"uid": "kids-english-studio"}, "req_params": {
            "text": text, "speaker": voice["speaker"],
            "audio_params": {"format": "mp3", "sample_rate": 24000,
                             "speech_rate": int(voice.get("speech_rate", -20))},
            "additions": json.dumps(additions, ensure_ascii=False)}}

    def synthesize(self, cues: list[dict], voice: dict, work_dir: Path,
                   allow_paid: bool) -> dict[str, tuple[Path, str]]:
        if not allow_paid:
            raise PaidCallBlocked("英文音色 B 属于计费 TTS；确认后须加 --allow-paid")
        import base64, urllib.request
        work_dir.mkdir(parents=True, exist_ok=True)
        cache = rebuild_live_cache(work_dir, {})
        out: dict[str, tuple[Path, str]] = {}
        todo = []
        for c in cues:
            hit = cache.get(_cache_key(c["text"], voice))
            if hit and Path(hit).exists():
                out[c["cue_id"]] = (Path(hit), voice["voice_id"])
            else:
                todo.append(c)
        if not todo:
            return out
        gdir = work_dir / f"live-en-b-{time.strftime('%Y%m%d-%H%M%S')}"
        seg = gdir / "out" / "segments"
        seg.mkdir(parents=True, exist_ok=True)
        (gdir / "episode.json").write_text(json.dumps({
            "title": "kes en-b", "voice": voice,
            "lines": [{"id": i, "text": c["text"]} for i, c in enumerate(todo, 1)],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        for i, c in enumerate(todo, 1):
            req = urllib.request.Request(self.URL, data=json.dumps(self.build_body(c["text"], voice)).encode(),
                                         headers=self._headers(voice["resource_id"]))
            audio = bytearray()
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("code", 0) not in (0, 20000000):
                        raise RuntimeError("TTS provider error")
                    if data.get("data"):
                        audio.extend(base64.b64decode(data["data"], validate=True))
            if not audio:
                raise RuntimeError(f"Empty TTS audio for cue {c['cue_id']}")
            mp3 = seg / f"{i:02d}-attempt1.mp3"
            wav = seg / f"{i:02d}-attempt1.wav"
            mp3.write_bytes(bytes(audio))
            run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)])
            out[c["cue_id"]] = (wav, voice["voice_id"])
        return out


def synthesize_english_b(cues: list[dict], voices: dict, work_dir: Path,
                         allow_paid: bool, adapter: EnglishNativeAdapter | None = None
                         ) -> dict[str, tuple[Path, str]]:
    voice = voices["live_en_b"]
    if not voice["speaker"] or not voice["voice_id"]:
        raise ValueError("英文音色 B 尚未填写 speaker/voice_id（请在 kes/audio/voices.json 的 live_en_b 填入火山引擎英文音色 ID）")
    if not allow_paid:
        raise PaidCallBlocked("英文音色 B 属于计费 TTS；确认后须加 --allow-paid")
    return (adapter or VolcEnglishAdapter()).synthesize(cues, voice, work_dir, allow_paid)


def say_to_wav(text: str, voice: str, rate: int, out_wav: Path) -> Path:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "s.aiff"
        run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text])
        run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), "-ar", "48000", "-ac", "1",
             "-af", "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-50dB,areverse",
             str(out_wav)])
    return out_wav


def synthesize_mock(cues: list[dict], voices: dict, seg_dir: Path) -> dict[str, tuple[Path, str]]:
    out = {}
    for c in cues:
        v = voices["mock"][c["lang"]]
        wav = seg_dir / f"{c['cue_id']}.wav"
        say_to_wav(c["text"], v["voice"], v["rate"], wav)
        out[c["cue_id"]] = (wav, v["voice_id"])
    return out


def _cache_key(text: str, v: dict) -> str:
    import hashlib
    return hashlib.sha1(f"{text}|{v['resource_id']}|{v['speaker']}|{v.get('speech_rate', 0)}".encode()).hexdigest()


def rebuild_live_cache(work_dir: Path, voices: dict) -> dict:
    """扫描已有的 live-* 目录，把已付费生成的句子登记进缓存（避免重复计费）。"""
    cache = {}
    for ep_path in sorted(work_dir.glob("live-*/episode.json")):
        ep = json.loads(ep_path.read_text(encoding="utf-8"))
        v = ep["voice"]
        seg = ep_path.parent / "out" / "segments"
        for line in ep["lines"]:
            wavs = sorted(seg.glob(f"{line['id']:02d}-attempt*.wav"))
            if wavs:
                cache[_cache_key(line["text"], v)] = str(wavs[-1])
    return cache


def synthesize_live(cues: list[dict], voices: dict, work_dir: Path, allow_paid: bool,
                    en_voice: str = "a", english_b_adapter: EnglishNativeAdapter | None = None
                    ) -> dict[str, tuple[Path, str]]:
    """按音色分组，每组生成一个 wanwu episode 并调用 `wanwu tts --allow-paid-api`。已生成过的句子走缓存，不重复计费。"""
    if en_voice not in ("a", "b"):
        raise ValueError(f"未知英文音色方案：{en_voice}")
    english_cues = [c for c in cues if c["lang"] == "en"] if en_voice == "b" else []
    if english_cues:
        native = synthesize_english_b(english_cues, voices, work_dir, allow_paid, english_b_adapter)
        cues = [c for c in cues if c["lang"] != "en"]
    else:
        native = {}
    work_dir.mkdir(parents=True, exist_ok=True)
    cache = rebuild_live_cache(work_dir, voices)
    out = dict(native)
    todo = []
    for c in cues:
        v = voices["live"][c["lang"]]
        hit = cache.get(_cache_key(c["text"], v))
        if hit and Path(hit).exists():
            out[c["cue_id"]] = (Path(hit), v["voice_id"])
        else:
            todo.append(c)
    if not todo:
        return out
    cues = todo
    if not allow_paid:
        raise PaidCallBlocked(
            f"live 模式需要计费调用火山 TTS（本集 {len(cues)} 句）。确认后加 --allow-paid 重新运行。")
    groups: dict[str, list[dict]] = {}
    for c in cues:
        v = voices["live"][c["lang"]]
        key = f"{v['resource_id']}|{v['speaker']}|{v.get('speech_rate', 0)}"
        groups.setdefault(key, []).append(c)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    for gi, (key, group) in enumerate(groups.items(), 1):
        resource_id, speaker, rate = key.split("|")
        voice_id = next(voices["live"][c["lang"]]["voice_id"] for c in group)
        gdir = work_dir / f"live-{stamp}-g{gi}"
        gdir.mkdir(parents=True, exist_ok=False)
        ep = {
            "title": f"kes {gi}",
            "lines": [{"id": i, "text": c["text"]} for i, c in enumerate(group, 1)],
            "voice": {"resource_id": resource_id, "speaker": speaker, "speech_rate": int(rate)},
            "context_texts": voices.get("context_texts", []),
            "pronunciation_dict": {},
        }
        ep_path = gdir / "episode.json"
        ep_path.write_text(json.dumps(ep, ensure_ascii=False, indent=2), encoding="utf-8")
        subprocess.run([voices["wanwu_bin"], "tts", str(ep_path), "--output", str(gdir / "out"),
                        "--allow-paid-api"], check=True)
        seg = gdir / "out" / "segments"
        for i, c in enumerate(group, 1):
            wavs = sorted(seg.glob(f"{i:02d}-attempt*.wav"))
            if not wavs:
                raise RuntimeError(f"wanwu tts 没有产出第 {i} 句：{c['text']}")
            out[c["cue_id"]] = (wavs[-1], voice_id)
    return out
