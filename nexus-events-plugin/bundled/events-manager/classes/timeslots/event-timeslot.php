<?php
namespace EM\Event;

use EM_DateTime;
use EM_Event;

class Timeslot extends \EM\Timeslot {

	/**
	 * EM_Event object associated with timeslot
	 * @var EM_Event
	 */
	public $event;
	public $timeslot_id;
	public $timeslot_capacity;
	public $timeslot_status = 1;

	/**
	 * Field definitions mapping to database columns.
	 */
	public $fields = array(
		'timeslot_id' => array('type' => '%d', 'null' => false),
		'timerange_id' => array('type' => '%d', 'null' => false),
		'event_id' => array('type' => '%d', 'null' => false),
		'timeslot_start' => array('type' => '%s', 'null' => false),
		'timeslot_end' => array('type' => '%s', 'null' => true),
		'timeslot_status' => array('type' => '%s', 'null' => true),
	);

	/**
	 * Field shortcuts for external API references.
	 */
	public static $field_shortcuts = array(
		'id' => 'timerange_id',
		'start' => 'timeslot_start',
		'end' => 'timeslot_end',
		'status' => 'timeslot_status',
	);

	/**
	 * @param array|int $args
	 * @param EM_Event $EM_Event
	 */
	public function __construct( $args, $EM_Event ) {
		global $wpdb;
		// load timeslot from database if id supplied
		if ( is_numeric( $args ) ) {
			// Bound to the event as well as the id: a slot id posted from the browser could otherwise name any event's slot, and the booking would land on this event carrying the other one's times and a fresh per-slot count.
			$sql = "SELECT * FROM " . EM_EVENT_TIMESLOTS_TABLE . " WHERE timeslot_id = " . absint( $args );
			if ( ! empty( $EM_Event->event_id ) ) {
				$sql .= " AND event_id = " . absint( $EM_Event->get_event_id() );
			}
			$args = $wpdb->get_row( $sql, ARRAY_A );
			$loaded_event = true;
		}
		if ( $args ) {
			$args['timezone'] = $EM_Event->event_timezone;
			// load timeslot from array or DB array
			parent::__construct( $args );
			// set event timeslot-specific stuff
			$this->timeslot_id = absint($args['timeslot_id'] ?? 0);
			//$this->timeslot_capacity = absint($args['timeslot_capacity'] ?? 0) ?: null;
			$this->timeslot_status = absint($args['timeslot_status'] ?? 1) ;
			// correct dates if necessary
			if ( empty($loaded_event) ) {
				// times may have been provided as minutes without dates, so we set the dates just in case
				$start = $EM_Event->start();
				$end = $EM_Event->end();
				$this->start->setDate( $start->format('Y'), $start->format('m'), $start->format('d') );
				$this->end->setDate( $end->format('Y'), $end->format('m'), $end->format('d') );
			}
		}
		$this->event = $EM_Event;
	}

	public function __clone () {
		$this->start = clone $this->start;
		$this->end = clone $this->end;
	}

	/**
	 * Sets status property and all timeslots in this timerange to the same status. Makes a single SQL call to update all event timeslots belonging to this timerange.
	 * @param $status
	 *
	 * @return void
	 */
	public function set_status( $status, $db = true ) {
		$this->timeslot_status = (int) $status;
		if ( $db ) {
			global $wpdb;
			$sql = "UPDATE " . EM_EVENT_TIMESLOTS_TABLE . " SET timeslot_status = " . $this->timeslot_status . " WHERE timeslot_id = " . absint( $this->timeslot_id );
			$wpdb->query( $sql );
		}
	}

	public function get_uid() {
		return absint($this->event->event_id) . ':' . absint($this->timeslot_id);
	}

	public function uid() {
		echo $this->get_uid();
	}

	/**
	 * Returns a copy of the base event with timeslot information merged in
	 * @param bool $convert
	 *
	 * @return EM_Event
	 */
	public function get_event( $convert = false ) {
		// return a copoy
		if ( $this->event->timeslot_id == $this->timeslot_id && $this->event->event_type === 'timeslot' ) {
			return $this->event;
		}
		$EM_Event = $convert ? $this->event : clone $this->event;
		$EM_Event->event_start = '';
		$EM_Event->event_end = '';
		$EM_Event->event_start_date = $this->start->getDate();
		$EM_Event->event_start_time = $this->start->getTime();
		$EM_Event->event_end_date = $this->end->getDate();
		$EM_Event->event_end_time = $this->end->getTime();
		$EM_Event->timeslot_id = $this->timeslot_id;
		$EM_Event->event_type = 'timeslot';
		if ( $this->timeslot_status !== null ) {
			$EM_Event->event_active_status = $this->timeslot_status;
		}
		return $EM_Event;
	}

	public function cancel() {
		global $wpdb;
		// cancel timeslot in DB if not already cancelled
		if ( $this->timeslot_status === 0 ) {
			$this->timeslot_status = 0;
			$wpdb->update( EM_EVENT_TIMESLOTS_TABLE, ['timeslot_status' => 0 ], [ 'timeslot_id' => $this->timeslot_id ] );
		}
		// 'cancel' the event so bookings and other things get triggered correctly
		$this->get_event()->cancel();
	}

	public function to_array( $db = false ) {
		return [
			'timerange_id' => $this->timerange_id,
			'start' => $this->start->getTime(),
			'end' => $this->end->getTime(),
			'capacity' => (int) $this->timeslot_capacity,
			'status' => (int) $this->timeslot_status,
		];
	}
}