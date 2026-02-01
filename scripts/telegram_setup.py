from __future__ import annotations

import getpass
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class TelegramChat:
    chat_id: int
    title: str
    chat_type: str


def parse_group_chats(updates: Dict) -> List[TelegramChat]:
    chats: Dict[int, TelegramChat] = {}
    for update in updates.get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        chat_type = chat.get("type")
        if chat_type not in {"group", "supergroup"}:
            continue
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        title = chat.get("title") or "Unnamed group"
        chats[int(chat_id)] = TelegramChat(chat_id=int(chat_id), title=title, chat_type=chat_type)
    return list(chats.values())


def _prompt_token() -> str:
    token = getpass.getpass("TELEGRAM_BOT_TOKEN (saisi masqué): ").strip()
    if not token:
        raise SystemExit("Token Telegram manquant.")
    return token


def _poll_updates(token: str, timeout_s: int = 60) -> List[TelegramChat]:
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    deadline = time.time() + timeout_s
    seen_offset: Optional[int] = None
    while time.time() < deadline:
        payload = {"timeout": 5}
        if seen_offset is not None:
            payload["offset"] = seen_offset
        try:
            resp = httpx.get(url, params=payload, timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError:
            time.sleep(2)
            continue
        results = data.get("result", [])
        if results:
            seen_offset = max(item.get("update_id", 0) for item in results) + 1
        chats = parse_group_chats(data)
        if chats:
            return chats
        time.sleep(3)
    return []


def _update_env_file(path: Path, values: Dict[str, str]) -> None:
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = []
    keys = set(values.keys())
    for line in existing:
        if not line or line.strip().startswith("#") or "=" not in line:
            updated.append(line)
            continue
        key, _ = line.split("=", 1)
        if key in values:
            updated.append(f"{key}={values[key]}")
            keys.remove(key)
        else:
            updated.append(line)
    for key in sorted(keys):
        updated.append(f"{key}={values[key]}")
    path.write_text("\n".join(updated) + ("\n" if updated else ""), encoding="utf-8")


def _build_env_values(chat_id: int, include_token: bool, token: str) -> Dict[str, str]:
    values = {
        "TELEGRAM_ENABLED": "true",
        "TELEGRAM_CHAT_ID": str(chat_id),
        "TELEGRAM_SEND_NO_GO_IMPORTANT": "true",
    }
    if include_token:
        values["TELEGRAM_BOT_TOKEN"] = token
    return values


def main() -> None:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        token = _prompt_token()

    print("Attente d'un message de groupe… (envoyer 'test' dans le groupe)")
    chats = _poll_updates(token, timeout_s=60)
    if not chats:
        raise SystemExit("Aucun groupe trouvé. Vérifiez que le bot est dans le groupe et qu'un message a été envoyé.")

    print("\nGroupes détectés:")
    for idx, chat in enumerate(chats, start=1):
        print(f"{idx}) {chat.title} (id={chat.chat_id}, type={chat.chat_type})")

    choice = input("Choisir un groupe (numéro): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(chats)):
        raise SystemExit("Choix invalide.")
    selected = chats[int(choice) - 1]

    print(f"\nTELEGRAM_CHAT_ID = {selected.chat_id}")
    include_token = input("Écrire aussi TELEGRAM_BOT_TOKEN dans .env.local ? (y/N): ").strip().lower() == "y"
    values = _build_env_values(selected.chat_id, include_token, token)

    write_local = input("Écrire ces valeurs dans .env.local ? (y/N): ").strip().lower() == "y"
    if write_local:
        _update_env_file(REPO_ROOT / ".env.local", values)
        print("✅ .env.local mis à jour.")

    write_env = input("Écrire aussi dans .env ? (y/N): ").strip().lower() == "y"
    if write_env:
        _update_env_file(REPO_ROOT / ".env", values)
        print("✅ .env mis à jour.")


if __name__ == "__main__":
    main()
