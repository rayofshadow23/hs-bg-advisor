# hs-bg-advisor

Assistente per Hearthstone Battlegrounds: legge lo schermo del telefono Android (via adb) con OpenCV +
Tesseract e suggerisce la mossa a terminale. **Non invia mai tap**: osserva e basta.

## Setup
1. Telefono: Opzioni sviluppatore > Debug USB, collega al PC. `adb devices` deve mostrarlo.
2. `pip install -r requirements.txt` e installa `tesseract-ocr` di sistema.
3. Database carte: `cards.json` (279 carte) piu' le illustrazioni 256x256 in `data/card_art/<id>.jpg`
   (oppure in una cartella indicata da `$HS_BG_CARD_ART`). `python tools/build_card_db.py` li rigenera da
   HearthstoneJSON (serve la rete, una volta per stagione). Senza illustrazioni i minion compaiono come "?".
4. Avvia l'advisor:
   - `python main.py`: output solo a riga di comando sul terminale.
   - `python main.py --gui`: **overlay visivo a video** con finestra grafica che mostra lo streaming del gioco ed evidenzia direttamente sullo schermo i minion da comprare (core, add-on, triple), il tasto taverna e l'HUD di stato.

Il telefono deve essere 20:9 in orizzontale: `capture.py` porta ogni frame a 2000x900 e le coordinate
in `vision/regions.yaml` sono calibrate su quella risoluzione. Per verificarle su un tuo screenshot:
`python tools/calibrate.py shot.png` scrive `calibration.png` con tutti i rettangoli sovrapposti.

## Cosa legge oggi (verificato su screenshot reali in `tests/fixtures/`)
| Dato | Come |
|---|---|
| Fase (acquisto / combattimento) | template del pulsante reroll di Bob e della targhetta "Combat" |
| Oro e oro massimo | OCR cifra per cifra; lo 0 con template; senza "/" il massimo e' 10 (ipotesi, 1 screenshot) |
| Turno | non e' sullo schermo: oro massimo = turno + 2 (fino al 7), poi si contano i combattimenti |
| Livello taverna | si contano le stelle del badge (1-4 verificate) |
| Costo upgrade, vita, armatura | OCR con preparazione dedicata per regione |
| Carte dello shop | stendardi viola (anche incantesimi, riconosciuti dall'assenza della goccia della vita); fino a 6 |
| Minion sul board | gocce rosse come indizio + griglia centrata a passo costante; fino a 4 verificati |
| Nome dei minion | cross-correlazione del centro della carta con l'illustrazione (scala 165, meta' risoluzione), soglia 0.65, filtro per tier, cache; 18 carte reali su 18 giuste |

## Ancora da fare / non verificato
- Nomi dei minion: verificati su 18 carte reali (punteggi 0.82-0.94). Non riconosciute: una demone verde
  (0.35-0.47, probabilmente non e' nel db), il fumo viola di un'animazione (ritaglio piatto, scartato).
  Velocita': 27 ms a carta al tier 1, ~250 ms al tier 4-5 con il filtro di tier; senza filtro ~0.3 s.
- Mano (in basso a destra, tagliata dal bordo): regione definita ma non letta.
- Board con 5-7 minion e shop a 7 carte: il passo della griglia e' misurato solo con 1, 2 e 4 minion.
- Timer: l'OCR lo legge male, non usato.
- Soglie dei template (fase, zero) calibrate su pochi frame: piu' screenshot le renderebbero affidabili.

## Comp e carte chiave
`data/comps.json` contiene le comp della tier list HSReplay (tier, difficolta', quando committare, carte
core e add-on). Per aggiornarlo a ogni patch: esporta la pagina in markdown e lancia
`python tools/parse_hsreplay_comps.py export.md`. L'advisor segnala le carte dello shop che sono core
(peso pieno) o add-on (meta') di una comp forte, o di una comp gia' avviata sul board.

## Test
`pytest` (29 test, solo la cartella `tests/`; i test OCR si saltano se `tesseract` non e' installato).

## Strumenti
- `tools/calibrate.py shot.png`: overlay delle regioni e delle carte individuate.
- `tools/match_report.py shot.png [...] [--sheet tavola.png]`: nomi riconosciuti e tavola ritaglio/illustrazione.
- `tools/parse_hsreplay_comps.py`, `tools/build_card_db.py`: dati (comp HSReplay, carte e illustrazioni).
- `tools/experiments/`: i tuoi script di prova, non modificati (percorsi `/home/ray/...`).
