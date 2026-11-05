<?php
namespace EM;
// TODO add repeating functionality for additional Archetypes
// TODO add more input support for sdettings page
// TDO add logic of sowing headers an d JS triggers for radios in admin page
// TODO page options for new ATs
// TODO archetype locking in widgets and shoctcodes

/**
 * @property $options
 */
class Archetypes {
	public static $enabled = true;
	public static $base;
	public static $event = [];
	public static $location = [];
	public static $types = [];
	protected static $options = [];
	protected static $current;

	// Multisite helpers
	public static function get_ms_mode(){
		return is_multisite() ? get_site_option('dbem_ms_archetypes_mode', 'custom') : 'custom';
	}

	public static function init(){
		if ( is_multisite() && !is_network_admin() ) {
			static::$enabled = get_site_option('dbem_ms_archetypes_enabled', true);
		}
		static::$enabled = static::$enabled && ( !defined('EM_CUSTOM_ARCHETYPES') || EM_CUSTOM_ARCHETYPES );

		// add custom caps filtering
		add_filter( 'map_meta_cap', [ static::class, 'map_meta_cap'], 10, 4 );
		// add thumbnail support to theme
		add_action('after_setup_theme', [ static::class, 'after_setup_theme'] ,100);

		// Prep Event CPT
		$event_cpt = get_option('em_cp_events_cpt', 'event');
		static::$event = [
			'cpt' => $event_cpt,
			'cpts' => get_option('em_cp_events_cpts') ?: $event_cpt . 's',
			'show_in_rest' => em_use_block_editor(),
			'slug' => get_option('dbem_cp_events_slug', 'events'),
			'label' => get_option('dbem_cp_events_label' ),
			'label_single' => get_option('dbem_cp_events_label_single' ),
			'repeating' => get_option('dbem_repeating_enabled'), // if enabled, CTPs will create a repeating CPT type
			'taxonomies' => [],
			'menu_icon' => get_option('dbem_cp_events_menu_icon') ?: 'dashicons-em-calendar',
		];

		// add repeating events as an archetype, albeit a special one
		$location_cpt = defined('EM_POST_TYPE_LOCATION') ? EM_POST_TYPE_LOCATION : get_option('em_cp_locations_cpt', 'location');
		if( get_option('dbem_locations_enabled', true) ){
			$location_cpt_supports = ['title','editor','excerpt','thumbnail','author'];
			if( get_option('dbem_cp_locations_custom_fields') ) $location_cpt_supports[] = 'custom-fields';
			if( get_option('dbem_cp_locations_comments') ) $location_cpt_supports[] = 'comments';
			$location_slug = get_option('dbem_cp_locations_slug', 'locations');
			static::$location = [
				'cpt' => $location_cpt,
				'cpts' => get_option('em_cp_locations_cpts') ?: $location_cpt . 's' ,
				'slug' => $location_slug,
				'label' => get_option('dbem_cp_locations_label' ),
				'label_single' => get_option('dbem_cp_locations_label_single' ),
				'capability_type' => ['location', 'locations'],
				'capabilities' => true, // created in create_archetype_cpt based on capability_type
				'show_ui' => !(EM_MS_GLOBAL && !is_main_site() && get_site_option('dbem_ms_mainblog_locations')),
				'show_in_menu' => 'edit.php?post_type='.$event_cpt,
				'show_in_rest' => em_use_block_editor(),
				'exclude_from_search' => !get_option('dbem_cp_locations_search_results'),
				'has_archive' => get_option( 'dbem_cp_locations_has_archive', false ) == true,
				'supports' => apply_filters('em_cp_location_supports', $location_cpt_supports),
			];
		}

		// Legacy constants
		if ( !defined('EM_POST_TYPE_LOCATION') ) define( 'EM_POST_TYPE_LOCATION', Archetypes::$location['cpt'] ?? 'location' );
		define( 'EM_POST_TYPE_LOCATION_SLUG', Archetypes::$location['slug'] ?? 'locations' );

		// Deal with Gutenberg
		if( em_use_block_editor() ){
			add_filter('gutenberg_can_edit_post_type', [ static::class, 'gutenberg_can_edit_post_type' ], 10, 2 ); //Gutenberg
		}

		// add extra achetypes of EM
		if ( static::$enabled ) {
			// Determine source of archetypes: subsite custom vs network-defined
			$source = 'site';
			if ( is_multisite() ) {
				$mode = get_site_option('dbem_ms_archetypes_mode', 'custom');
				if ( $mode === 'network' || $mode === 'choose' ) {
					$source = 'network';
				}
			}
			if ( $source === 'network' ) {
				$archetypes = (array) get_site_option( 'em_ms_event_archetypes', [] );
			} else {
				$archetypes = (array) get_option( 'em_event_archetypes', [] );
			}
			$archetypes = apply_filters( 'em_event_archetypes', $archetypes );
			static::$types = array_merge( static::$types, $archetypes );
			// add repeating sub-archetypes setting
			foreach ( static::$types as $type => $archetype ) {
				if ( !isset( $archetype['repeating'] ) || $archetype['repeating'] === '' ) {
					static::$types[ $type ]['repeating'] = Archetypes::get_option( 'dbem_repeating_enabled', $type );
				}
			}
			if ( is_multisite() && !is_network_admin() && static::get_ms_mode() === 'choose' ) {
				// check if default is a custom type, if so switch main with default
				$default = get_option( 'em_archetype_default', static::$event['cpt'] );;
				if ( $default !== static::$event['cpt'] && isset( static::$types[$default] ) ) {
					static::$types[ static::$event['cpt'] ] = static::$event;
					static::$event = static::$types[ $default ];
					unset( static::$types[ $default ] );
				}
			}
		}

		// Event Constants
		$event_cpt = defined( 'EM_POST_TYPE_EVENT' ) ? EM_POST_TYPE_EVENT : static::$event['cpt'];
		if ( !defined( 'EM_POST_TYPE_EVENT') ) define( 'EM_POST_TYPE_EVENT', $event_cpt );
		$event_slug = defined( 'EM_POST_TYPE_EVENT_SLUG' ) ? EM_POST_TYPE_EVENT_SLUG : static::$event['slug'];
		if ( !defined( 'EM_POST_TYPE_EVENT_SLUG') ) define( 'EM_POST_TYPE_EVENT_SLUG', $event_slug );
		define( 'EM_ADMIN_URL',admin_url().'edit.php?post_type='.EM_POST_TYPE_EVENT ); //we assume the admin url is absolute with at least one querystring

		add_action( 'em_taxonomies_init', [ static::class, 'em_taxonomies_init' ] );

		if ( is_admin() && strstr( $_REQUEST['page'] ?? '', 'events-manager-' ) ) {
			include( EM_DIR . '/classes/em-archetypes-admin.php' );
		}

		add_action('init', [ static::class, 'register_post_types'], 1 );

		// as JS for editor
		add_filter( 'em_enqueue_assets', [ static::class, 'em_enqueue_assets' ] );
	}

	/**
	 * Add taxonomy settings to event and custom archetypes once taxonomies have been initially set up.
	 *
	 * @return void
	 */
	public static function em_taxonomies_init() {
		if ( static::get_option( 'dbem_categories_enabled', EM_POST_TYPE_EVENT ) ) {
			static::$event['taxonomies'][] = EM_TAXONOMY_CATEGORY;
		}
		if ( static::get_option( 'dbem_tags_enabled', EM_POST_TYPE_EVENT ) ) {
			static::$event['taxonomies'][] = EM_TAXONOMY_TAG;
		}
		foreach ( static::$types as $type => $archetype ) {
			// add taxonomies
			if ( !isset($archetype['taxonomies']) || $archetype['taxonomies'] === '' ) {
				if ( static::get_option( 'dbem_categories_enabled', $type ) ) {
					static::$types[$type]['taxonomies'][] = EM_TAXONOMY_CATEGORY;
				}
				if ( static::get_option( 'dbem_tags_enabled', $type ) ) {
					static::$types[$type]['taxonomies'][] = EM_TAXONOMY_TAG;
				}
			}
		}
	}

	public static function em_enqueue_assets( $assets ) {
		$js = Scripts_and_Styles::get_minified_extension_js().'.js'.'?v='.EM_VERSION;
		$assets['#em-opt-archetypes'] = [
			'js' => [
				'archetypes' => EM_DIR_URI . 'includes/js/admin-archetype-editor' . $js,
				'archetypes_ms' => EM_DIR_URI . 'includes/js/admin-archetypes' . $js,
				'qs' => 'qs/qs' . $js,
			],
			// CSS added in partials/admin/archetypes.scss
		];
		return $assets;
	}

	/**
	 * Gets an archetype by its CPT name, does not get repeating sub-archetypes, just the parent archetype.
	 * @param $type
	 *
	 * @return array|mixed|void
	 */
	public static function get( $type ) {
		if ( $type === static::$event['cpt'] ) {
			return static::$event;
		}
		if ( !empty( static::$types[$type] ) ) {
			return static::$types[$type];
		}
		if ( !empty( static::$location[$type] ) ) {
			return static::$location[$type];
		}
		return null;
	}

	/**
	 * Detects the current archetype being viewed, if there is one. Otherwise it will default to the default event archetype.
	 *
	 * Custom archetypes will become current if on a custom archetype listing page or a specific archetype event page.
	 *
	 * @return string
	 */
	public static function get_current() {
		global $EM_Event;
		if ( !static::$types ) return static::$event['cpt'];
		if ( static::$current !== null ) {
			$current = static::$current;
		} elseif ( is_admin() ) {
			if ( Archetypes::is_event( $_GET['post_type'] ?? '' ) ) {
				$current = Archetypes::is_repeating($_GET['post_type']) ? Archetypes::get_repeating_archetype($_GET['post_type']) : $_GET['post_type'];
			} elseif ( !empty($_GET['post']) ) {
				$post_type = get_post_type( $_GET['post'] );
				if ( $post_type && Archetypes::is_event( $post_type ) ) {
					$current = Archetypes::is_repeating( $post_type ) ? Archetypes::get_repeating_archetype( $post_type ) : $post_type;
				}
			}
		} elseif ( did_action( 'wp' ) && is_singular() ) {
			$post_type = get_post_type( get_the_ID() );
			if ( $post_type && self::is_event($post_type) ) {
				$current = Archetypes::is_repeating( $post_type ) ? Archetypes::get_repeating_archetype( $post_type ) : $post_type;
			}
		}
		if ( empty( $current ) && !empty( $EM_Event->event_archetype ) ) {
			$current = $EM_Event->event_archetype;
		}
		return apply_filters( 'em_archetype_get_current', $current ?? static::$event['cpt'] );
	}

	public static function set_current( $archetype ) {
		if ( static::is_event( $archetype, false ) ) {
			static::$current = $archetype;
		}
	}

	public static function revert_current() {
		static::$current = null;
	}

	public static function get_options() {
		if ( empty( static::$options ) ) {
			static::$options = get_option( 'em_event_archetypes_options', [] );
		}
		return static::$options;
	}

	public static function get_selected_archetypes() {
		if ( !is_multisite() || is_network_admin() ) return [];
		$mode = static::get_ms_mode();
		if ( $mode !== 'choose' ) return [];
		$selected = get_option('em_archetypes_selected', []);
		return is_array($selected) ? $selected : [];
	}

	/**
	 * Gets an option from the WordPress options table, by default the option requested is directly retrieved via the WordPress get_option function.
	 *
	 * Options that can be customized on a per-archetype basis can override the filters in this function to provide archetype–specific functionality.
	 *
	 * The only caveat with the additional parameters is that the default option cannot be equal to an archetype name, unless the archetype name is also supplied as the third parameter.
	 *
	 * @param $option
	 * @param mixed ...$args May consist of the default option value and then the archetype name, otherwise one or the other is supported.
	 *
	 * @return mixed|null
	 */
	public static function get_option( $option, ...$args ) {
		// determine default and archetype values based on number of args
		$default = false;
		$archetype = Archetypes::get_current();
		if ( count( $args ) > 1 ) {
			// if more than one arg, first is default second is archetype
			$default = $args[0];
			$archetype = $args[1];
		} elseif ( count( $args ) === 1 ) {
			// check if only arg is archetype or default value
			if ( is_array( $args[0] ) ) {
				// for now, we only support a single archetype
				$args[0] = current( $args[0] );
			}
			if ( static::is_event( $args[0] ) ) {
				$archetype = $args[0];
			} else {
				$default = $args[0];
			}
		}
		// get custom archetype option name and possibly a value
		if ( $archetype !== static::$event['cpt'] ) {
			if ( empty( static::$options ) ) {
				static::$options = get_option( 'em_event_archetypes_options', [] );
			}
			if ( isset( static::$options[ $archetype ][ $option ] ) ) {
				$opt = static::$options[ $archetype ][ $option ];
				if ( $opt !== null && $opt !== '' ) {
					$value = $opt;
				}
			}
			$value = apply_filters( 'em_archetype_get_option_' . $option, $value ?? get_option( $option ), $archetype, $default );
		} else {
			$value = get_option( $option, $default );
		}

		return $value;
	}

	public static function get_option_values( $option = null ) {
		$event_page_ids = [
			static::$event['cpt'] => get_option( $option ),
		];
		foreach ( static::$types as $type => $archetype ) {
			if ( !empty( static::$options[$type][$option] ) ) {
				$event_page_ids[ $type ] = static::$options[$type][$option];
			}
		}
		return $event_page_ids;
	}

	public static function get_default_post_type() {
		if ( !static::$base ) {
			$event_cpt_supports = ['title','editor','excerpt','thumbnail','author'];
			if( get_option('dbem_cp_events_custom_fields') ) $event_cpt_supports[] = 'custom-fields';
			if( get_option('dbem_cp_events_comments') ) $event_cpt_supports[] = 'comments';

			// merge $type with defaults which is the $event
			static::$base = apply_filters( 'em_ct__default', [ // __ not a typo, made to avoid conflicts
				'public' => true,
				'hierarchical' => false,
				'show_ui' => true,
				'show_in_menu' => true,
				'show_in_nav_menus'=>true,
				'show_in_rest' => em_use_block_editor(),
				'can_export' => true,
				'exclude_from_search' => !get_option('dbem_cp_events_search_results'),
				'publicly_queryable' => true,
				'query_var' => true,
				'has_archive' => get_option('dbem_cp_events_has_archive', false) == true,
				'supports' => apply_filters('em_cp_event_supports', $event_cpt_supports),
				'capability_type' => ['event', 'events'],
				'rewrite' => ['slug' => static::$event['slug'],'with_front'=>false],
				'capabilities' => [
					'publish_posts' => 'publish_events',
					'edit_posts' => 'edit_events',
					'edit_others_posts' => 'edit_others_events',
					'delete_posts' => 'delete_events',
					'delete_others_posts' => 'delete_others_events',
					'read_private_posts' => 'read_private_events',
					'edit_post' => 'edit_event',
					'delete_post' => 'delete_event',
					'read_post' => 'read_event',
				],
				'description' => __('Display %s on your blog.','events-manager'),
				'labels' => array (
					'name' => static::$event['label'],
					'singular_name' => static::$event['label_single'],
					'menu_name' => static::$event['label'],
					'add_new' => __( 'Add %s', 'events-manager' ),
					'add_new_item' => __( 'Add New %s', 'events-manager' ),
					'edit' => __( 'Edit', 'events-manager' ),
					'edit_item' => __( 'Edit %s', 'events-manager' ),
					'new_item' => __( 'New %s', 'events-manager' ),
					'view' => __( 'View', 'events-manager' ),
					'view_item' => __( 'View %s', 'events-manager' ),
					'search_items' => __( 'Search %s', 'events-manager' ),
					'not_found' => __( 'No %s Found', 'events-manager' ),
					'not_found_in_trash' => __( 'No %s Found in Trash', 'events-manager' ),
					'parent' => __( 'Parent %s', 'events-manager' ),
				),
				'menu_icon' => 'dashicons-em-calendar',
				'yarpp_support' => true,
			]);
		}
		return static::$base;
	}

	public static function get_default_post_type_repeating( $archetype ) {
		$filter_key = str_replace('-', '_', $archetype['cpt']);
		$archetype['repeating'] = false;
		// add legacy suffix for main event CPT
		$suffix = $archetype['cpt'] === EM_POST_TYPE_EVENT ? '-recurring' : '-repeating';
		$repeating_base = [ // specifically keyed event_recurring to trigger legacy filter em_cpt_event_recurring
			'cpt' => $archetype['cpt'] . $suffix,
			'cpts' => $archetype['cpts'] . $suffix,
			'slug' => $archetype['cpt'] . $suffix,
			'label' => sprintf( __( 'Repeating %s', 'events-manager'), $archetype['label'] ),
			'label_single' => sprintf( __('Repeating %s', 'events-manager'), $archetype['label_single'] ),
			// specifics we override
			'public' => apply_filters('em_cp_'. $filter_key .'_public', false),
			'show_in_menu' => 'edit.php?post_type='.$archetype['cpt'],
			'show_in_nav_menus'=>false,
			'publicly_queryable' => apply_filters('em_cp_'. $filter_key .'_publicly_queryable', false),
			'exclude_from_search' => true,
			'has_archive' => false,
			'capability_type' => ['event', 'events'],
			'capabilities' => true, // created in create_archetype_cpt based on capability_type
		];
		$archetype = array_merge( $archetype, $repeating_base );
		return apply_filters('em_cpt_' . $filter_key , $archetype );
	}

	public static function create_archetype_cpt( $type ) {
		// merge $type with defaults which is the $event
		$base = static::$base ?? static::get_default_post_type();
		$archetype = array_merge( $base, $type );
		// add dynamic values from $type back into $archetype
		if ( empty($type['labels']) ) {
			$labels = $base['labels'];
			$archetype['labels'] = [
				'name' => $type['label'],
				'singular_name' => $type['label_single'],
				'menu_name' => $type['label'],
				'add_new' => sprintf( $labels['add_new'], $type['label_single'] ),
				'add_new_item' => sprintf( $labels['add_new_item'], $type['label_single'] ),
				'edit' => sprintf( $labels['edit'], $type['label_single'] ),
				'edit_item' => sprintf( $labels['edit_item'], $type['label_single'] ),
				'new_item' => sprintf( $labels['new_item'], $type['label_single'] ),
				'view' => sprintf( $labels['view'], $type['label_single'] ),
				'view_item' => sprintf( $labels['view_item'], $type['label_single'] ),
				'search_items' => sprintf( $labels['search_items'], $type['label'] ),
				'not_found' => sprintf( $labels['not_found'], $type['label'] ),
				'not_found_in_trash' => sprintf( $labels['not_found_in_trash'], $type['label'] ),
				'parent' => sprintf( $labels['parent'], $type['label_single'] ),
			];
		}
		if ( empty($type['capability_type']) ) {
			$archetype['capability_type'] = [ 'event', 'events' ]; // default to event for now so we use general caps;
			// future could be [ $type['cpt'], $type['cpts'] ?? $type['cpt'] ]
		}
		if ( !empty($type['capabilities']) && $type['capabilities'] === true ) {
			// dynamically create capabilities map based on capability_type, shortcut for creating quick custom caps map
			$archetype['capabilities'] = static::generate_capabilities( $archetype );
		}
		if ( empty($type['description']) ) {
			$archetype['description'] = sprintf( $base['description'], strtolower( $type['label'] ) );
		}
		if ( empty($type['rewrite']) ) {
			$archetype['rewrite'] = [ 'slug' => $archetype['slug'], 'with_front' => false ];
		}
		if ( !isset( $archetype['taxonomies'] ) || $archetype['taxonomies'] === '' ) {
			$archetype['taxonomies'] = [];
		}
		// return final post type of archetype
		return $archetype;
	}

	public static function register_post_types() {
		do_action('em_archetypes_register_post_types');
		// set the post types we will register
		$post_types = [ static::$event['cpt'] => static::$event ];
		if ( static::$location ) {
			$post_types[ static::$location['cpt'] ] = static::$location;
		}
		// register post types
		if ( static::$enabled ) {
			// In choose mode on subsites, filter custom types based on selection
			$mode = static::get_ms_mode();
			$selected = static::get_selected_archetypes();
			foreach ( static::$types as $key => $type ) {
				if ( $mode === 'choose' && !is_network_admin() && is_multisite() ) {
					if ( !in_array( $key, (array) $selected, true ) ) continue;
				}
				// register
				$post_types[ $type['cpt'] ] = $type;
			}
		}
		// sort the $post_types array so if any of the $post_types['slug'] values are within in another, they are moved to the end of the array for later registration
		$sorted = [];
		$unsorted = $post_types;
		while ( !empty( $unsorted ) ) {
			foreach ( $unsorted as $key => $type ) {
				$move_to_end = false;
				foreach ( $unsorted as $key_check => $type_check ) {
					if ( $key != $key_check && strstr( $type_check['slug'], $type['slug'] ) !== false ) {
						$move_to_end = true;
						break;
					}
				}
				if ( !$move_to_end ) {
					$sorted[ $key ] = $type;
					unset( $unsorted[ $key ] );
				}
			}
			// prevent infinite loops, if we get here then there's a circular dependency and remaining items get added as-is
			if ( !empty( $unsorted ) ) {
				$sorted = array_merge( $sorted, $unsorted );
				break;
			}
		}
		$post_types = $sorted;
		// register the post types
		foreach ( $post_types as $type ) {
			static::register_post_type( $type );
		}
		static::$base = null; // clean memory
	}

	public static function register_post_type( $type, $basename = null ) {
		$archetype = static::create_archetype_cpt( $type );
		// apply filters to CPT, since that's applied already
		$archetype = apply_filters( 'em_cpt_' . $basename ?? $type['cpt'], $archetype );
		// register the archetype CPT
		register_post_type( $archetype['cpt'], $archetype );
		// repeating feature
		if ( !empty($archetype['repeating']) ) {
			if ( is_array( $archetype['repeating'] ) ) {
				// custom repeating CPT
				static::register_post_type( $archetype['repeating'] );
			} else {
				$repeating = static::get_default_post_type_repeating( $type );
				static::register_post_type( $repeating, $basename === 'event' ? 'event_repeating' : null );
			}
		}
	}

	public static function generate_capabilities( $archetype ) {
		if ( empty( $archetype['capability_type'] ) || !is_array( $archetype['capability_type'] ) ) {
			$cap = [ $archetype['cpt'], $archetype['cpts'] ?? $archetype['cpt'] ];
		} else {
			$cap = $archetype['capability_type'];
		}
		return [
			'publish_posts' => 'publish_' . $cap[1],
			'edit_posts' => 'edit_' . $cap[1],
			'edit_others_posts' => 'edit_others_' . $cap[1],
			'delete_posts' => 'delete_' . $cap[1],
			'delete_others_posts' => 'delete_others_' . $cap[1],
			'read_private_posts' => 'read_private_' . $cap[1],
			'read_post' => 'read_' . $cap[0],
			'edit_post' => 'edit_' . $cap[0],
			'delete_post' => 'delete_' . $cap[0],
		];
	}

	public static function gutenberg_can_edit_post_type( $can_edit, $post_type ){
		// check this is a post type in our archetypes CPTs
		if ( in_array( $post_type, static::get_cpts() ) ) {
			$can_edit = true;
		}
		return $can_edit;
	}


	/**
	 * Maps a meta capability to EM archetypes if requesting the relevant CPT-related capability for our archetype CPTs
	 *
	 * @param array $caps The primitive capabilities required by the user.
	 * @param string $cap The requested meta capability.
	 * @param int $user_id The user ID requesting the capability.
	 * @param array $args Additional arguments, typically including the object ID.
	 *
	 * @return array The modified list of primitive capabilities required by the user.
	 */
	public static function map_meta_cap( $caps, $cap, $user_id, $args ) {
		if ( !empty( $args[0] ) ) {
			$post = get_post($args[0]);
			//check for revisions and deal with non-event post types
			if( !empty($post->post_type) && $post->post_type == 'revision' ) $post = get_post($post->post_parent);
			if( empty($post->post_type) || !(self::is_event( $post->post_type ) || self::is_location( $post->post_type )) ) return $caps;

			$c = [ 'read' => [], 'edit' => [], 'delete' => [] ];

			$c = static::map_meta_cap_type( $c, static::$event );
			if ( static::$location ) {
				$c = static::map_meta_cap_type( $c, static::$location );
			}
			foreach ( static::$types as $archetype ) {
				$c = static::map_meta_cap_type( $c, $archetype );
			}

			// Only reset $caps when the requested capability is one of our archetype meta caps for this post type. Resetting on any object-carrying cap emptied the requirement list for unrelated caps (e.g. edit_user, promote_user), which reads as allow.
			if ( !empty( $c['read'][$post->post_type] ) && $c['read'][$post->post_type] == $cap ) {
				$caps = [];
				if ( 'private' != $post->post_status ) {
					$caps[] = 'read';
				} elseif ( $user_id == $post->post_author ) {
					$caps[] = 'read';
				} else {
					$post_type = get_post_type_object( $post->post_type );
					$caps[] = $post_type->cap->read_private_posts;
				}
			} elseif ( !empty( $c['edit'][$post->post_type] ) && $c['edit'][$post->post_type] == $cap  ) {
				$caps = [];
				$post_type = get_post_type_object( $post->post_type );
				if ( $user_id == $post->post_author ) {
					$caps[] = $post_type->cap->edit_posts;
				} else {
					$caps[] = $post_type->cap->edit_others_posts;
				}
			} elseif ( !empty( $c['delete'][$post->post_type] ) && $c['delete'][$post->post_type] == $cap ) {
				$caps = [];
				$post_type = get_post_type_object( $post->post_type );
				if ( $user_id == $post->post_author ) {
					$caps[] = $post_type->cap->delete_posts;
				} else {
					$caps[] = $post_type->cap->delete_others_posts;
				}
			}
		}

		/* Return the capabilities required by the user. */

		return $caps;
	}

	public static function map_meta_cap_repeating( $c, $archetype ) {
		if ( !empty($archetype['repeating']) ) {
			$repeating = $archetype['repeating'];
			if ( !is_array( $repeating ) ) {
				$suffix = $archetype['cpt'] === EM_POST_TYPE_EVENT ? '-recurring' : '-repeating';
				$repeating = [ // specifically keyed event_recurring to trigger legacy filter em_cpt_event_recurring
					'cpt' => $archetype['cpt'] . $suffix,
					'capability_type' => ['event', 'events'],
				];
			}
			return static::map_meta_cap_type( $c, $repeating );
		}
		return $c;
	}

	public static function map_meta_cap_type( $c, $archetype ) {
		// create cap sets
		$cpt = $archetype['cpt'];
		// WP rewrites the requested $cap to the post type's own meta cap name before firing this filter, so the registered CPT is the only thing we can match against, not what the archetype was stored with.
		$post_type = get_post_type_object( $cpt );
		if ( $post_type ) {
			$caps = (array) $post_type->cap;
		} elseif ( !empty($archetype['capabilities']) && is_array($archetype['capabilities']) ) {
			$caps = $archetype['capabilities'];
		} else {
			$caps = static::generate_capabilities( $archetype );
		}
		$c['read'][$cpt] = $caps['read_post'];
		$c['edit'][$cpt] = $caps['edit_post'];
		$c['delete'][$cpt] = $caps['delete_post'];
		$c = static::map_meta_cap_repeating( $c, $archetype );
		return $c;
	}

	public static function map_meta_map_check( $args ) {
		$post = get_post( $args[0] );
		//check for revisions and deal with non-event post types
		if ( !empty( $post->post_type ) && $post->post_type == 'revision' ) {
			$post = get_post( $post->post_parent );
		}

		if ( empty( $post->post_type ) || !in_array( $post->post_type, static::get_cpts() ) ) {
			return false;
		}

		//continue with getting post type and assigning caps
		return ( static::is_event( $post ) ) ? em_get_event( $post ) : em_get_location( $post );
	}

	public static function after_setup_theme(){
		if( !get_option('disable_post_thumbnails') && function_exists('add_theme_support') ){
			global $_wp_theme_features;
			if( !empty($_wp_theme_features['post-thumbnails']) ){
				//either leave as true, or add our cpts to this
				if( !empty($_wp_theme_features['post-thumbnails'][0]) && is_array($_wp_theme_features['post-thumbnails'][0]) ){
					//add to featured image post types for specific themes
					$post_thumbnails = array_merge( $_wp_theme_features['post-thumbnails'][0], static::get_cpts() );
					add_theme_support('post-thumbnails', $post_thumbnails);
				}
			}else{
				add_theme_support( 'post-thumbnails', static::get_cpts() ); //need to add this for themes that don't have it.
			}
		}
	}

	public static function get_event_types() {
		$types = [ static::$event['cpt'] ];
		foreach ( static::$types as $type ) {
			$types[] = $type['cpt'];
		}
		return $types;
	}

	public static function get_cpts ( $exclude = [], $include = [] ) {
		$valid_cpts = [];
		if ( ( !$include || in_array( 'event', $include ) ) && !in_array( 'event', $exclude ) ) {
			$valid_cpts[] = static::$event['cpt'];
			$event_included = true;
		}
		if ( ( !$include || in_array( 'location', $include ) ) && !in_array( 'location', $exclude ) && static::$location ) {
			$valid_cpts[] = static::$location['cpt'];
		}
		if ( ( !$include || in_array( 'repeating', $include ) ) && !in_array( 'repeating', $exclude ) ) {
			if ( !empty( static::$event['repeating'] ) ) {
				$valid_cpts[] = static::$event['repeating']['cpt'] ?? static::$event['cpt'] . '-recurring';
			}
			foreach ( static::$types as $archetype ) {
				if ( !empty( $archetype['repeating'] ) ) {
					$valid_cpts[] = $archetype['repeating']['cpt'] ?? $archetype['cpt'] . '-repeating';
				}
			}
		}
		if ( ( !$include || in_array( 'types', $include ) ) && !in_array( 'types', $exclude ) ) {
			foreach ( static::$types as $type ) {
				$valid_cpts[] = $type['cpt'];
			}
		}

		return $valid_cpts;
	}

	public static function is_valid_cpt( $cpt, $exclude = [], $include = [] ) {
		$cpt = static::get_post_type( $cpt );
		return in_array( $cpt, static::get_cpts( $exclude, $include ) );
	}

	/**
	 * Checks if a post type is an event, accepts, a post type string, post or event object.
	 * You can also pass falsy values to trigger false results if using shorthand ?? to check post or request variables.
	 *
	 * @param string|\EM_Event|\WP_Post|false $cpt
	 * @param bool $include_repeating   Include repeating event CPTs in the check
	 *
	 * @return bool
	 */
	public static function is_event( $cpt, $include_repeating = true ) {
		$cpt = static::get_post_type( $cpt );
		if ( $include_repeating ) {
			// check repeating too
			return $cpt && in_array( $cpt, static::get_cpts( ['location'] ) );
		} else {
			return $cpt && in_array( $cpt, [ static::$event['cpt'], ...array_keys( static::$types ) ] );
		}
	}

	/**
	 * Checks if a post type is a location, accepts, a post type string, post or location object.
	 * You can also pass falsy values to trigger false results if using shorthand ?? to check post or request variables.
	 *
	 * @param string|\EM_Event|\WP_Post|false $cpt
	 * @param bool $include_repeating   Include repeating event CPTs in the check
	 *
	 * @return bool
	 */
	public static function is_location( $cpt ) {
		$cpt = static::get_post_type( $cpt );
		return $cpt && ( static::$location['cpt'] ?? null ) === $cpt;
	}

	/**
	 * Checks if a post type is a repeating event, accepts, a post type string, post or event object.
	 * You can also pass falsy values to trigger false results if using shorthand ?? to check post or request variables.
	 *
	 * @param string|\EM_Event|\WP_Post|false $cpt
	 *
	 * @return bool
	 */
	public static function is_repeating( $cpt ) {
		$cpt = static::get_post_type( $cpt );
		return $cpt && in_array( $cpt, static::get_cpts( [], [ 'repeating' ] ) );
	}

	/**
	 * Gets parent archetype for a repeating event subarchetype. Accepts a post type string, archetype, post or event object.
	 * You can also pass falsy values to trigger false results if using shorthand ?? to check post or request variables.
	 * @param $cpt
	 *
	 * @return string|false
	 */
	public static function get_repeating_archetype( $cpt = null ){
		$cpt = static::get_post_type( $cpt );
		if ( self::is_repeating($cpt) ) {
			// find parent archetype
			if ( static::$event['repeating'] ) {
				$repeating_cpt = !empty( static::$event['repeating']['cpt'] ) ? static::$event['repeating']['cpt'] : static::$event['cpt'] . '-recurring';
				if ( $cpt === $repeating_cpt ) {
					return static::$event['cpt'];
				}
			}
			if ( static::$enabled ) {
				foreach ( static::$types as $type => $archetype ) {
					if ( !empty( $archetype['repeating'] ) ) {
						$repeating_cpt = !empty( $archetype['repeating']['cpt'] ) ? $archetype['repeating']['cpt'] : $type . '-repeating';
						if ( $cpt === $repeating_cpt ) {
							return $archetype['cpt'];
						}
					}
				}
			}
		}
		return false;
	}

	/**
	 * Gets the CPT name of a repeating event subarchetype when passed the parent archetype. Accepts a post type string, post or event object. If no CPT supplied, the current/default CPT is used.
	 * You can also pass falsy values to trigger false results if using shorthand ?? to check post or request variables.
	 * @param $cpt
	 *
	 * @return mixed|string|void
	 */
	public static function get_repeating_cpt ( $cpt = null ) {
		$cpt = static::get_post_type( $cpt );
		if ( is_string( $cpt ) ) {
			if ( static::$event['cpt'] === $cpt && static::$event['repeating'] ) {
				return static::$event['repeating']['cpt'] ?? static::$event['cpt'] . '-recurring';
			}
			if ( !empty( static::$types[$cpt]['repeating'] ) ) {
				return static::$types[$cpt]['repeating']['cpt'] ?? $cpt . '-repeating';
			}
		}
		return false;
	}

	/**
	 * Gets the CPT name of a post type. Accepts a post type string, post ID, post or event object. If no CPT supplied, the current/default CPT is used.
	 * Useful for geting the CPT value from multiple possible types of supplied arguments, a utility function to avoid checking object/variable types repeatedly.
	 * You can also pass falsy values to trigger false results if using shorthand ?? to check post or request variables.
	 * @param $cpt
	 *
	 * @return string|false
	 */
	public static function get_post_type( $cpt ) {
		if ( is_array( $cpt ) ) {
			return false;
		}
		if ( !is_string( $cpt ) ) {
			if( !empty( $cpt->post_type ) ){
				$cpt = $cpt->post_type;
			} elseif( !empty( $cpt->event_archetype ) ){
				$cpt = $cpt->post_type;
			} elseif ( !empty( $cpt['cpt'] ) ) {
				$cpt = $cpt['cpt'];
			} elseif ( !empty( $cpt['post_type'] ) ) {
				$cpt = $cpt['post_type'];
			} elseif ( !empty( $cpt['event_archetype'] ) ) {
				$cpt = $cpt['event_archetype'];
			} elseif ( is_numeric( $cpt ) ) {
				$cpt = get_post_type( $cpt );
			} else {
				// string, make sure it is a cPT present in archetypes
				if ( !in_array( $cpt, static::get_cpts() ) ) {
					$cpt = (string) $cpt;
				} else {
					$cpt = false;
				}
			}
		}
		return $cpt;
	}

	/**
	 * Reverse-engineer name of archetype based on post type name, meaning the archetype could be a repeating event subarchetype which becomes the actual archetype name.
	 * @param $post_type
	 *
	 * @return void
	 */
	public static function get_from_cpt( $post_type ) {
		$archetype = false;
		$cpts = static::get_cpts();
		if ( in_array( $post_type, $cpts ) ) {
			if ( Archetypes::is_repeating( $post_type ) ) {
				$archetype = Archetypes::get_repeating_archetype( $post_type );
			} else {
				$archetype = $post_type;
			}
		}
		return $archetype;
	}
}
Archetypes::init();