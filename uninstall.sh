#!/bin/bash

DEST="$HOME/.local/bin/mix"
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

echo "Uninstalling mix..."

# Remove binary
if [ -f "$DEST" ]; then
  rm "$DEST"
  echo "✓ Removed $DEST"
else
  echo "  mix not found at $DEST (already uninstalled?)"
fi

# Remove PATH line from shell rc files
for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.config/fish/config.fish"; do
  if [ -f "$RC" ] && grep -qF "$PATH_LINE" "$RC"; then
    # portable in-place delete — works on both Linux and macOS
    grep -vF "$PATH_LINE" "$RC" > "$RC.tmp" && mv "$RC.tmp" "$RC"
    echo "✓ Removed PATH entry from $RC"
  fi
done

echo "Done. Restart shell or run: exec \$SHELL"
