<?php
namespace EM\Notifications;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * The notification types Events Manager ships in core. Each describes the EM lifecycle hook that fires it, the capability needed to receive it, and a resolver that turns the hook's EM object into a recipient owner + a generic (no-PII) payload. Pro and add-ons register their own types the same way on the em_notifications_register hook — see Notifications::register_type().
 */
class Types {

	public static function register_defaults() {
		// New booking. em_booking_added (classes/em-booking.php) fires once, on INSERT only, with ( EM_Booking, $mail ).
		Notifications::register_type( array(
			'key'               => 'booking_added',
			'label'             => __( 'New bookings', 'events-manager' ),
			'group'             => 'bookings',
			'hook'              => 'em_booking_added',
			'hook_args'         => 2,
			'capability'        => 'manage_bookings',
			'others_capability' => 'manage_others_bookings',
			'resolve'           => array( __CLASS__, 'resolve_booking_added' ),
		) );

		// Booking cancelled. em_booking_status_changed fires on every transition with ( EM_Booking, array('status'=>..) ); we only notify on status 3 = cancelled.
		Notifications::register_type( array(
			'key'               => 'booking_cancelled',
			'label'             => __( 'Booking cancellations', 'events-manager' ),
			'group'             => 'bookings',
			'hook'              => 'em_booking_status_changed',
			'hook_args'         => 2,
			'capability'        => 'manage_bookings',
			'others_capability' => 'manage_others_bookings',
			'resolve'           => array( __CLASS__, 'resolve_booking_cancelled' ),
		) );

		// New event. em_event_added (classes/em-event.php) fires with ( EM_Event ). The useful audience is moderators (others scope, edit_others_events) on submission/multi-author sites; the creator can opt into own scope too.
		Notifications::register_type( array(
			'key'               => 'event_added',
			'label'             => __( 'New events', 'events-manager' ),
			'group'             => 'events',
			'hook'              => 'em_event_added',
			'hook_args'         => 1,
			'capability'        => 'edit_events',
			'others_capability' => 'edit_others_events',
			'resolve'           => array( __CLASS__, 'resolve_event_added' ),
		) );
	}

	public static function resolve_booking_added( $EM_Booking, $mail = true ) {
		if ( ! is_object( $EM_Booking ) ) {
			return null;
		}
		$event = $EM_Booking->get_event();
		if ( empty( $event ) || empty( $event->event_id ) ) {
			return null;
		}
		return array(
			'owner_user_id' => (int) $event->event_owner,
			'title'         => $event->event_name,
			'body'          => __( 'New booking received', 'events-manager' ),
			'data'          => array(
				'type'    => 'booking_added',
				'site'    => home_url(),
				'booking' => $EM_Booking->booking_id,
				'event'   => $event->event_id,
			),
		);
	}

	public static function resolve_booking_cancelled( $EM_Booking, $args = array() ) {
		if ( ! is_object( $EM_Booking ) ) {
			return null;
		}
		// status_changed fires for every transition; only cancellations (3) are interesting here.
		$status = is_array( $args ) && isset( $args['status'] ) ? (int) $args['status'] : (int) $EM_Booking->booking_status;
		if ( 3 !== $status ) {
			return null;
		}
		$event = $EM_Booking->get_event();
		if ( empty( $event ) || empty( $event->event_id ) ) {
			return null;
		}
		return array(
			'owner_user_id' => (int) $event->event_owner,
			'title'         => $event->event_name,
			'body'          => __( 'A booking was cancelled', 'events-manager' ),
			'data'          => array(
				'type'    => 'booking_cancelled',
				'site'    => home_url(),
				'booking' => $EM_Booking->booking_id,
				'event'   => $event->event_id,
			),
		);
	}

	public static function resolve_event_added( $EM_Event ) {
		if ( ! is_object( $EM_Event ) || empty( $EM_Event->event_id ) ) {
			return null;
		}
		return array(
			'owner_user_id' => (int) $EM_Event->event_owner,
			'title'         => $EM_Event->event_name,
			'body'          => __( 'A new event was created', 'events-manager' ),
			'data'          => array(
				'type'  => 'event_added',
				'site'  => home_url(),
				'event' => $EM_Event->event_id,
			),
		);
	}
}
