"""The earbuds view reads Maid BT's watcher and reports what Bluetooth output really is: parse the json, keep
codecs honest - every Bluetooth codec is lossy, only the files themselves stay lossless."""

from sleeve import earbuds

CONNECTED = {
    "chassis": 3,
    "laptop_mode": False,
    "devices": [{
        "name": "Earbuds", "mac": "F0:00:00:00:00:01", "connected": True,
        "profile": "a2dp", "mic_holders": [], "battery": 74,
        "case": "n/a (connected)",
    }],
}


def test_the_watchers_json_is_read_and_bad_output_is_not():
    assert earbuds.status(run=lambda: '{"devices": [{"mac": "F0:00:00:00:00:01", "connected": true}]}') is not None
    assert earbuds.status(run=lambda: "not json at all") is None
    assert earbuds.status(run=lambda: "") is None
    assert earbuds.status(run=lambda: '{"no": "devices"}') is None


def test_the_codec_arrives_from_the_bluetooth_sink_and_nothing_else():
    pactl = 'Name: bluez_output.F0_00_00_00_00_01.1\n\tbluez5.codec = "ldac"'
    assert earbuds.codec(run=lambda: pactl) == "ldac"
    assert earbuds.codec(run=lambda: "Name: alsa_output.pci-something") == ""
    assert earbuds.codec(run=lambda: "") == ""


def test_connected_earbuds_name_the_codec_and_call_it_lossy():
    line = earbuds.describe(CONNECTED, "ldac")
    assert line.startswith("Earbuds: connected") and "battery 74%" in line
    assert "LDAC over Bluetooth (lossy" in line and "files stay lossless on disk" in line
    assert "lossless Bluetooth" not in line.replace("files stay lossless", "")  # never about the radio


def test_docked_earbuds_say_so_and_claim_nothing():
    docked = {"devices": [dict(CONNECTED["devices"][0], connected=False,
                               battery=None, case="in charging case (silent)")]}
    line = earbuds.describe(docked, "")
    assert line == "Earbuds: in charging case (silent)"


def test_silent_watchers_leave_the_line_empty():
    assert earbuds.describe(None, "ldac") == ""
    assert earbuds.describe({}, "") == ""
    assert earbuds.describe({"devices": []}, "sbc") == ""
