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
class Event_Timezone extends Event_Action_Field {

	/**
	 * Field name/label
	 */
	public static function get_name() {
		return __('Event Timezone', 'events-manager-thrive-automator');
	}
	
	/**
	 * Field description
	 */
	public static function get_description() {
		return __('Timezone format of event, in PHP-compatible DateTimeZone format.', 'events-manager-thrive-automator');
	}
	
	public static function get_placeholder() {
		return 'Europe/Madrid';
	}
	
	
	public static function get_id() {
		return 'events-manager/event_timezone';
	}
}
