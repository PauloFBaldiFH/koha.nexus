<?php
/**
 * Events Manager — Gutenberg blocks + validation guard bootstrap.
 *
 * Responsibilities:
 *   1. Register the "events-manager" block category.
 *   2. Register dynamic blocks whose render_callback delegates to the existing
 *      widget classes — single source of truth: the widget's widget() method.
 *   3. Expose validation errors collected during save_post via a REST field
 *      (em_validation_errors) on the event / location / event-recurring CPTs,
 *      so the Gutenberg editor can surface them.
 *   4. Capture errors from the existing em_event_save / em_location_save
 *      filters into a transient keyed by post_id + user_id. This is the bridge
 *      between the PHP-side validation flow (unchanged) and the JS-side
 *      Gutenberg notice display — all plugins that already hook em_event_save
 *      or call $EM_Event->add_error() keep working.
 *   5. Enqueue the JS validation guard in the block editor for EM post types.
 *
 * Nothing in this file mutates EM's existing save/validate pipeline — it only
 * listens to the hooks that already exist and translates the result into a
 * Gutenberg-friendly payload.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class EM_Blocks {

	const VALIDATION_TRANSIENT_PREFIX = 'em_validation_errors_';
	const VALIDATION_TRANSIENT_TTL    = HOUR_IN_SECONDS;
	const REST_FIELD                  = 'em_validation_errors';

	/**
	 * Hook everything in.
	 */
	public static function init() {
		add_filter( 'block_categories_all', [ __CLASS__, 'register_block_category' ], 10, 2 );
		add_action( 'init', [ __CLASS__, 'register_blocks' ] );
		// register_post_type_args fires inside register_post_type() during init;
		// adding the filter here (before init runs) ensures we catch every CPT.
		add_filter( 'register_post_type_args', [ __CLASS__, 'add_event_when_template' ], 10, 2 );
		add_action( 'rest_api_init', [ __CLASS__, 'register_rest_field' ] );
		add_action( 'rest_api_init', [ __CLASS__, 'register_validation_endpoint' ] );
		add_action( 'enqueue_block_editor_assets', [ __CLASS__, 'enqueue_editor_assets' ] );
		add_action( 'enqueue_block_editor_assets', [ __CLASS__, 'enqueue_block_editor_data' ] );
		// EM frontend CSS needs to load in BOTH the editor iframe and the frontend
		// so ServerSideRender previews look styled. enqueue_block_editor_assets only
		// reaches the parent document, not the iframe. enqueue_block_assets is the
		// canonical hook for that — it fires in the iframe AND on the frontend
		// (frontend already enqueues via wp_enqueue_scripts; WP dedupes by handle).
		add_action( 'enqueue_block_assets', [ __CLASS__, 'enqueue_block_styles' ] );

		// Hook into the existing EM save filters AFTER the rest of EM core has
		// processed them, so plugins that add errors via $EM_Event->add_error()
		// during em_get_post_meta / em_event_validate are already captured.
		// Works for both classic wp-admin/post.php saves and Gutenberg REST saves:
		// EM_Event_Post_Admin now also registers on rest_api_init (see
		// classes/em-event-post-admin.php), and events-manager.php loads the
		// admin/API include block for both is_admin() and REST_REQUEST.
		//
		// These remain useful as a defense-in-depth surface: classic metabox AJAX
		// saves still flow through here, and non-Gutenberg REST clients can read
		// the resulting `em_validation_errors` REST field. The primary Gutenberg
		// UX path is now the ACF-style click intercept (see register_validation_endpoint
		// and blocks/src/gutenberg-validation/index.js).
		add_filter( 'em_event_save', [ __CLASS__, 'capture_event_errors' ], 9999, 2 );
		add_filter( 'em_location_save', [ __CLASS__, 'capture_location_errors' ], 9999, 2 );

		// Stop EM's dbem_notes wpautop from mangling block-rendered HTML inside
		// single-event pages. EM's event-single.php template uses the
		// #_EVENTNOTES placeholder, which expands to the already block-rendered
		// post_content and then runs the dbem_notes filter chain — including
		// wpautop (classes/em-event.php line 4045). wpautop emits unbalanced
		// </p> tags around self-closing inline children (e.g. EM's empty
		// em-icon spans), which browsers then "fix" by inserting empty <p></p>
		// — and those phantom paragraphs take up grid cells in
		// em-item-meta-line, collapsing the address column to 0px.
		//
		// Solution: at priority 5 (before wpautop at 10), detect if the content
		// being filtered came from a block render, and if so remove wpautop for
		// just this invocation. We re-add it at priority 11 so subsequent
		// dbem_notes calls (e.g. classic-editor event descriptions) keep their
		// wpautop behaviour intact.
		add_filter( 'dbem_notes', [ __CLASS__, 'maybe_skip_wpautop' ], 5 );
		add_filter( 'dbem_notes', [ __CLASS__, 'restore_wpautop' ], 11 );
	}

	/**
	 * Detect block-rendered output and temporarily remove wpautop from
	 * dbem_notes so it doesn't mangle the markup.
	 */
	public static function maybe_skip_wpautop( $content ) {
		if ( is_string( $content ) && (
			strpos( $content, 'em-list-widget' ) !== false ||
			strpos( $content, 'em-event-content' ) !== false ||
			strpos( $content, 'em-view-container' ) !== false ||
			strpos( $content, 'wp-block-events-manager' ) !== false
		) ) {
			remove_filter( 'dbem_notes', 'wpautop' );
		}
		return $content;
	}

	/**
	 * Re-add wpautop to dbem_notes after the current invocation finishes, so
	 * subsequent classic-editor content keeps its autop behaviour.
	 */
	public static function restore_wpautop( $content ) {
		if ( ! has_filter( 'dbem_notes', 'wpautop' ) ) {
			add_filter( 'dbem_notes', 'wpautop', 10 );
		}
		return $content;
	}

	/* -----------------------------------------------------------------
	 * Block registration
	 * ----------------------------------------------------------------- */

	public static function register_block_category( $categories, $context ) {
		// Only register if not already there (defensive against double-load).
		foreach ( $categories as $cat ) {
			if ( isset( $cat['slug'] ) && $cat['slug'] === 'events-manager' ) {
				return $categories;
			}
		}
		array_unshift( $categories, [
			'slug'  => 'events-manager',
			'title' => __( 'Events Manager', 'events-manager' ),
			'icon'  => 'calendar-alt',
		] );
		return $categories;
	}

	public static function register_blocks() {
		$build_dir = __DIR__ . '/build';

		// Calendar — delegates to EM_Widget_Calendar.
		if ( file_exists( $build_dir . '/calendar/block.json' ) ) {
			register_block_type( $build_dir . '/calendar', [
				'render_callback' => [ __CLASS__, 'render_calendar' ],
			] );
		}

		// Events list — delegates to EM_Widget.
		if ( file_exists( $build_dir . '/events/block.json' ) ) {
			register_block_type( $build_dir . '/events', [
				'render_callback' => [ __CLASS__, 'render_events' ],
			] );
		}

		// Locations list — delegates to EM_Locations_Widget (only if locations enabled).
		if ( file_exists( $build_dir . '/locations/block.json' ) && get_option( 'dbem_locations_enabled', true ) ) {
			register_block_type( $build_dir . '/locations', [
				'render_callback' => [ __CLASS__, 'render_locations' ],
			] );
		}

		// Event When — inline date/time/recurrence canvas block. Editor-only;
		// no frontend render callback needed (save() returns null in JS).
		if ( file_exists( $build_dir . '/event-when/block.json' ) ) {
			register_block_type( $build_dir . '/event-when' );
		}
	}

	/**
	 * Add the em/event-when block as the first entry in the event CPT template
	 * so new events start with it pre-inserted and locked. The JS guard also
	 * injects it into existing events that don't have it yet.
	 */
	public static function add_event_when_template( $args, $post_type ) {
		if ( ! em_use_block_editor() ) {
			return $args;
		}
		// Only the canvas layout seeds the in-editor block; the tabs/metaboxes layouts present the real metaboxes instead.
		if ( ! class_exists( 'EM\Editor\Editor' ) ) {
			return $args;
		}
		// Seed the canvas block only for CPTs whose editor effectively renders in the canvas — events (incl. recurring + archetypes); the location editor shelves canvas.
		$registry = isset( $args['labels'] ) ? \EM\Editor\Editor::registry_for_post_type( $post_type ) : null;
		if ( ! $registry || \EM\Editor\Editor::effective_layout( $registry ) !== 'canvas' ) {
			return $args;
		}
		$args['template'] = array_merge(
			[ [ 'em/event-when', [ 'lock' => [ 'move' => true, 'remove' => true ] ] ] ],
			$args['template'] ?? []
		);
		return $args;
	}

	/* -----------------------------------------------------------------
	 * Render callbacks — delegate to the existing widget classes so that
	 * widget() and the block share one rendering implementation.
	 * ----------------------------------------------------------------- */

	private static function render_widget( $widget_class, $attrs ) {
		if ( ! class_exists( $widget_class ) ) {
			return '';
		}
		$widget = new $widget_class();
		$args = [
			'before_widget' => '',
			'after_widget'  => '',
			'before_title'  => '<h3 class="wp-block-events-manager__title">',
			'after_title'   => '</h3>',
		];

		// Block.json attributes default to empty strings/zero for many fields
		// (format, format_header, no_events_text, etc.). When passed straight to
		// the widget, array_merge( $widget->defaults, $attrs ) lets those empty
		// strings clobber the widget's real defaults — most importantly the
		// per-item format template, which produces empty <li> output for every
		// event/location. Strip empty values so the widget's defaults kick in
		// for any field the user hasn't actually configured.
		$instance = [];
		foreach ( (array) $attrs as $key => $value ) {
			if ( $value === '' || $value === null ) {
				continue;
			}
			$instance[ $key ] = $value;
		}

		ob_start();
		$widget->widget( $args, $instance );
		$html = ob_get_clean();

		// The EM widget templates (templates/formats/block_*_list_item_format.php
		// and the items they render) are indented for readability — newlines and
		// tabs between every tag. When this output ends up inside a single-event
		// post (the_content path) and then through the dbem_notes filter chain
		// in classes/em-event.php (which add wpautop, line 4045), all that
		// inter-tag whitespace gets turned into spurious <p>…</p> and <br />
		// wrappers, breaking the address grid and the flex/grid item alignment.
		// Compressing whitespace between tags leaves wpautop with nothing to
		// expand, so the block markup arrives at the browser intact.
		return preg_replace( '/>\s+</', '><', $html );
	}

	public static function render_calendar( $attrs ) {
		return self::render_widget( 'EM_Widget_Calendar', $attrs );
	}

	public static function render_events( $attrs ) {
		return self::render_widget( 'EM_Widget', $attrs );
	}

	public static function render_locations( $attrs ) {
		return self::render_widget( 'EM_Locations_Widget', $attrs );
	}

	/* -----------------------------------------------------------------
	 * Pre-save validation endpoint — ACF-style.
	 *
	 * The JS guard (blocks/src/gutenberg-validation/index.js) intercepts clicks
	 * on the Publish/Update button, snapshots the classic metabox form, and
	 * POSTs it here. We rehydrate $_POST / $_REQUEST with the snapshot so EM's
	 * existing get_post_meta() + validate() pipeline reads the editor's current
	 * state (including metabox fields like dates/times/location that the REST
	 * post payload doesn't carry), then return { valid, errors } as JSON.
	 *
	 * If errors come back, the JS aborts the save and shows them via createErrorNotice.
	 * If valid, the JS dispatches savePost() programmatically and Gutenberg proceeds.
	 *
	 * Reference: ACF's integration pattern from Gutenberg issue #12692.
	 * ----------------------------------------------------------------- */

	public static function register_validation_endpoint() {
		register_rest_route( 'events-manager/v1', '/blocks/event/validate', [
			'methods'             => 'POST',
			'callback'            => [ __CLASS__, 'rest_validate' ],
			'permission_callback' => [ __CLASS__, 'rest_validate_permission' ],
			'args'                => [
				'post_id' => [
					'type'              => 'integer',
					'required'          => false,
					'default'           => 0,
					'sanitize_callback' => 'absint',
				],
				'post_type' => [
					'type'              => 'string',
					'required'          => true,
					'sanitize_callback' => 'sanitize_key',
				],
				'form_data' => [
					'type'     => 'string',
					'required' => true,
				],
			],
		] );
	}

	/**
	 * Permission check: the user must be able to edit this specific post (or
	 * generally edit events/locations if this is a brand new post with no ID yet).
	 */
	public static function rest_validate_permission( WP_REST_Request $request ) {
		$post_id = (int) $request->get_param( 'post_id' );
		if ( $post_id ) {
			return current_user_can( 'edit_post', $post_id );
		}
		return current_user_can( 'edit_events' ) || current_user_can( 'edit_posts' );
	}

	/**
	 * Validation handler — rehydrates EM globals from the form snapshot, runs
	 * EM_Event::validate() (or EM_Location::validate()), normalises the errors
	 * into the same shape the JS guard already understands.
	 */
	public static function rest_validate( WP_REST_Request $request ) {
		$post_id   = (int) $request->get_param( 'post_id' );
		$post_type = (string) $request->get_param( 'post_type' );
		$form_data = (string) $request->get_param( 'form_data' );

		// jQuery's $(form).serialize() output is URL-encoded; parse_str() turns
		// it back into the same shape EM's get_post_meta() expects from $_POST,
		// including bracketed names like em_attributes[foo].
		$parsed = [];
		if ( $form_data !== '' ) {
			parse_str( $form_data, $parsed );
		}

		// Stash and replace $_POST / $_REQUEST so EM's existing pipeline reads
		// the editor's current state instead of the (empty) REST body.
		$saved_post    = $_POST;
		$saved_request = $_REQUEST;
		$_POST         = $parsed;
		$_REQUEST      = array_merge( $saved_request, $parsed );

		$is_location = ( defined( 'EM_POST_TYPE_LOCATION' ) && $post_type === EM_POST_TYPE_LOCATION );
		$EM_Object   = null;

		try {
			if ( $is_location ) {
				$EM_Object = $post_id ? em_get_location( $post_id, 'post_id' ) : new EM_Location();
				$EM_Object->post_type = $post_type;
				$EM_Object->get_post_meta();
				$EM_Object->validate();
			} else {
				$EM_Object = $post_id ? em_get_event( $post_id, 'post_id' ) : new EM_Event();
				$EM_Object->post_type = $post_type;
				$EM_Object->get_post_meta();
				$EM_Object->validate();
			}

			$raw_errors = method_exists( $EM_Object, 'get_errors' ) ? $EM_Object->get_errors() : [];
			if ( ! is_array( $raw_errors ) ) {
				$raw_errors = [];
			}
		} finally {
			// Always restore globals — even if validate() threw.
			$_POST    = $saved_post;
			$_REQUEST = $saved_request;
		}

		// Normalise into { code, message } pairs (same shape as the REST field).
		$payload = [];
		foreach ( $raw_errors as $idx => $err ) {
			if ( is_string( $err ) ) {
				$payload[] = [
					'code'    => 'em_error_' . $idx,
					'message' => wp_strip_all_tags( $err ),
				];
			} elseif ( is_array( $err ) ) {
				foreach ( $err as $code => $message ) {
					$payload[] = [
						'code'    => is_string( $code ) ? $code : 'em_error_' . $idx,
						'message' => wp_strip_all_tags( is_string( $message ) ? $message : wp_json_encode( $message ) ),
					];
				}
			}
		}

		$payload = apply_filters( 'em_validation_errors_payload', $payload, $EM_Object );

		return rest_ensure_response( [
			'valid'  => empty( $payload ),
			'errors' => $payload,
		] );
	}

	/* -----------------------------------------------------------------
	 * Validation guard — capture errors → transient → REST field.
	 * ----------------------------------------------------------------- */

	/**
	 * Hook for em_event_save. $result is the success boolean returned by
	 * EM_Event::save(); $EM_Event is the populated event object whose
	 * ->errors array now reflects core + all plugin-added errors.
	 *
	 * @param bool      $result
	 * @param EM_Event  $EM_Event
	 * @return bool
	 */
	public static function capture_event_errors( $result, $EM_Event ) {
		if ( ! is_object( $EM_Event ) || empty( $EM_Event->post_id ) ) {
			return $result;
		}
		self::store_errors( (int) $EM_Event->post_id, $result, $EM_Event );
		return $result;
	}

	public static function capture_location_errors( $result, $EM_Location ) {
		if ( ! is_object( $EM_Location ) || empty( $EM_Location->post_id ) ) {
			return $result;
		}
		self::store_errors( (int) $EM_Location->post_id, $result, $EM_Location );
		return $result;
	}

	/**
	 * Write or clear the validation errors transient for this post + user.
	 *
	 * On success we clear any stale transient so the editor stops showing old
	 * errors. On failure we serialize errors into a Gutenberg-ready shape.
	 */
	private static function store_errors( $post_id, $success, $em_object ) {
		$user_id = get_current_user_id();
		$key     = self::transient_key( $post_id, $user_id );

		if ( $success ) {
			delete_transient( $key );
			return;
		}

		$raw = method_exists( $em_object, 'get_errors' ) ? $em_object->get_errors() : [];
		if ( ! is_array( $raw ) ) {
			$raw = [];
		}

		$payload = [];
		foreach ( $raw as $idx => $err ) {
			if ( is_string( $err ) ) {
				$payload[] = [
					'code'    => 'em_error_' . $idx,
					'message' => wp_strip_all_tags( $err ),
				];
			} elseif ( is_array( $err ) ) {
				// EM_Object::add_error() occasionally stores keyed sub-arrays.
				foreach ( $err as $code => $message ) {
					$payload[] = [
						'code'    => is_string( $code ) ? $code : 'em_error_' . $idx,
						'message' => wp_strip_all_tags( is_string( $message ) ? $message : wp_json_encode( $message ) ),
					];
				}
			}
		}

		/**
		 * Filter the validation error payload before it is stored for the
		 * Gutenberg editor to read. Plugins can shape entries to add a
		 * 'field' hint or upgrade the 'code' to something more semantic.
		 */
		$payload = apply_filters( 'em_validation_errors_payload', $payload, $em_object );

		if ( empty( $payload ) ) {
			delete_transient( $key );
			return;
		}

		set_transient( $key, $payload, self::VALIDATION_TRANSIENT_TTL );
	}

	private static function transient_key( $post_id, $user_id ) {
		return self::VALIDATION_TRANSIENT_PREFIX . $post_id . '_' . $user_id;
	}

	/* -----------------------------------------------------------------
	 * REST exposure — adds em_validation_errors to the event REST response.
	 * ----------------------------------------------------------------- */

	public static function register_rest_field() {
		$post_types = self::em_post_types();
		if ( empty( $post_types ) ) {
			return;
		}
		register_rest_field( $post_types, self::REST_FIELD, [
			'get_callback'    => [ __CLASS__, 'rest_get_errors' ],
			'update_callback' => null,
			'schema'          => [
				'description' => __( 'Events Manager validation errors from the last save, if any.', 'events-manager' ),
				'type'        => 'array',
				'context'     => [ 'edit' ],
				'readonly'    => true,
				'items'       => [
					'type'       => 'object',
					'properties' => [
						'code'    => [ 'type' => 'string' ],
						'message' => [ 'type' => 'string' ],
						'field'   => [ 'type' => 'string' ],
					],
				],
			],
		] );
	}

	public static function rest_get_errors( $post_arr ) {
		$post_id = isset( $post_arr['id'] ) ? (int) $post_arr['id'] : 0;
		if ( ! $post_id ) {
			return [];
		}
		$user_id = get_current_user_id();
		$key     = self::transient_key( $post_id, $user_id );
		$errors  = get_transient( $key );
		return is_array( $errors ) ? $errors : [];
	}

	/* -----------------------------------------------------------------
	 * Editor asset enqueue — JS plugin that reads em_validation_errors,
	 * locks publish and surfaces notices.
	 * ----------------------------------------------------------------- */

	/**
	 * enqueue_block_assets: fires in BOTH the editor iframe (page/post editor)
	 * AND the frontend. EM's public CSS only loads on the frontend by default
	 * (via wp_enqueue_scripts), which leaves the editor iframe unstyled when
	 * blocks render their ServerSideRender previews. Calling enqueue_public_styles
	 * here pushes the events-manager stylesheet into the iframe; on the
	 * frontend WP dedupes by handle so there's no double-load.
	 *
	 * We also enqueue EM's public JS in the EDITOR ONLY because the Calendar
	 * block relies on it to layer visual indicators (event-day circles, pill
	 * markers, etc.) on top of the server-rendered grid. On the frontend, JS
	 * is already enqueued by EM_Scripts_and_Styles::public_enqueue() (hooked
	 * to wp_enqueue_scripts) with a properly-filtered deps array — calling
	 * enqueue_scripts() with its default deps array (which includes the
	 * admin-only 'wp-color-picker' handle) FIRST would poison the registration:
	 * wp_enqueue_script is a no-op on the second call, so the bad deps stick
	 * and WP silently refuses to print events-manager.js because the dep
	 * doesn't exist on the frontend.
	 */
	public static function enqueue_block_styles() {
		if ( ! class_exists( 'EM_Scripts_and_Styles' ) ) {
			return;
		}
		EM_Scripts_and_Styles::register();
		if ( is_admin() || self::frontend_post_has_em_block() ) {
			EM_Scripts_and_Styles::enqueue_public_styles();
		}
		// is_admin() is true in the block editor iframe (it's an admin page)
		// and false on the public frontend. Gate the JS enqueue on it so we
		// only push the calendar-indicator JS into the editor.
		if ( is_admin() ) {
			EM_Scripts_and_Styles::enqueue_scripts();
			// The em/event-when canvas block renders EM's classic When /
			// Recurrences / Bookings metabox HTML inside the editor iframe. Those
			// forms are styled by EM's admin + event-editor stylesheets, which
			// normally only reach the parent admin document: admin CSS via
			// admin_enqueue, and the event-editor CSS via EM's JS asset-loader
			// keyed on the .em-event-editor body class. Neither crosses into the
			// iframe, leaving the canvas forms unstyled. Push them in here (gated
			// to EM CPT editors so unrelated page/post editors stay untouched).
			// Both stylesheets are .em-namespaced so they can't leak into the
			// block editor's own chrome. enqueue_admin_styles also fires
			// em_enqueue_admin_styles, which is how EM Pro adds its bookings/
			// tickets admin CSS for the Bookings tab.
			if ( self::is_em_cpt_editor_screen() ) {
				EM_Scripts_and_Styles::enqueue_admin_styles();
				// Fire em_enqueue_admin_scripts inside the iframe too, so add-ons (e.g. Pro custom emails) can inject their editor JS into the canvas — the scripts analogue of the admin-styles hook above.
				EM_Scripts_and_Styles::enqueue_admin_scripts();
				EM_Scripts_and_Styles::enqueue_event_editor_styles();
				// Also pull WordPress core's own admin stylesheets into the iframe so the
				// metabox forms inherit the standard backend styling (inputs, selects,
				// .button, .postbox, .form-table, dashicons). The canvas iframe is a bare
				// document that otherwise only has EM's admin CSS, so the controls look
				// unstyled next to the classic editor. These rules are .wp-admin /
				// .wp-core-ui scoped, matching the wrapper the canvas block renders around
				// the metabox HTML, so they don't leak into the block editor's own chrome.
				foreach ( array( 'common', 'forms', 'buttons', 'dashicons' ) as $core_style ) {
					wp_enqueue_style( $core_style );
				}
				// The canvas iframe inherits the theme's editor content font (often a
				// serif at 16px), so the metabox content reads differently to the classic
				// backend, which uses the admin system-font stack at 13px. Pin that stack
				// on the wrapper so the panels match the classic editor exactly. Scoped to
				// .em-event-editor so it only touches our consolidated metabox content.
				wp_add_inline_style( 'forms',
					'.em-event-when-block,.em-event-editor{font-family:-apple-system,"system-ui","Segoe UI",Roboto,Oxygen-Sans,Ubuntu,Cantarell,"Helvetica Neue",sans-serif;}'
					. '.em-event-editor{font-size:13px;line-height:1.4em;}'
				);
			}
		}
	}

	/**
	 * True when the current admin request is the block editor for an EM CPT
	 * (event / event-recurring / location). Used to gate the admin-side
	 * stylesheets we push into the editor iframe. Prefers the current screen
	 * (reliable on post.php / post-new.php) and falls back to the request so it
	 * still resolves if the screen isn't set yet.
	 */
	private static function is_em_cpt_editor_screen() {
		if ( ! is_admin() ) {
			return false;
		}
		$post_types = self::em_post_types();
		if ( empty( $post_types ) ) {
			return false;
		}
		if ( function_exists( 'get_current_screen' ) ) {
			$screen = get_current_screen();
			if ( $screen && $screen->post_type ) {
				return in_array( $screen->post_type, $post_types, true );
			}
		}
		if ( ! empty( $_GET['post_type'] ) ) {
			return in_array( sanitize_key( wp_unslash( $_GET['post_type'] ) ), $post_types, true );
		}
		if ( ! empty( $_GET['post'] ) ) {
			$pt = get_post_type( absint( $_GET['post'] ) );
			return $pt && in_array( $pt, $post_types, true );
		}
		return false;
	}

	protected static function frontend_post_has_em_block() {
		if ( is_admin() || ! function_exists( 'has_block' ) ) {
			return false;
		}
		$post = get_post();
		if ( ! $post ) {
			return false;
		}
		foreach ( [ 'events-manager/events', 'events-manager/calendar', 'events-manager/locations', 'events-manager/event-when' ] as $block ) {
			if ( has_block( $block, $post ) ) {
				return true;
			}
		}
		return false;
	}

	public static function enqueue_editor_assets() {
		// Validation guard JS only loads on the EM CPT editors (event /
		// event-recurring / location). Other block editors (page, widget, etc.)
		// don't need the publish-intercept logic.
		$post_types = self::em_post_types();
		if ( empty( $post_types ) ) {
			return;
		}
		$screen = function_exists( 'get_current_screen' ) ? get_current_screen() : null;
		if ( $screen && $screen->post_type && ! in_array( $screen->post_type, $post_types, true ) ) {
			return;
		}

		$asset_file = __DIR__ . '/build/gutenberg-validation/index.asset.php';
		if ( ! file_exists( $asset_file ) ) {
			return;
		}
		$asset = include $asset_file;

		// Merge jquery into deps — the JS uses window.jQuery to serialise the
		// classic editor form (#post), so we need to guarantee it's loaded.
		// wp-scripts won't add it to index.asset.php because we don't `import`
		// jquery (it isn't an ES module here).
		$deps = $asset['dependencies'] ?? [];
		if ( ! in_array( 'jquery', $deps, true ) ) {
			$deps[] = 'jquery';
		}

		wp_enqueue_script(
			'em-gutenberg-validation',
			plugins_url( 'build/gutenberg-validation/index.js', __FILE__ ),
			$deps,
			$asset['version'] ?? null,
			true
		);
		wp_set_script_translations( 'em-gutenberg-validation', 'events-manager' );
	}

	/**
	 * Expose data the block inspectors need (currently the list of event
	 * archetypes) to the editor as window.EMBlocks, so the Calendar block can
	 * offer the same archetype choice the widget does. Attached to wp-blocks so
	 * it runs before any block's editor script.
	 */
	public static function enqueue_block_editor_data() {
		$archetypes = [];
		if ( class_exists( '\EM\Archetypes' ) && ! empty( \EM\Archetypes::$types ) ) {
			foreach ( \EM\Archetypes::$types as $type => $archetype ) {
				$archetypes[] = [
					'value' => $type,
					'label' => isset( $archetype['label'] ) ? $archetype['label'] : $type,
				];
			}
		}
		wp_add_inline_script(
			'wp-blocks',
			'window.EMBlocks = ' . wp_json_encode( [ 'archetypes' => $archetypes ] ) . ';',
			'before'
		);
	}

	private static function em_post_types() {
		// Union of the editor registries' post types — events (incl. archetypes + recurring) and the location CPT even when renamed. Falls back to the legacy set if the editor classes aren't loaded.
		if ( class_exists( '\\EM\\Editor\\Editor' ) ) {
			$types = \EM\Editor\Event::instance()->post_types();
			if ( get_option( 'dbem_locations_enabled', true ) ) {
				$types = array_merge( $types, \EM\Editor\Location::instance()->post_types() );
			}
			$types = array_values( array_unique( array_filter( $types ) ) );
			if ( ! empty( $types ) ) {
				return $types;
			}
		}
		$types = [];
		if ( defined( 'EM_POST_TYPE_EVENT' ) ) {
			$types[] = EM_POST_TYPE_EVENT;
		}
		if ( defined( 'EM_POST_TYPE_LOCATION' ) && get_option( 'dbem_locations_enabled', true ) ) {
			$types[] = EM_POST_TYPE_LOCATION;
		}
		if ( get_option( 'dbem_repeating_enabled' ) ) {
			$types[] = 'event-recurring';
		}
		return $types;
	}
}

EM_Blocks::init();

// The editor tab registry + layout controller now live in classes/editor/ (\EM\Editor\*), loaded from events-manager.php.
