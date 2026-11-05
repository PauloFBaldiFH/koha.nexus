#!/usr/bin/env bash
# Only use with the disposable containers described in tests/README.md.
set -euo pipefail
[[ "${NXEV_TEST_RUN:-}" == disposable ]] || { echo 'Use somente em site descartável.' >&2; exit 1; }
wp_test() { docker exec nexus-events-wp php /tmp/wp-cli.phar --allow-root "$@"; }
wp_test plugin deactivate tainacan
wp_test eval 'if (!class_exists("Nexus_Eventos\\Public_UI")) throw new Exception("addon missing"); if (!strlen(do_shortcode("[nexus_eventos]"))) throw new Exception("agenda missing"); echo "PASS: agenda without Tainacan\n";'
wp_test plugin activate tainacan
wp_test plugin deactivate nexus-eventos
wp_test eval 'global $wpdb; if (!$wpdb->get_var("SELECT COUNT(*) FROM ".$wpdb->prefix."nxev_certificates")) throw new Exception("data lost"); echo "PASS: data preserved\n";'
wp_test plugin activate nexus-eventos
