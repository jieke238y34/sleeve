#!/bin/sh
# Install Sleeve for your user (no root needed): its own Python environment, a `sleeve` command, an icon and a
# launcher entry. Run it from a copy of the repository, or straight from the web:
#
#   curl -fsSL https://raw.githubusercontent.com/jieke238y34/sleeve/main/install.sh | sh
#
# Options:  --uninstall   remove what this script installed (your music, playlists and settings are left alone)
#           --help
# Environment: SLEEVE_PREFIX (default ~/.local/share/sleeve), SLEEVE_SOURCE (a folder or git URL to install from)
set -eu

APP_ID="io.github.jieke238y34.Sleeve"
REPO_URL="git+https://github.com/jieke238y34/sleeve"
PREFIX="${SLEEVE_PREFIX:-$HOME/.local/share/sleeve}"
VENV="$PREFIX/venv"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"

say() { printf '%s\n' "$*"; }
fail() { printf 'Sleeve install: %s\n' "$*" >&2; exit 1; }

case "${1:-}" in
    --help|-h) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --uninstall)
        rm -rf "$VENV"
        rm -f "$BIN/sleeve" "$APPS/$APP_ID.desktop" "$ICONS/$APP_ID.svg"
        command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" >/dev/null 2>&1 || true
        say "Sleeve is uninstalled. Your music, playlists and settings (~/.config/sleeve) were not touched."
        exit 0 ;;
    "") ;;
    *) fail "unknown option $1 (try --help)" ;;
esac

# --- Python 3.10 or newer --------------------------------------------------------------------------------------------
PY=""
for candidate in python3 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        PY="$candidate"; break
    fi
done
[ -n "$PY" ] || fail "Python 3.10 or newer is needed. Fedora: sudo dnf install python3 · Debian/Ubuntu: sudo apt install python3 python3-venv"
"$PY" -c 'import venv, ensurepip' 2>/dev/null || fail "Python's venv module is missing. Debian/Ubuntu: sudo apt install python3-venv"

# --- where to install from: this checkout if there is one, else GitHub ---------------------------------------------------
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || true)
if [ -n "${SLEEVE_SOURCE:-}" ]; then SOURCE="$SLEEVE_SOURCE"
elif [ -n "$HERE" ] && [ -f "$HERE/pyproject.toml" ] && [ -d "$HERE/sleeve" ]; then SOURCE="$HERE"
else SOURCE="$REPO_URL"; fi

say "Installing Sleeve from $SOURCE"
say "(this downloads Qt, about 200 MB, the first time)"
# Stamp the build number when installing from a checkout, so --version and the updater report a truth. A source
# that is not a git checkout (a tarball) is left alone.
if [ "$SOURCE" != "$REPO_URL" ] && [ -d "$SOURCE/.git" ]; then
    "$PY" "$SOURCE/tools/stamp_build.py" || say "note: could not stamp the build number into the copy"
fi
mkdir -p "$PREFIX" "$BIN" "$APPS" "$ICONS"
"$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
# shellcheck disable=SC2086
"$VENV/bin/python" -m pip install --quiet ${SLEEVE_PIP_ARGS:-} "$SOURCE"

# --- command, icon, launcher entry ---------------------------------------------------------------------------------------
ln -sf "$VENV/bin/sleeve" "$BIN/sleeve"
ICON_SRC=$("$VENV/bin/python" -c 'import pathlib, sleeve; print(pathlib.Path(sleeve.__file__).parent / "data" / "sleeve.svg")')
[ -f "$ICON_SRC" ] && cp "$ICON_SRC" "$ICONS/$APP_ID.svg"
cat > "$APPS/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Sleeve
GenericName=Music Player
Comment=Music library, player and sync dashboard
Exec=$VENV/bin/sleeve
Icon=$APP_ID
Terminal=false
Categories=AudioVideo;Audio;Player;Qt;
Keywords=music;player;library;playlist;
StartupWMClass=sleeve
Actions=PlayPause;Next;Previous;

[Desktop Action PlayPause]
Name=Play / Pause
Exec=$VENV/bin/sleeve --play-pause

[Desktop Action Next]
Name=Next song
Exec=$VENV/bin/sleeve --next

[Desktop Action Previous]
Name=Previous song
Exec=$VENV/bin/sleeve --previous
EOF
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

say ""
say "Sleeve is installed. Start it from your application menu, or run: sleeve"
case ":$PATH:" in *":$BIN:"*) ;; *) say "(add $BIN to your PATH to use the 'sleeve' command in a terminal)" ;; esac

# --- optional helpers: say what is missing, never install anything without being asked --------------------------------
missing=""
command -v pactl >/dev/null 2>&1 || missing="$missing pactl (volume above 100%)"
command -v ffmpeg >/dev/null 2>&1 || missing="$missing ffmpeg (same-volume levelling)"
if [ -n "$missing" ]; then
    say ""
    say "Optional, not installed:$missing"
    if command -v dnf >/dev/null 2>&1; then say "  Fedora:        sudo dnf install pulseaudio-utils ffmpeg-free"
    elif command -v apt >/dev/null 2>&1; then say "  Debian/Ubuntu: sudo apt install pulseaudio-utils ffmpeg"
    elif command -v pacman >/dev/null 2>&1; then say "  Arch:          sudo pacman -S libpulse ffmpeg"
    fi
fi
