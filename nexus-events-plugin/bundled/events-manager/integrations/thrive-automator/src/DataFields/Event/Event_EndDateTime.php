<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_EndDateTime extends Event_Field {

	public static function get_id() {
		return 'event_end';
	}
	
	public static function get_supported_filters() {
		return [ 'date_comparison' ];
	}

	public static function get_name() {
		return __('Event End Date and Time', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('UTC MySQL-formatted DateTime for end of event.', 'events-manager-thrive-automator');
	}
	
	public static function return_data_from_event( $EM_Event ){
		return $EM_Event->end()->getDateTime(true);
	}
	
	public static function get_field_value_type() {
		return static::TYPE_DATETIME;
	}
}
