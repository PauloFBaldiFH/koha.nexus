from kei_panel.widgets.pacman import ART_W, PacmanLoader, _ART


def render(loader, width=40, height=5):
    """What render() draws at this size (no app needed)."""
    if loader.compact or height < 5:
        return loader._render_line(width).plain
    return loader._render_art(width).plain


def test_art_frames_have_one_width():
    for plain, frames in _ART.items():
        for frame in frames:
            assert len(frame) == 5
            assert {len(row) for row in frame} == {ART_W}, (plain, frame)


def test_plain_mode_is_ascii_only():
    loader = PacmanLoader(plain=True)
    for frame in range(8):
        loader.frame = frame
        loader.x = frame
        assert render(loader).isascii()
    loader.compact = True
    assert render(loader, height=1).isascii()


def test_indeterminate_moves_and_wraps():
    loader = PacmanLoader()
    rows = []
    for x in (0, 5, 40 - ART_W + 1):
        loader.x = x
        rows.append(render(loader).splitlines()[0])
    assert rows[0].index("▄") < rows[1].index("▄")
    assert rows[2] == rows[0]       # past the end: back to the start


def test_determinate_eats_pellets_behind():
    loader = PacmanLoader(plain=True)
    loader.progress = 0.5
    mid = render(loader).splitlines()[2]
    head = mid.index("#")
    assert set(mid[:head].strip()) <= {"-"}      # eaten trail
    assert "." in mid[head:]                       # pellets still ahead
    loader.progress = 1.0
    assert "." not in render(loader).splitlines()[2]


def test_compact_line():
    loader = PacmanLoader(compact=True, plain=True)
    loader.progress = 0.25
    line = render(loader, width=21, height=1)
    assert line.startswith("=====") and line[5] in "Cc" and line.endswith(".")
