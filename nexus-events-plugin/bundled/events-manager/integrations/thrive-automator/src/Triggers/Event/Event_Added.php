<?php
namespace EM\Thrive\Automator\Triggers\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_Added extends Event_Trigger {
	
	public $event_param_key = 0;

	public static function get_id() {
		return 'events-manager/event_added';
	}

	public static function get_wp_hook() {
		return 'em_event_added';
	}

	public static function get_name() {
		return __('Event Created', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('When an event has been created, published or not.', 'events-manager-thrive-automator');
	}
}
