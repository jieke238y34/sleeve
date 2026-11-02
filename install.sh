#!/bin/sh
# Install Sleeve for your user (no root needed): its own Python environment, a `sleeve` command, an icon and a
# launcher entry. Run it from a copy of the repository, or straight from the web:
#
#   curl -fsSL https://raw.githubusercontent.com/jieke238y34/sleeve/main/install.sh | sh
#
# Options:  --uninstall   remove what this script installed (your music, playlists and settings are left alone)
#           --dev         install the newest code on the main branch instead of the newest release, to try work
#                         that has not been released yet (`sleeve --update` then tells you it is ahead)
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
# its SHA-256 is HEX (from the web: curl ... | sh -s -- --sha256 HEX). --dev is documented in --help.
SHA256=""
UNINSTALL=""
while [ $# -gt 0 ]; do
    case "$1" in
        --help|-h)
            if [ -f "$0" ]; then sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
            else printf '%s\n' "Usage: sh install.sh [--uninstall | --dev | --sha256 HEX]  (this run was piped in, so there is no file to print the full help from)"; fi
            exit 0 ;;
        --uninstall) UNINSTALL=1 ;;
        --dev) SLEEVE_FROM=main ;;
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
# The one command to install python3 with, in the words of the package manager found; the fallback is the one
# install.sh has named since the start.
PY_HINT="Fedora:        sudo dnf install python3"
if command -v apt >/dev/null 2>&1; then PY_HINT="Debian/Ubuntu: sudo apt install python3 python3-venv"
elif command -v pacman >/dev/null 2>&1; then PY_HINT="Arch:          sudo pacman -S python"
elif command -v zypper >/dev/null 2>&1; then PY_HINT="openSUSE:      sudo zypper install python3"
elif command -v apk >/dev/null 2>&1; then PY_HINT="Alpine:        sudo apk add python3"
fi
PY=""
for candidate in python3 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        PY="$candidate"; break
    fi
done
[ -n "$PY" ] || fail "Python 3.10 or newer is needed. To install it: $PY_HINT"
"$PY" -c 'import venv, ensurepip' 2>/dev/null || fail "Python's venv module is missing. Debian/Ubuntu: sudo apt install python3-venv; most other distros ship it inside python3, so a full reinstall of that package brings it"

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

kde_env
say "$(kde_env_line)"

# --- where to install from: this checkout if there is one, else GitHub ---------------------------------------------------
# Run straight from the web (`curl ... | sh`), `$0` is the shell itself, not this script, so no checkout in the
# current folder is ever mistaken for it: only a real $0 file counts.
FROM_WEB=""
HERE=""
if [ -f "$0" ]; then
    HERE=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || true)
else FROM_WEB=1
fi
if [ -n "${SLEEVE_SOURCE:-}" ]; then SOURCE="$SLEEVE_SOURCE"
elif [ -n "$SHA256" ]; then SOURCE="$REPO_URL"             # a hash is for a downloaded wheel, never a checkout
elif [ -n "$HERE" ] && [ -f "$HERE/pyproject.toml" ] && [ -d "$HERE/sleeve" ]; then SOURCE="$HERE"
else SOURCE="$REPO_URL"; fi

# Straight from the web the default is the newest published release (what `sleeve --update` follows), so a normal
# install is never ahead of it. --dev (or SLEEVE_FROM=main) installs the newest source instead. If GitHub cannot be
# reached at all, a piped install stops instead of silently installing source code; a checkout can still install
# itself. If no release has been published yet, the newest source is installed and that is said out loud.
RELEASE_API="https://api.github.com/repos/jieke238y34/sleeve/releases/latest"
RELEASE_PREFIX="https://github.com/jieke238y34/sleeve/releases/download/"
NET_FAIL=""
# The wheel attached to the newest release, or nothing: a plain return 1 means "none found / no tools" and the
# caller falls back; NET_FAIL=1 means GitHub was reachable but misbehaved, which a piped install must not survive
# survive silently.
latest_wheel() {
    TMP="${TMPDIR:-/tmp}/sleeve-release.$$.http"
    HTTP=""
    if command -v curl >/dev/null 2>&1; then
        HTTP=$(curl -sSL --proto "=https" --proto-redir "=https" --max-time 20 -H "Accept: application/vnd.github+json" \
                     -o "$TMP" -w '%{http_code}' "$RELEASE_API" 2>/dev/null)
        case "$HTTP" in *[!0-9]*|"") HTTP="000";; esac
    elif command -v wget >/dev/null 2>&1; then
        if wget -q -T 20 -O "$TMP" "$RELEASE_API" 2>/dev/null; then HTTP="200"; else HTTP="000"; fi
    else rm -f "$TMP"; return 1
    fi
    case "$HTTP" in
        200) W="$("$PY" -c '
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
sys.exit(1)' "$RELEASE_PREFIX" < "$TMP")" ;;
        404) W="" ;;                                 # no release published yet: an ordinary "none"
        *) W=""; NET_FAIL=1 ;;                       # bad gateway, rate limit, no route: that is a different thing
    esac
    rm -f "$TMP"
    [ -n "$W" ] || return 1
    printf '%s\n' "$W"
}
RELEASE=""
RELEASE_URL="${TMPDIR:-/tmp}/sleeve-release.$$.url"
if [ "$SOURCE" = "$REPO_URL" ] && [ "${SLEEVE_FROM:-release}" != "main" ]; then
    latest_wheel > "$RELEASE_URL" || true                       # the function runs unwrapped, so NET_FAIL survives it
    RELEASE=$(cat "$RELEASE_URL") || RELEASE=""
    rm -f "$RELEASE_URL"
    if [ -n "$RELEASE" ]; then SOURCE="$RELEASE"
    elif [ -n "$SHA256" ]; then fail "--sha256 needs a release wheel, and none could be fetched"
    elif [ -n "$NET_FAIL" ] && [ -n "$FROM_WEB" ]; then
        fail "the newest release could not be fetched from GitHub, so nothing was installed: check the internet and run it again, or git clone the repository and run ./install.sh there"
    elif [ -n "$NET_FAIL" ]; then
        say "note: GitHub could not be reached; installing the newest source from the repository instead"
    elif [ -n "$FROM_WEB" ]; then
        say "note: no release has been published yet, so this installs the newest code on the main branch, not a released build"
    else say "note: no published release could be fetched; installing the newest source instead"
    fi
fi
if [ -z "$RELEASE" ] && [ "$SOURCE" = "$REPO_URL" ] && [ "${SLEEVE_FROM:-release}" = "main" ]; then
    say "dev build: installing the newest code from the main branch. It is not a released build."
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
        https://*) command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1 || fail "curl or wget is needed to download the wheel"
                   if command -v curl >/dev/null 2>&1; then
                       curl -fsSL --proto "=https" --proto-redir "=https" --max-time 300 -o "$WORK/${SOURCE##*/}" "$SOURCE" || fail "could not download $SOURCE"
                   else
                       wget -q -T 300 -O "$WORK/${SOURCE##*/}" "$SOURCE" || fail "could not download $SOURCE"
                   fi ;;
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
if LABEL=$(cd / && "$VENV/bin/python" -c 'from sleeve import build_label; print(build_label())' 2>/dev/null) && [ -n "$LABEL" ]; then
    say "That is Sleeve $LABEL."
fi
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
    elif command -v zypper >/dev/null 2>&1; then say "  openSUSE:      sudo zypper install pulseaudio-utils ffmpeg"
    fi
fi
