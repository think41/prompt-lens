#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_ROOT/.venv"

# --- uv check ---
if ! command -v uv &>/dev/null; then
    echo "[PromptLens] uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# --- venv + deps ---
echo "[PromptLens] Creating venv at $VENV..."
uv venv "$VENV" --python 3.11

echo "[PromptLens] Installing dependencies..."
uv pip install --python "$VENV/bin/python" -r "$REPO_ROOT/backend/requirements.txt"

# --- developer ID ---
echo "[PromptLens] Generating developer ID..."

if [[ "$(uname)" == "Darwin" ]]; then
    MACHINE_UUID=$(system_profiler SPHardwareDataType | awk '/UUID/ { print $3 }')
elif [[ -f /etc/machine-id ]]; then
    MACHINE_UUID=$(cat /etc/machine-id)
else
    MACHINE_UUID=$(hostname)
fi

DEVELOPER_ID=$(echo -n "$MACHINE_UUID" | "$VENV/bin/python" -c "import hashlib,sys; print(hashlib.sha256(sys.stdin.read().encode()).hexdigest())")

# --- shell env ---
SHELL_RC=""
if [[ -f "$HOME/.zshrc" ]]; then
    SHELL_RC="$HOME/.zshrc"
elif [[ -f "$HOME/.bashrc" ]]; then
    SHELL_RC="$HOME/.bashrc"
fi

set_env() {
    local key="$1" val="$2"
    if [[ -n "$SHELL_RC" ]]; then
        if grep -q "export ${key}=" "$SHELL_RC" 2>/dev/null; then
            sed -i.bak "s|export ${key}=.*|export ${key}=${val}|" "$SHELL_RC"
            rm -f "${SHELL_RC}.bak"
        else
            echo "export ${key}=${val}" >> "$SHELL_RC"
        fi
    fi
    export "${key}=${val}"
}

set_env PROMPTLENS_DEVELOPER_ID "$DEVELOPER_ID"
set_env PROMPTLENS_ENDPOINT "http://localhost:8000"
set_env PROMPTLENS_TEAM_ID "default"

echo ""
echo "[PromptLens] Setup complete."
echo "  venv:                    $VENV"
echo "  PROMPTLENS_DEVELOPER_ID: $DEVELOPER_ID"
echo ""
echo "Activate venv:  source $VENV/bin/activate"
echo "Or restart shell: source ${SHELL_RC:-~/.bashrc}"
