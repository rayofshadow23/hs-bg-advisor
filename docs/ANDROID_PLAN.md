# Android: piano e stato (Oppo Find X5)

Obiettivo: la stessa funzione della versione PC (leggere lo schermo, capire fase/oro/shop/board, suggerire la mossa) con i consigli disegnati sopra il gioco. Nessun tap automatico.

## Stato

| Fase | Cosa | Stato |
|---|---|---|
| 0 | Template delle cifre 0-9 al posto di Tesseract (`vision/templates/digits/`) | fatto |
| 1 | Prototipo overlay + cattura (Kotlin): servizio in primo piano, finestra non toccabile | fatto |
| 2 | **Strada A**: il PC fa la visione, il telefono disegna (`main.py --serve`, `GET /state`, `run_overlay.sh`) | fatto, provato |
| 3 | **Strada B**: tutto sul telefono (MediaProjection + Python embedded con Chaquopy, `standalone_engine.py`) | fatto, in uso su Oppo Find X5 |
| 4 | Rifinitura ColorOS (batteria, avvio automatico, notifica con "Nuova Partita" / "Ferma") | fatto in parte: dipende da ColorOS |
| 5 | Consigli di gioco sul telefono: impegno su comp/tribù, "Cerca", vendita a board pieno, marcatori `3x/CORE/ADD-ON/TRIBU/VENDI` | fatto |

Dettagli d'uso e di build in [`android/README.md`](../android/README.md).

## Com'è fatto

| Pezzo | Soluzione |
|---|---|
| Cattura | `MediaProjection` + `ImageReader` (~3 fps); in modalità PC `adb screencap` |
| Overlay | `TYPE_APPLICATION_OVERLAY` non toccabile, disegnato solo nei margini e in fasce libere (la cattura include l'overlay) |
| Visione | OpenCV (maschere HSV, template matching, componenti connesse), nessun OCR esterno |
| Python sul telefono | Chaquopy 15, Python 3.10, OpenCV 4.5.1 e NumPy; i sorgenti vengono copiati da Gradle in `app/src/main/python` |
| Carte | cross-correlazione con le 279 illustrazioni incluse nell'app |
| Advisor | stesso `advisor.py` del PC |

## Ancora da fare / da verificare

- **Board con 5-7 minion**: `locate_board` usa un passo fisso tra le carte; con 6-7 minion il gioco le stringe e i riquadri risultano sfasati (attacco e vita si leggono comunque, i nomi no). Servono screenshot a schermo intero per ricalibrare.
- **Mano e freeze** non letti: la vendita e le azioni legali li ignorano.
- **Prestazioni e batteria** in partita lunga: nessuna misura sistematica (tempo per frame, calore).
- **FLAG_SECURE / Android 14+**: la cattura funziona sul Find X5; altri telefoni e versioni di Android non provati. Da Android 14 il consenso alla registrazione schermo si chiede a ogni avvio.
- **Aggiornamento dei dati**: `data/comps.json` e `cards.json` vanno rigenerati a ogni patch (`tools/parse_hsreplay_comps.py`, `tools/build_card_db.py`); sull'app significa ricompilare.
- **Avviso Chaquopy**: il build usa un Python 3.12 sul PC e non precompila i `.pyc` (Chaquopy preferisce 3.10); l'app funziona, il primo avvio è un po' più lento.

## Rischi

- **Termini di Blizzard**: leggere lo schermo e disegnare un overlay non invia input, ma un'app di terze parti sopra il gioco non è garantita da regole esplicite. Nessun tap automatico: un `AccessibilityService` che tocca lo schermo è il passo che renderebbe concreto il rischio di ban (e andrebbe provato solo su un account secondario).
- **ColorOS** può chiudere i servizi in background: servono "Mostra sopra altre app", avvio automatico e nessuna ottimizzazione batteria.
- **L'overlay finisce nella cattura**: per questo i marcatori stanno fuori dalle zone lette. Elementi nuovi vanno disegnati nei margini (x < 270 o x > 1690 su 2000x900) o nelle fasce libere sopra le carte.

## Prossimi passi possibili

1. Ricalibrare la griglia del board con screenshot a 5-7 minion.
2. Leggere la mano e lo stato di freeze.
3. Funzione di valutazione dello stato e ricerca breve sulle azioni legali (`actions.py`) per scegliere la mossa in modo "matematico", sostituendo i punteggi scritti a mano.
4. Misure di prestazioni sul telefono e riduzione dei frame quando lo schermo non cambia.
