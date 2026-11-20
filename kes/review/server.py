"""Local loopback review server and persistent review data."""
from __future__ import annotations

import copy
import http.server
import json
import re
import shutil
import threading
import time
import webbrowser
from http import HTTPStatus
from pathlib import Path

from ..core.common import dump_json, load_json


class ReviewState:
    def __init__(self, episode_dir: Path):
        self.episode_dir = Path(episode_dir)
        self.episode_path = self.episode_dir / "episode.json"
        if not self.episode_path.is_file():
            raise FileNotFoundError(self.episode_path)
        self.review_dir = self.episode_dir / "review"
        self.review_dir.mkdir(parents=True, exist_ok=True)
        self.comments_file = self.review_dir / "comments.json"
        self.versions_file = self.review_dir / "versions.json"
        self.status_file = self.review_dir / "status.json"
        self.comments = load_json(self.comments_file) if self.comments_file.exists() else []
        self.versions = load_json(self.versions_file) if self.versions_file.exists() else []
        self.status_data = load_json(self.status_file) if self.status_file.exists() else {"status": "waiting", "version": 0}
        self.lock = threading.RLock()

    def video_path(self) -> Path | None:
        episode_id = load_json(self.episode_path)["episode_id"]
        timeline = self.episode_dir / "audio_timeline.json"
        mode = load_json(timeline).get("mode") if timeline.exists() else None
        # A mismatched mock/live video would attach comments to the wrong time axis.
        names = [f"{episode_id}_{mode}.mp4"] if mode else [
            f"{episode_id}.mp4", f"{episode_id}_live.mp4", f"{episode_id}_mock.mp4"
        ]
        for name in dict.fromkeys(names):
            path = self.episode_dir / name
            if path.is_file():
                return path
        return None

    def timeline(self) -> dict:
        manifest = self.episode_dir / "frames_manifest.json"
        if manifest.exists():
            data = load_json(manifest)
            return {"fps": data.get("fps", 24), "shots": data.get("shots", []), "total_frames": data.get("total_frames", 0)}
        audio = self.episode_dir / "audio_timeline.json"
        if audio.exists():
            cues = load_json(audio).get("cues", [])
            return {"fps": 24, "shots": [
                {"cue_id": c["cue_id"], "start_frame": round(c["start_ms"] * 24 / 1000),
                 "end_frame": round((c["end_ms"] + c.get("pause_after_ms", 0)) * 24 / 1000)}
                for c in cues
            ]}
        return {"fps": 24, "shots": []}

    def get_status(self) -> dict:
        with self.lock:
            return self.status_data.copy()

    def set_status(self, status: str) -> None:
        if status not in {"waiting", "submitted", "ready", "approved"}:
            raise ValueError("Invalid status")
        with self.lock:
            self.status_data["status"] = status
            dump_json(self.status_file, self.status_data)

    def _save_comments(self) -> None:
        dump_json(self.comments_file, self.comments)

    def add_comment(self, frame: int, cue_id: str | None, text: str) -> dict:
        if type(frame) is not int or frame < 0 or not isinstance(text, str) or not text.strip():
            raise ValueError("frame must be a nonnegative integer; text must be nonempty")
        with self.lock:
            timeline = self.timeline()
            fps = int(timeline.get("fps") or 24)
            shot = next((s for s in timeline["shots"] if s["start_frame"] <= frame < s["end_frame"]), None)
            if shot:
                cue_id = shot["cue_id"]
            h, remainder = divmod(frame, fps * 3600)
            m, remainder = divmod(remainder, fps * 60)
            sec, ff = divmod(remainder, fps)
            ids = [int(c["id"][1:]) for c in self.comments if re.fullmatch(r"c\d+", c.get("id", ""))]
            ids += [int(c["id"][1:]) for v in self.versions for c in v.get("comments", [])
                    if re.fullmatch(r"c\d+", c.get("id", ""))]
            comment = {"id": f"c{max(ids, default=0) + 1:06d}", "frame": frame,
                       "timecode": f"{h:02d}:{m:02d}:{sec:02d}:{ff:02d}", "cue_id": cue_id,
                       "shot": (shot.get("camera") or shot.get("action")) if shot else None,
                       "text": text.strip(), "created_at": time.time(), "agent_reply": None}
            self.comments.append(comment)
            self._save_comments()
            return comment.copy()

    def update_comment(self, comment_id: str, text: str | None = None, agent_reply: str | None = None) -> dict | None:
        with self.lock:
            for comment in self.comments:
                if comment["id"] == comment_id:
                    if text is not None:
                        if not isinstance(text, str) or not text.strip():
                            raise ValueError("text must be nonempty")
                        comment["text"] = text.strip()
                    if agent_reply is not None:
                        if not isinstance(agent_reply, str):
                            raise ValueError("agent_reply must be a string")
                        comment["agent_reply"] = agent_reply
                    self._save_comments()
                    return comment.copy()
        return None

    def delete_comment(self, comment_id: str) -> bool:
        with self.lock:
            remaining = [c for c in self.comments if c["id"] != comment_id]
            if len(remaining) == len(self.comments):
                return False
            self.comments = remaining
            self._save_comments()
            return True

    def save_version(self, reason: str) -> dict:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be nonempty")
        with self.lock:
            video = self.video_path()
            number = len(self.versions) + 1
            video_record = None
            if video:
                archive = self.review_dir / "versions" / f"v{number:04d}.mp4"
                archive.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(video, archive)
                video_record = {"file": video.name, "archive": str(archive.relative_to(self.episode_dir)),
                                "size": archive.stat().st_size, "mtime_ns": video.stat().st_mtime_ns}
            version = {"version": number, "timestamp": time.time(), "reason": reason.strip(),
                       "video": video_record, "comments": copy.deepcopy(self.comments)}
            self.versions.append(version)
            dump_json(self.versions_file, self.versions)
            self.status_data["version"] = version["version"]
            dump_json(self.status_file, self.status_data)
            return copy.deepcopy(version)

    def register_version(self, reason: str) -> dict:
        with self.lock:
            version = self.save_version(reason)
            self.set_status("ready")
            return version

    def submit(self) -> None:
        with self.lock:
            self.save_version("submitted")
            self.set_status("submitted")


class ReviewHandler(http.server.BaseHTTPRequestHandler):
    def _local_request(self) -> bool:
        hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        origin = self.headers.get("Origin")
        return self.headers.get("Host") in hosts and (origin is None or origin in {f"http://{h}" for h in hosts})

    def do_GET(self):
        if not self._local_request():
            return self.send_error(HTTPStatus.FORBIDDEN)
        path = self.path.split("?", 1)[0]
        if path == "/":
            return self._bytes(get_review_html().encode(), "text/html; charset=utf-8")
        if path == "/api/episode":
            state = self.server.state
            return self._json({"ok": True, "data": load_json(state.episode_path),
                               "timeline": state.timeline(), "video": state.video_path() is not None})
        if path == "/api/comments":
            with self.server.state.lock:
                return self._json({"ok": True, "comments": copy.deepcopy(self.server.state.comments)})
        if path == "/api/status":
            return self._json({"ok": True, "status": self.server.state.get_status()})
        if path == "/video":
            return self._video()
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if not self._local_request():
            return self.send_error(HTTPStatus.FORBIDDEN)
        path = self.path.split("?", 1)[0]
        if path not in {"/api/comments", "/api/comments/update", "/api/comments/delete",
                        "/api/submit", "/api/approve", "/api/version"}:
            return self.send_error(HTTPStatus.NOT_FOUND)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 1_000_000:
                raise ValueError("Invalid body size")
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object")
            state = self.server.state
            if path == "/api/comments":
                result = {"comment": state.add_comment(data.get("frame"), data.get("cue_id"), data.get("text", ""))}
            elif path == "/api/comments/update":
                comment = state.update_comment(data.get("id"), data.get("text"), data.get("agent_reply"))
                if comment is None:
                    return self._json({"ok": False, "error": "Comment not found"}, HTTPStatus.NOT_FOUND)
                result = {"comment": comment}
            elif path == "/api/comments/delete":
                if not state.delete_comment(data.get("id")):
                    return self._json({"ok": False, "error": "Comment not found"}, HTTPStatus.NOT_FOUND)
                result = {}
            elif path == "/api/submit":
                state.submit()
                result = {"exit_code": 2}
            elif path == "/api/approve":
                state.set_status("approved")
                result = {"exit_code": 0}
            else:
                result = {"version": state.register_version(data.get("reason", "new video"))}
            self._json({"ok": True, **result})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def _video(self):
        path = self.server.state.video_path()
        if path is None:
            return self.send_error(HTTPStatus.NOT_FOUND, "Video not found")
        size = path.stat().st_size
        start, end = 0, size - 1
        range_header = self.headers.get("Range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
            if not match or not any(match.groups()):
                return self._bad_range(size)
            if match.group(1):
                start = int(match.group(1))
                end = min(int(match.group(2)), size - 1) if match.group(2) else end
            else:
                start = max(0, size - int(match.group(2)))
            if start >= size or start > end:
                return self._bad_range(size)
        count = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT if range_header else HTTPStatus.OK)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(count))
        if range_header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with path.open("rb") as video:
                video.seek(start)
                while count:
                    chunk = video.read(min(count, 1024 * 1024))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    count -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _bad_range(self, size):
        self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
        self.send_header("Content-Range", f"bytes */{size}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _bytes(self, body: bytes, content_type: str):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def run_review_server(episode_dir: Path, port: int = 0, timeout: int = 1800, no_open: bool = False) -> int:
    state = ReviewState(episode_dir)
    if state.get_status()["status"] in {"submitted", "approved"}:
        state.set_status("waiting")

    class BoundHandler(ReviewHandler):
        pass

    with http.server.ThreadingHTTPServer(("127.0.0.1", port), BoundHandler) as server:
        server.state = state
        server.daemon_threads = True
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"📺 审片台：{url}", flush=True)
        if not no_open:
            webbrowser.open(url)
        started = time.monotonic()

        def stop_on_decision():
            while True:
                status = state.get_status()["status"]
                if status in {"submitted", "approved"} or (timeout > 0 and time.monotonic() - started >= timeout):
                    server.shutdown()
                    return
                time.sleep(0.05)

        thread = threading.Thread(target=stop_on_decision, daemon=True)
        thread.start()
        server.serve_forever(poll_interval=0.05)
        thread.join()
    status = state.get_status()["status"]
    return 2 if status == "submitted" else 0 if status == "approved" else 1


def get_review_html(episode_dir: Path | None = None, export_path: Path | None = None) -> str:
    html = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
    if episode_dir is None:
        return html.replace("__OFFLINE_DATA__", "null")
    import os
    state = ReviewState(episode_dir)
    video = state.video_path()
    data = {"episode": load_json(state.episode_path), "timeline": state.timeline(), "comments": state.comments,
            "video": os.path.relpath(video, export_path.parent) if video and export_path else None}
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return html.replace("__OFFLINE_DATA__", payload)
