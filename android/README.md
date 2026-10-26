# HS BG Advisor per Android

L'app disegna sopra Hearthstone un overlay non toccabile (i tocchi arrivano al gioco): turno, oro, taverna e vita a sinistra, consigli a destra, marcatori sopra le carte da comprare (`3x`, `CORE`, `ADD-ON`, `TRIBU`) e `VENDI` sopra il minion del board da vendere. Tutto sta nei margini e in fasce libere, fuori dalle zone che la visione legge, perché la cattura include l'overlay.

Due modalità, scelte nell'app:

| Modalità | Cattura | Visione e consigli |
|---|---|---|
| **Standalone** | `MediaProjection` sul telefono (~3 fps) | Python embedded (Chaquopy) con OpenCV, nessun PC |
| **PC Client** | `adb screencap` dal PC | `python main.py --serve` sul PC, l'app interroga `GET /state` |

```
Standalone:  MediaProjection -> AdvisorBridge -> Chaquopy (standalone_engine.py) -> OverlayService
PC Client:   adb screencap -> main.py --serve -> JSON /state -> StatePoller -> OverlayService
```

## Compilare (da terminale, anche con VS Code)

1. Prerequisiti: `sudo apt install openjdk-17-jdk unzip wget` e l'SDK Android da riga di comando (`sdkmanager "platforms;android-34" "build-tools;34.0.0" "platform-tools"`, con `ANDROID_HOME` impostato).
2. Python **3.8-3.12 sul PC** per il build (Chaquopy 15 non funziona con la 3.13+). Se il tuo è più recente: `pip install uv && uv python install 3.12`.
3. Crea `android/local.properties` (non è nel repository, contiene percorsi del tuo PC):
   ```
   sdk.dir=/home/TUO_UTENTE/Android
   chaquopy.buildPython=/percorso/del/python3.12
   ```
   Il percorso si trova con `uv python find 3.12`; se `python3.12` è nel PATH, la seconda riga si può omettere.
4. Compila e installa:
   ```bash
   cd android
   ./gradlew assembleDebug
   adb install -r app/build/outputs/apk/debug/app-debug.apk
   ```
   Il primo build scarica Chaquopy, OpenCV e NumPy per Android: ci vogliono alcuni minuti. Gradle copia il motore Python (`*.py`, `vision/`, `data/`, `cards.json`) in `app/src/main/python` prima di ogni build.

Con Android Studio: `File > Open` sulla cartella `android/`, poi Run.

## Permessi (ColorOS / Oppo)

Nell'app, in ordine:
1. **Mostra sopra altre app**: abilita.
2. **Risparmio batteria**: "Senza restrizioni"; in *Impostazioni > App > HS BG Advisor* abilita Avvio automatico e attività in background, altrimenti ColorOS può chiudere il servizio.
3. Su Android 13+ consenti le notifiche (servono al servizio in primo piano).

## Uso

**Standalone**: scegli la modalità, tocca **Avvia Advisor**, conferma la condivisione dello schermo (si ripete a ogni avvio), apri Hearthstone in orizzontale. Dalla notifica puoi premere "Nuova Partita" (azzera turno e stato) o "Ferma".

**PC Client**: sul PC, con il venv attivo,
```bash
./run_overlay.sh [--gui]       # adb reverse tcp:8765 tcp:8765 + apre l'app + python main.py --serve
```
Nell'app scegli la modalità PC e tocca Avvia (indirizzo `http://127.0.0.1:8765/state`). Via Wi-Fi: `python main.py --serve --serve-host 0.0.0.0` e nell'app l'IP del PC.

Prova senza giocare: `python main.py --serve --image tests/fixtures/turn4_recruit.png`.

## Formato JSON (`GET /state`)

`seq`, `base_size` [2000, 900], `phase`, `turn`, `gold`, `max_gold`, `tavern_tier`, `upgrade_cost`, `hero_health`, `hero_armor`, `shop[]` e `board[]` (nome, tier, tribù, attacco, vita, `spell`, `rect`), `tips[]` (testo, `action`, `card_index`, `role`, `zone` = `shop` o `board`, `score`, `comp`). Vedi `overlay_server.py`.

## Limiti noti

- Il codice Kotlin è stato provato finora su un solo telefono (Oppo Find X5); il comportamento dell'overlay sopra Hearthstone dipende da ColorOS.
- Il telefono deve restare in orizzontale durante il gioco.
- Avvio lento al primo uso: Python e OpenCV si caricano una volta.
