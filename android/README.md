# HS BG Advisor (Android Standalone & Overlay)

Assistente per Hearthstone Battlegrounds funzionante **100% standalone sullo smartphone** (nessun PC, nessun cavo, nessun server esterno) oppure come client overlay connesso al PC.

---

## 📱 Architettura Standalone (Strada B)

L'app esegue l'intera pipeline di analisi direttamente sul dispositivo:
1. **Cattura Schermo**: API `MediaProjection` di Android in background (~2-3 FPS).
2. **Visione & Advisory**: Motore Python embedded (**Chaquopy** con OpenCV e NumPy ottimizzati per ARM64) che riconosce fase, taverna, oro, vita/armatura, shop e composizione della board.
3. **Disegno Overlay**: Finestra trasparente non-intrusiva (`TYPE_APPLICATION_OVERLAY`) che mostra HUD laterale, marcatori sulle carte consigliate e pannello tattico.

```
+-------------------------------------------------------------+
|                     Android App (Kotlin)                    |
|                                                             |
|  [ MediaProjection API ] ---> Cattura schermo (2-3 FPS)     |
|             |                                               |
|             v                                               |
|    [ AdvisorBridge ]  <---> [ Chaquopy (Python Runtime) ]    |
|             |               - vision/ (OpenCV puro)         |
|             |               - advisor.py & actions.py       |
|             v               - regions.yaml & templates/     |
|  [ OverlayService ]   ---> Disegna box & consigli a schermo |
|  (TYPE_APPLICATION_OVERLAY) (Zero tap / Non-intrusivo)      |
+-------------------------------------------------------------+
```

---

## 🚀 Come Compilare e Installare (con Android Studio)

### Prerequisiti
- **Android Studio** (Hedgehog, Iguana, Koala o successivo) con JDK 17.
- Dispositivo Android (es. Oppo Find X5 con Android 12/13/14).

### Istruzioni di Build
1. Apri **Android Studio** e seleziona `Open` scegliendo la cartella `android/` del repository.
2. Attendi che Gradle sincronizzi le dipendenze e configuri Chaquopy (scaricherà i wheel precompilati di OpenCV e NumPy per Android).
3. Collega lo smartphone via cavo USB con **Debug USB** abilitato (in *Opzioni Sviluppatore*).
4. Seleziona il tuo dispositivo nel menu a tendina in alto e premi il pulsante **Run** (`Shift + F10` o icona Play verde).

---

## ⚙️ Configurazione Permessi su Smartphone (ColorOS / Oppo Find X5)

Per garantire che il servizio non venga interrotto da ColorOS durante le sessioni di gioco:

1. **Mostra sopra altre app**:
   - Apri l'app **HS BG Advisor** e tocca `1. Permesso 'Mostra sopra altre app'` -> Abilita.
2. **Disattivazione Risparmio Batteria**:
   - Tocca `2. Disattiva risparmio batteria` -> Seleziona **Senza restrizioni** (o *Nessuna ottimizzazione*).
   - In *Impostazioni > Gestione app > HS BG Advisor*: abilita **Avvio automatico** e **Consenti attività in background**.
3. **Avvio Sessione di Gioco**:
   - Tocca `3. Avvia Advisor` e conferma il popup di condivisione schermo (`MediaProjection`).
   - Apri Hearthstone Battlegrounds e gioca in orizzontale.
   - Per resettare lo stato a inizio partita o fermare l'overlay, usa i pulsanti rapidi nella notifica permanente in alto.

---

## 🖥️ Modalità PC Client (Alternativa Opzionale)

Se desideri eseguire il calcolo sul PC per risparmiare batteria sul telefono:
1. Nell'app seleziona **Modalità PC Client**.
2. Sul PC avvia:
   ```bash
   adb reverse tcp:8765 tcp:8765
   python main.py --serve
   ```
3. Nell'app tocca **Avvia Advisor**.
