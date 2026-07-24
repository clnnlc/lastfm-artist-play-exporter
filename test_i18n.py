import i18n

NEW_KEYS = ["setup.info_connect", "setup.connect", "setup.authorized"]


def test_new_setup_keys_present_in_both_languages():
    for key in NEW_KEYS:
        assert key in i18n.TRANSLATIONS, f"missing key: {key}"
        assert set(i18n.TRANSLATIONS[key]) >= {"de", "en"}, f"missing lang: {key}"
