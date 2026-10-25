# HS BG Overlay (Android) - strada A

L'app disegna sopra Hearthstone i consigli che il **PC** calcola. Il PC continua a catturare lo schermo con adb
e a fare visione + advisor; il telefono mostra solo il risultato. Nessun tap automatico: la finestra
dell'overlay e' non toccabile, i tocchi passano al gioco.

```
telefono --adb screencap--> PC (main.py --serve) --JSON /state--> app overlay sul telefono
```

## Cosa vedi
- **Sinistra** (HUD): turno, fase, oro, taverna, costo upgrade, vita. Se il PC non risponde lo dice.
- **Destra**: fino a 5 consigli, il primo e' il piu' importante.
- **Sopra lo shop**: un marcatore colorato sulle carte da comprare (`3x` tripla, `CORE`, `ADD-ON`, `TRIBU`).

Tutto e' disegnato fuori dalle zone che il PC legge (shop, board, oro, cifre), perche' `adb screencap` include
anche l'overlay. Se in futuro aggiungi elementi, tienili nei margini (x < 270 o x > 1690 su 2000x900).

## 1. Compilare l'app (una volta)
1. Installa **Android Studio** sul PC.
2. `File > Open` e scegli la cartella `android/` di questo repo; aspetta la sincronizzazione di Gradle.
3. Sul telefono: *Impostazioni > Info sul telefono*, tocca 7 volte "Numero build", poi *Opzioni sviluppatore >
   Debug USB* (gia' attivo se usi adb).
4. Collega il telefono, scegli il dispositivo in alto e premi **Run** (triangolo verde). L'app "HS BG Overlay" si installa.

> Questo codice e' stato scritto senza poterlo compilare (nessun SDK Android disponibile dove e' stato
> preparato). Se Android Studio segnala errori, incolla il messaggio e li correggo.

## 2. Permessi sull'Oppo (ColorOS)
- Apri l'app e tocca **1. Consenti 'Mostra sopra altre app'**, attiva l'interruttore.
- *Impostazioni > Batteria > HS BG Overlay*: "Consenti attivita' in background" / nessuna ottimizzazione,
  e in *Gestione app > Avvio automatico* abilitalo. Senza, ColorOS puo' chiudere il servizio.
- Su Android 13+ concedi anche le notifiche (serve per il servizio in primo piano).

## 3. Ogni sessione di gioco
Sul PC, nella cartella del progetto con il venv attivo:
```bash
adb reverse tcp:8765 tcp:8765      # il telefono raggiunge il PC via cavo come 127.0.0.1:8765
python main.py --serve             # cattura + visione + server JSON (aggiungi --gui se vuoi anche la finestra PC)
```
Sul telefono: apri l'app, **2. Avvia overlay**, poi apri Hearthstone (modalita' Battlegrounds, orizzontale).

Senza cavo (Wi-Fi): `python main.py --serve --serve-host 0.0.0.0`, poi nell'app metti
`http://IP_DEL_PC:8765/state` e collega il telefono via `adb connect` / debug wireless per la cattura.

## Provare l'overlay senza giocare
```bash
adb reverse tcp:8765 tcp:8765
python main.py --serve --image tests/fixtures/turn4_recruit.png   # pubblica uno stato fisso, Invio per chiudere
```
Avvia l'overlay sul telefono con qualsiasi app aperta: HUD e consigli compaiono ai margini.

## Formato JSON (`GET /state`)
`seq`, `base_size` [2000, 900], `phase`, `turn`, `gold`, `max_gold`, `tavern_tier`, `upgrade_cost`,
`hero_health`, `hero_armor`, `shop[]` e `board[]` (nome, tier, tribu', attacco, vita, `spell`, `rect`),
`tips[]` (testo, `action`, `card_index`, `role`, `score`, `comp`). Vedi `overlay_server.py`.

## Limiti noti
- Serve il PC acceso e collegato: e' la strada A, il telefono da solo e' la fase B del piano (`docs/ANDROID_PLAN.md`).
- Il PC cattura circa 1-2 volte al secondo: l'overlay segue con quel ritardo.
- Il telefono deve restare in orizzontale durante il gioco.
