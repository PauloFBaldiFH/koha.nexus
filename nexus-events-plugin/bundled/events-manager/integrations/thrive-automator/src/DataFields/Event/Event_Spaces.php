<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_Spaces extends Event_Field {

	public static function get_id() {
		return 'event_spaces';
	}
	
	public static function get_supported_filters() {
		return [ 'number_comparison' ];
	}

	public static function get_name() {
		return __('Event Spaces', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('The number of spaces of the event.', 'events-manager-thrive-automator');
	}
	
	public static function return_data_from_event( $EM_Event ){
		return $EM_Event->get_spaces();
	}
	
	public static function get_field_value_type() {
		return static::TYPE_NUMBER;
	}
}
