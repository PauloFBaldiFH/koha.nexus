<?php
/**
 * Events Manager — editor tab registry (base class).
 *
 * The single source of truth for which tabs an editor shows and which metaboxes fold into each one. There is one subclass per editable context — {@see \EM\Editor\Event}, {@see \EM\Editor\Location} — each exposing its own WordPress filter so add-ons can register first-class tabs. One registry feeds three presentation engines (see {@see \EM\Editor\Editor}): the Gutenberg canvas, the tabbed-metabox container, and plain stacked metaboxes. A site setting picks which engine presents the registry; registration is identical regardless.
 *
 * ── Public API ────────────────────────────────────────────────────────────────
 *
 * Add-ons hook the per-context filter directly (no wrapper functions):
 *
 *   add_filter( 'em_event_editor_tabs', function ( array $tabs ) : array {
 *       $tabs['seating'] = [
 *           'label'          => __( 'Seating', 'em-pro' ),
 *           'priority'       => 50,                        // lower sorts earlier; core uses 10–40
 *           'icon'           => 'dashicons-screenoptions', // dashicon for the responsive icon-only strip
 *           'canvas_support' => true,                      // tab default + can the tab render in the canvas iframe
 *           'metaboxes'      => [
 *               'em-seating-summary',                                        // string => add_meta_box id, inherits the tab defaults
 *               [ 'id' => 'em-seating-designer', 'canvas_support' => false ], // array => per-box override (this one stays native)
 *           ],
 *           // 'callback' => 'render_fn',                  // custom content instead of folding metaboxes (future)
 *       ];
 *       return $tabs;
 *   } );
 *
 * The location editor uses the 'em_location_editor_tabs' filter with the same shape. Read the resolved registry with {@see \EM\Editor\Event::instance()}->get_tabs() etc.
 *
 * ── canvas_support: tab level vs metabox level ─────────────────────────────────
 *
 * `canvas_support` is declared at BOTH levels. At the tab level it is the default for every metabox in that tab and decides whether the tab itself can live in the canvas iframe. At the metabox level it overrides that default for a single box, so a canvas tab can keep one fragile field (a complex selectize/TinyMCE/media field that won't survive the iframe boundary) rendering natively. Undeclared ⇒ false.
 *
 * A metabox entry is either a string (the add_meta_box() id, taking the tab's defaults) or an array of options carrying an `id` (plus optional canvas_support, class, …).
 *
 * Backward compatible by default: an add-on that registers nothing keeps rendering as an ordinary metabox. Tabs only ever consume metaboxes explicitly mapped to them.
 */
namespace EM\Editor;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

abstract class Tabs {

	/** Per-class singletons (Event, Location, …). */
	private static $instances = [];

	/** Per-request cache of the normalised, priority-sorted registry. */
	protected $cache = null;

	protected function __construct() {}

	/**
	 * The singleton for the called subclass — e.g. Event::instance(), Location::instance().
	 *
	 * @return static
	 */
	public static function instance() {
		$class = static::class;
		if ( ! isset( self::$instances[ $class ] ) ) {
			self::$instances[ $class ] = new static();
		}
		return self::$instances[ $class ];
	}

	/* ───────────────────────── Subclass contract ───────────────────────── */

	/** The filter add-ons hook to add or alter this context's tabs, e.g. 'em_event_editor_tabs'. */
	abstract public function filter_name();

	/** The post types this registry governs. */
	abstract public function post_types();

	/** Core tab definitions for this context, used as the initial value passed through the filter. */
	abstract protected function core_tabs();

	/** True when this registry governs the given post type. */
	public function handles( $post_type ) {
		return in_array( $post_type, $this->post_types(), true );
	}

	/** Whether this context can render inside the Gutenberg canvas iframe. Subclasses opt out (e.g. the location editor, whose map needs the parent document). */
	public function supports_canvas() {
		return true;
	}

	/* ───────────────────────── Accessors ───────────────────────── */

	/**
	 * The normalised, priority-sorted registry keyed by tab id. Cached per request. Each tab has label/priority/icon/canvas_support/metaboxes/callback; each metabox entry is the canonical [ id, canvas_support, class ] shape (plus any extra keys the caller supplied).
	 */
	public function get_tabs() {
		if ( $this->cache !== null ) {
			return $this->cache;
		}

		$raw = apply_filters( $this->filter_name(), $this->core_tabs() );
		if ( ! is_array( $raw ) ) {
			$raw = [];
		}

		$normalised = [];
		$order = 0;
		foreach ( $raw as $id => $tab ) {
			if ( ! is_array( $tab ) ) {
				continue;
			}
			$norm = self::normalize_tab( (string) $id, $tab );
			$norm['_order'] = $order++; // decorate for a stable sort
			$normalised[ (string) $id ] = $norm;
		}

		uasort( $normalised, function ( $a, $b ) {
			if ( $a['priority'] === $b['priority'] ) {
				return $a['_order'] <=> $b['_order'];
			}
			return $a['priority'] <=> $b['priority'];
		} );

		foreach ( $normalised as &$tab ) {
			unset( $tab['_order'] );
		}
		unset( $tab );

		$this->cache = $normalised;
		return $normalised;
	}

	/**
	 * The registry reshaped for the JS config (window.EM_EDITOR_TABS). Drops the PHP callback and exposes a has_callback flag instead.
	 */
	public function get_tabs_for_js() {
		$out = [];
		foreach ( $this->get_tabs() as $id => $tab ) {
			$out[] = [
				'id'             => $id,
				'label'          => $tab['label'],
				'priority'       => $tab['priority'],
				'icon'           => $tab['icon'],
				'canvas_support' => $tab['canvas_support'],
				'has_callback'   => ! empty( $tab['callback'] ),
				'metaboxes'      => array_map( function ( $box ) {
					return [ 'id' => $box['id'], 'canvas_support' => $box['canvas_support'], 'class' => $box['class'] ];
				}, $tab['metaboxes'] ),
			];
		}
		return $out;
	}

	/**
	 * Every metabox id mapped to a tab, flattened. Used by the engines to know which boxes the registry owns (to consolidate or hide).
	 *
	 * @param bool $canvas_only when true, only boxes whose effective canvas_support is true.
	 * @return string[]
	 */
	public function get_mapped_metabox_ids( $canvas_only = false ) {
		$ids = [];
		foreach ( $this->get_tabs() as $tab ) {
			foreach ( $tab['metaboxes'] as $box ) {
				if ( $canvas_only && ! $box['canvas_support'] ) {
					continue;
				}
				$ids[] = $box['id'];
			}
		}
		return array_values( array_unique( $ids ) );
	}

	/* ───────────────────────── Normalisation (shared, pure) ───────────────────────── */

	protected static function normalize_tab( $id, array $tab ) {
		$defaults = [
			'label'          => ucwords( str_replace( [ '-', '_' ], ' ', $id ) ),
			'priority'       => 10,
			'icon'           => '',
			'canvas_support' => false,
			'metaboxes'      => [],
			'callback'       => null,
		];
		$tab = array_merge( $defaults, $tab );

		$tab['priority']       = (int) $tab['priority'];
		$tab['canvas_support'] = (bool) $tab['canvas_support'];

		$boxes = is_array( $tab['metaboxes'] ) ? $tab['metaboxes'] : [];
		$tab['metaboxes'] = [];
		foreach ( $boxes as $box ) {
			$norm = self::normalize_metabox( $box, $tab['canvas_support'] );
			if ( $norm !== null ) {
				$tab['metaboxes'][] = $norm;
			}
		}

		return $tab;
	}

	/**
	 * Canonicalise one metabox entry. A bare string is the add_meta_box() id (inherits tab defaults); an array must carry an `id` and may override canvas_support / class / anything else. Null for an unusable entry so it's dropped.
	 *
	 * @param string|array $entry
	 * @param bool         $tab_canvas_default
	 * @return array|null
	 */
	protected static function normalize_metabox( $entry, $tab_canvas_default ) {
		if ( is_string( $entry ) ) {
			$entry = [ 'id' => $entry ];
		}
		if ( ! is_array( $entry ) || empty( $entry['id'] ) ) {
			return null;
		}
		$entry['id']             = (string) $entry['id'];
		$entry['canvas_support'] = array_key_exists( 'canvas_support', $entry ) ? (bool) $entry['canvas_support'] : (bool) $tab_canvas_default;
		$entry['class']          = isset( $entry['class'] ) ? (string) $entry['class'] : '';
		return $entry;
	}
}
