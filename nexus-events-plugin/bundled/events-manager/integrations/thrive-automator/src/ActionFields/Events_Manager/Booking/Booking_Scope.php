<?php
namespace EM\Thrive\Automator\ActionFields\Events_Manager\Booking;

use Thrive\Automator\Utils;


if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

/**
 * Class Url - representation of the URL field needed for the `Webhook` action
 *
 * @package EM\Thrive\Automator\Fields
 */
class Booking_Scope extends Booking_Action_Field {

	/**
	 * Field name/label
	 */
	public static function get_name() {
		return __('Event Scope', 'events-manager-thrive-automator');
	}
	
	/**
	 * Field description
	 */
	public static function get_description() {
		return __('The scopes of the booking for an event', 'events-manager-thrive-automator');
	}
	
	
	public static function get_id() {
		return 'events-manager/booking_scope';
	}
	
	/**
	 * Campaigns will be displayed in a dropdown select
	 */
	public static function get_type() {
		return Utils::FIELD_TYPE_SELECT;
	}
	
	/**
	 * Function that returns an array with campaigns (id/name) that will be used in the select
	 *
	 * @return array|array[]
	 */
	public static function get_options_callback( $action_id, $action_data ) {
		$options = array();
		$scopes = array(
			'future' => __('Future Bookings', 'events-manager-thrive-automator'),
			'past' => __('Past Bookings', 'events-manager-thrive-automator'),
			'all' => __('All Bookings', 'events-manager-thrive-automator'),
		);
		foreach( $scopes as $id => $label ){
			$options[] = [
				'id' => $id,
				'label' => $label,
			];
		}
		return $options;
	}
}
