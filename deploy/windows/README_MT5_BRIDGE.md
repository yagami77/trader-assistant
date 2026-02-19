# Bridge MT5 — configuration NSSM (comme avant)

Le bridge tourne en **service NSSM** (port 8080). Pour qu’il voie MT5, **MT5 doit tourner en session 0** (même session que les services).

**MT5 doit aussi être connecté au broker** (sinon `/health` et `/tick` restent 503). En session 0 (SYSTEM), le terminal installé classique n’a pas le profil utilisateur. → **Config MT5 portable** : voir **[MT5_PORTABLE_SESSION0.md](MT5_PORTABLE_SESSION0.md)** (dossier `C:\MT5Portable`, connexion + auto-login une fois, puis tâche au démarrage).

## Ce qui est en place

- **mt5-bridge**, **trader-core**, **trader-runner** = services NSSM.
- **restart_prod.ps1** redémarre les 3 services (init DB, reset trade, __pycache__, puis NSSM).

## Pour que le bridge voie MT5 après un redémarrage du VPS

Le bridge (service) est en **session 0**. MT5 lancé à la main après une connexion bureau est en **session utilisateur** → le bridge ne le voit pas.

**Solution : lancer MT5 au démarrage du système (session 0).**

Une seule fois, en **Administrateur** :

```powershell
cd C:\trader-assistant-core
.\scripts\install_mt5_at_system_startup.ps1
```

Cela crée une tâche planifiée : **MT5 est lancé au démarrage de Windows** (avant ouverture de session). Il tourne alors en session 0, comme le bridge, qui peut donc le voir.

**Important :** avec cette config, la fenêtre MT5 n’est **pas** visible quand tu te connectes en bureau à distance (elle est en session 0). Les données marché passent quand même par le bridge. Pour voir MT5 à l’écran, il faudrait une autre config (bridge en session utilisateur).

### Éviter deux MT5 (doublon)

Si MT5 est aussi dans le **Dossier de démarrage** Windows ou lancé à la main, une **deuxième** instance part en session utilisateur. Le bridge (session 0) ne parle qu’à l’instance en session 0 — d’où confusion ou erreurs.

- **À faire :** enlever MT5 du démarrage utilisateur (Paramètres Windows → Applications → Démarrage, ou supprimer le raccourci dans `Shell:Startup`).
- **Après un redémarrage**, si `check_mt5_session.ps1` montre 2 processus MT5 (un en session 0, un en session 2), fermer uniquement celui en session utilisateur :
  ```powershell
  .\scripts\kill_mt5_user_session.ps1
  ```
  Cela garde l’instance session 0 (celle du bridge) et ferme l’autre.

Après avoir exécuté le script une fois, à chaque redémarrage du VPS :

1. Windows démarre → la tâche lance MT5 (session 0).
2. Les services NSSM (mt5-bridge, trader-core, trader-runner) démarrent.
3. Le bridge et MT5 sont tous les deux en session 0 → le bridge voit MT5.

## Redémarrage propre (après modif de code)

```powershell
cd C:\trader-assistant-core
.\deploy\windows\restart_prod.ps1
```

Redémarre init DB, reset trade, les 3 services NSSM (mt5-bridge, trader-core, trader-runner) et fait le health check.
