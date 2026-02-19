# Messages Telegram — Exemple complet d’un setup A → Z

Récapitulatif de tous les messages possibles pendant la vie d’un trade (XAUUSD M15).

---

## A) GO — Lancement du setup

Déclenché quand le score est suffisant et que le système signale un GO.

```
🟦🟦🟦 GO BUY NOW ✅

XAUUSD (M15)

💰 Prix actuel MT5 (live) : 5027.50

➡️ Entrée : 5027.00
⛔ SL : 5012.00
🎯 TP1 : 5035.00 → Objectif principal (BE/fermé)
🎯 TP2 : 5048.00 🎁 Bonus (optionnel)

📋 SUIVI
• TP1 atteint → réduire 50%, SL à l'entrée (BE)
• TP2 atteint → fermer le reste
• SL touché → sortie complète

💎 Setup de qualité A+ ⚡
Score global : 92/100

Détails du score :
• Confluence H1 alignée (+10)
• Setup clair (+25)
...
```

---

## B) Suivi — MAINTIEN

Envoi à mi-chemin vers TP1 (une fois par trade) quand tout va bien.

```
🛫🟦 MAINTIEN BUY

Prix: 5031.00 | Entrée: 5027.00
SL: 5012.00 | TP1: 5035.00 | TP2: 5048.00
Plan inchangé, structure OK, pas de mur proche, objectif TP maintenu.
```

---

## C) Suivi — Message de situation

Envoi périodique (toutes les 2 min, si changement) pendant que le trade est actif.

```
📊 Suivi — Trade actif depuis 15 min

Prix: 5031.00 | Entrée: 5027.00 | +4.0 pts
SL: 5012.00 | TP1: 5035.00

H1: BULLISH (avec nous) | M15: structure OK

Score marché: 85/100

Analyse: Tout va bien, on est dans le bon sens.

➡️ On va vers TP1, laisser courir.
```

---

## D) Suivi — ALERTE (mur / faiblesse)

Quand structure M15, S/R ou pattern contre détecté.

**Version gain &lt; 5 pts :**
```
⚠️ ALERTE — Mur / faiblesse proche

Prix: 5029.00 | Entrée: 5027.00 | SL: 5012.00 | TP1: 5035.00
Surveiller le trade, zone sensible, mais pas encore de marge pour passer BE.
```

**Version gain ≥ 5 pts :**
```
⚠️ ALERTE — Attention mur / faiblesse

Prix: 5032.00 | Entrée: 5027.00 | SL: 5012.00 | TP1: 5035.00
Gain actuel ≈ 5.0 pts — sécurisation conseillée (BE / partiel).
```

**Version news HIGH imminente :**
```
⚠️ ALERTE — News HIGH imminente

Prix: 5032.00 | SL: 5012.00 | TP1: 5035.00
Sécurisation conseillée (BE / partiel).
```

---

## E) TP1 atteint — Break-even (BE_ENABLED=true)

Quand le prix atteint TP1 et que BE automatique est activé.

```
🎉 Bravo ! TP1 atteint

✅ SL passé à Break-even — sécurisation en place

🟦 BUY XAUUSD
━━━━━━━━━━━━━━━━━━
➡️ Entrée : 5027.00
⛔ SL (BE) : 5027.00
🎯 TP2 : 5048.00

💰 +8.0 pts réalisés (TP1)

📈 On laisse courir vers TP2 !
```

---

## F) Suivi post-TP1 (vers TP2)

Après BE, le message de situation utilise le nouveau SL.

```
📊 Suivi — Trade actif depuis 45 min

Prix: 5042.00 | Entrée: 5027.00 | +15.0 pts
SL: 5027.00 | TP1: 5035.00

H1: BULLISH (avec nous) | M15: structure OK

➡️ On va vers TP1, laisser courir.
```

---

## G) SORTIE — TP2 atteint

Le trade se termine en profit.

```
🎉 Bravo ! TP2 atteint

📊 Résultat du trade: PROFIT +21.0 point

Prix: 5048.00 | TP2: 5048.00
Trade réussi, objectif bonus. À la prochaine !
```

---

## H) SORTIE — SL touché

Le trade se termine en perte (ou au BE si SL a été déplacé).

```
😔 SL touché — trade raté

📊 Résultat du trade: PERTE — 15.0 point

Prix: 5012.00 | SL: 5012.00
On va récupérer dans la journée, on va faire mieux !
Trade clôturé. Prochaine opportunité.
```

---

## I) Clôture manuelle

Quand tu fermes le trade manuellement et appelles `POST /trade/manual-close`.

**Profit :**
```
✅ Trade clôturé manuellement

Résultat du trade : PROFIT +12.0 point

Tu peux enchaîner sur un autre trade.
```

**Perte :**
```
✅ Trade clôturé manuellement

Résultat du trade : PERTE 8.0 point

Tu peux enchaîner sur un autre trade.
```

---

## J) Autres messages possibles (hors setup)

**Pré-alerte news :**
```
🟠 PRÉ-ALERTE XAUUSD (M15)
📰 News: FOMC Minutes (HIGH)
⏳ Moment pré-event — dans 25 min — horizon 60 min
⚠️ Attention à la volatilité autour de la publication.
```

**NO GO (exemple) :**
```
🟦🟦🟦 BUY — NO GO ❌

XAUUSD (M15)
Bloqué par : RR_TOO_LOW
...

Score global : 65/100
```

**Données marché de retour :**
```
🟢 Données marché de retour — tu peux reprendre en temps réel.
```

**Résumé du jour :**
```
📊 Résumé du jour — 2 trade(s)

...
Total: +18.5 point
```

---

## Ordre typique d’un setup réussi (A → Z)

1. **A** — GO BUY NOW
2. **B** ou **C** — MAINTIEN ou message de situation (plusieurs fois possible)
3. **D** — ALERTE (optionnel, si zone sensible)
4. **E** — TP1 atteint, SL passé à BE
5. **F** — Suivi situation (post-TP1, vers TP2)
6. **G** — TP2 atteint → clôture

## Ordre typique si SL touché

1. **A** — GO
2. **B** / **C** — Suivi
3. **H** — SL touché → clôture

## Ordre si clôture manuelle

1. **A** — GO
2. … suivi …
3. **I** — Trade clôturé manuellement
