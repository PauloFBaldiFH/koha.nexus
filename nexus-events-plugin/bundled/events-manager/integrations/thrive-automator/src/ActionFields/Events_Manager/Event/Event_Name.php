<?php
namespace EM\Thrive\Automator\ActionFields\Events_Manager\Event;


if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

/**
 * Class Url - representation of the URL field needed for the `Webhook` action
 *
 * @package EM\Thrive\Automator\Fields
 */
class Event_Name extends Event_Action_Field {

	/**
	 * Field name/label
	 */
	public static function get_name() {
		return __('Event Name', 'events-manager-thrive-automator');
	}
	
	/**
	 * Field description
	 */
	public static function get_description() {
		return __('The name of the event', 'events-manager-thrive-automator');
	}
	
	
	public static function get_id() {
		return 'events-manager/event_name';
	}
}
