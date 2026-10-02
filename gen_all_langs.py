#!/usr/bin/env python3
"""
Offline generator of the panel dictionaries (lang/<code>.cache) with Argos Translate.

Only strings that are missing or broken in each dictionary are translated;
existing (reviewed) translations are kept. Every machine translation is
validated: if a variable (${VAR}, $VAR), a printf marker (%s) or an icon is
lost, the entry is discarded and the panel shows the English text instead.

    pip install argostranslate --break-system-packages
    python3 gen_all_langs.py            # all languages
    python3 gen_all_langs.py pt es      # only some languages
"""
import sys

import i18n_common as common

try:
    import argostranslate.package
    import argostranslate.settings
    import argostranslate.translate
except ImportError:
    print("[ERRO] Biblioteca em falta! Execute no terminal: pip install argostranslate --break-system-packages")
    sys.exit(1)

# Our strings are short: skip sentence splitting (it would need stanza/torch).
try:
    argostranslate.settings.chunk_type = argostranslate.settings.ChunkType.NONE
except AttributeError:
    pass

# Argos package codes that differ from our dictionary names.
ARGOS_CODES = {"pt": "pb"}  # "pb" = Brazilian Portuguese model


def ensure_argos_models(target_codes):
    """Atualiza o catálogo e descarrega pacotes em falta localmente."""
    print("[*] Sincronizando catálogo de modelos do Argos Translate...")
    argostranslate.package.update_package_index()
    available = argostranslate.package.get_available_packages()
    installed = {pkg.to_code for pkg in argostranslate.package.get_installed_packages() if pkg.from_code == "en"}

    for lang in target_codes:
        code = ARGOS_CODES.get(lang, lang)
        if code in installed or (code != lang and lang in installed):
            print(f"  [✓] Modelo en -> {code} já instalado.")
            continue
        pkg = next((p for p in available if p.from_code == "en" and p.to_code == code), None)
        if pkg is None and code != lang:
            pkg = next((p for p in available if p.from_code == "en" and p.to_code == lang), None)
        if pkg is None:
            print(f"  [!] Pacote não encontrado no catálogo para o idioma: {lang}")
            continue
        print(f"  [↓] Baixando modelo en -> {pkg.to_code}...")
        argostranslate.package.install_from_path(pkg.download())
        print(f"  [✓] Modelo en -> {pkg.to_code} pronto!")


def get_engine(lang):
    languages = argostranslate.translate.get_installed_languages()
    source = next((l for l in languages if l.code == "en"), None)
    for code in (ARGOS_CODES.get(lang, lang), lang):
        target = next((l for l in languages if l.code == code), None)
        if source and target:
            return source.get_translation(target)
    return None


def process_language(strings, lang):
    path = common.cache_path(lang)
    print(f"\n[+] Processando idioma: {lang.upper()} -> {path}")

    entries, dropped = common.clean_entries(strings, common.read_cache(path))
    pending = [s for s in strings if s not in entries]
    print(f"    Já traduzidas: {len(entries)} | Quebradas descartadas: {len(dropped)} | Restantes: {len(pending)}")
    if not pending:
        common.write_cache(path, entries, order=strings)
        print("    [✓] Idioma 100% atualizado.")
        return

    engine = get_engine(lang)
    if engine is None:
        print(f"    [!] Motor não carregado para en -> {lang}. Pulando...")
        common.write_cache(path, entries, order=strings)
        return

    rejected = 0
    for idx, source in enumerate(pending, 1):
        protected, tokens = common.protect_text(source)
        try:
            translated = common.unprotect_text(engine.translate(protected), tokens)
        except Exception:
            translated = None
        lead = source[: len(source) - len(source.lstrip())]
        trail = source[len(source.rstrip()):]
        fixed = common.repair_translation(source, lead + (translated or "").strip() + trail)
        if fixed is None:
            rejected += 1
        else:
            entries[source] = fixed

        if idx % 50 == 0 or idx == len(pending):
            common.write_cache(path, entries, order=strings)
            print(f"    Progresso: {idx}/{len(pending)} frases concluídas...")

    print(f"[OK] Idioma {lang.upper()} concluído! ({rejected} tradução(ões) rejeitada(s) ficam em inglês)")


def main(argv):
    langs = [a for a in argv if not a.startswith("-")] or common.TARGET_LANGS
    strings = common.extract_strings()
    print(f"[INFO] Total de frases encontradas no installer: {len(strings)}")
    ensure_argos_models(langs)
    for lang in langs:
        process_language(strings, lang)
    print("\n[SUCESSO] Processamento multilíngue concluído!")


if __name__ == "__main__":
    main(sys.argv[1:])
