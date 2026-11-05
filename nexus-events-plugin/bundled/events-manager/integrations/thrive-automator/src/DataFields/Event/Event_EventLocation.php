<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_EventLocation extends Event_Field {

	public static function get_id() {
		return 'event_location';
	}
	
	public static function get_supported_filters() {
		return [ 'string_equals' ];
	}

	public static function get_name() {
		return __('Event Location Address', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('Description destinatioino of event location (depending on type, maybe a url).', 'events-manager-thrive-automator');
	}

	public static function get_dummy_value() {
		return 'https://someurl.com';
	}
	
	public static function return_data_from_event( $EM_Event ){
		if( $EM_Event->has_event_location() ){
			return $EM_Event->get_event_location()->output();
		}
		return null;
	}
}