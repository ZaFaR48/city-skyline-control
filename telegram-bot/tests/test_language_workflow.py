from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers.language import change_language, choose_language
from handlers.start import cmd_start
from i18n import LANGUAGE_BY_BUTTON, MENU, TEXT, menu_label, t


class FakeState:
    def __init__(self, data=None):
        self.data = dict(data or {})

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def clear(self):
        self.data.clear()


class FakeMessage:
    def __init__(self, text="/start"):
        self.text = text
        self.from_user = SimpleNamespace(id=12345, username="operator", first_name="Operator", last_name=None)
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs.get("reply_markup")))
        return SimpleNamespace(message_id=len(self.answers))


@pytest.mark.asyncio
async def test_start_always_displays_three_language_choices(monkeypatch):
    async def registration(_user):
        return {"status": "activated", "role": "operator", "preferred_language": "ru", "username": "operator"}

    monkeypatch.setattr("handlers.start.api.registration_start", registration)
    message = FakeMessage()
    state = FakeState({"lang": "en", "old": "discarded"})
    await cmd_start(message, state)
    keyboard = message.answers[-1][1]
    assert [button.text for button in keyboard.keyboard[0]] == list(LANGUAGE_BY_BUTTON)
    assert state.data["pending_registration_result"]["status"] == "activated"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("button", "language", "menu_text"),
    [("🇹🇯 Тоҷикӣ", "tj", "Сабти стансияи нав"), ("🇷🇺 Русский", "ru", "Зарегистрировать станцию"), ("🇬🇧 English", "en", "Register station")],
)
async def test_language_selection_persists_and_immediately_rebuilds_menu(monkeypatch, button, language, menu_text):
    saved = {}

    async def persist(user, lang):
        saved.update(user_id=user.id, language=lang)
        return {"preferred_language": lang}

    monkeypatch.setattr("handlers.language.api.set_telegram_language", persist)
    state = FakeState({
        "lang": "tj",
        "role": "operator",
        "pending_registration_result": {"status": "activated", "role": "operator", "username": "operator"},
    })
    message = FakeMessage(button)
    await choose_language(message, state)
    assert saved == {"user_id": 12345, "language": language}
    assert state.data["lang"] == language
    keyboard = message.answers[-1][1]
    assert any(menu_text in item.text for row in keyboard.keyboard for item in row)
    assert any(menu_label(language, "change_language") == item.text for row in keyboard.keyboard for item in row)


@pytest.mark.asyncio
async def test_pending_registration_reply_uses_selected_language(monkeypatch):
    async def persist(_user, lang):
        return {"preferred_language": lang}

    monkeypatch.setattr("handlers.language.api.set_telegram_language", persist)
    state = FakeState({"pending_registration_result": {"status": "pending", "role": None}, "role": None})
    message = FakeMessage("🇷🇺 Русский")
    await choose_language(message, state)
    assert t("ru", "registration_pending") in [answer[0] for answer in message.answers]


@pytest.mark.asyncio
async def test_change_language_action_displays_selector():
    message = FakeMessage(menu_label("en", "change_language"))
    await change_language(message, FakeState({"lang": "en", "role": "viewer"}))
    assert [button.text for button in message.answers[-1][1].keyboard[0]] == list(LANGUAGE_BY_BUTTON)


def test_all_languages_have_identical_translation_and_menu_keys():
    assert set(TEXT["tj"]) == set(TEXT["ru"]) == set(TEXT["en"])
    assert set(MENU["tj"]) == set(MENU["ru"]) == set(MENU["en"])
