<?php
namespace EM\Integrations;

class Duplicate_Post_Plugins_Admin {
	public static function init() {
		// Yoast Duplicate Post plugin
		if ( defined('DUPLICATE_POST_CURRENT_VERSION') ) {
			if ( isset( $_GET['page'] ) && $_GET['page'] === 'duplicatepost' && isset( $GLOBALS['pagenow'] ) && $GLOBALS['pagenow'] === 'options-general.php' ) {
				add_action( 'admin_notices', [ static::class, 'yoast_duplicate_posts_admin_notices' ] );
			}
		}
		// Duplicate Page plugin
		if ( defined('DUPLICATE_PAGE_PLUGIN_VERSION') ) {
			add_action( 'admin_init', [ static::class, 'disable_duplicate_page_plugin' ] );
		}
		// Copy and Duplicate Plugin
		if ( defined('CDP_VERSION') ) {
			add_filter('post_row_actions', [static::class, 'disable_copy_and_duplicate_plugin_row_actions'], 10, 2);
			add_filter('page_row_actions', [static::class, 'disable_copy_and_duplicate_plugin_row_actions'], 10, 2);
			add_filter('option__cdp_globals', [ static::class, 'disable_copy_and_duplicate_plugin' ], 10, 1 );
		}
	}

	/**
	 * Detects if the current admin page is reltated to our CPTs as in Duplicate_Post_Plugins::get_cpts()
	 * @return bool
	 */
	public static function is_our_cpt() {
		// Your CPTs to disable Duplicate Page plugin features for
		global $typenow;

		// Try to detect list or edit screen for one of the blocked CPTs
		$current_post_type = null;

		if ( isset($_GET['post_type']) ) {
			$current_post_type = sanitize_text_field($_GET['post_type']);
		} elseif ( isset($_GET['post']) ) {
			$post = get_post((int)$_GET['post']);
			if ($post) {
				$current_post_type = $post->post_type;
			}
		} elseif ( isset($typenow) && $typenow ) {
			$current_post_type = $typenow;
		}

		return $current_post_type && in_array( $current_post_type, Duplicate_Post_Plugins::get_cpts() );
	}

	// Yoast Duplicate Post plugin

	/**
	 * @return void
	 */
	public static function yoast_duplicate_posts_admin_notices() {
		// Check if we're in admin, on options-general.php, and on the correct page.
		if (
			isset($_GET['page']) &&
			$_GET['page'] === 'duplicatepost' &&
			isset($GLOBALS['pagenow']) &&
			$GLOBALS['pagenow'] === 'options-general.php'
		) {
			?>
			<div class="notice notice-info">
				<p><?php esc_html_e('Duplicating Events and Locations has been disabled by Events Manager, to avoid breaking data. You can use our Events Manager duplication features instead.', 'events-manager'); ?></p>
				<script type="text/javascript">
					document.addEventListener('DOMContentLoaded', function(){
						if ( document.getElementById('duplicate-post-location') ) {
							document.getElementById('duplicate-post-location').checked = false;
							document.getElementById('duplicate-post-location').disabled = true;
							document.querySelector('label[for="duplicate-post-location"]').innerHTML += ' <em>[<?php echo esc_attr( sprintf(__('disabled by %s', 'events-manager'), 'Events Manager') ); ?>]</em>';
						}
						if ( document.getElementById('duplicate-post-<?php echo EM_POST_TYPE_EVENT; ?>') ) {
							document.getElementById('duplicate-post-<?php echo EM_POST_TYPE_EVENT; ?>').checked = false;
							document.getElementById('duplicate-post-<?php echo EM_POST_TYPE_EVENT; ?>').disabled = true;
							document.querySelector('label[for="duplicate-post-<?php echo EM_POST_TYPE_EVENT; ?>"]').innerHTML += ' <em>[<?php echo esc_attr( sprintf(__('disabled by %s', 'events-manager'), 'Events Manager') ); ?>]</em>';
						}
					});
				</script>
			</div>
			<?php
		}
	}


	// DUPLICATE PAGE plugin
	public static function disable_duplicate_page_plugin() {
		if ( static::is_our_cpt() ) {
			// Remove actions/filters from Duplicate Page plugin before they run
			// Remove row action links
			static::remove_hooks('post_row_actions', '/dt_duplicate_post_link/', 10 );
			static::remove_hooks('page_row_actions', '/dt_duplicate_post_link/', 10 );
			// Remove columns/buttons in the editor (classic/gutenberg)
			static::remove_hooks('post_submitbox_misc_actions', '/duplicate_page_custom_button_classic/');
			static::remove_hooks('admin_head', 'duplicate_page', '/duplicate_page_custom_button_guten/');
			// Remove admin bar link
			static::remove_hooks('wp_before_admin_bar_render', '/duplicate_page_admin_bar_link/');
		}
	}

	// Copy and Duplicate Plugin
	public static function disable_copy_and_duplicate_plugin( $option ) {
		if ( self::is_our_cpt() ) {
			$option['others']['cdp-content-custom'] = 'false';
		}
		return $option;
	}

	public static function disable_copy_and_duplicate_plugin_row_actions($actions, $post) {
		// List of post types you want to disable duplication for
		if ( in_array( $post->post_type, Duplicate_Post_Plugins::get_cpts() ) ) {
			unset($actions['cdp_copy']);
		}
		return $actions;
	}

	// UTILITIES

	/**
	 * Remove any filter/action callback from a hook (optionally at a given priority)
	 * whose method name matches $method_pattern.
	 *
	 * @param string      $hook           The hook name, e.g. 'post_row_actions'
	 * @param string      $method_pattern Regex pattern to match against method names
	 * @param int|null    $priority       If set, only check this priority level; if null, check all.
	 */
	public static function remove_hooks($hook, $method_pattern, $priority = null) {
		global $wp_filter;

		if (empty($wp_filter[$hook])) {
			return;
		}

		// WP 4.7+ uses WP_Hook objects, older uses arrays directly
		$callbacks_ref = is_object($wp_filter[$hook]) && isset($wp_filter[$hook]->callbacks)
			? $wp_filter[$hook]->callbacks
			: $wp_filter[$hook];

		// Determine which priorities to check
		$priorities = ($priority !== null) ? array($priority) : array_keys($callbacks_ref);

		foreach ($priorities as $prio) {
			if (empty($callbacks_ref[$prio])) {
				continue;
			}
			foreach ($callbacks_ref[$prio] as $id => $data) {
				$fun = $data['function'];
				// Only care about class method callbacks
				if (is_array($fun) && isset($fun[1]) && is_string($fun[1])) {
					$method = $fun[1];
					if (preg_match($method_pattern, $method)) {
						// Remove from the real $wp_filter object, by reference
						if (is_object($wp_filter[$hook]) && isset($wp_filter[$hook]->callbacks)) {
							unset($wp_filter[$hook]->callbacks[$prio][$id]);
							if (empty($wp_filter[$hook]->callbacks[$prio])) {
								unset($wp_filter[$hook]->callbacks[$prio]);
							}
						} else {
							unset($wp_filter[$hook][$prio][$id]);
							if (empty($wp_filter[$hook][$prio])) {
								unset($wp_filter[$hook][$prio]);
							}
						}
					}
				}
			}
		}
	}
}
Duplicate_Post_Plugins_Admin::init();