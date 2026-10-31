"""Every outside service Sleeve can talk to, in one list for Settings > APIs: whether it is on, what it is for, what is
sent and where. Plain data, no network, and never a password, token, key or session: only what is safe to show."""

from urllib.parse import urlsplit

DISCORD_STATES = {"ready": "Connected", "connecting": "Connecting", "unavailable": "Waiting for Discord or arRPC",
                  "off": "Off"}


def _row(name, on, state, what, sends, where):
    return {"name": name, "on": on, "state": state, "what": what, "sends": sends, "where": where}


def summary(settings, discord_state="off", lastfm_user="", lastfm_ready=False, lastfm_active=False, lastfm_queued=0):
    "A list of {name, on, state, what, sends, where} for each service, in the order Settings shows them."
    out = []
    # Discord (or arRPC): a local socket on this computer, not the internet
    discord_on = bool(settings.discord_presence)
    ident = settings.discord_client_id
    out.append(_row(
        "Discord", discord_on,
        DISCORD_STATES.get(discord_state, "On") if discord_on else "Off",
        "Shows the song you are playing as 'Listening to…' on your Discord profile."
        + (f" Application ID {ident}." if ident else " No Application ID yet."),
        "Song title and artist while playing, and the album cover address if 'Also show the album cover' is on. "
        "Cleared when you pause, switch it off or quit.",
        "Discord or arRPC running on this computer (a local socket). Sleeve has no servers of its own."))
    # Last.fm
    state = "Off"
    if lastfm_active and lastfm_ready:
        state = f"Connected as {lastfm_user}" if lastfm_user else "Connected"
    elif lastfm_ready:
        state = "Signed in, scrobbling is off"
    elif lastfm_active:
        state = "On, but not signed in"
    out.append(_row(
        "Last.fm", bool(lastfm_active and lastfm_ready), state,
        "Scrobbles what you listen to and shows the song playing now."
        + (f" {lastfm_queued} songs wait to be sent." if lastfm_queued else ""),
        "Song title, artist, album and length, and when you played it. Sent only while connected; unsent songs wait on "
        "this computer.",
        "ws.audioscrobbler.com over https. Your key and session are kept in a private file "
        "(~/.config/sleeve/lastfm.json)."))
    # Navidrome
    login = settings.navidrome
    if login:
        host = urlsplit(login["url"]).netloc
        out.append(_row(
            "Navidrome", True, f"Connected to {host} as {login['user']}",
            "Browse, search and stream your own library from your server (Navidrome page).",
            "A login token (never your password) with every request, search words, and which songs you played.",
            f"{login['url']} only. The token is kept in Sleeve's private settings file."))
    else:
        out.append(_row("Navidrome", False, "Not connected",
                        "Browse, search and stream your own library from your server (Navidrome page).",
                        "Nothing until you connect.", "The server address you type in Settings > Navidrome."))
    # MusicBrainz and the Cover Art Archive
    allowed = bool(settings.online_lookup_ok)
    out.append(_row(
        "MusicBrainz and Cover Art Archive", allowed, "Allowed" if allowed else "Not allowed yet (it asks first)",
        "Fills in missing tags (Health > Find tags online) and finds album covers for Discord.",
        "Song title, artist and album names, a second apart. No files and no listening history.",
        "musicbrainz.org and coverartarchive.org over https."))
    # GitHub, for updates
    check = bool(settings.update_check_ok)
    out.append(_row(
        "GitHub (updates)", check, "Allowed" if check else "Not allowed yet (it asks first)",
        "Tells you when a newer Sleeve is published; Update now installs it.",
        "A plain request for the newest release. Nothing about you or your music.",
        "api.github.com and github.com/jieke238y34/sleeve/releases, only when you press the button."))
    # dl.py: lyrics and downloads
    out.append(_row(
        "dl.py (downloads and lyrics)", True, "Runs only when you press a button",
        "Downloads new music and fetches lyrics (Downloads page). A separate program that you chose to trust.",
        "Playlist links and song names to the sources set in dl.py's own config.",
        "Whatever dl.py's config.ini names; Sleeve itself sends nothing for this."))
    return out


def as_text(rows):
    "The summary as plain text (for the copy button and for tests)."
    lines = []
    for r in rows:
        lines += [f"{r['name']}: {r['state']}", f"  What: {r['what']}", f"  Sent: {r['sends']}",
                  f"  Where: {r['where']}", ""]
    return "\n".join(lines).strip()
