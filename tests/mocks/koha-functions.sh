# Test double for /usr/share/koha/bin/koha-functions.sh (tests/ only):
# a daemon is "running" when tests/mocks/koha-mock left its state file.
is_zebra_running()      { [ -e /run/kei-mock/run/zebra ]; }
is_indexer_running()    { [ -e /run/kei-mock/run/indexer ]; }
is_es_indexer_running() { [ -e /run/kei-mock/run/es-indexer ]; }
is_plack_running()      { [ -e /run/kei-mock/run/plack ]; }
is_worker_running()     { [ -e /run/kei-mock/run/worker ]; }
