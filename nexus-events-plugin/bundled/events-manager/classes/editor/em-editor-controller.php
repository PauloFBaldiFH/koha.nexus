<?php
/**
 * Events Manager — editor layout controller.
 *
 * Reads the dbem_event_editor_layout setting and presents the relevant tab registry (event or location) through one of three engines:
 *
 *   canvas    — canvas-capable tabs render inside the Gutenberg iframe (the canvas block reads the registry config and folds each tab's metabox HTML in). Default for new installs.
 *   tabs      — the real metabox forms are consolidated into one tabbed container metabox in the parent document (native save, no canvas value-sync).
 *   metaboxes — classic stacked metaboxes; the registry is ignored for layout. Default for existing installs.
 *
 * The same engines serve both the event and location editors; the only difference is which {@see \EM\Editor\Tabs} subclass is resolved for the current screen. The canvas block and validation guard read the choice + registry from window.EM_EDITOR_TABS.
 */
namespace EM\Editor;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class Editor {

	/** @var array box_id => WP metabox definition, captured in tabs mode so render_tabs_metabox() can render each folded box's callback. One screen per request, so static is safe. */
	protected static $folded_boxes = [];

	/**
	 * The configured editor layout, validated. Defaults to metaboxes (least-disruptive fallback; install/upgrade sets the real value — metaboxes for existing installs, canvas for new).
	 *
	 * @return string canvas|tabs|metaboxes
	 */
	public static function layout() {
		$layout = get_option( 'dbem_event_editor_layout', 'metaboxes' );
		return in_array( $layout, [ 'canvas', 'tabs', 'metaboxes' ], true ) ? $layout : 'metaboxes';
	}

	/**
	 * The layout actually used on a given screen — the configured layout, except canvas is shelved (→ metaboxes) for a context whose registry opts out of canvas (e.g. the location editor).
	 */
	public static function effective_layout( $registry = null ) {
		$layout = self::layout();
		if ( $layout === 'canvas' && $registry && ! $registry->supports_canvas() ) {
			return 'metaboxes';
		}
		return $layout;
	}

	/**
	 * Whether canvas mode gathers its non-canvas tabs into a single tabbed fallback box (consumed by the Phase 3 fallback renderer).
	 */
	public static function canvas_fallback() {
		return (bool) get_option( 'dbem_event_editor_canvas_fallback', 1 );
	}

	public static function init() {
		if ( ! is_admin() ) {
			return;
		}
		// Settings page: reveal/hide the layout + fallback rows (the settings tab markup is sanitised, which strips inline <script>, so this rides the footer).
		add_action( 'admin_print_footer_scripts', [ self::class, 'print_settings_toggle_js' ] );

		// Hand the layout choice + the resolved tab registry to the editor JS.
		add_action( 'admin_print_scripts', [ self::class, 'print_editor_config' ] );

		$layout = self::layout();
		if ( $layout === 'canvas' ) {
			add_action( 'admin_head', [ self::class, 'print_canvas_hide_css' ] );
		} elseif ( $layout === 'tabs' ) {
			add_action( 'add_meta_boxes', [ self::class, 'consolidate_metaboxes' ], 20 );
			add_action( 'admin_head', [ self::class, 'print_panel_css' ] );
			add_action( 'admin_print_footer_scripts', [ self::class, 'print_panel_js' ] );
		}
	}

	/* ───────────────────────── Registry resolution ───────────────────────── */

	/**
	 * The tab registry that governs a post type — Location, then Event — or null.
	 *
	 * @return Tabs|null
	 */
	public static function registry_for_post_type( $post_type ) {
		$location = Location::instance();
		if ( $location->handles( $post_type ) ) {
			return $location;
		}
		$event = Event::instance();
		if ( $event->handles( $post_type ) ) {
			return $event;
		}
		return null;
	}

	/**
	 * The registry for the current admin screen, if it's an EM editor using the block editor.
	 *
	 * @return Tabs|null
	 */
	public static function current_registry() {
		if ( ! function_exists( 'em_use_block_editor' ) || ! em_use_block_editor() ) {
			return null;
		}
		$screen = function_exists( 'get_current_screen' ) ? get_current_screen() : null;
		if ( ! $screen || empty( $screen->post_type ) ) {
			return null;
		}
		return self::registry_for_post_type( $screen->post_type );
	}

	/* ───────────────────────── Editor JS config ───────────────────────── */

	/**
	 * Print window.EM_EDITOR_TABS — the layout choice, the canvas-fallback flag, and the normalised registry for this screen's context — so the canvas block and the validation guard build tabs from the registry instead of hard-coded ids.
	 */
	public static function print_editor_config() {
		$registry = self::current_registry();
		if ( ! $registry ) {
			return;
		}
		$config = [
			'layout'   => self::effective_layout( $registry ),
			'fallback' => self::canvas_fallback(),
			'tabs'     => $registry->get_tabs_for_js(),
		];
		echo '<script>window.EM_EDITOR_TABS = ' . wp_json_encode( $config ) . ";</script>\n";
	}

	/**
	 * Canvas mode: hide the classic postboxes that the canvas mirrors, keeping them in the DOM so their inputs still POST via the meta-box-loader. The canvas now renders EVERY mapped tab (not just canvas-capable ones), so hide them all to avoid showing each box twice. Registry-driven, so it covers both events and locations.
	 */
	public static function print_canvas_hide_css() {
		$registry = self::current_registry();
		if ( ! $registry ) {
			return;
		}
		if ( self::effective_layout( $registry ) !== 'canvas' ) {
			return;
		}
		$ids = $registry->get_mapped_metabox_ids( true );
		if ( empty( $ids ) ) {
			return;
		}
		$selectors = [];
		foreach ( $ids as $id ) {
			$selectors[] = '.block-editor-page #' . $id;
		}
		echo '<style>' . implode( ',', $selectors ) . '{display:none !important;}</style>' . "\n";
	}

	/* ───────────────────────── Settings page toggle ───────────────────────── */

	public static function print_settings_toggle_js() {
		$screen = function_exists( 'get_current_screen' ) ? get_current_screen() : null;
		if ( ! $screen || strpos( (string) $screen->id, 'events-manager-options' ) === false ) {
			return;
		}
		?>
		<script>
		( function () {
			function refresh() {
				var ed = document.querySelector('input[name="dbem_editor"]:checked');
				var gb = ed && ed.value === 'gutenberg';
				var layout = document.querySelector('input[name="dbem_event_editor_layout"]:checked');
				var canvas = layout && layout.value === 'canvas';
				document.querySelectorAll('.em-block-editor-option').forEach( function ( r ) { r.style.display = gb ? '' : 'none'; } );
				document.querySelectorAll('.em-canvas-layout-option').forEach( function ( r ) { r.style.display = ( gb && canvas ) ? '' : 'none'; } );
			}
			document.addEventListener('change', function ( e ) {
				if ( e.target.matches && e.target.matches('input[name="dbem_editor"], input[name="dbem_event_editor_layout"]') ) refresh();
			} );
			refresh();
		} )();
		</script>
		<?php
	}

	/* ───────────────────────── tabbed-metabox (tabs) engine ───────────────────────── */

	/**
	 * In tabs mode, fold the registry-mapped metaboxes into one tabbed container. The generic add_meta_boxes action fires BEFORE add_meta_boxes_{$post_type} (where EM registers its boxes), so we only validate here and defer the real work to a late pass on the type-specific hook.
	 */
	public static function consolidate_metaboxes( $post_type ) {
		if ( ! function_exists( 'em_use_block_editor' ) || ! em_use_block_editor() ) {
			return;
		}
		if ( ! self::registry_for_post_type( $post_type ) ) {
			return;
		}
		add_action( 'add_meta_boxes_' . $post_type, [ self::class, 'do_consolidate' ], 100 );
	}

	/**
	 * Late pass (after EM's own registration): pull each registry-mapped metabox out of $wp_meta_boxes (capturing its callback) and register a single container metabox (em-editor-tabs), titled with the CPT's singular name, that renders them as tabs. Folding into a real metabox keeps the content in the normal column, saving natively, with no hiding CSS needed.
	 */
	public static function do_consolidate( $post ) {
		$post_type = self::screen_post_type( $post );
		$registry  = $post_type ? self::registry_for_post_type( $post_type ) : null;
		if ( ! $registry ) {
			return;
		}
		self::$folded_boxes = [];
		foreach ( $registry->get_mapped_metabox_ids() as $box_id ) {
			$box = self::extract_metabox( $post_type, $box_id );
			if ( $box ) {
				self::$folded_boxes[ $box_id ] = $box;
			}
		}
		if ( empty( self::$folded_boxes ) ) {
			return;
		}
		add_meta_box( 'em-editor-tabs', self::container_title( $post_type ), [ self::class, 'render_tabs_metabox' ], $post_type, 'normal', 'high' );
	}

	/**
	 * Remove a registered metabox from $wp_meta_boxes and return its definition ({id,title,callback,args}), so its callback can be rendered inside the tabbed container. Null if absent.
	 */
	private static function extract_metabox( $screen, $box_id ) {
		global $wp_meta_boxes;
		if ( empty( $wp_meta_boxes[ $screen ] ) ) {
			return null;
		}
		foreach ( $wp_meta_boxes[ $screen ] as $context => $priorities ) {
			if ( ! is_array( $priorities ) ) {
				continue;
			}
			foreach ( $priorities as $priority => $boxes ) {
				if ( is_array( $boxes ) && ! empty( $boxes[ $box_id ] ) ) {
					$box = $boxes[ $box_id ];
					unset( $wp_meta_boxes[ $screen ][ $context ][ $priority ][ $box_id ] );
					return $box;
				}
			}
		}
		return null;
	}

	/**
	 * Title for the container metabox — the CPT/archetype singular name (e.g. "Event", "Location"), with a generic fallback.
	 */
	private static function container_title( $screen ) {
		$obj = get_post_type_object( $screen );
		if ( $obj && ! empty( $obj->labels->singular_name ) ) {
			return $obj->labels->singular_name;
		}
		return __( 'Details', 'events-manager' );
	}

	/**
	 * Render the tabbed container: one tab per registry tab that has folded boxes present, each panel rendering its metaboxes' callbacks inline. The original box ids ride on the wrappers so EM's recurrence-visibility JS (which keys on #em-event-recurring) keeps working; the registry class carries the visibility hooks.
	 */
	public static function render_tabs_metabox( $post, $metabox = null ) {
		$post_type = self::screen_post_type( $post );
		$registry  = $post_type ? self::registry_for_post_type( $post_type ) : null;
		if ( ! $registry ) {
			return;
		}

		$render = [];
		foreach ( $registry->get_tabs() as $id => $tab ) {
			$boxes = [];
			foreach ( $tab['metaboxes'] as $box ) {
				if ( isset( self::$folded_boxes[ $box['id'] ] ) ) {
					$boxes[] = $box;
				}
			}
			if ( $boxes ) {
				$render[ $id ] = [ 'label' => $tab['label'], 'boxes' => $boxes ];
			}
		}
		if ( empty( $render ) ) {
			return;
		}

		echo '<div class="em-editor-tabs em">';
		if ( count( $render ) > 1 ) {
			echo '<div class="em-editor-tabs-bar" role="tablist">';
			$first = true;
			foreach ( $render as $id => $data ) {
				printf(
					'<button type="button" class="em-editor-tab%s" data-em-tab-target="%s">%s</button>',
					$first ? ' is-active' : '',
					esc_attr( $id ),
					esc_html( $data['label'] )
				);
				$first = false;
			}
			echo '</div>';
		}

		echo '<div class="em-editor-tabs-body">';
		$first = true;
		foreach ( $render as $id => $data ) {
			printf( '<div class="em-editor-tab-panel" data-em-tab="%s"%s>', esc_attr( $id ), $first ? '' : ' hidden' );
			foreach ( $data['boxes'] as $box ) {
				$stored = self::$folded_boxes[ $box['id'] ];
				$class  = trim( 'em-editor-tab-box ' . $box['class'] );
				printf( '<div id="%1$s" class="%2$s" data-em-metabox="%1$s">', esc_attr( $box['id'] ), esc_attr( $class ) );
				if ( isset( $stored['callback'] ) && is_callable( $stored['callback'] ) ) {
					call_user_func( $stored['callback'], $post, $stored );
				}
				echo '</div>';
			}
			echo '</div>';
			$first = false;
		}
		echo '</div></div>';
	}

	/** Resolve the post type from the current screen, falling back to the passed post object. */
	private static function screen_post_type( $post ) {
		$screen = function_exists( 'get_current_screen' ) ? get_current_screen() : null;
		if ( $screen && ! empty( $screen->post_type ) ) {
			return $screen->post_type;
		}
		return is_object( $post ) && isset( $post->post_type ) ? $post->post_type : '';
	}

	/**
	 * Tabbed-container styles (printed in admin_head so there's no FOUC and no dependency on an EM style handle being enqueued yet). The grey inset sets the card apart from the surrounding meta-box areas; the card itself is a fixed-width, centred panel.
	 */
	public static function print_panel_css() {
		if ( ! self::current_registry() ) {
			return;
		}
		?>
		<style>
		#em-editor-tabs .inside { margin:0; padding:20px; background:#f0f0f0; }
		.em-editor-tabs { max-width:920px; margin:0 auto; background:#fff; border:1px solid #e0e0e0; border-radius:8px; box-shadow:0 1px 2px rgba(0,0,0,.04); box-sizing:border-box; }
		.em-editor-tabs-bar { display:flex; gap:4px; border-bottom:1px solid #dcdcde; padding:0 12px; }
		.em-editor-tabs-bar .em-editor-tab { appearance:none; background:none; border:none; border-bottom:3px solid transparent; margin-bottom:-1px; padding:11px 16px; font-size:14px; font-weight:600; color:inherit; opacity:.6; cursor:pointer; }
		.em-editor-tabs-bar .em-editor-tab.is-active { border-bottom-color:var(--wp-admin-theme-color,#3858e9); opacity:1; }
		.em-editor-tab-panel { padding:16px 18px; }
		.em-editor-tab-panel[hidden] { display:none; }
		/* EM's recurrence-visibility CSS keys on a .em ancestor of the form; inside the tabs container .em is BELOW the form, so re-scope the hide here. syncRecurringMetabox() toggles em-is-recurring on the metabox form. */
		form:not(.em-is-recurring) #em-editor-tabs .recurring-event-editor { display:none; }
		</style>
		<?php
	}

	/**
	 * Tab-switching + a belt-and-suspenders widget init, printed in the footer. The click handler is delegated so it survives the metabox being mounted/reloaded by Gutenberg.
	 */
	public static function print_panel_js() {
		if ( ! self::current_registry() ) {
			return;
		}
		?>
		<script>
		( function () {
			document.addEventListener( 'click', function ( e ) {
				var btn = e.target.closest && e.target.closest( '.em-editor-tabs-bar .em-editor-tab' );
				if ( ! btn ) { return; }
				var wrap = btn.closest( '.em-editor-tabs' );
				if ( ! wrap ) { return; }
				var t = btn.getAttribute( 'data-em-tab-target' );
				wrap.querySelectorAll( '.em-editor-tab' ).forEach( function ( b ) { b.classList.toggle( 'is-active', b.getAttribute( 'data-em-tab-target' ) === t ); } );
				wrap.querySelectorAll( '.em-editor-tab-panel' ).forEach( function ( p ) { p.hidden = p.getAttribute( 'data-em-tab' ) !== t; } );
			} );
			// EM's native init usually catches the server-rendered metabox, but Gutenberg can mount it late — re-run widget setup once it appears.
			var n = 0, iv = setInterval( function () {
				var wrap = document.querySelector( '.em-editor-tabs' );
				if ( wrap && ! wrap.dataset.emReady ) {
					wrap.dataset.emReady = '1';
					if ( typeof window.em_setup_ui_elements === 'function' ) { try { window.em_setup_ui_elements( wrap ); } catch ( e ) {} }
					clearInterval( iv );
				} else if ( ++n > 40 ) { clearInterval( iv ); }
			}, 250 );
		} )();
		</script>
		<?php
	}
}
