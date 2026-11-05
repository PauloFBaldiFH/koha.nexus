<?php
namespace EM\Thrive\Automator\Triggers\Booking;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Booking_Added extends Booking_Trigger {

	public static function get_id() {
		return 'events-manager/booking_added';
	}

	public static function get_wp_hook() {
		return 'em_booking_added';
	}

	public static function get_name() {
		return __('Booking Added', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('When a new booking has been made.', 'events-manager-thrive-automator');
	}
}
