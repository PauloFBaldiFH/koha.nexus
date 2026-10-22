#!/usr/bin/env python3
"""Extract the installer's unchanged library before its runtime dispatcher.

The Bats driver sources this snapshot through KEI_INSTALLER so tests do not
launch the application dispatcher or menu. The repository stays read-only.
"""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installer', type=Path)
    parser.add_argument('output', type=Path)
    options = parser.parse_args()
    source = options.installer.read_text(encoding='utf-8')
    marker = 'if [ -n "$KEI_CLI_MODE" ]; then\n'
    if source.count(marker) != 1:
        parser.error('Installer runtime dispatcher changed; review library extraction')
    library = source.split(marker, 1)[0]
    if 'koha_exec() {' not in library or '_lt_magic_run() {' not in library:
        parser.error('Installer import functions are missing before the dispatcher')
    options.output.write_text(library, encoding='utf-8')
    options.output.chmod(0o600)
    print('Prepared import function library:', options.output)


if __name__ == '__main__':
    main()
