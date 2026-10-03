from kei_panel.widgets.pacman import PacmanLoader


def test_one_ascii_line_in_brackets():
    loader = PacmanLoader()
    for frame in range(6):
        loader.frame = frame
        loader.x = frame
        line = loader.line(40).plain
        assert len(line) == 40 and "\n" not in line and line.isascii()
        assert line[0] == "[" and line[-1] == "]"


def test_determinate_eats_pellets_behind():
    loader = PacmanLoader()
    loader.progress = 0.5
    line = loader.line(32).plain
    head = line.index("C")
    assert set(line[1:head]) == {"-"}         # eaten trail
    assert "o" in line[head:]                  # pellets still ahead
    loader.progress = 1.0
    assert "o" not in loader.line(32).plain


def test_indeterminate_moves_and_wraps():
    loader = PacmanLoader()
    heads = []
    for x in (0, 5, 30):
        loader.x = x
        heads.append(loader.line(32).plain.index("C"))
    assert heads[0] < heads[1] and heads[2] == heads[0]   # past the end: back to the start


def test_mouth_opens_and_closes():
    loader = PacmanLoader()
    loader.progress = 0.3
    loader.frame = 1
    assert "c" in loader.line(20).plain
