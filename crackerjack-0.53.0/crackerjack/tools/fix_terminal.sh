#!/bin/bash
# Terminal Recovery Script for Crackerjack Monitor Issues
# Run this if your terminal gets stuck after quitting the monitor

echo "🔧 Restoring terminal state after Crackerjack Monitor..."

# Comprehensive terminal restoration sequence (matches enhanced_progress_monitor.py)
printf "\033[?1049l"  # Exit alternate screen buffer (CRITICAL)
printf "\033[?1000l"  # Disable mouse tracking
printf "\033[?1003l"  # Disable all mouse events
printf "\033[?1015l"  # Disable urxvt mouse mode
printf "\033[?1006l"  # Disable SGR mouse mode
printf "\033[?25h"    # Show cursor
printf "\033[?1004l"  # Disable focus events
printf "\033[?2004l"  # Disable bracketed paste mode
printf "\033[?7h"     # Enable line wrap
printf "\033[0m"      # Reset all attributes
printf "\r"           # Carriage return

# Restore terminal input modes
stty echo icanon icrnl ixon 2>/dev/null || stty sane 2>/dev/null

# Final reset
reset 2>/dev/null || clear

echo ""
echo "✅ Terminal restored! You should now have:"
echo "   - Command history working (↑/↓ keys)"
echo "   - Normal character input"
echo "   - Visible cursor"
echo "   - Proper line editing"
echo ""
echo "If issues persist, try: source ~/.bashrc (or ~/.zshrc)"
