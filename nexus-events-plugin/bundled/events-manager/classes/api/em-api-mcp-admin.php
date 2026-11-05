<?php
namespace EM\API;

/**
 * AI / MCP setup meta box on Events > Settings > General.
 *
 * The wizard itself — WordPress version check, MCP Adapter install/activate, the
 * server URL, authentication status and subdirectory discovery diagnostics — now
 * lives in the bundled \Pixelite\OAuth_App_Passwords library, shared with the
 * bbPress API plugin so both render an identical screen. This class is just the
 * Events Manager seam: it keeps the settings-page postbox chrome and forwards to
 * the library's drop-in renderer. The library auto-registers its own
 * install/activate handlers in wp-admin.
 *
 * The only Events-Manager-specific behaviour retained here is resolving the MCP
 * Adapter download URL from the GitHub release API (via the library's
 * pixelite_oauth_mcp_adapter_zip filter), so nothing is lost versus the previous
 * in-house wizard.
 */
class MCP_Admin {

	const ADAPTER_REPO = 'WordPress/mcp-adapter';
	const DOCS_URL     = 'https://wp-events-plugin.com/documentation/ai/';

	/** Drop-in renderer in the bundled OAuth library. */
	const OAUTH_ADMIN = '\\Pixelite\\OAuth_App_Passwords\\Admin';

	public static function init() {
		add_action( 'em_settings_general_footer', array( static::class, 'render_settings_box' ) );
		// Resolve the MCP Adapter ZIP from the GitHub release API (with fallback),
		// preserving the behaviour of the previous in-house installer.
		add_filter( 'pixelite_oauth_mcp_adapter_zip', array( static::class, 'adapter_download_url' ) );
	}

	public static function render_settings_box() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		$admin = static::OAUTH_ADMIN;
		?>
		<div class="postbox em-mcp-wrap" id="em-opt-mcp">
			<div class="handlediv" title="<?php esc_attr_e( 'Click to toggle', 'events-manager' ); ?>"><br /></div>
			<h3><span><?php esc_html_e( 'AI / MCP Setup', 'events-manager' ); ?></span></h3>
			<div class="inside">
				<?php
				if ( class_exists( $admin ) && method_exists( $admin, 'render' ) ) {
					$admin::render( array(
						// The postbox <h3> is the section title, so suppress the drop-in's own heading.
						'heading'     => '',
						'server_path' => MCP_Server::server_path(),
						'docs_url'    => static::DOCS_URL,
						'intro'       => __( 'Connect Events Manager to MCP-compatible AI clients (Claude, Cursor, ChatGPT custom connectors, VS Code, Codex) by exposing Events Manager Abilities through the WordPress MCP Adapter. Clients authenticate through a one-click consent screen and a refreshable Application Password — no manual key juggling.', 'events-manager' ),
					) );
				} else {
					echo '<p>' . esc_html__( 'The bundled OAuth library is not loaded, so the AI / MCP setup screen is unavailable.', 'events-manager' ) . '</p>';
				}
				?>
			</div>
		</div>
		<?php
	}

	/**
	 * Resolve the MCP Adapter download ZIP. Allows an explicit override via
	 * em_mcp_adapter_download_url, otherwise queries the GitHub release API and
	 * falls back to the latest-release asset URL the library passes in.
	 *
	 * @param string $default ZIP URL the library would use by default.
	 * @return string
	 */
	public static function adapter_download_url( $default = '' ) {
		$filtered = apply_filters( 'em_mcp_adapter_download_url', '' );
		if ( $filtered ) {
			return esc_url_raw( $filtered );
		}

		$fallback = $default ? $default : 'https://github.com/WordPress/mcp-adapter/releases/latest/download/mcp-adapter.zip';
		$response = wp_remote_get( 'https://api.github.com/repos/' . static::ADAPTER_REPO . '/releases/latest', array(
			'timeout' => 10,
			'headers' => array( 'Accept' => 'application/vnd.github+json' ),
		) );
		if ( is_wp_error( $response ) || wp_remote_retrieve_response_code( $response ) !== 200 ) {
			return $fallback;
		}
		$release = json_decode( wp_remote_retrieve_body( $response ), true );
		if ( empty( $release['assets'] ) || ! is_array( $release['assets'] ) ) {
			return $fallback;
		}
		foreach ( $release['assets'] as $asset ) {
			if ( ! empty( $asset['browser_download_url'] ) && preg_match( '/\.zip$/', $asset['browser_download_url'] ) ) {
				return esc_url_raw( $asset['browser_download_url'] );
			}
		}
		return $fallback;
	}
}
