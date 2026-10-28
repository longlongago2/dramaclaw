from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.m09


class _FakeTaskManager:
    def __init__(self):
        self.updates = []

    def update_progress_for_project(self, *args, **kwargs):
        self.updates.append((args, kwargs))


def _ctx(tmp_path):
    return SimpleNamespace(output_dir=tmp_path)


def _write_beat_video(project_dir, episode: int, beat_num: int) -> None:
    video_dir = project_dir / "videos" / "beats" / f"ep{episode:03d}"
    video_dir.mkdir(parents=True)
    (video_dir / f"beat_{beat_num:02d}.mp4").write_bytes(b"video")


def test_compose_episode_preserves_embedded_audio_when_no_external_mp3(
    monkeypatch,
    tmp_path,
):
    from novelvideo.task_backend.runners import video

    _write_beat_video(tmp_path, episode=1, beat_num=3)
    manager = _FakeTaskManager()
    commands = []

    def fake_run(cmd, **_kwargs):
        commands.append(cmd)
        if cmd[0] == "ffprobe":
            return SimpleNamespace(returncode=0, stdout="0\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(video, "get_task_manager", lambda: manager)
    monkeypatch.setattr(video, "run_project_subprocess", fake_run)

    result = video.run_compose_episode(
        {
            "episode": 1,
            "payload": {
                "output_dir": str(tmp_path),
                "beats": [{"beat_number": 3}],
            },
        },
        _ctx(tmp_path),
    )

    clip_cmd = next(cmd for cmd in commands if cmd[0] == "ffmpeg" and "beat_0003.mp4" in cmd[-1])
    assert result["video_path"].endswith("videos/episodes/ep001_final.mp4")
    assert "anullsrc=r=44100:cl=stereo" not in clip_cmd
    assert clip_cmd[clip_cmd.index("-map") + 1] == "0:v:0"
    assert "0:a:0" in clip_cmd
    assert any(
        "使用视频内置音轨" in line
        for _args, kwargs in manager.updates
        for line in kwargs.get("logs", [])
    )


@pytest.mark.parametrize(
    "source,external_exists,embedded_exists,audio_type,expected",
    [
        ("auto", True, True, "narration", "external"),
        ("auto", False, True, "narration", "embedded"),
        ("auto", False, False, "narration", "silence"),
        ("auto", True, True, "silence", "embedded"),
        ("auto", True, True, "action", "embedded"),
        ("embedded", True, True, "narration", "embedded"),
        ("embedded", True, False, "narration", "silence"),
        ("silence", True, True, "narration", "silence"),
        ("external", True, True, "narration", "external"),
    ],
)
def test_compose_uses_selected_audio_source(
    monkeypatch, tmp_path, source, external_exists, embedded_exists, audio_type, expected
):
    from novelvideo.task_backend.runners import video
    from novelvideo.utils.path_resolver import PathResolver

    _write_beat_video(tmp_path, 1, 3)
    audio_path = PathResolver(str(tmp_path), 1).audio(3)
    if external_exists:
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"audio")
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        return SimpleNamespace(
            returncode=0, stdout="0\n" if embedded_exists else "", stderr=""
        )

    monkeypatch.setattr(video, "get_task_manager", _FakeTaskManager)
    monkeypatch.setattr(video, "run_project_subprocess", fake_run)
    video.run_compose_episode(
        {"episode": 1, "payload": {
            "beats": [{"beat_number": 3, "audio_type": audio_type}],
            # JSON queue round-trips turn numeric keys into strings.
            "beat_audio_sources": {"3": source},
        }}, _ctx(tmp_path),
    )
    clip_cmd = next(cmd for cmd in commands if cmd[0] == "ffmpeg")
    assert (str(audio_path) in clip_cmd) == (expected == "external")
    assert ("0:a:0" in clip_cmd) == (expected == "embedded")
    assert ("anullsrc=r=44100:cl=stereo" in clip_cmd) == (expected == "silence")
    if source in {"external", "silence"}:
        assert not any(cmd[0] == "ffprobe" for cmd in commands)


@pytest.mark.parametrize("missing", ["video", "external audio"])
def test_compose_rejects_missing_assets_before_running_ffmpeg(monkeypatch, tmp_path, missing):
    from novelvideo.task_backend.runners import video

    if missing != "video":
        _write_beat_video(tmp_path, 1, 3)
    monkeypatch.setattr(video, "get_task_manager", _FakeTaskManager)
    monkeypatch.setattr(video, "run_project_subprocess", lambda *a, **kw: pytest.fail("ffmpeg ran"))
    with pytest.raises(ValueError, match=f"missing {missing}"):
        video.run_compose_episode(
            {"episode": 1, "payload": {
                "beats": [{"beat_number": 3}],
                "beat_audio_sources": {3: "external"} if missing != "video" else {},
            }}, _ctx(tmp_path),
        )


def test_compose_does_not_silently_skip_failed_shots(monkeypatch, tmp_path):
    from novelvideo.task_backend.runners import video

    _write_beat_video(tmp_path, 1, 3)
    monkeypatch.setattr(video, "get_task_manager", _FakeTaskManager)
    monkeypatch.setattr(video, "run_project_subprocess", lambda *a, **kw: SimpleNamespace(
        returncode=1, stdout="", stderr="invalid clip",
    ))
    with pytest.raises(RuntimeError, match="Beat 3"):
        video.run_compose_episode(
            {"episode": 1, "payload": {"beats": [{"beat_number": 3}], "beat_audio_sources": {3: "silence"}}},
            _ctx(tmp_path),
        )
