<?php
/**
 * Consent screen template.
 *
 * @var array $pixelite_oauth_view Provided by Consent::render().
 * @package Pixelite\OAuth_App_Passwords
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

$v        = $pixelite_oauth_view;
$branding = $v['branding'];
$user     = $v['user'];
?><!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
	<meta charset="<?php bloginfo( 'charset' ); ?>" />
	<meta name="viewport" content="width=device-width, initial-scale=1" />
	<meta name="robots" content="noindex, nofollow" />
	<title><?php
		/* translators: %s: app name */
		printf( esc_html__( 'Authorize %s', 'wp-oauth-app-passwords' ), esc_html( $v['app_name'] ) );
	?> — <?php echo esc_html( $branding['site_name'] ); ?></title>
	<style>
		:root {
			--wpoap-accent: #2563eb;
			--wpoap-accent-hover: #1d4ed8;
			--wpoap-ink: #1e2327;
			--wpoap-muted: #646970;
			--wpoap-line: #dcdcde;
			--wpoap-bg: #f0f0f1;
			--wpoap-card: #ffffff;
		}
		* { box-sizing: border-box; }
		html, body { margin: 0; padding: 0; }
		body {
			font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
			background: var(--wpoap-bg);
			color: var(--wpoap-ink);
			min-height: 100vh;
			display: flex;
			align-items: center;
			justify-content: center;
			padding: 24px;
			line-height: 1.5;
		}
		.wpoap-card {
			background: var(--wpoap-card);
			width: 100%;
			max-width: 460px;
			border: 1px solid var(--wpoap-line);
			border-radius: 12px;
			box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 8px 24px rgba(0,0,0,.06);
			overflow: hidden;
		}
		.wpoap-head {
			padding: 28px 32px 0;
			text-align: center;
		}
		.wpoap-logo {
			max-width: 180px;
			max-height: 64px;
			width: auto;
			height: auto;
			margin: 0 auto 8px;
			display: block;
		}
		.wpoap-sitename {
			font-size: 13px;
			color: var(--wpoap-muted);
			text-decoration: none;
			letter-spacing: .02em;
		}
		.wpoap-body { padding: 20px 32px 28px; }
		h1 {
			font-size: 20px;
			font-weight: 600;
			text-align: center;
			margin: 12px 0 4px;
		}
		.wpoap-sub {
			text-align: center;
			color: var(--wpoap-muted);
			font-size: 14px;
			margin: 0 0 20px;
		}
		.wpoap-field { margin: 0 0 18px; }
		.wpoap-field label {
			display: block;
			font-size: 13px;
			font-weight: 600;
			margin-bottom: 6px;
		}
		.wpoap-field input[type=text] {
			width: 100%;
			padding: 9px 12px;
			font-size: 15px;
			border: 1px solid var(--wpoap-line);
			border-radius: 7px;
			color: var(--wpoap-ink);
		}
		.wpoap-field input[type=text]:focus {
			outline: 2px solid var(--wpoap-accent);
			outline-offset: -1px;
			border-color: var(--wpoap-accent);
		}
		.wpoap-fake-input {
			width: 100%;
			padding: 9px 12px;
			font-size: 15px;
			line-height: 1.4;
			border: 1px solid var(--wpoap-line);
			border-radius: 7px;
			color: var(--wpoap-ink);
			cursor: text;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.wpoap-fake-input:focus {
			outline: 2px solid var(--wpoap-accent);
			outline-offset: -1px;
			border-color: var(--wpoap-accent);
		}
		.wpoap-hint { font-size: 12px; color: var(--wpoap-muted); margin-top: 5px; }
		.wpoap-dest {
			text-align: center;
			font-size: 13px;
			color: var(--wpoap-muted);
			margin: -12px 0 18px;
			overflow-wrap: anywhere;
		}
		.wpoap-dest strong { color: var(--wpoap-text); font-weight: 600; }
		.wpoap-unverified {
			display: flex;
			gap: 8px;
			align-items: flex-start;
			background: #fcf3e6;
			border: 1px solid #dba617;
			border-radius: 9px;
			padding: 11px 13px;
			font-size: 13px;
			line-height: 1.45;
			margin: 0 0 18px;
		}
		.wpoap-unverified svg { flex: 0 0 18px; margin-top: 1px; color: #8a6116; }
		.wpoap-perms {
			background: #f6f7f7;
			border: 1px solid var(--wpoap-line);
			border-radius: 9px;
			padding: 4px 16px;
			margin: 0 0 18px;
		}
		.wpoap-perm {
			display: flex;
			gap: 10px;
			padding: 11px 0;
			border-bottom: 1px solid var(--wpoap-line);
		}
		.wpoap-perm:last-child { border-bottom: 0; }
		.wpoap-perm svg { flex: 0 0 18px; margin-top: 2px; color: var(--wpoap-accent); }
		.wpoap-perm-label { font-weight: 600; font-size: 14px; }
		.wpoap-perm-desc { font-size: 13px; color: var(--wpoap-muted); }
		.wpoap-user {
			font-size: 13px;
			color: var(--wpoap-muted);
			text-align: center;
			margin: 0 0 20px;
		}
		.wpoap-user strong { color: var(--wpoap-ink); }
		.wpoap-user a { color: var(--wpoap-accent); text-decoration: none; }
		.wpoap-actions { display: flex; gap: 10px; }
		.wpoap-btn {
			flex: 1;
			font-size: 15px;
			font-weight: 600;
			padding: 11px 16px;
			border-radius: 8px;
			border: 1px solid;
			cursor: pointer;
			transition: background .12s ease, border-color .12s ease;
		}
		.wpoap-btn-primary { background: var(--wpoap-accent); border-color: var(--wpoap-accent); color: #fff; }
		.wpoap-btn-primary:hover { background: var(--wpoap-accent-hover); border-color: var(--wpoap-accent-hover); }
		.wpoap-btn-secondary { background: #fff; border-color: var(--wpoap-line); color: #3c434a; }
		.wpoap-btn-secondary:hover { background: #f6f7f7; }
		.wpoap-foot {
			text-align: center;
			font-size: 11px;
			color: var(--wpoap-muted);
			padding: 0 32px 20px;
		}
		@media (prefers-color-scheme: dark) {
			:root {
				--wpoap-ink: #e2e4e7; --wpoap-muted: #9ca3af; --wpoap-line: #3c434a;
				--wpoap-bg: #101317; --wpoap-card: #1d2327;
			}
			.wpoap-perms { background: #23282d; }
			.wpoap-btn-secondary { background: #1d2327; color: #e2e4e7; }
			.wpoap-btn-secondary:hover { background: #23282d; }
		}
	</style>
</head>
<body>
	<div class="wpoap-card" role="dialog" aria-modal="true" aria-labelledby="wpoap-title">
		<div class="wpoap-head">
			<?php if ( $branding['logo_url'] ) : ?>
				<img class="wpoap-logo" src="<?php echo esc_url( $branding['logo_url'] ); ?>" alt="<?php echo esc_attr( $branding['site_name'] ); ?>" />
			<?php endif; ?>
			<a class="wpoap-sitename" href="<?php echo esc_url( $branding['site_url'] ); ?>"><?php echo esc_html( $branding['site_name'] ); ?></a>
		</div>

		<div class="wpoap-body">
			<h1 id="wpoap-title"><?php
				/* translators: %s: app name */
				printf( esc_html__( 'Connect %s', 'wp-oauth-app-passwords' ), '<span>' . esc_html( $v['app_name'] ) . '</span>' );
			?></h1>
			<p class="wpoap-sub"><?php
				/* translators: %s: site name */
				printf( esc_html__( 'Grant this application access to %s on your behalf.', 'wp-oauth-app-passwords' ), esc_html( $branding['site_name'] ) );
			?></p>

			<?php if ( ! empty( $v['destination'] ) ) : ?>
				<p class="wpoap-dest"><?php
					/* translators: %s: host the credential will be sent to, e.g. claude.ai */
					printf( esc_html__( 'Your credential will be sent to %s', 'wp-oauth-app-passwords' ), '<strong>' . esc_html( $v['destination'] ) . '</strong>' );
				?></p>
			<?php endif; ?>

			<?php if ( ! empty( $v['self_registered'] ) ) : ?>
				<div class="wpoap-unverified">
					<svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M10 2.5a1 1 0 0 1 .87.5l7 12A1 1 0 0 1 17 16.5H3a1 1 0 0 1-.87-1.5l7-12a1 1 0 0 1 .87-.5Zm0 4a.9.9 0 0 0-.9.98l.3 3.2a.6.6 0 0 0 1.2 0l.3-3.2A.9.9 0 0 0 10 6.5Zm0 6a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z" fill="currentColor"/></svg>
					<div><?php esc_html_e( 'This application registered itself with your site and has not been reviewed by anyone. Only approve it if you started this connection yourself and recognise the destination above.', 'wp-oauth-app-passwords' ); ?></div>
				</div>
			<?php endif; ?>

			<form method="post" action="<?php echo esc_url( $v['form_action'] ); ?>">
				<?php wp_nonce_field( 'pixelite_oauth_consent', '_pixelite_oauth_nonce' ); ?>
				<?php foreach ( $v['hidden'] as $name => $value ) : ?>
					<input type="hidden" name="<?php echo esc_attr( $name ); ?>" value="<?php echo esc_attr( $value ); ?>" />
				<?php endforeach; ?>

				<div class="wpoap-field">
					<label for="wpoap-app-label"><?php esc_html_e( 'App Label', 'wp-oauth-app-passwords' ); ?></label>
					<input type="hidden" name="app_label" id="wpoap-app-label" value="<?php echo esc_attr( $v['app_name'] ); ?>" maxlength="191" aria-label="<?php esc_attr_e( 'App Label', 'wp-oauth-app-passwords' ); ?>" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" data-1p-ignore data-form-type="other" /><div id="wpoap-app-label-fake" class="wpoap-fake-input" role="button" tabindex="0" aria-label="<?php esc_attr_e( 'App label — click to edit', 'wp-oauth-app-passwords' ); ?>" onclick="var h=document.getElementById('wpoap-app-label');h.type='text';this.style.display='none';h.focus();" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();this.click();}"><?php echo esc_html( $v['app_name'] ); ?></div>
					<p class="wpoap-hint"><?php esc_html_e( 'This label appears in your profile under Application Passwords, where you can revoke access at any time.', 'wp-oauth-app-passwords' ); ?></p>
				</div>

				<div class="wpoap-perms">
					<?php foreach ( $v['scopes'] as $row ) : ?>
						<div class="wpoap-perm">
							<svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.8 3.8 6.8-6.8a1 1 0 0 1 1.4 0Z" fill="currentColor"/></svg>
							<div>
								<div class="wpoap-perm-label"><?php echo esc_html( $row['label'] ); ?></div>
								<?php if ( ! empty( $row['description'] ) ) : ?>
									<div class="wpoap-perm-desc"><?php echo esc_html( $row['description'] ); ?></div>
								<?php endif; ?>
							</div>
						</div>
					<?php endforeach; ?>
					<div class="wpoap-perm">
						<svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M10 2a4 4 0 0 1 4 4v2h1a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1h1V6a4 4 0 0 1 4-4Zm2 6V6a2 2 0 1 0-4 0v2h4Z" fill="currentColor"/></svg>
						<div>
							<div class="wpoap-perm-label"><?php
							if ( '' !== $v['account_note'] ) {
								/* translators: %s: optional account note, e.g. a role label */
								printf( esc_html__( 'Acts as your account (%s)', 'wp-oauth-app-passwords' ), esc_html( $v['account_note'] ) );
							} else {
								esc_html_e( 'Acts as your account', 'wp-oauth-app-passwords' );
							}
							?></div>
							<div class="wpoap-perm-desc"><?php
							if ( ! empty( $v['restricted'] ) ) {
								esc_html_e( 'Access is limited to the features listed above, within what your account is permitted to do.', 'wp-oauth-app-passwords' );
							} else {
								esc_html_e( 'The application can only do what your account is permitted to do.', 'wp-oauth-app-passwords' );
							}
							?></div>
						</div>
					</div>
				</div>

				<p class="wpoap-user"><?php
					/* translators: %s: user display name */
					printf( esc_html__( 'Signed in as %s.', 'wp-oauth-app-passwords' ), '<strong>' . esc_html( $user->display_name ) . '</strong>' );
				?> <a href="<?php echo esc_url( $v['switch_url'] ); ?>"><?php esc_html_e( 'Switch account', 'wp-oauth-app-passwords' ); ?></a></p>

				<div class="wpoap-actions">
					<button type="submit" name="approve" value="1" class="wpoap-btn wpoap-btn-primary"><?php esc_html_e( 'Approve', 'wp-oauth-app-passwords' ); ?></button>
					<button type="submit" name="deny" value="1" class="wpoap-btn wpoap-btn-secondary"><?php esc_html_e( 'Cancel', 'wp-oauth-app-passwords' ); ?></button>
				</div>
			</form>
		</div>

		<div class="wpoap-foot"><?php esc_html_e( 'Secured by WordPress Application Passwords.', 'wp-oauth-app-passwords' ); ?></div>
	</div>
</body>
</html>
<?php
