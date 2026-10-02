"""vision.conf / ai-keys.conf: the same rules as the Perl side, keys kept private."""

import stat

from kei_panel import aiconf


def test_defaults_fill_an_empty_file(tmp_path):
    c = aiconf.load(tmp_path / "missing.conf")
    assert c["provider"] == "openai" and c["url"].startswith("https://")
    assert set(aiconf.CONF_KEYS) <= set(c)


def test_save_is_private_and_round_trips(tmp_path):
    path = tmp_path / "vision.conf"
    c = aiconf.with_defaults({"provider": "gemini", "token": "AIza-secret\nlang=xx"})
    aiconf.save(path, c)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    back = aiconf.load(path)
    assert back["provider"] == "gemini" and back["token"] == "AIza-secretlang=xx"
    assert back["lang"] == ""          # a newline in a value cannot add a key


def test_every_provider_keeps_its_own_key(tmp_path):
    path = tmp_path / "vision.conf"
    aiconf.save_all(path, aiconf.with_defaults({"provider": "gemini", "token": "gem-key-123456"}))
    aiconf.save_all(path, aiconf.with_defaults({"provider": "openai", "token": "sk-openai-7890"}))
    assert aiconf.load(path)["token"] == "sk-openai-7890"            # the active one, for the web UI
    assert aiconf.key_for(path, "gemini") == "gem-key-123456"         # remembered
    keys = aiconf.keys_path(path)
    assert stat.S_IMODE(keys.stat().st_mode) == 0o600
    aiconf.save_all(path, aiconf.with_defaults({"provider": "gemini", "token": ""}))
    assert "gemini" not in aiconf.load_keys(keys)                     # cleared on purpose


def test_mask_never_shows_more_than_four_characters():
    assert aiconf.mask("") == ""
    assert aiconf.mask("short") == "••••"
    assert aiconf.mask("AIzaSyD-0123456789abcd") == "••••abcd"


def test_endpoint_problems_match_the_perl_rules():
    ok = {"provider": "gemini", "url": "https://generativelanguage.googleapis.com/v1beta/openai", "token": "k"}
    assert aiconf.endpoint_problem(ok) == ""
    assert aiconf.endpoint_problem(ok | {"token": ""}) == "NO_TOKEN"
    assert aiconf.endpoint_problem(ok | {"url": "ftp://x"}) == "URL"
    assert aiconf.endpoint_problem({"provider": "compatible", "url": "http://example.com/v1",
                                    "token": "k"}) == "TOKEN_PLAIN"
    assert aiconf.endpoint_problem({"provider": "ollama", "url": "http://localhost:11434", "token": ""}) == ""
    assert aiconf.endpoint_problem({"provider": "openai", "url": "http://192.168.0.9:8000/v1",
                                    "token": ""}) == ""


def test_selector_lists_every_provider_once():
    assert sorted(aiconf.SELECTOR_ORDER) == sorted(aiconf.PROVIDERS) == sorted(aiconf.LABELS)
