<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_Name extends Event_Field {

	public static function get_id() {
		return 'event_name';
	}
	
	public static function get_supported_filters() {
		return [ 'string_equals' ];
	}

	public static function get_name() {
		return __('Event Name', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('The title or name of the event.', 'events-manager-thrive-automator');
	}
	
	public static function get_dummy_value() {
		return 'Some Super Event';
	}
	
	public static function return_data_from_event( $EM_Event ){
		return $EM_Event->event_name;
	}
}
