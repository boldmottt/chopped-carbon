#!/usr/bin/env bash
# One-time setup for Forged Carbon Illustrator script.
# Installs the Python tool at ~/.forge_carbon/ and prepares an isolated venv.
set -euo pipefail

INSTALL_DIR="$HOME/.forge_carbon"
HERE="$(cd "$(dirname "$0")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found. Install Python 3.10+ first:"
    echo "  brew install python3"
    echo "  or  https://www.python.org/downloads/"
    exit 1
fi

echo "==> Installing to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
for item in forge_carbon forge_vectorize.py requirements.txt illustrator scripts; do
    src="$HERE/$item"
    if [ -e "$src" ]; then
        cp -R "$src" "$INSTALL_DIR/"
    fi
done

echo "==> Building AppleScript runner.app (Illustrator <-> shell bridge)"
if command -v osacompile >/dev/null 2>&1; then
    AS_SRC="$(mktemp /tmp/forged_runner.XXXXXX.applescript)"
    cat > "$AS_SRC" <<'APPLESCRIPT'
on run
    set homeDir to POSIX path of (path to home folder)
    set requestFile to homeDir & ".forge_carbon/request.sh"
    try
        do shell script "/bin/bash " & quoted form of requestFile
    end try
end run
APPLESCRIPT
    rm -rf "$INSTALL_DIR/runner.app"
    osacompile -o "$INSTALL_DIR/runner.app" "$AS_SRC"
    rm -f "$AS_SRC"
    echo "    runner.app: $INSTALL_DIR/runner.app"
else
    echo "    WARN: osacompile not found - JSX won't be able to invoke Python."
fi

echo "==> Setting up Python virtual environment"
cd "$INSTALL_DIR"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
./.venv/bin/pip install --upgrade pip --quiet --timeout 120 --retries 5
./.venv/bin/pip install --quiet --timeout 120 --retries 5 -r requirements.txt

JSX_SRC="$INSTALL_DIR/illustrator/forged_carbon.jsx"

echo
echo "==> Done."
echo
echo "JSX 위치: $JSX_SRC"
echo
echo "일러스트레이터에서 사용:"
echo "  File > Scripts > Other Script... 선택 -> 위 .jsx 선택"
echo
echo "자주 쓰려면 Illustrator Scripts 폴더에 복사 (관리자 비밀번호 필요할 수 있음):"
ILLU_DIRS=(/Applications/Adobe\ Illustrator\ */Presets.localized/*/Scripts)
for d in "${ILLU_DIRS[@]}"; do
    if [ -d "$d" ]; then
        echo "  sudo cp \"$JSX_SRC\" \"$d/\""
    fi
done
