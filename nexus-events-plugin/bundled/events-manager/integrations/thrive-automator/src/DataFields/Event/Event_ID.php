<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_ID extends Event_Field {

	public static function get_id() {
		return 'event_id';
	}
	
	public static function get_supported_filters() {
		return [ 'number_comparison' ];
	}

	public static function get_name() {
		return __('Event ID', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('The ID of the event.', 'events-manager-thrive-automator');
	}
	
	public static function return_data_from_event( $EM_Event ){
		return $EM_Event->event_id;
	}
	
	public static function get_field_value_type() {
		return static::TYPE_NUMBER;
	}
}
