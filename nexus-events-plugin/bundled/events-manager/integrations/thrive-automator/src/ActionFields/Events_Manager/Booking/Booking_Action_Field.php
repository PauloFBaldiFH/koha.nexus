<?php
namespace EM\Thrive\Automator\ActionFields\Events_Manager\Booking;

use Thrive\Automator\Items\Action_Field;
use Thrive\Automator\Utils;


if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

/**
 * Class Url - representation of the URL field needed for the `Webhook` action
 *
 * @package EM\Thrive\Automator\Fields
 */
class Booking_Action_Field extends Action_Field {

	/**
	 * Field name/label
	 */
	public static function get_name() {
		return 'Event Action Field';
	}
	
	public static function get_id() {
		return 'event_action_field';
	}

	/**
	 * Field description
	 */
	public static function get_description() {
		return 'Event action field description.';
	}

	/**
	 * Field tooltip
	 */
	public static function get_tooltip() {
		return static::get_name();
	}

	/**
	 * Field input placeholder
	 */
	public static function get_placeholder() {
		return static::get_name();
	}

	public static function get_type() {
		return Utils::FIELD_TYPE_TEXT;
	}
	
	public static function allow_dynamic_data(): bool {
		return true;
	}
}
