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
class Booking_Status extends Booking_Action_Field {

	/**
	 * Field name/label
	 */
	public static function get_name() {
		return __('Booking Status', 'events-manager-thrive-automator');
	}
	
	/**
	 * Field description
	 */
	public static function get_description() {
		return __('The status of the booking for an event', 'events-manager-thrive-automator');
	}
	
	
	public static function get_id() {
		return 'events-manager/booking_status';
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
		$EM_Booking = new \EM_Booking();
		$options = array();
		foreach( $EM_Booking->status_array as $id => $label ){
			$options[] = [
				'id' => $id,
				'label' => $label,
			];
		}
		return $options;
	}
}
