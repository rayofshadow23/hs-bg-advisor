# Esperimenti (versione dell'utente, non modificati)

Servivano a mettere a punto il matching delle carte. Hanno percorsi scritti a mano (`/home/ray/...`)
e leggono `minions.json` dell'app Android `bg-assistant`, che non fa parte di questo progetto.
La logica equivalente, con percorsi relativi e misurata sugli screenshot, e' in `vision/minions.py`;
per provarla su uno screenshot: `python tools/match_report.py shot.png`.
