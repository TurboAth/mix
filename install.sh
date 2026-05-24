#!/bin/bash
set -e

REPO="https://raw.githubusercontent.com/TurboAth/mix/main/mix.py"
DEST="$HOME/.local/bin/mix"

mkdir -p "$HOME/.local/bin"
curl -fsSL "$REPO" -o "$DEST"
chmod +x "$DEST"

# Add to PATH if not already there
SHELL_RC=""
case "$SHELL" in
  */zsh)  SHELL_RC="$HOME/.zshrc" ;;
  */fish) SHELL_RC="$HOME/.config/fish/config.fish" ;;
  *)      SHELL_RC="$HOME/.bashrc" ;;
esac

if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
  echo "Added ~/.local/bin to PATH in $SHELL_RC"
  echo "Run: source $SHELL_RC"
fi

echo "✓ mix installed → $DEST"
echo "Usage: mix CIA-2026-season-1-episode-3"
