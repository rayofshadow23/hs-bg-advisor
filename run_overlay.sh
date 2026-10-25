#!/usr/bin/env bash
# Avvia tutto per l'overlay: collega la porta, apre l'app sul telefono e lancia il lettore con il server JSON.
# Uso: ./run_overlay.sh [opzioni di main.py, es. --gui]
set -e
cd "$(dirname "$0")"
[ -f .venv/bin/activate ] && source .venv/bin/activate
adb get-state >/dev/null 2>&1 || { echo "Nessun telefono: collega il cavo e abilita il debug USB (adb devices)"; exit 1; }
adb reverse tcp:8765 tcp:8765
adb shell am start -n it.ray.hsoverlay/.MainActivity >/dev/null
echo "App aperta sul telefono: tocca '2. Avvia overlay' (solo la prima volta dopo ogni riavvio dell'app), poi apri Hearthstone."
exec python main.py --serve "$@"
