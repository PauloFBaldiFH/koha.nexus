#!/usr/bin/env python3
"""Report the Koha.Nexus panel's bundled translations using its own loader."""

from __future__ import annotations

import argparse
import ast
import base64
import binascii
from collections import defaultdict
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "panel")]

from i18n_common import TARGET_LANGS
from kei_panel import i18n, menus
from kei_panel.routines.platforms import TAINACAN_DIAGNOSIS_STATES
from kei_panel.views.base import PLATFORM_NAMES, ZONE_TITLES

INSTALLER = ROOT / "installer"
CATALOGS = ROOT / "lang"
PANEL = ROOT / "panel" / "kei_panel"

# Identifiers, bare symbols, and formats whose spelling is part of the UI.
# An unchanged word outside this list still needs a language-specific review.
NEUTRAL = {
    "${h} h ${m} min", "${m} min", "${n} s", "%Y-%m-%d", "CPU", "Docker",
    "ISBN", "ISSN", "Koha", "Koha ${old} → ${new}", "Koha ${v}",
    "Koha + Tainacan + DSpace", "Microsoft OneDrive", "OK", "SIP2 & Z39.50",
    "SSL", "Tainacan", "WebDAV (Nextcloud, ownCloud...)", "❌ ${step}",
    "🏧  SIP2", "📡  Z39.50", "📱  SMS", "🔐  WireGuard VPN",
    "🚨 Fail2ban", "🧱 UFW",
}


def alternatives(node):
    """Extract literals that are passed whole to the translator."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.IfExp):
        yield from alternatives(node.body)
        yield from alternatives(node.orelse)
    elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        for value in node.values:
            yield from alternatives(value)
    elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Dict):
        for value in node.value.values:
            yield from alternatives(value)


def inventory():
    messages = defaultdict(set)
    dynamic = defaultdict(list)
    portuguese = i18n.load_cache(CATALOGS / "pt.cache") | i18n.load_menu_pt(INSTALLER)

    def add(source, location):
        if source:
            messages[source].add(location)

    for path in sorted(PANEL.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in portuguese:
                add(node.value, f"{path.relative_to(ROOT)}:{node.lineno}")
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in {"t", "tx", "t_literal"} and node.args):
                continue
            location = f"{path.relative_to(ROOT)}:{node.lineno}"
            for source in alternatives(node.args[0]):
                if node.func.id == "tx":
                    source = source.replace("\n", "\\n")
                add(source, location)
            if not isinstance(node.args[0], ast.Constant):
                dynamic[ast.unparse(node.args[0])].append(location)

    for section in menus.SECTIONS:
        for source in (section.label, section.title, section.prompt):
            add(source, f"menus.SECTIONS[{section.id}]")
        for entry in section.entries:
            for source in (entry.label, entry.confirm):
                add(source, f"menus.SECTIONS[{section.id}].entries")
    for source in menus.DESCRIPTIONS.values():
        add(source, "menus.DESCRIPTIONS")
    for table, location in (
        (PLATFORM_NAMES, "views.base.PLATFORM_NAMES"),
        (ZONE_TITLES, "views.base.ZONE_TITLES"),
        *[(table, f"routines.platforms.TAINACAN_DIAGNOSIS_STATES[{field}]")
          for field, table in TAINACAN_DIAGNOSIS_STATES.items()],
    ):
        for source in table.values():
            add(source, location)

    # The DSpace runtime supplies its installation stages and checks over the
    # task protocol. The panel looks them up when rendering progress and rows.
    path = ROOT / "platforms" / "dspace" / "runtime.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "STAGES" for target in node.targets
        ):
            for _, label, detail in ast.literal_eval(node.value).values():
                add(label, "platforms/dspace/runtime.py:STAGES")
                add(detail, "platforms/dspace/runtime.py:STAGES")
    preflight = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "preflight")
    for node in ast.walk(preflight):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "add":
            for arg in node.args[2:]:
                for source in alternatives(arg):
                    add(source, f"platforms/dspace/runtime.py:{node.lineno}")

    # DSpace task errors can reach a dialog even when the plan cannot be built.
    # Inventory complete messages and record format expressions for review.
    for file in ("runtime.py", "operations.py"):
        path = ROOT / "platforms" / "dspace" / file
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "Refused" and node.args):
                continue
            location = f"{path.relative_to(ROOT)}:{node.lineno}"
            source = node.args[0]
            for text in alternatives(source):
                add(text.replace("\n", " "), location)
            if not isinstance(source, ast.Constant):
                dynamic[ast.unparse(source)].append(location)

    return messages, dynamic


def malformed_rows(path):
    malformed = []
    for number, line in enumerate(path.read_bytes().splitlines(), 1):
        if not line.strip() or line.startswith(b"#"):
            continue
        try:
            key, value = line.split(b"|")
            if not all(base64.b64decode(field, validate=True).decode("utf-8").strip() for field in (key, value)):
                malformed.append(number)
        except (ValueError, binascii.Error):
            malformed.append(number)
    return malformed


def coverage(messages):
    report = {}
    english = i18n.Translator("en", None)
    # Audit the bundled release, regardless of cached downloads on this host.
    with tempfile.TemporaryDirectory() as empty_config, patch.object(i18n, "CONFIG_DIR", Path(empty_config)):
        for language in sorted(TARGET_LANGS):
            translator = i18n.Translator(language, INSTALLER)
            table = translator.table | translator.menu_pt
            missing, invalid, identical = [], [], []
            for source in sorted(messages):
                value = table.get(source)
                if value is None:
                    missing.append(source)
                elif (not value.strip() or not i18n.is_safe(source, value)
                      or source.count("\n") != value.count("\n")
                      or source.count("\\n") != value.count("\\n")):
                    invalid.append(source)
                elif source not in NEUTRAL and translator(source).casefold() == english(source).casefold():
                    identical.append(source)
            report[language] = {
                "missing": missing,
                "invalid": invalid,
                "identical": identical,
                "malformed_rows": malformed_rows(CATALOGS / f"{language}.cache"),
            }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Include source locations and individual gaps")
    args = parser.parse_args()
    messages, dynamic = inventory()
    report = coverage(messages)
    if args.json:
        print(json.dumps({
            "locations": {source: sorted(locations) for source, locations in sorted(messages.items())},
            "dynamic_calls": dict(sorted(dynamic.items())),
            "coverage": report,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"{len(messages)} messages; identical renders require terminology review")
        print("lang   missing   invalid   identical   malformed rows")
        for language, result in report.items():
            counts = " ".join(f"{len(items):>9}" for items in result.values())
            print(f"{language:<4} {counts}")


if __name__ == "__main__":
    main()
