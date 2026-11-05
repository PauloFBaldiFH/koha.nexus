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
class Event_Start extends Event_Action_Field {

	/**
	 * Field name/label
	 */
	public static function get_name() {
		return __('Event Start Date/Time (UTC)', 'events-manager-thrive-automator');
	}
	
	/**
	 * Field description
	 */
	public static function get_description() {
		return __('The start date and time of the event in UTC timezone with a MySQL DATETIME format.', 'events-manager-thrive-automator');
	}
	
	public static function get_placeholder() {
		return 'YYYY-MM-DD HH:MM:SS';
	}
	
	
	public static function get_id() {
		return 'events-manager/event_start';
	}
}
