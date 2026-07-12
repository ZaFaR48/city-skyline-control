from i18n import menu_label, t
from keyboards import main_keyboard


def labels(keyboard):
    return {button.text for row in keyboard.keyboard for button in row}


def test_operator_menu_has_station_workflows_and_no_admin_controls():
    items = labels(main_keyboard("en", role="operator"))
    assert menu_label("en", "register_station") in items
    assert menu_label("en", "update_station") in items
    assert menu_label("en", "station_summary") in items
    assert t("en", "my_access") in items
    assert t("en", "pending_users") not in items
    assert menu_label("en", "settings") not in items
    assert menu_label("en", "vpn") not in items


def test_viewer_menu_is_read_only_and_localized():
    for lang in ("tj", "ru", "en"):
        items = labels(main_keyboard(lang, role="viewer"))
        assert menu_label(lang, "search_station") in items
        assert menu_label(lang, "register_station") not in items
        assert menu_label(lang, "update_station") not in items
        assert t(lang, "my_access").startswith("👤")
