<?php
/**
 * Events Manager — location editor tab registry.
 *
 * Locations have a single core tab (Where), so by default no tab strip shows — just the editor window. Attributes become a second tab only when enabled. Add-ons extend via the 'em_location_editor_tabs' filter.
 */
namespace EM\Editor;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class Location extends Tabs {

	public function filter_name() {
		return 'em_location_editor_tabs';
	}

	public function post_types() {
		return [ defined( 'EM_POST_TYPE_LOCATION' ) ? EM_POST_TYPE_LOCATION : 'location' ];
	}

	/** The location editor shelves canvas — its core content is the Where map, which needs the parent document. Canvas falls back to stacked metaboxes. */
	public function supports_canvas() {
		return false;
	}

	protected function core_tabs() {
		$tabs = [];

		$tabs['where'] = [
			'label'          => __( 'Where', 'events-manager' ),
			'priority'       => 10,
			'icon'           => 'dashicons-location',
			'canvas_support' => true,
			'metaboxes'      => [ 'em-location-where' ],
		];

		if ( em_get_option( 'dbem_location_attributes_enabled' ) ) {
			$tabs['attributes'] = [
				'label'          => __( 'Attributes', 'events-manager' ),
				'priority'       => 20,
				'icon'           => 'dashicons-list-view',
				'canvas_support' => false,
				'metaboxes'      => [ 'em-location-attributes' ],
			];
		}

		return $tabs;
	}
}
