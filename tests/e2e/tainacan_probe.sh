#!/bin/bash
# What a Tainacan installation really offers, level by level, read only.
# Runs inside the test machine (tests/e2e/tainacan_e2e.sh), as root, with
# the installer as config.sh. Prints "level.key=value" lines; nothing here
# changes WordPress.
#
#   service   the address answers through Apache
#   wordpress WordPress is installed, its home and site URLs
#   plugin    the Tainacan plugin: installed, active, version
#   admin     the login page and the Tainacan admin page answer
#   public    theme, front page, permalinks, sample content, what the
#             collections and items addresses show without a login
set -u
lib() {
    bash -c "source /usr/local/bin/config.sh >/dev/null 2>&1
log() { :; }
SYS_LANG=en
$1" 3>&-
}
wp() { lib "_kei_tn_wp $*" 2>/dev/null; }
say() { printf '%s=%s\n' "$1" "$(printf '%s' "$2" | tr '\n\t' '  ' | cut -c1-400)"; }

url=$(lib '_kei_tn_get url')
say install.url "$url"
say install.status "$(lib '_kei_tn_get status')"

# How the address was chosen: the route to the Internet and every IPv4.
say net.route_get "$(ip -4 route get 1.1.1.1 2>/dev/null | head -n 1)"
say net.addresses "$(ip -4 -o addr show 2>/dev/null | awk '{ print $2 "=" $4 }' | tr '\n' ' ')"
say net.default_routes "$(ip -4 route show default 2>/dev/null | tr '\n' ';')"
say net.get_server_ip "$(lib 'get_server_ip')"

code() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$@"; }
say service.home_http "$(code "$url/")"
say service.home_redirect "$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 20 "$url/")"

say wordpress.installed "$(wp core is-installed && echo yes || echo no)"
say wordpress.version "$(wp core version)"
say wordpress.home "$(wp option get home)"
say wordpress.siteurl "$(wp option get siteurl)"
say wordpress.lang "$(wp language core list --status=active --field=language)"

say plugin.list "$(wp plugin list --fields=name,status,version --format=csv | tail -n +2 | tr '\n' ' ')"
say plugin.tainacan_files "$(lib 'cid=$(_kei_tn_cid wordpress); docker exec "$cid" sh -c "ls /var/www/html/wp-content/plugins/tainacan"' | tr '\n' ' ')"

say admin.login_http "$(code "$url/wp-login.php")"
say admin.tainacan_page_http_anonymous "$(code "$url/wp-admin/admin.php?page=tainacan_admin")"

say public.theme_active "$(wp theme list --status=active --field=name)"
say public.themes "$(wp theme list --fields=name,status,version --format=csv | tail -n +2 | tr '\n' ' ')"
say public.block_theme "$(wp eval 'echo wp_is_block_theme() ? "yes" : "no";')"
say public.show_on_front "$(wp option get show_on_front)"
say public.page_on_front "$(wp option get page_on_front)"
say public.permalink_structure "$(wp option get permalink_structure)"
say public.posts "$(wp post list --post_type=post --fields=ID,post_title,post_status --format=csv | tail -n +2 | tr '\n' ' ')"
say public.pages "$(wp post list --post_type=page --fields=ID,post_title,post_status --format=csv | tail -n +2 | tr '\n' ' ')"
say public.menus "$(wp menu list --fields=name,count --format=csv 2>/dev/null | tail -n +2 | tr '\n' ' ')"
say public.navigation_posts "$(wp post list --post_type=wp_navigation --fields=ID,post_title --format=csv | tail -n +2 | tr '\n' ' ')"
# The collections post type: is it public, has it an archive, which address.
say public.collection_type "$(wp eval '$o = get_post_type_object("tainacan-collection"); if (!$o) { echo "none"; return; } echo "public=", var_export($o->public, true), " has_archive=", var_export($o->has_archive, true), " slug=", is_array($o->rewrite) ? $o->rewrite["slug"] : var_export($o->rewrite, true);')"
say public.collections_archive_link "$(wp eval 'echo get_post_type_archive_link("tainacan-collection");')"
say public.items_repository_link "$(wp eval 'echo function_exists("\\Tainacan\\Theme_Helper::get_instance") ? "helper" : ""; $o = get_option("tainacan_option_items_repository_list"); echo " option=", var_export($o, true);')"
say public.tainacan_options "$(wp option list --search='tainacan*' --fields=option_name --format=csv | tail -n +2 | tr '\n' ' ')"
say public.rewrite_tainacan "$(wp rewrite list --format=csv 2>/dev/null | grep -iE 'collection|tainacan|items' | head -n 12 | tr '\n' ' ')"
say public.block_templates "$(wp eval 'foreach (get_block_templates() as $t) { if (stripos($t->slug, "tainacan") !== false || stripos($t->slug, "collection") !== false || stripos($t->slug, "item") !== false) echo $t->slug, " "; }')"
say public.tainacan_blocks "$(wp eval 'foreach (WP_Block_Type_Registry::get_instance()->get_all_registered() as $n => $b) if (strpos($n, "tainacan/") === 0) echo $n, " ";')"

# Without a login: the home page and the collections address, as text.
text() { curl -s -L --max-time 20 "$1" | python3 -I -c 'import html, re, sys
t = sys.stdin.read()
t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", t)
t = re.sub(r"(?s)<[^>]+>", " ", t)
print(" ".join(html.unescape(t).split())[:600])'; }
say public.home_text "$(text "$url/")"
link=$(wp eval 'echo get_post_type_archive_link("tainacan-collection");')
[ -n "$link" ] && say public.collections_text "$(text "$link")"
say public.collections_api_anonymous "$(curl -s --max-time 20 "$url/wp-json/tainacan/v2/collections" | head -c 300)"
say health.panel "$(lib 'kei_tainacan_health')"
