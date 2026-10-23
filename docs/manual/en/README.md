# Koha.Nexus user manual

This manual explains how to use the Koha.Nexus installer and control panel. The procedures were checked against the repository at revision `a319c52`, whose application code matches the revision reviewed for the Portuguese manual. It does not replace Koha's own manual for cataloguing, circulation and library administration.

[Português brasileiro](../pt-BR/README.md)

The English manual is delivered in batches of up to three chapters for review:

1. [Installation on Windows, Debian and Ubuntu](01-installation.md).
2. [Getting started and using the panel](02-panel.md).
3. [Backup and restore](03-backup-restore.md).

The next batches cover Magic Import, enrichment, appearance, local AI, administration and troubleshooting.

Action names follow the English labels in the panel's source. The language of your installation may differ. Do not use the option numbers from an old menu to locate actions in the current panel.

## Reading the notices

- **Destructive action:** the operation can replace or delete data. Read the on-screen confirmation before continuing.
- **To confirm:** the inspected code does not establish the claim, or differs from the previous documentation. These points are identified in the relevant chapter.
- **Source:** the file and function supporting an instruction. Checking the source is not equivalent to testing an installation on a real computer.

## Points to confirm

- **To confirm:** public availability and address of the Microsoft Store listing. Packaging support does not establish that a listing is available.
- **To confirm:** the official RAM minimum for Debian/Ubuntu outside Windows. The installation guide recommends 4 GB for a dedicated server, with 8 GB recommended, but the current Linux preflight does not enforce that numerical threshold.
- **To confirm:** end-to-end operation of the MSIX on Windows ARM64. The generated manifest declares x64; this manual does not promise ARM64 compatibility for that package.
