<?php
namespace EM\Thrive\Automator\Actions\Events_Manager;

use EM\Thrive\Automator\Apps\Events_Manager;
use Thrive\Automator\Items\Action;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Booking_User_Status extends Action {

	public static function get_id() {
		return 'events-manager/booking-user-status';
	}

	public static function get_name() {
		return __('Change User Booking Statuses', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('Change the status of a users bookings.', 'events-manager-thrive-automator');
	}

	public static function get_image() {
		return Events_Manager::get_logo();
	}

	public static function get_app_id() {
		return Events_Manager::get_id();
	}

	/**
	 * This action requires only one action field for setup
	 *
	 * @return array
	 */
	public static function get_required_action_fields() {
		return [
			'events-manager/booking_status',
			'events-manager/booking_scope',
			'events-manager/booking_send_email',
			'events-manager/booking_ignore_capacity',
		];
	}

	/**
	 * Get an array of keys with the required data-objects
	 *
	 * @return array
	 */
	public static function get_required_data_objects() {
		return ['user_data'];
	}

	/**
	 * To implement actual action operation
	 */
	public function do_action( $data ) {
		$user_data = $data['user_data'];
		if( $user_data instanceof \Thrive\Automator\Items\User_Data ){
			$user_id = $user_data->get_value('user_id');
			$status = $this->get_automation_data_value( 'events-manager/booking_status' );
			$scope = $this->get_automation_data_value( 'events-manager/booking_scope' );
			$email = $this->get_automation_data_value( 'events-manager/booking_send_email' ) == true;
			$ignore_spaces = $this->get_automation_data_value( 'events-manager/booking_ignore_capacity' ) == true;
			// get user emails based on scope
			global $wpdb;
			$sql = $wpdb->prepare('SELECT booking_id FROM '. EM_BOOKINGS_TABLE. ' WHERE person_id=%d', $user_id);
			if( $scope === 'past' ){
				$sql .= ' AND event_id IN ( SELECT event_id FROM '. EM_EVENTS_TABLE .' WHERE event_start < NOW() )';
			}elseif( $scope === 'future' ){
				$sql .= ' AND event_id IN ( SELECT event_id FROM '. EM_EVENTS_TABLE .' WHERE event_start > NOW() )';
			}
			$bookings = $wpdb->get_col($sql);
			foreach( $bookings as $booking_id ){
				$EM_Booking = em_get_booking($booking_id);
				$EM_Booking->set_status($status, $email, $ignore_spaces);
			}
		}
	}
}
