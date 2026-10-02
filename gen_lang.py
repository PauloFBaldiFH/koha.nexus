#!/usr/bin/env python3
"""
Online generator of the panel dictionaries (Google Translate, falling back to
MyMemory), for machines where the offline Argos models are not available.

Same rules as gen_all_langs.py: only missing/broken entries are translated,
reviewed translations are kept and every result is validated.

    pip install deep-translator
    python3 gen_lang.py            # all languages
    python3 gen_lang.py pt es      # only some languages
"""
import sys
import time

import i18n_common as common

try:
    from deep_translator import GoogleTranslator, MyMemoryTranslator
except ImportError:
    print("[ERRO] Instale a biblioteca: pip install deep-translator")
    sys.exit(1)

# Codes used by the online services when they differ from our file names.
GOOGLE_CODES = {"zh": "zh-CN", "tl": "tl", "pt": "pt"}
MYMEMORY_CODES = {
    "pt": "pt-BR", "es": "es-ES", "fr": "fr-FR", "de": "de-DE", "it": "it-IT",
    "nl": "nl-NL", "ru": "ru-RU", "pl": "pl-PL", "uk": "uk-UA", "cs": "cs-CZ",
    "sv": "sv-SE", "tr": "tr-TR", "ar": "ar-SA", "ja": "ja-JP", "zh": "zh-CN",
    "hi": "hi-IN", "bn": "bn-IN", "id": "id-ID", "tl": "tl-PH", "fa": "fa-IR",
    "vi": "vi-VN", "ko": "ko-KR",
}


def translate_phrase(text, lang):
    """Tenta via Google; se bloqueado, usa MyMemory."""
    try:
        res = GoogleTranslator(source="en", target=GOOGLE_CODES.get(lang, lang)).translate(text)
        if res:
            return res
    except Exception:
        pass
    try:
        res = MyMemoryTranslator(source="en-US", target=MYMEMORY_CODES.get(lang, lang)).translate(text)
        if res:
            return res
    except Exception:
        pass
    return None


def process_language(strings, lang):
    path = common.cache_path(lang)
    print(f"\n[+] Processando idioma: {lang.upper()} -> {path}")

    entries, dropped = common.clean_entries(strings, common.read_cache(path))
    pending = [s for s in strings if s not in entries]
    print(f"    Já traduzidas: {len(entries)} | Quebradas descartadas: {len(dropped)} | Restantes: {len(pending)}")

    rejected = 0
    for idx, source in enumerate(pending, 1):
        protected, tokens = common.protect_text(source)
        translated = translate_phrase(protected, lang)
        if translated is not None:
            translated = common.unprotect_text(translated, tokens)
        lead = source[: len(source) - len(source.lstrip())]
        trail = source[len(source.rstrip()):]
        fixed = common.repair_translation(source, lead + (translated or "").strip() + trail)
        if fixed is None:
            rejected += 1
        else:
            entries[source] = fixed

        if idx % 10 == 0 or idx == len(pending):
            common.write_cache(path, entries, order=strings)
            print(f"    Progresso: {idx}/{len(pending)} frases concluídas...")
        time.sleep(0.3)

    common.write_cache(path, entries, order=strings)
    print(f"[OK] Idioma {lang.upper()} concluído! ({rejected} tradução(ões) rejeitada(s) ficam em inglês)")


def main(argv):
    langs = [a for a in argv if not a.startswith("-")] or common.TARGET_LANGS
    strings = common.extract_strings()
    print(f"[INFO] Total de frases encontradas: {len(strings)}")
    for lang in langs:
        process_language(strings, lang)
    print("\n[SUCESSO] Todos os idiomas foram processados.")


if __name__ == "__main__":
    main(sys.argv[1:])
