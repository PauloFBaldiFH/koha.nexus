<?php
namespace EM;

class Taxonomies {
	public static $base;
	public static $taxonomies = [];

	public static function init(){
		// constants
		if( !defined('EM_TAXONOMY_CATEGORY') ) define('EM_TAXONOMY_CATEGORY', 'event-categories' );
		if( !defined('EM_TAXONOMY_TAG') ) define('EM_TAXONOMY_TAG', 'event-tags');
		define('EM_TAXONOMY_TAG_SLUG', get_option('dbem_taxonomy_tag_slug', 'events/tags'));
		define('EM_TAXONOMY_CATEGORY_SLUG', EM_MS_GLOBAL ? get_site_option('dbem_taxonomy_category_slug', 'events/categories') : get_option('dbem_taxonomy_category_slug', 'events/categories') );

		// initialize the base tags for EM, if enabled
		$tags_enabled = em_get_option('dbem_tags_enabled');
		if ( !$tags_enabled ) {
			// check archetype options
			foreach ( Archetypes::get_options() as $options ) {
				if ( !empty($options['dbem_tags_enabled']) ) {
					$tags_enabled = true;
				}
			}
		}
		if ( $tags_enabled ) {
			static::$taxonomies['event-tags'] =  [
				'taxonomy' => EM_TAXONOMY_TAG,
				'shortname' => 'tags',
				'label' => sprintf( __('%s Tags'), Archetypes::$event['label'] ),
				'singular_label' => sprintf( __('%s Tag'), Archetypes::$event['label'] ),
				'slug' => EM_TAXONOMY_TAG_SLUG,
				'hierarchical' => false,
			];
		}
		$categories_enabled = get_option('dbem_categories_enabled');
		if ( !$categories_enabled ) {
			// check archetype options
			foreach ( Archetypes::get_options() as $options ) {
				if ( !empty($options['dbem_categories_enabled']) ) {
					$categories_enabled = true;
				}
			}
		}
		if ( $categories_enabled ) {
			static::$taxonomies['event-categories'] = [
				'taxonomy' => EM_TAXONOMY_CATEGORY,
				'shortname' => 'categories',
				'label' => sprintf( __('%s Categories'), Archetypes::$event['label_single'] ),
				'singular_label' => sprintf( __('%s Category'), Archetypes::$event['label_single'] ),
				'global' => EM_MS_GLOBAL,
				'slug' => EM_TAXONOMY_CATEGORY_SLUG,
			];
		}

		// set the trigger to register
		add_action('em_archetypes_register_post_types', [ static::class, 'register_taxonomies'], 10, 2 );
		do_action('em_taxonomies_init');
	}

	public static function get_default_taxonomy() {
		if ( !static::$base ) {
			// merge $type with defaults which is the $event
			static::$base = apply_filters( 'em_ct__default', [ // __ not a typo, made to avoid conflicts
				'hierarchical' => true,
				'public' => true,
				'show_ui' => true,
				// Mirror the CPT show_in_rest gating from classes/em-archetypes.php so the
				// Gutenberg block-editor sidebar can render the Categories/Tags panels for
				// EM events. Without show_in_rest, WP's block editor silently omits the
				// taxonomy panel even when the CPT itself is in REST, leaving users no way
				// to assign categories/tags to a post being edited in Gutenberg.
				'show_in_rest' => em_use_block_editor(),
				'query_var' => true,
				// for now caps are fixed
				'capabilities' => [
					'manage_terms' => 'edit_event_categories',
					'edit_terms' => 'edit_event_categories',
					'delete_terms' => 'delete_event_categories',
					'assign_terms' => 'edit_events',
				],
				'labels' => array(
					'name'=>__('%s','events-manager'),
					'singular_name'=>__('%s','events-manager'),
					'search_items'=>__('Search %s','events-manager'),
					'popular_items'=>__('Popular %s','events-manager'),
					'all_items'=>__('All %s','events-manager'),
					'parent_items'=>__('Parent %s','events-manager'),
					'parent_item_colon'=>__('Parent %s:','events-manager'),
					'edit_item'=>__('Edit %s','events-manager'),
					'update_item'=>__('Update %s','events-manager'),
					'add_new_item'=>__('Add New %s','events-manager'),
					'new_item_name'=>__('New %s Name','events-manager'),
					'separate_items_with_commas'=>__('Separate %s with commas','events-manager'),
					'add_or_remove_items'=>__('Add or remove %s','events-manager'),
					'choose_from_the_most_used'=>__('Choose from most used %s','events-manager'),
				),
				//'update_count_callback' => '',
				//'show_tagcloud' => true,
				//'show_in_nav_menus' => true,
			]);
		}
		return static::$base;
	}

	public static function create_taxonomy( $type ) {
		// merge $type with defaults which is the $event
		$base = static::$base ?? static::get_default_taxonomy();
		$taxonomy = array_merge( $base, $type );
		// add dynamic values from $type back into $archetype
		if ( empty($taxonomy['rewrite']) ) {
			$taxonomy['rewrite'] = [ 'slug' => $type['slug'], 'with_front' => false ];
		}
		$l = $taxonomy['labels'];
		$taxonomy['labels'] = [
			'name' => $type['label'],
			'singular_name' => $type['singular_label'],
			'menu_name' => $type['label'],
			'search_items' => sprintf( $l['search_items'], $type['label'] ),
			'popular_items' => sprintf( $l['popular_items'], $type['label'] ),
			'all_items' => sprintf( $l['all_items'], $type['label'] ),
			'parent_items' => sprintf( $l['parent_items'], $type['label'] ),
			'parent_item_colon' => sprintf( $l['parent_item_colon'], $type['singular_label'] ),
			'edit_item' => sprintf( $l['edit_item'], $type['singular_label'] ),
			'update_item' => sprintf( $l['update_item'], $type['singular_label'] ),
			'add_new_item' => sprintf( $l['add_new_item'], $type['singular_label'] ),
			'new_item_name' => sprintf( $l['new_item_name'], $type['singular_label'] ),
			'separate_items_with_commas' => sprintf( $l['separate_items_with_commas'], $type['label'] ),
			'add_or_remove_items' => sprintf( $l['add_or_remove_items'], $type['label'] ),
			'choose_from_the_most_used' => sprintf( $l['choose_from_the_most_used'], $type['label'] ),
		];
		return $taxonomy;
	}

	public static function register_taxonomies() {
		// register the taxonomies
		foreach ( static::$taxonomies as $taxonomy_type ) {
			static::register_taxonomy( $taxonomy_type );
		}
	}

	public static function register_taxonomy( $taxonomy_type ) {
		$taxonomy = static::create_taxonomy( $taxonomy_type );
		// apply filters to taxonomy, this will adhere to legacy outputs of em_cpt_tags and em_cpt_categories
		$taxonomy = apply_filters( 'em_cpt_' . $taxonomy['shortname'] ?? $taxonomy['taxonomy'], $taxonomy );
		// register the taxonomy, CPTs can add themselves later
		register_taxonomy( $taxonomy['taxonomy'], [], $taxonomy );
	}
}
Taxonomies::init();
?>