"""Remove from queue edits the list only and never touches a file."""

from test_app import qapp  # noqa: F401  (fixture)

from sleeve import player


def test_remove_from_the_queue_only_edits_the_list_never_the_file(qapp, tmp_path):  # noqa: F811
    paths = []
    for name in "abcd":
        f = tmp_path / f"{name}.mp3"
        f.write_bytes(b"x")
        paths.append(str(f))
    p = player.Player()
    p.set_queue(paths, start=1)
    p.remove_at(3)                                            # after the playing song: just gone from the list
    assert p.queue == paths[:3] and p.index == 1
    p.remove_at(0)                                            # before it: the playing song stays the playing song
    assert p.queue == paths[1:3] and p.index == 0 and p.queue[p.index] == paths[1]
    p.remove_at(0)                                            # the playing one: the next takes its place
    assert p.queue == [paths[2]] and p.queue[p.index] == paths[2]
    p.remove_at(0)                                            # the last one: the queue is empty
    assert p.queue == []
    p.remove_at(5)                                            # nothing there: nothing happens
    assert all((tmp_path / f"{n}.mp3").exists() for n in "abcd")      # the files are untouched
    p.close()
