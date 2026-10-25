#!/usr/bin/env bats
# robots.txt of the OPAC (Google Search Console assistant and the nightly
# sitemap): the panel's own file, or someone else's with only its Sitemap:
# line changed. Runs the helpers alone on a temporary document root.

setup() {
    REPO="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    W="$BATS_TEST_TMPDIR"
    sed -n '/^OPAC_DOCROOT=/,/^opac_sitemap_install_cron() {/p' "$REPO/installer" | sed '$d' > "$W/sitemap.sh"
    mkdir -p "$W/htdocs"
    export KEI_OPAC_DOCROOT="$W/htdocs"
}

run_sm() { bash -c "log() { :; }; source '$W/sitemap.sh'; $1"; }

@test "the panel's robots.txt points to the sitemap and keeps crawlers out of searches only" {
    run run_sm "opac_robots_publish https://catalogo.exemplo.org/"
    [ "$status" -eq 0 ]
    f="$W/htdocs/robots.txt"
    grep -qx "Sitemap: https://catalogo.exemplo.org/sitemapindex.xml" "$f"
    grep -qx "Disallow: /cgi-bin/koha/opac-search.pl" "$f"
    ! grep -qx "Disallow: /cgi-bin/" "$f"
    ! grep -q "opac-detail" "$f"
    [ "$(stat -c %a "$f")" = 644 ]

    # A new address replaces the line, nothing piles up.
    run run_sm "opac_robots_publish https://biblioteca.exemplo.org"
    [ "$(grep -c '^Sitemap:' "$f")" = 1 ]
    grep -qx "Sitemap: https://biblioteca.exemplo.org/sitemapindex.xml" "$f"
    [ -z "$(ls "$W/htdocs" | grep -v '^robots.txt$')" ]
}

@test "someone else's robots.txt keeps its rules; only the Sitemap: line is set" {
    printf 'User-agent: *\nDisallow: /privado/\nsitemap: https://velho.exemplo.org/s.xml\n' > "$W/htdocs/robots.txt"
    run run_sm "opac_robots_publish https://catalogo.exemplo.org"
    [ "$status" -eq 0 ]
    f="$W/htdocs/robots.txt"
    grep -qx "Disallow: /privado/" "$f"
    ! grep -qi "velho.exemplo.org" "$f"
    grep -qx "Sitemap: https://catalogo.exemplo.org/sitemapindex.xml" "$f"
    ! grep -q "opac-search" "$f"
}

@test "an address that is not a URL is refused before the sitemap script runs" {
    run run_sm "opac_sitemap_publish \"https://x.org/'; touch $W/pwned; '\""
    [ "$status" -ne 0 ]
    [ ! -e "$W/pwned" ]
}
