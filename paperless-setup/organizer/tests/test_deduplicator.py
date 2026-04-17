from mac_organizer.deduplicator import location_score


def test_trash_penalized():
    assert location_score("/Users/x/.Trash/foo.pdf") > location_score("/Users/x/Documents/foo.pdf")


def test_downloads_penalized():
    assert location_score("/Users/x/Downloads/foo.pdf") > location_score("/Users/x/Documents/foo.pdf")


def test_shorter_path_preferred_for_equal_context():
    a = location_score("/Users/x/Documents/foo.pdf")
    b = location_score("/Users/x/Documents/sub/deeper/foo.pdf")
    assert a < b
