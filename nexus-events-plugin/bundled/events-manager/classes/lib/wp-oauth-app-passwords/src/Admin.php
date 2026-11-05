<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Drop-in admin renderer for the "AI / MCP setup" screen.
 *
 * This is the single, shared UI that every consuming plugin (Events Manager,
 * bbPress API, …) drops into its own settings page so the connection wizard
 * looks identical everywhere. A host plugin's only integration line is:
 *
 *     \Pixelite\OAuth_App_Passwords\Admin::render();
 *
 * The card / pill styling mirrors the Events Manager AI/MCP meta box so the two
 * products are visually indistinguishable. The install / activate POST handlers
 * and admin notices are registered automatically by Server::boot() in wp-admin,
 * so the host plugin does not need to wire anything up itself.
 *
 * All internal references use self:: / static:: / ::class so the namespace can
 * be renamed or removed without touching call sites.
 */
class Admin {

	/** Canonical MCP Adapter plugin file. */
	const ADAPTER_PLUGIN = 'mcp-adapter/mcp-adapter.php';

	/** admin-post.php actions. */
	const ACTION_INSTALL  = 'pixelite_oauth_mcp_install';
	const ACTION_ACTIVATE = 'pixelite_oauth_mcp_activate';

	/** Shared nonce action for both forms. */
	const NONCE = 'pixelite_oauth_mcp';

	private static $booted        = false;
	private static $printed_style = false;
	private static $printed_js    = false;

	/**
	 * Register the install / activate handlers and admin notice. Called once from
	 * Server::boot() when in wp-admin, so host plugins get this for free.
	 */
	public static function boot(): void {
		if ( self::$booted ) {
			return;
		}
		self::$booted = true;

		add_action( 'admin_post_' . self::ACTION_INSTALL, array( static::class, 'handle_install' ) );
		add_action( 'admin_post_' . self::ACTION_ACTIVATE, array( static::class, 'handle_activate' ) );
		add_action( 'admin_notices', array( static::class, 'admin_notices' ) );
	}

	/* ---------------------------------------------------------------------
	 * Render
	 * ------------------------------------------------------------------ */

	/**
	 * Render the AI / MCP setup section. Call this from inside any settings page.
	 *
	 * @param array $args {
	 *     @type string $server_path  REST path of the MCP server. Default the
	 *                                MCP Adapter's bundled default server.
	 *     @type string $heading      Section <h2>. Empty string hides it.
	 *     @type string $intro        Intro paragraph. Empty uses the default copy.
	 *     @type string $docs_url     Optional "read the documentation" link.
	 * }
	 */
	public static function render( array $args = array() ): void {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$args = wp_parse_args( $args, array(
			'server_path' => 'mcp/mcp-adapter-default-server',
			'heading'     => __( 'AI / MCP setup', 'wp-oauth-app-passwords' ),
			'intro'       => '',
			'docs_url'    => '',
		) );

		$abilities = self::abilities_ready();
		$adapter   = self::adapter_state();
		$ready     = $abilities && $adapter['active'];
		$mcp_url   = (string) apply_filters( 'pixelite_oauth_mcp_public_url', Support::public_url( rest_url( $args['server_path'] ) ), $args['server_path'] );
		$oauth     = Support::availability();
		$discovery = method_exists( Server::class, 'discovery_status' ) ? Server::discovery_status() : null;

		self::print_styles();

		echo '<div class="pixelite-mcp-wrap">';

		if ( '' !== $args['heading'] ) {
			echo '<h2 class="pixelite-mcp-heading">' . esc_html( $args['heading'] ) . '</h2>';
		}

		echo '<p class="pixelite-mcp-intro">';
		if ( '' !== $args['intro'] ) {
			echo wp_kses_post( $args['intro'] );
		} else {
			esc_html_e( 'Connect this site to MCP-compatible AI clients (Claude, Cursor, ChatGPT custom connectors, VS Code, Codex) by exposing its Abilities through the WordPress MCP Adapter. Clients authenticate with a refreshable Application Password issued through a one-click consent screen — no manual key juggling.', 'wp-oauth-app-passwords' );
		}
		if ( '' !== $args['docs_url'] ) {
			echo ' ' . sprintf(
				/* translators: %s: link to documentation page. */
				esc_html__( 'For more information, read our %s page.', 'wp-oauth-app-passwords' ),
				'<a href="' . esc_url( $args['docs_url'] ) . '" target="_blank" rel="noopener">' . esc_html__( 'documentation', 'wp-oauth-app-passwords' ) . '</a>'
			);
		}
		echo '</p>';

		echo '<div class="pixelite-mcp-grid">';
		self::card_wordpress( $abilities );
		self::card_adapter( $adapter );
		self::card_url( $ready, $mcp_url, $discovery );
		self::card_auth( $oauth );
		self::card_discovery( $discovery );
		echo '</div>';

		self::print_copy_script();

		echo '</div>';
	}

	private static function card_wordpress( bool $abilities ): void {
		$state = $abilities ? 'is-ready' : 'is-error';
		$label = $abilities ? __( 'Ready', 'wp-oauth-app-passwords' ) : __( 'Blocked', 'wp-oauth-app-passwords' );
		?>
		<div class="pixelite-mcp-card <?php echo esc_attr( $state ); ?>">
			<span class="pixelite-mcp-pill <?php echo esc_attr( $state ); ?>"><?php echo esc_html( $label ); ?></span>
			<h2><?php esc_html_e( '1. WordPress 7.0+', 'wp-oauth-app-passwords' ); ?></h2>
			<p><?php echo esc_html( sprintf( /* translators: %s: WordPress version. */ __( 'WordPress version: %s', 'wp-oauth-app-passwords' ), get_bloginfo( 'version' ) ) ); ?></p>
			<p><?php echo $abilities
				? esc_html__( 'The Abilities API is available.', 'wp-oauth-app-passwords' )
				: esc_html__( 'The Abilities API is not available. Update to WordPress 7.0 or later (the Abilities API ships in core from 7.0).', 'wp-oauth-app-passwords' ); ?></p>
		</div>
		<?php
	}

	private static function card_adapter( array $adapter ): void {
		$state = $adapter['active'] ? 'is-ready' : ( $adapter['installed'] ? 'is-warning' : 'is-error' );
		?>
		<div class="pixelite-mcp-card <?php echo esc_attr( $state ); ?>">
			<span class="pixelite-mcp-pill <?php echo esc_attr( $state ); ?>"><?php echo esc_html( $adapter['label'] ); ?></span>
			<h2><?php esc_html_e( '2. MCP Adapter', 'wp-oauth-app-passwords' ); ?></h2>
			<p><?php esc_html_e( 'Install and activate the official WordPress MCP Adapter so AI clients can discover this site\'s abilities.', 'wp-oauth-app-passwords' ); ?></p>
			<?php if ( '' !== $adapter['version'] ) : ?>
				<p class="pixelite-mcp-meta"><?php echo esc_html( sprintf( /* translators: %s: plugin version. */ __( 'Detected version: %s', 'wp-oauth-app-passwords' ), $adapter['version'] ) ); ?></p>
			<?php endif; ?>
			<div class="pixelite-mcp-actions">
				<?php if ( ! $adapter['installed'] ) : ?>
					<?php if ( current_user_can( 'install_plugins' ) ) : ?>
						<?php self::action_form( self::ACTION_INSTALL, __( 'Install MCP Adapter', 'wp-oauth-app-passwords' ) ); ?>
					<?php endif; ?>
					<a class="button" href="https://github.com/WordPress/mcp-adapter/releases" target="_blank" rel="noopener"><?php esc_html_e( 'Manual download', 'wp-oauth-app-passwords' ); ?></a>
				<?php elseif ( ! $adapter['active'] ) : ?>
					<?php if ( current_user_can( 'activate_plugins' ) ) : ?>
						<?php self::action_form( self::ACTION_ACTIVATE, __( 'Activate MCP Adapter', 'wp-oauth-app-passwords' ) ); ?>
					<?php endif; ?>
				<?php else : ?>
					<a class="button" href="<?php echo esc_url( admin_url( 'plugins.php' ) ); ?>"><?php esc_html_e( 'View plugins', 'wp-oauth-app-passwords' ); ?></a>
				<?php endif; ?>
			</div>
		</div>
		<?php
	}

	private static function card_url( bool $ready, string $mcp_url, $discovery ): void {
		$state = $ready ? 'is-ready' : 'is-warning';
		$label = $ready ? __( 'Ready', 'wp-oauth-app-passwords' ) : __( 'Pending', 'wp-oauth-app-passwords' );
		?>
		<div class="pixelite-mcp-card <?php echo esc_attr( $state ); ?>">
			<span class="pixelite-mcp-pill <?php echo esc_attr( $state ); ?>"><?php echo esc_html( $label ); ?></span>
			<h2><?php esc_html_e( '3. MCP server URL', 'wp-oauth-app-passwords' ); ?></h2>
			<?php if ( $ready ) : $id = wp_unique_id( 'pixelite-mcp-url-' ); ?>
				<p><?php esc_html_e( 'Paste this URL into your MCP client (Claude → Settings → Connectors → Add custom connector, etc.):', 'wp-oauth-app-passwords' ); ?></p>
				<div class="pixelite-mcp-url-row">
					<textarea id="<?php echo esc_attr( $id ); ?>" readonly rows="2"><?php echo esc_textarea( $mcp_url ); ?></textarea>
					<button type="button" class="button" data-pixelite-mcp-copy-target="#<?php echo esc_attr( $id ); ?>"><?php esc_html_e( 'Copy', 'wp-oauth-app-passwords' ); ?></button>
				</div>
				<?php if ( is_array( $discovery ) && ! empty( $discovery['actual_as'] ) ) : ?>
					<p class="pixelite-mcp-meta"><?php printf(
						/* translators: %s: OAuth discovery metadata URL. */
						esc_html__( 'OAuth discovery: %s', 'wp-oauth-app-passwords' ),
						'<code>' . esc_html( $discovery['actual_as'] ) . '</code>'
					); ?></p>
				<?php endif; ?>
			<?php else : ?>
				<p><?php esc_html_e( 'Complete steps 1 and 2 first. The MCP server URL will appear here once WordPress 7.0+ and the MCP Adapter are both active.', 'wp-oauth-app-passwords' ); ?></p>
			<?php endif; ?>
		</div>
		<?php
	}

	private static function card_auth( array $oauth ): void {
		$state = $oauth['available'] ? 'is-ready' : 'is-error';
		$label = $oauth['available'] ? __( 'Ready', 'wp-oauth-app-passwords' ) : __( 'Unavailable', 'wp-oauth-app-passwords' );
		?>
		<div class="pixelite-mcp-card <?php echo esc_attr( $state ); ?>">
			<span class="pixelite-mcp-pill <?php echo esc_attr( $state ); ?>"><?php echo esc_html( $label ); ?></span>
			<h2><?php esc_html_e( '4. Authentication', 'wp-oauth-app-passwords' ); ?></h2>
			<?php if ( $oauth['available'] ) : ?>
				<p><?php esc_html_e( 'Clients connect through a one-click consent screen and receive a refreshable Application Password. It appears in the user\'s profile under Application Passwords and can be revoked there at any time.', 'wp-oauth-app-passwords' ); ?></p>
			<?php else : ?>
				<p><?php echo esc_html( $oauth['reason'] ); ?></p>
			<?php endif; ?>
		</div>
		<?php
	}

	/**
	 * Subdirectory discovery card. Only shown on subdirectory installs, where
	 * RFC 8414 clients look for OAuth metadata at the domain root and miss the
	 * subdirectory unless a redirect is added. This turns the single biggest
	 * "the AI client won't connect" failure into a self-diagnosing, copy-paste fix.
	 */
	private static function card_discovery( $discovery ): void {
		if ( ! is_array( $discovery ) || empty( $discovery['is_subdir'] ) ) {
			return;
		}
		$reachable = $discovery['root_reachable']; // true|false|null
		$ok        = ( true === $reachable );
		$state     = $ok ? 'is-ready' : ( null === $reachable ? 'is-warning' : 'is-error' );
		$label     = $ok
			? __( 'OK', 'wp-oauth-app-passwords' )
			: ( null === $reachable ? __( 'Unknown', 'wp-oauth-app-passwords' ) : __( 'Action needed', 'wp-oauth-app-passwords' ) );
		?>
		<div class="pixelite-mcp-card <?php echo esc_attr( $state ); ?>">
			<span class="pixelite-mcp-pill <?php echo esc_attr( $state ); ?>"><?php echo esc_html( $label ); ?></span>
			<h2><?php esc_html_e( '5. AI client discovery', 'wp-oauth-app-passwords' ); ?></h2>
			<p><?php printf(
				/* translators: %s: subdirectory path, e.g. /support. */
				esc_html__( 'WordPress is installed in a subdirectory (%s). AI clients look for the OAuth metadata at your domain root per RFC 8414, which does not reach this subdirectory unless you add a redirect.', 'wp-oauth-app-passwords' ),
				'<code>' . esc_html( $discovery['subdir'] ) . '</code>'
			); ?></p>
			<p>
				<strong><?php esc_html_e( 'Live test:', 'wp-oauth-app-passwords' ); ?></strong>
				<code><?php echo esc_html( $discovery['expected_as'] ); ?></code> &rarr;
				<?php if ( $ok ) : ?>
					<span class="pixelite-mcp-ok"><?php esc_html_e( 'reachable — discovery should work.', 'wp-oauth-app-passwords' ); ?></span>
				<?php elseif ( null === $reachable ) : ?>
					<span class="pixelite-mcp-warn"><?php esc_html_e( 'could not be tested from the server (loopback blocked). Verify it returns JSON from outside.', 'wp-oauth-app-passwords' ); ?></span>
				<?php else : ?>
					<span class="pixelite-mcp-bad"><?php esc_html_e( 'not reachable — AI clients will fail to connect until you add the redirect below.', 'wp-oauth-app-passwords' ); ?></span>
				<?php endif; ?>
			</p>
			<?php if ( ! $ok && ! empty( $discovery['htaccess'] ) ) : ?>
				<p><?php esc_html_e( 'Add this to your domain-root .htaccess (Apache), above the “# BEGIN WordPress” block:', 'wp-oauth-app-passwords' ); ?></p>
				<pre class="pixelite-mcp-fix"><?php echo esc_html( $discovery['htaccess'] ); ?></pre>
				<p class="pixelite-mcp-meta"><?php esc_html_e( 'On nginx, add equivalent location redirects forwarding /.well-known/oauth-* (with the subdirectory suffix) to the subdirectory’s /.well-known/oauth-* paths. After adding it, reload this page to re-test.', 'wp-oauth-app-passwords' ); ?></p>
			<?php endif; ?>
		</div>
		<?php
	}

	private static function action_form( string $action, string $label ): void {
		// Rendered inside the EM settings page which wraps all tab content in a single outer <form>. Nested HTML forms are invalid — browsers ignore the inner <form> tag and the submit button ends up submitting the outer form instead. We avoid nesting by using a plain button with data attributes; the JS below constructs and submits a detached form on click so admin-post.php is actually reached.
		?>
		<button type="button" class="button button-primary"
			data-pixelite-post-action="<?php echo esc_attr( $action ); ?>"
			data-pixelite-post-nonce="<?php echo esc_attr( wp_create_nonce( self::NONCE ) ); ?>"
			data-pixelite-post-url="<?php echo esc_attr( admin_url( 'admin-post.php' ) ); ?>"
		><?php echo esc_html( $label ); ?></button>
		<?php
	}

	/* ---------------------------------------------------------------------
	 * Install / activate handlers (admin-post.php)
	 * ------------------------------------------------------------------ */

	public static function handle_install(): void {
		check_admin_referer( self::NONCE );
		if ( ! current_user_can( 'install_plugins' ) ) {
			wp_die( esc_html__( 'You need permission to install plugins.', 'wp-oauth-app-passwords' ) );
		}

		require_once ABSPATH . 'wp-admin/includes/plugin.php';
		require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
		require_once ABSPATH . 'wp-admin/includes/plugin-install.php';
		require_once ABSPATH . 'wp-admin/includes/file.php';
		require_once ABSPATH . 'wp-admin/includes/misc.php';

		$skin     = new \WP_Ajax_Upgrader_Skin();
		$upgrader = new \Plugin_Upgrader( $skin );
		$result   = $upgrader->install( self::adapter_zip() );

		if ( is_wp_error( $result ) ) {
			self::redirect( 'error', $result->get_error_message() );
		}
		if ( ! self::adapter_state( true )['installed'] ) {
			self::redirect( 'error', __( 'Install completed but the MCP Adapter plugin was not detected.', 'wp-oauth-app-passwords' ) );
		}

		$activate = activate_plugin( self::ADAPTER_PLUGIN );
		if ( is_wp_error( $activate ) ) {
			self::redirect( 'error', $activate->get_error_message() );
		}
		self::redirect( 'success', __( 'MCP Adapter installed and activated.', 'wp-oauth-app-passwords' ) );
	}

	public static function handle_activate(): void {
		check_admin_referer( self::NONCE );
		if ( ! current_user_can( 'activate_plugins' ) ) {
			wp_die( esc_html__( 'You need permission to activate plugins.', 'wp-oauth-app-passwords' ) );
		}
		require_once ABSPATH . 'wp-admin/includes/plugin.php';
		$activate = activate_plugin( self::ADAPTER_PLUGIN );
		if ( is_wp_error( $activate ) ) {
			self::redirect( 'error', $activate->get_error_message() );
		}
		self::redirect( 'success', __( 'MCP Adapter activated.', 'wp-oauth-app-passwords' ) );
	}

	private static function redirect( string $type, string $message ): void {
		set_transient( self::notice_key(), array( 'type' => $type, 'message' => $message ), MINUTE_IN_SECONDS );
		$back = wp_get_referer();
		if ( ! $back ) {
			$back = admin_url();
		}
		wp_safe_redirect( $back );
		exit;
	}

	public static function admin_notices(): void {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		$notice = get_transient( self::notice_key() );
		if ( ! is_array( $notice ) ) {
			return;
		}
		delete_transient( self::notice_key() );
		printf(
			'<div class="notice %s is-dismissible"><p>%s</p></div>',
			esc_attr( 'success' === $notice['type'] ? 'notice-success' : 'notice-error' ),
			esc_html( $notice['message'] )
		);
	}

	private static function notice_key(): string {
		return 'pixelite_oauth_mcp_notice_' . get_current_user_id();
	}

	/* ---------------------------------------------------------------------
	 * State helpers
	 * ------------------------------------------------------------------ */

	public static function abilities_ready(): bool {
		return function_exists( 'wp_register_ability' );
	}

	private static function adapter_zip(): string {
		return (string) apply_filters(
			'pixelite_oauth_mcp_adapter_zip',
			'https://github.com/WordPress/mcp-adapter/releases/latest/download/mcp-adapter.zip'
		);
	}

	/**
	 * @return array{installed:bool, active:bool, plugin_file:string, version:string, label:string}
	 */
	private static function adapter_state( bool $refresh = false ): array {
		if ( ! function_exists( 'get_plugins' ) ) {
			require_once ABSPATH . 'wp-admin/includes/plugin.php';
		}
		if ( $refresh ) {
			wp_clean_plugins_cache( false );
		}
		$plugins     = get_plugins();
		$plugin_file = self::find_adapter_plugin_file( $plugins );
		$installed   = '' !== $plugin_file;
		$active      = $installed && ( is_plugin_active( $plugin_file ) || ( is_multisite() && is_plugin_active_for_network( $plugin_file ) ) );
		$version     = $installed && ! empty( $plugins[ $plugin_file ]['Version'] ) ? $plugins[ $plugin_file ]['Version'] : '';

		return array(
			'installed'   => $installed,
			'active'      => $active,
			'plugin_file' => $plugin_file,
			'version'     => $version,
			'label'       => $active
				? __( 'Active', 'wp-oauth-app-passwords' )
				: ( $installed ? __( 'Installed', 'wp-oauth-app-passwords' ) : __( 'Missing', 'wp-oauth-app-passwords' ) ),
		);
	}

	private static function find_adapter_plugin_file( array $plugins ): string {
		if ( isset( $plugins[ self::ADAPTER_PLUGIN ] ) ) {
			return self::ADAPTER_PLUGIN;
		}
		foreach ( $plugins as $plugin_file => $plugin_data ) {
			$name = isset( $plugin_data['Name'] ) ? $plugin_data['Name'] : '';
			if ( 0 === strpos( $plugin_file, 'mcp-adapter/' ) || false !== stripos( $name, 'MCP Adapter' ) ) {
				return $plugin_file;
			}
		}
		return '';
	}

	/* ---------------------------------------------------------------------
	 * Assets — printed inline, once, so the drop-in has no enqueue dependency
	 * ------------------------------------------------------------------ */

	private static function print_styles(): void {
		if ( self::$printed_style ) {
			return;
		}
		self::$printed_style = true;
		?>
		<style>
			.pixelite-mcp-wrap { max-width: 800px; }
			.pixelite-mcp-heading { margin-top: 2em; }
			.pixelite-mcp-grid { display: flex; flex-direction: column; gap: 12px; margin: 18px 0; }
			.pixelite-mcp-card { background: #fff; border: 1px solid #dcdcde; border-radius: 4px; padding: 14px; border-left: 5px solid #8c8f94; }
			.pixelite-mcp-card h2 { margin-top: 0; }
			.pixelite-mcp-card.is-ready { border-left-color: #00a32a; }
			.pixelite-mcp-card.is-warning { border-left-color: #dba617; }
			.pixelite-mcp-card.is-error { border-left-color: #d63638; }
			.pixelite-mcp-pill { border-radius: 999px; display: inline-block; font-size: 12px; font-weight: 700; margin-bottom: 10px; padding: 5px 10px; text-transform: uppercase; }
			.pixelite-mcp-pill.is-ready { background: #d9f2e3; color: #005c12; }
			.pixelite-mcp-pill.is-warning { background: #fff4cb; color: #704d00; }
			.pixelite-mcp-pill.is-error { background: #f8d7da; color: #8a2424; }
			.pixelite-mcp-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; align-items: center; }
			.pixelite-mcp-actions form { margin: 0; }
			.pixelite-mcp-url-row { align-items: stretch; display: flex; gap: 8px; margin-top: 10px; }
			.pixelite-mcp-url-row textarea { background: #f6f7f7; flex: 1; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; min-height: 40px; min-width: 0; padding: 8px 10px; resize: vertical; }
			.pixelite-mcp-url-row .button { flex-shrink: 0; }
			.pixelite-mcp-meta { color: #646970; font-size: .9em; }
			.pixelite-mcp-fix { background: #1d2327; color: #e2e4e7; padding: 1em; border-radius: 4px; overflow: auto; user-select: all; margin: 10px 0 0; }
			.pixelite-mcp-ok { color: #1a7f1a; }
			.pixelite-mcp-warn { color: #c08500; }
			.pixelite-mcp-bad { color: #b32d2e; }
		</style>
		<?php
	}

	private static function print_copy_script(): void {
		if ( self::$printed_js ) {
			return;
		}
		self::$printed_js = true;
		?>
		<script>
			(function () {
				// Copy-to-clipboard buttons.
				var copyButtons = document.querySelectorAll('[data-pixelite-mcp-copy-target]');
				copyButtons.forEach(function (button) {
					button.addEventListener('click', function () {
						var target = document.querySelector(button.getAttribute('data-pixelite-mcp-copy-target'));
						if (!target) { return; }
						target.focus();
						target.select();
						var done = function () { button.textContent = <?php echo wp_json_encode( __( 'Copied', 'wp-oauth-app-passwords' ) ); ?>; };
						if (navigator.clipboard && window.isSecureContext) {
							navigator.clipboard.writeText(target.value).then(done);
							return;
						}
						try { if (document.execCommand('copy')) { done(); } } catch (e) {}
					});
				});

				// Action buttons (install / activate). These cannot use a nested <form> because the EM settings page already wraps its tab content in an outer form; browsers ignore inner form tags. Instead we build and submit a detached form via JS so admin-post.php is actually reached.
				var actionButtons = document.querySelectorAll('[data-pixelite-post-action]');
				actionButtons.forEach(function (button) {
					button.addEventListener('click', function () {
						var form = document.createElement('form');
						form.method = 'post';
						form.action = button.getAttribute('data-pixelite-post-url');
						var nonce = document.createElement('input');
						nonce.type = 'hidden'; nonce.name = '_wpnonce'; nonce.value = button.getAttribute('data-pixelite-post-nonce');
						var action = document.createElement('input');
						action.type = 'hidden'; action.name = 'action'; action.value = button.getAttribute('data-pixelite-post-action');
						form.appendChild(nonce);
						form.appendChild(action);
						document.body.appendChild(form);
						form.submit();
					});
				});
			})();
		</script>
		<?php
	}
}
