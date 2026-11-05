<?php
/**
 * Events Manager — event editor tab registry.
 *
 * Maps the core event metaboxes onto tabs. Add-ons extend via the 'em_event_editor_tabs' filter. Gated tabs (where/bookings/attributes) follow the same global options that gate their metaboxes; the engines additionally skip any box whose metabox isn't actually present for the current event.
 */
namespace EM\Editor;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class Event extends Tabs {

	public function filter_name() {
		return 'em_event_editor_tabs';
	}

	public function post_types() {
		if ( class_exists( '\EM\Archetypes' ) ) {
			$cpts = \EM\Archetypes::get_cpts( [ 'location' ] ); // every event CPT (event, recurring, archetypes) — not locations
			if ( ! empty( $cpts ) ) {
				return $cpts;
			}
		}
		return [ 'event', 'event-recurring' ];
	}

	protected function core_tabs() {
		$tabs = [];

		$tabs['when'] = [
			'label'          => __( 'When', 'events-manager' ),
			'priority'       => 10,
			'icon'           => 'dashicons-calendar-alt',
			'canvas_support' => true,
			'metaboxes'      => [
				'em-event-when',
				// The Recurrences box carries EM's own visibility classes — show/hide is driven by form.em-is-recurring in events-manager-event-editor.css — so it needs that wrapper class wherever it is folded.
				[ 'id' => 'em-event-recurring', 'class' => 'em-recurrences-section recurring-event-editor' ],
			],
		];

		if ( em_get_option( 'dbem_locations_enabled', true ) ) {
			$tabs['where'] = [
				'label'          => __( 'Where', 'events-manager' ),
				'priority'       => 20,
				'icon'           => 'dashicons-location',
				'canvas_support' => false, // the location picker + map are not yet proven inside the canvas iframe
				'metaboxes'      => [ 'em-event-where' ],
			];
		}

		if ( em_get_option( 'dbem_rsvp_enabled', true ) ) {
			$tabs['bookings'] = [
				'label'          => __( 'Bookings', 'events-manager' ),
				'priority'       => 30,
				'icon'           => 'dashicons-tickets-alt',
				'canvas_support' => true,
				'metaboxes'      => [ 'em-event-bookings' ],
			];
		}

		if ( em_get_option( 'dbem_attributes_enabled', true ) ) {
			$tabs['attributes'] = [
				'label'          => __( 'Attributes', 'events-manager' ),
				'priority'       => 40,
				'icon'           => 'dashicons-list-view',
				'canvas_support' => true,
				'metaboxes'      => [ 'em-event-attributes' ],
			];
		}

		return $tabs;
	}
}
