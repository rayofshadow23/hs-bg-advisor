# Piano: overlay Android per Oppo Find X5

Obiettivo: la stessa funzione di oggi (leggere lo schermo, capire fase/oro/shop/board, suggerire la mossa)
ma **tutto sul telefono**, con i consigli disegnati sopra il gioco. Nessun tap automatico.

## Come funzionerebbe
| Pezzo | Soluzione su Android |
|---|---|
| Cattura schermo | `MediaProjection` + `ImageReader` (al posto di `adb screencap`): 5-10 fps, nessun cavo |
| Overlay | finestra `TYPE_APPLICATION_OVERLAY` (permesso "Mostra sopra altre app"), servizio in primo piano |
| Visione | stesse operazioni di oggi (maschere HSV, template matching, componenti connesse) con OpenCV Android |
| Numeri | **template delle cifre 0-9** invece di Tesseract (il font di Hearthstone e' fisso): piu' veloce, nessun binario esterno |
| Carte | stessa cross-correlazione con le 279 illustrazioni (incluse nell'APK, ~10 MB) |
| Advisor / actions | stessa logica di `advisor.py` e `actions.py` |

Il Find X5 (2400x1080, 20:9, Snapdragon 888) ha esattamente la risoluzione per cui `regions.yaml` e' calibrato.

## Tre strade
| | Cosa | Difficolta' | Tempo (part-time) |
|---|---|---|---|
| **A. Overlay + cervello sul PC** | l'app mostra solo i box/testi che il PC calcola (JSON via Wi-Fi o `adb reverse`) | bassa | 2-4 giorni |
| **B. Python sul telefono (Chaquopy)** | si riusa quasi tutto il codice Python in un'app Android minima; Kotlin solo per cattura e overlay | media | 1-2 settimane |
| **C. Riscrittura Kotlin nativa** | porting di visione + advisor | alta | 4-6 settimane |

**Consiglio: A come primo passo (valida overlay e cattura), poi B.** C solo se B e' troppo lenta o pesante.

## Fasi
0. **Digit templates (sul PC, prima di tutto).** Sostituire Tesseract con template delle cifre: serve per B/C e
   migliora anche la versione PC. Raccogliere cifre bianche/verdi da piu' screenshot.
1. **Prototipo cattura + overlay (Kotlin).** App con servizio in primo piano: chiede MediaProjection, mostra un
   rettangolo sopra il gioco, salva uno screenshot per verificare che Hearthstone non blocchi la cattura.
2. **Strada A**: invio dei frame/risultati al PC e disegno dei box e dei consigli sul telefono.
3. **Strada B**: integrazione Chaquopy (numpy + opencv), `main.read_state` chiamato dal servizio, misura dei tempi
   (obiettivo: < 400 ms per ciclo).
4. **Rifinitura ColorOS**: esclusione dal risparmio batteria, avvio automatico, widget per start/stop, tema scuro.
5. **Opzionale**: sidebar dei consigli come nella GUI PC, vibrazione quando c'e' una tripla.

## Rischi e punti da verificare
- **FLAG_SECURE**: se Hearthstone lo imposta la cattura e' nera. Le foto dello schermo che hai fatto fanno pensare
  di no; si verifica in fase 1.
- **L'overlay finisce nella cattura**: il frame contiene anche i box disegnati. Si risolve nascondendo l'overlay
  un istante durante la cattura o disegnando solo cornici sottili fuori dalle regioni lette.
- **Consenso a ogni avvio**: da Android 14 `MediaProjection` richiede il permesso a ogni sessione.
- **ColorOS e batteria**: servono "Mostra sopra altre app", "Avvio automatico" e nessuna ottimizzazione batteria,
  altrimenti il servizio viene ucciso. Anche "Assistente giochi" di Oppo puo' interferire.
- **Prestazioni e calore**: gioco + visione sullo stesso telefono; mitigare con 2-3 cicli al secondo e lettura
  solo quando il frame e' stabile.
- **Termini di Blizzard**: leggere lo schermo e disegnare un overlay non invia input, ma un'app di terze parti
  sopra il gioco non e' garantita da regole esplicite. Nessun tap automatico (un `AccessibilityService`
  che tocca lo schermo e' il passo che rende reale il rischio di ban).
- **Calibrazione**: le regioni sono per 2000x900; Android riporta 2400x1080, stessa proporzione, ridimensionare.

## Cosa serve da te
- Versione di Android/ColorOS del telefono (Impostazioni > Info sul telefono).
- Uno screenshot **fatto dal telefono** (tasto volume + power) in partita, per vedere formato e risoluzione reali.
- Android Studio sul PC (o solo la riga di comando con Gradle): lo installiamo nella fase 1.
