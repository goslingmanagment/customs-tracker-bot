from core.brief_text_parser import parse_original_brief_sections


def test_parse_sections_with_ru_markers_and_emojis():
    raw = (
        "📦 Описание заказа\n"
        "Дата: 18.02.2026\n"
        "🎥 Описание задания:\n\n"
        "Первая строка.\n"
        "Вторая строка.\n\n"
        "👗 Одежда: аутфит из скрина\n\n"
        "📝Заметки: без музыки, громкие стоны\n"
        "🔥Срочность: Высокая\n"
    )

    parsed = parse_original_brief_sections(raw)

    assert parsed["description_original"] == "Первая строка.\nВторая строка."
    assert parsed["outfit_original"] == "аутфит из скрина"
    assert parsed["notes_original"] == "без музыки, громкие стоны"


def test_parse_sections_without_emojis_and_with_english_markers():
    raw = (
        "Task description: Slow tease in first minute.\n"
        "Continue with dildo blowjob.\n"
        "Outfit: Red dress\n"
        "Notes: No music\n"
        "Priority: high\n"
    )

    parsed = parse_original_brief_sections(raw)

    assert parsed["description_original"] == "Slow tease in first minute.\nContinue with dildo blowjob."
    assert parsed["outfit_original"] == "Red dress"
    assert parsed["notes_original"] == "No music"


def test_parse_sections_missing_optional_blocks():
    raw = (
        "Описание задания:\n"
        "Только описание без других полей.\n"
        "Сроки: До 24.02.2026\n"
    )

    parsed = parse_original_brief_sections(raw)

    assert parsed["description_original"] == "Только описание без других полей."
    assert parsed["outfit_original"] is None
    assert parsed["notes_original"] is None


def test_parse_sections_preserves_internal_newlines():
    raw = (
        "Описание задания:\n"
        "Блок 1\n\n"
        "Блок 2\n"
        "Наряд:\n"
        "Сет А\n\n"
        "Сет Б\n"
    )

    parsed = parse_original_brief_sections(raw)

    assert parsed["description_original"] == "Блок 1\n\nБлок 2"
    assert parsed["outfit_original"] == "Сет А\n\nСет Б"
