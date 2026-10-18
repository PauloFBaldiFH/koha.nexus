"""On-demand enrichment over the direct Z39.50 servers.

A librarian asks for one record (or a few) to be enriched now; the
dispatcher asks a ranked handful of the direct servers of
panel/kei_panel/data/z3950_direct.json and merges what they answer.
Plan: /mnt/project-files/on-demand-enrichment/plan.md (2026-10-18).

    targets   the direct server list, with the exclusion rule applied
    policy    which hosts and addresses may never be contacted
    connect   the only way this package opens a connection: resolve,
              check every address, then a z3950.Session to that address
    limits    concurrency, rate and daily limits per host and provider
    health    health.db: circuit breaker, capabilities, daily counters
    plan      what to ask a server for one record
    select    which servers, in what order, in which wave
    dispatch  asks them: waves, early stop, alternates, cache
    service   the koha-nexus-ondemand unit: jobs.db in, report out

The koha.nexus gateway, its tunnel (sru.koha.nexus, catalog.koha.nexus)
and every local endpoint are refused here, whatever the list says.
"""
