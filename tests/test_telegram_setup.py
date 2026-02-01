from pathlib import Path

from scripts import telegram_setup
from scripts.telegram_setup import parse_group_chats


def test_parse_group_chats_filters_groups():
    updates = {
        "result": [
            {
                "update_id": 1,
                "message": {
                    "chat": {"id": -100, "title": "Signals", "type": "supergroup"}
                },
            },
            {"update_id": 2, "message": {"chat": {"id": 42, "type": "private"}}},
            {
                "update_id": 3,
                "message": {"chat": {"id": -200, "title": "Traders", "type": "group"}},
            },
        ]
    }
    chats = parse_group_chats(updates)
    ids = {chat.chat_id for chat in chats}
    assert ids == {-100, -200}


def test_setup_writes_env_local_only(monkeypatch, tmp_path):
    def fake_poll(token, timeout_s=60):
        return [telegram_setup.TelegramChat(chat_id=-123, title="Group", chat_type="group")]

    inputs = iter(["1", "n", "y", "n"])
    monkeypatch.setattr(telegram_setup, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(telegram_setup, "_poll_updates", fake_poll)
    monkeypatch.setattr(telegram_setup, "_prompt_token", lambda: "token")
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    telegram_setup.main()

    env_local = tmp_path / ".env.local"
    env_file = tmp_path / ".env"
    assert env_local.exists()
    assert not env_file.exists()
    content = env_local.read_text(encoding="utf-8")
    assert "TELEGRAM_CHAT_ID=-123" in content
    assert "TELEGRAM_BOT_TOKEN" not in content


def test_build_env_values_includes_token_only_when_requested():
    values = telegram_setup._build_env_values(-123, include_token=False, token="secret")
    assert "TELEGRAM_BOT_TOKEN" not in values
    values = telegram_setup._build_env_values(-123, include_token=True, token="secret")
    assert values["TELEGRAM_BOT_TOKEN"] == "secret"
