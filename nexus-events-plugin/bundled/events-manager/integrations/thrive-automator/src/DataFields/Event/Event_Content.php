<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_Content extends Event_Field {

	public static function get_id() {
		return 'event_content';
	}
	
	public static function get_supported_filters() {
		return [ 'string_equals' ];
	}

	public static function get_name() {
		return __('Event Content', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('The content or description of the event.', 'events-manager-thrive-automator');
	}
	
	public static function get_dummy_value() {
		return 'Lorem Ipsum ...';
	}
	
	public static function return_data_from_event( $EM_Event ){
		return $EM_Event->post_content;
	}
}
