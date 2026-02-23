# Analyse des fichiers non utilisés ou optionnels

Analyse effectuée pour nettoyer le système. Entrées du système : API (`app.api.main`), runner (`app.scripts.runner_loop`), MT5 bridge (`services.mt5_bridge.main`), scripts planifiés ou documentés.

---

## 1. Code mort (jamais importé) — à supprimer

| Fichier | Raison |
|---------|--------|
| **`app/providers/base.py`** | Définit `DataProvider` (Protocol) mais n’est importé nulle part. Le projet utilise `MarketDataProvider` dans `app/providers/market_data_provider.py` et `get_provider()` dans `app/providers/__init__.py`. |

---

## 2. Scripts utilitaires / one-off (ni appelés par l’API ni par des tâches)

Ces scripts ne sont pas dans la chaîne API / runner / NSSM. Utiles en manuel ou pour du debug. À garder ou supprimer selon ton usage.

| Script | Rôle | Recommandation |
|--------|------|----------------|
| `scripts/analyze_no_go_session.py` | Analyse NO_GO d’une session (SQLite direct, pas d’app). | **Optionnel** — partiellement couvert par `run_ai_advisory.py` (simulation + rapport). Tu peux le garder pour des analyses légères sans IA. |
| `scripts/analyze_decisions_recent.py` | Affiche les décisions récentes (DB direct). | **Optionnel** — utile en debug. Garder si tu l’utilises. |
| `scripts/inspect_signals_db.py` | Inspection directe de la DB signaux. | **Optionnel** — debug. |
| `scripts/send_report_telegram.py` | Envoie un message fixe “RAPPORT — Améliorations” sur Telegram. | **One-off** — message figé, probablement obsolète. Candidat à supprimer si tu ne l’utilises plus. |
| `scripts/send_update_go_group.py` | Envoie un message fixe “Mise à jour robot” sur Telegram. | **One-off** — idem. |
| `scripts/send_telegram_format_test.py` | Test manuel du format Telegram. | **Optionnel** — garder si tu testes l’envoi à la main. |
| `scripts/extract_scores_wins_losses.py` | Extrait les listes de scores wins/pertes depuis le JSON advisory. | **Utile** — utilisé pour l’analyse (scores par style). À garder. |
| `scripts/telegram_setup.py` | Configuration initiale du bot Telegram (chat_id, etc.). | **Utile** — documenté dans README. À garder. |

---

## 3. Tests et e2e

| Fichier | Statut |
|---------|--------|
| `tests/e2e/generate_report.py` | Génère `REPORT_SPRINT2.md` ; utilisé par les e2e (référence docker-compose). À garder si tu lances les e2e. |
| Tous les `tests/test_*.py` | Utilisés par pytest. À garder. |

---

## 4. Docs / rapports potentiellement obsolètes

Rapports de sprint ou anciens specs. À archiver ou supprimer si tu ne t’en sers plus.

| Fichier | Type |
|---------|------|
| `REPORT_SPRINT2.md` | Rapport généré / ancien sprint |
| `REPORT_SPRINT2_6.md`, `REPORT_SPRINT2_8.md`, `REPORT_SPRINT2_9.md` | Anciens rapports |
| `REPORT_SPRINT2.txt` | Idem |
| `REPORT_SPRINT3_COACH.md` | Rapport coach |
| `SPEC_PROJECT.md` | Spec projet (à garder si encore référence) |

Les docs dans `docs/` (AI_ADVISORY_LAYER, SCORING_*, CRITERES_*, etc.) sont utiles ; à garder.

---

## 5. Résumé des actions recommandées

1. **Supprimer (code mort)** : `app/providers/base.py`.
2. **Supprimer au choix** : `scripts/send_report_telegram.py`, `scripts/send_update_go_group.py` si tu ne les utilises plus.
3. **Optionnel** : déplacer ou supprimer les `REPORT_SPRINT*.md` et `REPORT_SPRINT2.txt` si tu veux alléger la racine du repo.
4. **Garder** : tout le reste (app/, services/, scripts utiles ou documentés, tests, docs/).

Si tu veux, on peut ne supprimer que le code mort (`base.py`) et laisser le reste en l’état pour l’instant.
