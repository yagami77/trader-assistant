# MT5 en session 0 (portable, connecté au broker)

Le bridge NSSM tourne en **session 0**. Pour qu’il reçoive les ticks et que `/health` + `/tick` répondent, **MT5 doit tourner en session 0 ET être connecté au compte broker**. En session SYSTEM, le terminal installé classique n’a pas le profil utilisateur → pas de connexion → 503.

**Solution : MT5 en mode portable** dans `C:\MT5Portable`, avec connexion + auto-login enregistrés une fois. La tâche au démarrage lance ce même binaire en session 0.

---

## 1. Créer le MT5 portable (une fois, en Admin)

```powershell
cd C:\trader-assistant-core
.\scripts\setup_mt5_portable.ps1
```

Cela copie l’installation MT5 depuis `C:\Program Files\MetaTrader 5` vers `C:\MT5Portable`.

---

## 2. Connexion au broker + auto-login (une fois, à la main)

**Une seule instance MT5** : fermez tout MT5 (y compris session utilisateur) avant.

1. Lancez : **`C:\MT5Portable\terminal64.exe`** avec l’argument **`/portable`**  
   (ou créez un raccourci : cible `C:\MT5Portable\terminal64.exe`, argument `/portable`, “Commencer dans” `C:\MT5Portable`).
2. Dans MT5 : **Fichier → Connexion au compte de trading** (ou équivalent).
3. Connectez-vous au **compte broker** (login / mot de passe).
4. **Activez “Connexion automatique”** (ou équivalent) pour que la session 0 se connecte au redémarrage.
5. Vérifiez qu’un **graphique** (ex. XAUUSD) reçoit bien les **ticks**.
6. Fermez MT5. Les paramètres (dont auto-login) sont enregistrés dans `C:\MT5Portable`.

Ensuite, la tâche planifiée lancera **`C:\MT5Portable\terminal64.exe` /portable** en session 0 (SYSTEM) et utilisera ce même profil → connexion automatique.

---

## 3. Tâche au démarrage (déjà configurée)

La tâche **MT5-AtStartup-Session0** est installée par :

```powershell
.\scripts\install_mt5_at_system_startup.ps1
```

Elle exécute le batch qui lance **`C:\MT5Portable\terminal64.exe` /portable** après 30 s (compte SYSTEM, session 0).  
Aucune autre instance MT5 ne doit être lancée (pas de MT5 dans le démarrage utilisateur, pas de double-clic sur un autre terminal).

---

## 4. Vérifications après redémarrage

```powershell
cd C:\trader-assistant-core
.\scripts\test_bridge.ps1
```

Résultat attendu :

- **Sessions** : un seul **terminal64** en **SessionId: 0**, bridge (python) en **SessionId: 0**.
- **/ping** → 200  
- **/health** → 200 (plus de 503)  
- **/tick** → 200 avec bid/ask (ex. XAUUSD)

Si `/health` reste 503 : MT5 portable pas encore lancé en session 0, ou auto-login pas fait dans `C:\MT5Portable`.

---

## 5. Redémarrage prod (bridge + core)

Après modification de code ou pour tout redémarrer proprement :

```powershell
cd C:\trader-assistant-core\deploy\windows
.\restart_prod.ps1
```

Cela redémarre mt5-bridge, trader-core, trader-runner (NSSM). **MT5** est lancé par la tâche au démarrage ; inutile de le relancer à la main.

---

## Rappel

- **Une seule instance MT5** : celle en session 0 (portable).
- Ne pas lancer MT5 depuis le bureau ou le dossier de démarrage utilisateur.
- Si deux processus MT5 apparaissent : `.\scripts\kill_mt5_user_session.ps1` pour fermer celui en session utilisateur.
