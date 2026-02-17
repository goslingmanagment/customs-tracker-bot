from handlers.replies import looks_like_shot_report


def test_shot_detection_supports_gotovo():
    assert looks_like_shot_report("готово")


def test_shot_detection_supports_short_gotov():
    assert looks_like_shot_report("готов")


def test_shot_detection_supports_gotova():
    assert looks_like_shot_report("готова")
