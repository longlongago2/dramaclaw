from novelvideo.task_backend import limits


def test_default_video_limits_match_stable_video_admission_policy(monkeypatch):
    for name in (
        "ST_PROJECT_MAX_ACTIVE_VIDEO_TASKS",
        "ST_PROJECT_MIN_ACTIVE_VIDEO_TASKS",
        "ST_PROJECT_USER_MAX_ACTIVE_VIDEO_TASKS",
        "ST_CE_GLOBAL_MAX_ACTIVE_VIDEO_TASKS",
    ):
        monkeypatch.delenv(name, raising=False)

    assert limits.project_lane_active_limit("video") == 4
    assert limits.project_user_lane_active_limit("video") == 2
    assert limits.project_lane_effective_active_limit("video", eligible_user_count=1) == 2
    assert limits.global_lane_concurrency("video") == 2


def test_explicit_video_user_limit_overrides_default(monkeypatch):
    monkeypatch.setenv("ST_PROJECT_USER_MAX_ACTIVE_VIDEO_TASKS", "1")
    assert limits.project_user_lane_active_limit("video") == 1
