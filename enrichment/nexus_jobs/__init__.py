"""koha.nexus enrichment jobs: the throttled worker and the job flow
(design.md 2.3 and 2.5).

    queued     a job is created (scope: the whole catalogue or biblionumbers)
    exported   Koha's records were exported to jobs/ID/export.xml (by the
               installer, as root: the worker never reads Koha's database)
    matching   the worker reads them 20 at a time, matches each against
               static.db with nexus_enrich, sleeps, checkpoints
    ready      staged report written (M0/M1/W/R counts, before/after diff);
               nothing has reached Koha
    applying   "Apply": safety backup, then one Koha staged import of at most
    applied    500 records at a time (stage_file.pl + commit_file.pl)
    reverting  "Revert": commit_file.pl --revert, batch by batch
    reverted
    failed, cancelled

Everything is kept in jobs.db, so a reboot or a WSL shutdown resumes where
it stopped.
"""

__version__ = "0.1.0"
