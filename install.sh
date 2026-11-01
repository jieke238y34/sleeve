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

# Developer options, left out of --help: --sha256 HEX installs the release wheel (or the .whl in SLEEVE_SOURCE) only if
# its SHA-256 is HEX (from the web: curl ... | sh -s -- --sha256 HEX); SLEEVE_FROM=main installs the newest source
# instead of the newest release.
SHA256=""
UNINSTALL=""
while [ $# -gt 0 ]; do
    case "$1" in
        --help|-h) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        --uninstall) UNINSTALL=1 ;;
        --sha256)
            [ $# -ge 2 ] || fail "--sha256 needs the 64 hexadecimal digits of the wheel's SHA-256"
            SHA256=$(printf '%s' "$2" | tr 'A-F' 'a-f'); shift ;;
        --sha256=*) SHA256=$(printf '%s' "${1#--sha256=}" | tr 'A-F' 'a-f') ;;
        *) fail "unknown option $1 (try --help)" ;;
    esac
    shift
done
if [ -n "$SHA256" ]; then
    case "$SHA256" in
        *[!0-9a-f]*) fail "--sha256 must be 64 hexadecimal digits" ;;
    esac
    [ "${#SHA256}" -eq 64 ] || fail "--sha256 must be 64 hexadecimal digits"
    [ -z "$UNINSTALL" ] || fail "--sha256 goes with an install, not --uninstall"
fi

case "${UNINSTALL:-}" in
    1)
        rm -rf "$VENV"
        rm -f "$BIN/sleeve" "$APPS/$APP_ID.desktop" "$ICONS/$APP_ID.svg"
        command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" >/dev/null 2>&1 || true
        say "Sleeve is uninstalled. Your music, playlists and settings (~/.config/sleeve) were not touched."
        exit 0 ;;
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

# by visadaking (github.com/visadaking)
# --- optional KDE version info for the install log 
# Report detected KDE versions when available; missing tools must not stop installation.
kde_env() {
  local plasma fw qt

  plasma=$(plasmashell --version 2>/dev/null | awk 'NR==1{print $2}') || plasma=""
  [ -n "$plasma" ] || plasma=$(kwin_wayland --version 2>/dev/null | awk 'NR==1{print $2}') || plasma=""

  fw=$(kf6-config --version 2>/dev/null) || fw=""
  [ -n "$fw" ] || fw=$(pkg-config --modversion KF6CoreAddons 2>/dev/null) || fw=""
  [ -n "$fw" ] || fw=$(rpm -q --qf '%{VERSION}' kf6-kcoreaddons 2>/dev/null) || fw=""
  [ -n "$fw" ] || fw=$(dpkg-query -W -f='${Version}' libkf6coreaddons6 2>/dev/null) || fw=""
  [ -n "$fw" ] || fw=$(pacman -Q kf6-kcoreaddons 2>/dev/null | awk '{print $2}') || fw=""

  qt=$(qmake6 -query QT_VERSION 2>/dev/null) || qt=""
  [ -n "$qt" ] || qt=$(qtpaths6 --qt-version 2>/dev/null) || qt=""
  [ -n "$qt" ] || qt=$(pkg-config --modversion Qt6Core 2>/dev/null) || qt=""

  KDE_PLASMA="$plasma"
  KDE_FRAMEWORKS="$fw"
  KDE_QT="$qt"
}

kde_env_line() {
  if [ -z "${KDE_PLASMA:-}${KDE_FRAMEWORKS:-}${KDE_QT:-}" ]; then
    echo "KDE: not detected (non-KDE session or tools missing)"
  else
    echo "KDE: Plasma ${KDE_PLASMA:-?} | Frameworks ${KDE_FRAMEWORKS:-?} | Qt ${KDE_QT:-?}"
  fi
}

# --- where to install from: this checkout if there is one, else GitHub ---------------------------------------------------
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || true)
if [ -n "${SLEEVE_SOURCE:-}" ]; then SOURCE="$SLEEVE_SOURCE"
elif [ -n "$SHA256" ]; then SOURCE="$REPO_URL"             # a hash is for a downloaded wheel, never a checkout
elif [ -n "$HERE" ] && [ -f "$HERE/pyproject.toml" ] && [ -d "$HERE/sleeve" ]; then SOURCE="$HERE"
else SOURCE="$REPO_URL"; fi

# Straight from the web the default is the newest published release (what `sleeve --update` follows), so a normal
# install is never ahead of it. SLEEVE_FROM=main installs the newest source instead; no release, no curl or no network
# falls back to the source too. A checkout, or SLEEVE_SOURCE, is always installed as it is.
RELEASE_API="https://api.github.com/repos/jieke238y34/sleeve/releases/latest"
RELEASE_PREFIX="https://github.com/jieke238y34/sleeve/releases/download/"
latest_wheel() {
    command -v curl >/dev/null 2>&1 || return 1
    curl -fsSL --proto "=https" --proto-redir "=https" --max-time 20 -H "Accept: application/vnd.github+json" "$RELEASE_API" 2>/dev/null | "$PY" -c '
import json, sys
try:
    assets = json.load(sys.stdin).get("assets", [])
except ValueError:
    sys.exit(1)
for a in assets:
    url = a.get("browser_download_url", "")
    if url.startswith(sys.argv[1]) and url.endswith(".whl"):
        print(url)
        sys.exit(0)
sys.exit(1)' "$RELEASE_PREFIX"
}
RELEASE=""
if [ "$SOURCE" = "$REPO_URL" ] && [ "${SLEEVE_FROM:-release}" != "main" ]; then
    RELEASE=$(latest_wheel) || RELEASE=""
    if [ -n "$RELEASE" ]; then SOURCE="$RELEASE"
    elif [ -n "$SHA256" ]; then fail "--sha256 needs a release wheel, and none could be fetched"
    else say "note: no published release could be fetched; installing the newest source instead"; fi
fi

WORK=""
trap '[ -z "$WORK" ] || rm -rf "$WORK"' EXIT
# --sha256: download the wheel, compare its SHA-256 with the one given and install that very file, or nothing at all.
if [ -n "$SHA256" ]; then
    case "$SOURCE" in
        *.whl) ;;
        *) fail "--sha256 checks a wheel: use it with the release (no SLEEVE_SOURCE) or SLEEVE_SOURCE=<a .whl file or address>" ;;
    esac
    WORK=$(mktemp -d)
    case "$SOURCE" in
        https://*) command -v curl >/dev/null 2>&1 || fail "curl is needed to download the wheel"
                   curl -fsSL --proto "=https" --proto-redir "=https" --max-time 300 -o "$WORK/${SOURCE##*/}" "$SOURCE" || fail "could not download $SOURCE" ;;
        *) [ -f "$SOURCE" ] || fail "no such file: $SOURCE"
           cp "$SOURCE" "$WORK/${SOURCE##*/}" ;;
    esac
    GOT=$("$PY" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$WORK/${SOURCE##*/}")
    [ "$GOT" = "$SHA256" ] || fail "the wheel does not match the SHA-256 you gave, so nothing was installed (it is $GOT)"
    say "The SHA-256 matches."
    SOURCE="$WORK/${SOURCE##*/}"
fi

# Installing from the web: fetch the repository (history only, no old file contents) so the build number can be counted
# and stamped, exactly as for a checkout. Without git the install still works, it just shows the version alone.
if [ "$SOURCE" = "$REPO_URL" ] && command -v git >/dev/null 2>&1; then
    WORK=$(mktemp -d)
    if git clone -q --filter=blob:none "${REPO_URL#git+}" "$WORK/sleeve" 2>/dev/null; then SOURCE="$WORK/sleeve"
    else say "note: could not fetch the repository with git; the build number will not be shown"; fi
fi

say "Installing Sleeve from $SOURCE"
say "(this downloads Qt, about 200 MB, the first time)"
# Stamp the build number when the source is a git checkout (a local one, or the clone above), so --version, Settings
# and the updater all know it. A source that is not a git checkout (a tarball) is left alone.
if [ "$SOURCE" != "$REPO_URL" ] && [ -z "$RELEASE" ] && [ -d "$SOURCE/.git" ]; then
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
