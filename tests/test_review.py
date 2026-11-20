"""Review station tests: HTTP API, comment management, versioning."""
import json
import time
import urllib.request
import urllib.error
import subprocess
import sys
import re
from pathlib import Path

import pytest

from kes.review.server import ReviewState, ReviewHandler, run_review_server
from kes.core.common import dump_json, load_json
from kes.core.script_generator import generate


@pytest.fixture
def episode_dir(tmp_path):
    """Create a test episode directory with episode.json."""
    ep = generate("颜色 30 秒 3 个词")
    ep_path = dump_json(tmp_path / "episode.json", ep)
    return tmp_path


@pytest.fixture
def review_state(episode_dir):
    """Create a ReviewState instance."""
    return ReviewState(episode_dir)


class TestReviewState:
    """Test comment and version management."""

    def test_init_creates_review_dir(self, episode_dir):
        state = ReviewState(episode_dir)
        assert (episode_dir / "review").exists()

    def test_add_comment(self, review_state):
        comment = review_state.add_comment(frame=100, cue_id="c001", text="需要调整表情")
        assert comment["id"]
        assert comment["frame"] == 100
        assert comment["cue_id"] == "c001"
        assert comment["timecode"] == "00:00:04:04"
        assert comment["text"] == "需要调整表情"
        assert comment["created_at"]
        assert comment["agent_reply"] is None

    def test_add_multiple_comments(self, review_state):
        c1 = review_state.add_comment(100, "c001", "问题 1")
        c2 = review_state.add_comment(200, "c002", "问题 2")
        assert len(review_state.comments) == 2
        assert c1["id"] != c2["id"]

    def test_comments_persisted(self, episode_dir):
        state1 = ReviewState(episode_dir)
        state1.add_comment(100, "c001", "问题")
        state2 = ReviewState(episode_dir)
        assert len(state2.comments) == 1
        assert state2.comments[0]["text"] == "问题"

    def test_update_comment_text(self, review_state):
        c = review_state.add_comment(100, "c001", "原意见")
        updated = review_state.update_comment(c["id"], text="修改后的意见")
        assert updated["text"] == "修改后的意见"

    def test_update_comment_agent_reply(self, review_state):
        c = review_state.add_comment(100, "c001", "问题")
        updated = review_state.update_comment(c["id"], agent_reply="已修复")
        assert updated["agent_reply"] == "已修复"

    def test_update_nonexistent_comment(self, review_state):
        result = review_state.update_comment("nonexistent", text="新文本")
        assert result is None

    def test_delete_comment(self, review_state):
        c = review_state.add_comment(100, "c001", "临时意见")
        assert len(review_state.comments) == 1
        review_state.delete_comment(c["id"])
        assert len(review_state.comments) == 0

    def test_save_version(self, review_state):
        review_state.add_comment(100, "c001", "问题 A")
        review_state.add_comment(200, "c002", "问题 B")
        version = review_state.save_version("初版")
        assert version["version"] == 1
        assert version["reason"] == "初版"
        assert len(version["comments"]) == 2
        assert version["timestamp"]

    def test_multiple_versions(self, review_state, episode_dir):
        review_state.add_comment(100, "c001", "v1")
        review_state.save_version("版本 1")
        review_state.comments = []
        review_state.add_comment(200, "c002", "v2")
        review_state.save_version("版本 2")

        versions = load_json(episode_dir / "review" / "versions.json")
        assert len(versions) == 2
        assert versions[0]["reason"] == "版本 1"
        assert versions[1]["reason"] == "版本 2"

    def test_set_status(self, review_state, episode_dir):
        review_state.set_status("submitted")
        status = load_json(episode_dir / "review" / "status.json")
        assert status["status"] == "submitted"

    def test_get_status(self, review_state):
        review_state.set_status("approved")
        status = review_state.get_status()
        assert status["status"] == "approved"


class TestReviewAPI:
    """Test HTTP API endpoints."""

    def test_api_episode(self, episode_dir):
        """Test /api/episode endpoint."""
        ReviewHandler.episode_path = episode_dir / "episode.json"
        ReviewHandler.state = ReviewState(episode_dir)

        # Simulate request
        ep = load_json(episode_dir / "episode.json")
        assert ep["episode_id"]
        assert ep["cues"]

    def test_api_comments_empty(self, episode_dir):
        """Test /api/comments returns empty list initially."""
        state = ReviewState(episode_dir)
        assert state.comments == []

    def test_api_comments_after_add(self, episode_dir):
        """Test /api/comments returns added comments."""
        state = ReviewState(episode_dir)
        state.add_comment(100, "c001", "测试意见")
        assert len(state.comments) == 1
        assert state.comments[0]["text"] == "测试意见"

    def test_api_status_initial(self, episode_dir):
        """Test /api/status returns initial waiting state."""
        state = ReviewState(episode_dir)
        status = state.get_status()
        assert status["status"] == "waiting"
        assert status["version"] == 0

    def test_api_status_after_submit(self, episode_dir):
        """Test status changes to submitted."""
        state = ReviewState(episode_dir)
        state.set_status("submitted")
        status = state.get_status()
        assert status["status"] == "submitted"

    def test_api_status_after_approve(self, episode_dir):
        """Test status changes to approved."""
        state = ReviewState(episode_dir)
        state.set_status("approved")
        status = state.get_status()
        assert status["status"] == "approved"


class TestReviewWorkflow:
    """Test complete review workflows."""

    def test_submit_workflow(self, episode_dir):
        """Test submission workflow."""
        state = ReviewState(episode_dir)
        state.add_comment(100, "c001", "需要改进")
        state.add_comment(200, "c002", "音量过大")
        state.set_status("submitted")

        # Verify persistence
        status = load_json(episode_dir / "review" / "status.json")
        assert status["status"] == "submitted"
        comments = load_json(episode_dir / "review" / "comments.json")
        assert len(comments) == 2

    def test_approve_workflow(self, episode_dir):
        """Test approval workflow."""
        state = ReviewState(episode_dir)
        state.set_status("approved")

        status = load_json(episode_dir / "review" / "status.json")
        assert status["status"] == "approved"

    def test_iterate_workflow(self, episode_dir):
        """Test iteration: submit → agent reply → new version."""
        state = ReviewState(episode_dir)

        # Initial submission
        state.add_comment(100, "c001", "问题 A")
        state.save_version("初版")
        state.set_status("submitted")

        # Agent processes
        state.update_comment(state.comments[0]["id"], agent_reply="已修复，请复审")
        state.set_status("waiting")

        # Second review
        state.add_comment(150, "c002", "细节调整")
        state.save_version("复审版")

        versions = load_json(episode_dir / "review" / "versions.json")
        assert len(versions) == 2
        assert versions[0]["reason"] == "初版"
        assert versions[1]["reason"] == "复审版"

    def test_export_comments_as_json(self, episode_dir):
        """Test exporting comments as JSON."""
        state = ReviewState(episode_dir)
        state.add_comment(100, "c001", "问题 A")
        state.add_comment(200, "c002", "问题 B")

        comments = load_json(episode_dir / "review" / "comments.json")
        assert len(comments) == 2
        json_str = json.dumps(comments, ensure_ascii=False, indent=2)
        assert "问题 A" in json_str
        assert "问题 B" in json_str

    def test_export_comments_as_text(self, episode_dir):
        """Test exporting comments as plain text."""
        state = ReviewState(episode_dir)
        state.add_comment(100, "c001", "问题 A")
        state.add_comment(200, "c002", "问题 B")

        text_lines = [
            f"Frame #{c['frame']} ({c['cue_id']}): {c['text']}"
            for c in state.comments
        ]
        text = "\n".join(text_lines)
        assert "Frame #100 (c001): 问题 A" in text
        assert "Frame #200 (c002): 问题 B" in text


class TestReviewServer:
    """Test HTTP server startup and control flow."""

    def test_server_instantiation(self, episode_dir):
        """Test that server can be instantiated without crashing."""
        try:
            # Don't actually run the server, just verify setup works
            ReviewHandler.state = ReviewState(episode_dir)
            ReviewHandler.episode_path = episode_dir / "episode.json"
            assert ReviewHandler.state is not None
            assert ReviewHandler.episode_path.exists()
        except Exception as e:
            pytest.fail(f"Server instantiation failed: {e}")

    def test_review_state_persistence_across_instances(self, episode_dir):
        """Test that ReviewState reads persisted comments on new instance."""
        state1 = ReviewState(episode_dir)
        state1.add_comment(100, "c001", "first comment")
        c_id = state1.comments[0]["id"]

        # Create new instance
        state2 = ReviewState(episode_dir)
        assert len(state2.comments) == 1
        assert state2.comments[0]["id"] == c_id
        assert state2.comments[0]["text"] == "first comment"


class TestReviewExportHTML:
    """Test HTML export functionality."""

    def test_html_generation(self):
        """Test that review HTML can be generated."""
        from kes.review.server import get_review_html
        html = get_review_html()
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "videoplayer" in html.lower() or "video" in html
        assert "审片台" in html
        assert "/api/episode" in html
        assert "/api/comments" in html

    def test_html_export_to_file(self, tmp_path):
        """Test that HTML can be exported to a file."""
        from kes.review.server import get_review_html
        output_path = tmp_path / "review.html"
        html = get_review_html()
        output_path.write_text(html, encoding="utf-8")
        assert output_path.exists()
        assert "<!DOCTYPE html>" in output_path.read_text()

    def test_html_contains_video_endpoint(self):
        """Test that generated HTML references /video endpoint."""
        from kes.review.server import get_review_html
        html = get_review_html()
        assert 'src="/video"' in html


class TestReviewAPIFlow:
    """Test realistic API flows."""

    def test_complete_review_flow(self, episode_dir):
        """Test a complete review workflow via API-like calls."""
        state = ReviewState(episode_dir)

        # Step 1: Get initial status
        status = state.get_status()
        assert status["status"] == "waiting"

        # Step 2: Add comments
        c1 = state.add_comment(50, "c001", "音量太大")
        c2 = state.add_comment(100, "c002", "表情需要调整")
        assert len(state.comments) == 2

        # Step 3: Submit for review
        state.set_status("submitted")
        status = state.get_status()
        assert status["status"] == "submitted"

        # Step 4: Agent processes and adds replies
        state.update_comment(c1["id"], agent_reply="已降低 2dB")
        state.update_comment(c2["id"], agent_reply="已调整表情")
        state.set_status("waiting")

        # Step 5: Save version
        version = state.save_version("第一次修改")
        assert version["version"] == 1
        assert len(version["comments"]) == 2

        # Step 6: Second review - add new comment
        c3 = state.add_comment(150, "c003", "细节处理很好")
        assert len(state.comments) == 3

        # Step 7: Approve
        state.set_status("approved")
        status = state.get_status()
        assert status["status"] == "approved"

        # Verify persistence
        state2 = ReviewState(episode_dir)
        assert len(state2.comments) == 3
        assert state2.comments[0]["agent_reply"] == "已降低 2dB"
        assert state2.get_status()["status"] == "approved"

    def test_reject_then_approve_flow(self, episode_dir):
        """Test reject→revise→approve flow."""
        state = ReviewState(episode_dir)

        # Reject with comments
        state.add_comment(100, "c001", "需要重新录音")
        state.set_status("submitted")

        # Agent processes
        state.update_comment(state.comments[0]["id"], agent_reply="已重新录音")
        state.set_status("waiting")

        # Second review
        state.comments = []
        state.add_comment(200, None, "重新录音很好")
        state.set_status("approved")

        final_status = state.get_status()
        assert final_status["status"] == "approved"

    def test_concurrent_operations(self, episode_dir):
        """Test multiple rapid operations."""
        state = ReviewState(episode_dir)

        # Rapid adds
        for i in range(10):
            state.add_comment(i * 10, f"c{i:03d}", f"意见 {i}")

        assert len(state.comments) == 10
        ids = [c["id"] for c in state.comments]
        assert len(set(ids)) == 10  # All unique


def _start_cli(episode_dir, timeout=10):
    proc = subprocess.Popen(
        [sys.executable, "-m", "kes.cli", "review", str(episode_dir), "--port", "0",
         "--timeout", str(timeout), "--no-open"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    first = proc.stdout.readline()
    match = re.search(r"http://127\.0\.0\.1:\d+/", first)
    assert match, (first, proc.stderr.read())
    return proc, match.group(0)


def _request(url, path, payload=None, headers=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url + path.lstrip("/"), data=body, headers=headers or {})
    with urllib.request.urlopen(req, timeout=4) as response:
        raw = response.read()
        return response.status, dict(response.headers), json.loads(raw) if path.startswith("/api/") else raw


def test_real_http_submit_register_approve_and_export(episode_dir, tmp_path):
    ep = load_json(episode_dir / "episode.json")
    video = episode_dir / f"{ep['episode_id']}_mock.mp4"
    video.write_bytes(b"0123456789")
    dump_json(episode_dir / "audio_timeline.json", {"mode": "mock"})
    dump_json(episode_dir / "frames_manifest.json", {
        "fps": 24, "total_frames": 48,
        "shots": [{"cue_id": "c001", "start_frame": 0, "end_frame": 48, "camera": "static"}],
    })
    proc, url = _start_cli(episode_dir)
    try:
        assert _request(url, "/api/status")[2]["status"]["status"] == "waiting"
        episode = _request(url, "/api/episode")[2]
        assert episode["timeline"]["shots"][0]["cue_id"] == "c001"
        assert episode["video"] is True
        status, headers, data = _request(url, "/video", headers={"Range": "bytes=2-5"})
        assert (status, headers["Content-Range"], data) == (206, "bytes 2-5/10", b"2345")
        c = _request(url, "/api/comments", {"frame": 12, "cue_id": "c001", "text": "调整字幕"})[2]["comment"]
        assert c["timecode"] == "00:00:00:12" and c["shot"] == "static"
        assert _request(url, "/api/comments/update", {"id": c["id"], "text": "调整字幕位置"})[2]["comment"]["text"] == "调整字幕位置"
        assert _request(url, "/api/submit", {})[2]["exit_code"] == 2
        output, errors = proc.communicate(timeout=5)
        assert proc.returncode == 2, (output, errors)
        assert "调整字幕位置" in output
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()

    state = ReviewState(episode_dir)
    assert state.versions[0]["comments"][0]["text"] == "调整字幕位置"
    assert (episode_dir / state.versions[0]["video"]["archive"]).read_bytes() == b"0123456789"
    state.update_comment(c["id"], agent_reply="已调整字幕")
    # Simulate a newly rendered file without invoking render/audio or paid APIs.
    video.write_bytes(b"abcdefghij")
    command = [sys.executable, "-m", "kes.cli", "review", str(episode_dir),
               "--register-version", "字幕修订版"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    state = ReviewState(episode_dir)
    assert state.get_status() == {"status": "ready", "version": 2}
    assert state.versions[0]["comments"][0]["agent_reply"] is None
    assert state.versions[1]["comments"][0]["agent_reply"] == "已调整字幕"
    assert (episode_dir / state.versions[1]["video"]["archive"]).read_bytes() == b"abcdefghij"

    proc, url = _start_cli(episode_dir)
    try:
        assert _request(url, "/api/status")[2]["status"]["status"] == "ready"
        assert _request(url, "/api/approve", {})[2]["exit_code"] == 0
        proc.communicate(timeout=5)
        assert proc.returncode == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()

    export = tmp_path / "review.html"
    result = subprocess.run([sys.executable, "-m", "kes.cli", "review", str(episode_dir),
                             "--export-html", str(export)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    html = export.read_text()
    assert 'const offlineData = {' in html
    assert '调整字幕位置' in html
    assert video.name in html
    assert 'const offline = offlineData !== null' in html


def test_real_http_validation_and_timeout(episode_dir):
    proc, url = _start_cli(episode_dir, timeout=1)
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            _request(url, "/api/submit", {}, headers={"Origin": "https://example.invalid"})
        assert exc.value.code == 403
        with pytest.raises(urllib.error.HTTPError) as exc:
            _request(url, "/api/comments", {"frame": "bad", "text": "x"})
        assert exc.value.code == 400
        with pytest.raises(urllib.error.HTTPError) as exc:
            _request(url, "/api/comments/delete", {"id": "missing"})
        assert exc.value.code == 404
        proc.communicate(timeout=5)
        assert proc.returncode == 1
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
