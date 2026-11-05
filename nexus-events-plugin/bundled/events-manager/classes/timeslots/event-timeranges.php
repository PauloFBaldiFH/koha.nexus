<?php
namespace EM\Event;
use EM_DateTime;
use EM_Event;

/**
 * Handles timeslot saving and retrieval for an event, which additionally saves individual timeslots into a separate table.
 *
 * @property int $length The number of timeslots in this collection.
 */
class Timeranges extends \EM\Timeranges {

	/**
	 * @var EM_Event
	 */
	public $event;
	public $timeslots = [];
	public $status = 1;

	/**
	 * Constructor to initialize the Event Timeslots collection.
	 * 
	 * @param EM_Event|int $event The event object or event ID to load timeslots for
	 */
	public function __construct( $group_id, $event = null ) {
		if ( $event instanceof EM_Event ) {
			$this->event = $event;
		} elseif ( is_numeric($event) ) {
			$this->event = em_get_event( $event );
		} else {
			_doing_it_wrong( static::class . '::_contstruct' , 'You must supply an EM_Event object or event ID to load timeslots in Events Manager.', '7.2' );;
			$this->event = new EM_Event();
		}
		parent::__construct( $group_id );
		$this->allow_timeranges = $this->event->get_option( 'dbem_event_timeranges_enabled', true );
		$this->allow_edit = !$this->event->event_id;
		$this->delete_action = $this->event->get_option('dbem_event_status_enabled') ? 'cancel' : 'delete';
	}

	public function get_timerange( $data = null ) {
		return new Timerange( $data, $this->event );
	}

	/**
	 * Loads event timeranges, always padding with the default event timerange (stored or new), if no timeranges are found.
	 * @param $padding
	 *
	 * @return Timerange[]|\EM\Timerange[]
	 */
	public function load_timeranges ( $padding = true ) {
		if ( !$this->timeranges ) {
			if ( ( $this->event->is_recurring( true ) || $this->event->is_repeated() ) && $this->group_id === 'event_' . $this->event->get_event_id() ) {
				// we load all timeranges from recurrence sets, not this event itself, which has no timeranges associated directly with it
				// for a repeated event (not the repeating template) we also load from recurrence sets, but a repated event belongs to a single recurrence set
				$Recurrence_Sets = $this->event->is_repeated() ? [ $this->event->get_recurrence_set() ] : $this->event->get_recurrence_sets();
				foreach ( $Recurrence_Sets as $Recurrence_Set ) {
					$Timeranges = $Recurrence_Set->get_timeranges();
					foreach ( $Timeranges as $Timerange ) {
						if ( !array_key_exists( $Timerange->timerange_id, $this->timeranges ) ) {
							$this->timeranges[ $Timerange->timerange_id ] = $Timerange;
						}
					}
				}
				if ( !$this->timeranges && $padding ) {
					$this->timeranges[0] = new Timerange( [], $this->event );
				}
			} else {
				// load timeranges for this group id
				parent::load_timeranges(); // Load without padding, pad here if needed
				if ( $padding && !$this->timeranges ) {
					$Timerange = new Timerange( [
						'timerange_id' => 0,
						'timerange_start' => $this->event->start()->getTime(),
						'timerange_end' => $this->event->end()->getTime(),
						'timerange_all_day' => $this->event->event_all_day,
					], $this->event );
					if ( $this->event->get_event_id() ) {
						$Timerange->group_id = 'event_' . $this->event->get_event_id();
					}
					$this->timeranges = [ $Timerange ];
				}
			}
		}
		return $this->timeranges;
	}

	public function load_timeslots() {
		global $wpdb;
		if ( !$this->timeslots ) {
			$this->timeslots = [];
			if ( $this->event->get_event_id() > 0 && !$this->event->is_recurring( true ) ) {
				// get timeslots from DB
				$timeslots_data = $wpdb->get_results( "SELECT * FROM " . EM_EVENT_TIMESLOTS_TABLE . " WHERE event_id=" . absint( $this->event->get_event_id() ) . " ORDER BY timeslot_start", ARRAY_A );
				if ( !$timeslots_data ) {
					// prefill with start and end dates of the event
					$timeslots_data = [[
						'timeslot_all_day' => $this->event->event_all_day,
						'timeslot_start' => $this->event->start()->getTimestamp(),
						'timeslot_end' => $this->event->end()->getTimestamp(),
						'timeslot_id' => null,
					]];
				}
				foreach ( $timeslots_data as $timeslot_data ) {
					$this->timeslots[ absint($timeslot_data['timeslot_id']) ] = new Timeslot( $timeslot_data, $this->event );
				}
			} elseif ( $this->event->is_recurring( true ) ) {
				// generate timeslots, because recurring events don't have timeslots, recurrences sets will need to change the dates for each recurrence
				$this->timeslots = $this->generate_timeslots();
			}
		}
		return $this->timeslots;
	}

	public function has_timeslots() {
		if ( $this->event->event_type === 'timeslot' ) {
			return false;
		}
		return parent::has_timeslots();
	}

	public function get() {
		return $this->load_timeslots();
	}

	/**
	 * Return array of timeslots, in seconds since midnight for a day based on timerange rules in this set.
	 * @return Timeslot[]
	 */
	public function get_timeslots() {
		return $this->load_timeslots();
	}

	/**
	 * Saves event timeslots to the database, if an event array is supplied as context, the timeranges are not saved and just timeslots are saved, which is useful for saving recurrences or repetitions.
	 * @param $event If supplied, it is assumed that the timeranges has been saved
	 *
	 * @return bool
	 * @throws \Exception
	 */
	public function save( $event = null, $edit_action = null ) {
		global $wpdb;
		if ( $this->allow_edit || $edit_action ) {
			$has_timeslots = $this->has_timeslots();
			$event_active_status = 1;
			if ( !$event && $this->event->is_recurring( true ) && $has_timeslots) {
				// just save the timeranges, recurring and repeating doesn't have timeslots themselves, only the recurrences
				parent::save();
			} elseif ( $has_timeslots && $this->validate() ){ // do not create event timeslots if timeranges are invalid
				// we have more than one timerange or Timeslot here,
				// save group id to timeranges, in case it's a new event
				$this->group_id = 'event_' . $this->event->event_id;
				foreach ( $this->timeranges as $Timerange ) {
					$Timerange->group_id = $this->group_id;
				}
				// get the event details we'll use further on, either supplied argument (e.g. for repeating/recurring events saving recurrences) or the context event
				if ( $event ) {
					// it is assumed that the current timeranges have been saved with valid timerange_id values, so we generate new timeslots
					$Timeslots = $this->generate_timeslots( true );
					if ( is_array( $event ) ) {
						// we're essentially saving a duplicate template of timeranges/timeslots for a different event context, such as for a recurrence/repeated
						$event_id = absint( $event['event_id'] );
						$event_active_status = absint( $event['event_active_status'] );
						// if a different start/end date is supplied, clone the timeslots and change the dates for this time around
						if ( !empty( $event['event_start'] ) && !empty( $event['event_end'] ) ) {
							// create a clone of the timeslots objects and change the date of new cloned object
							foreach ( $Timeslots as $k => $Timeslot ) {
								$Timeslot = clone( $Timeslot );
								$Timeslots[$k] = $Timeslot;
								// get the start time first, feed it back into an new EM_Event object with date, and timezone so it's set to the current timezone
								$start_time = $Timeslot->start->getTime();
								$Timeslot->start = new EM_DateTime( $event['event_start_date'] . ' ' . $start_time, $event['event_timezone'] ?? $this->event->event_timezone );
								$end_time = $Timeslot->end->getTime();
								$Timeslot->end = new EM_DateTime( $event['event_end_date'] . ' ' . $end_time, $event['event_timezone'] ?? $this->event->event_timezone );
							}
						}
					}
				} else {
					$event = $this->event;
					$event_active_status = $event->event_active_status;
					// save the timerange data to the database unless it's a recurrence (repeated too), recurrences inherit timerange information from the main event, repeated events will dynamically pull timerange info from the repeating event template
					if ( !$event->is_recurrence( true ) ) {
						parent::save();
					}
					// generate timeslots after saving so we have valid timerange_id values
					$Timeslots = $this->generate_timeslots( true);
				}
				if ( $event instanceof EM_Event ) {
					$event_id = $event->event_id;
					$event_active_status = $event->event_active_status;
				}
				// build the array of timeslots we will save, based on the start/end dates of the event
				if ( !empty( $event_id ) ) {
					// get the current records if there are any, so we can compare with the currently generated timeslots and either add, edit, or delete/cancel
					$event_timeslots = $wpdb->get_results( "SELECT * FROM " . EM_EVENT_TIMESLOTS_TABLE . " WHERE event_id=" . absint( $event_id ), ARRAY_A );
					$events_timeslots_unmatched = [];
					$events_timerange_id_updates = [];
					// compare generated timeslots with current timeslots, match existing timeslots, identify deleted or newly added ones
					foreach ( $event_timeslots as $event_timeslot ) {
						// find a matching Timeslot in the generated timeslots
						$found_match = false;
						foreach ( $Timeslots as $k => $Timeslot ) { /* @var Timeslot $Timeslot */
							// do we have a match? If so, remove it from the Timeslot data as we don't need to take further action
							if ( $Timeslot->start->getDateTime('UTC') === $event_timeslot['timeslot_start'] ) {
								// matching dates found, at least, start time is the same and we can modify the end-time if necessary
								$found_match = true;
								// remove from the Timeslot array, we don't need to save it as a new one
								unset( $Timeslots[ $k ] );
								// update end times if necessary
								if ( $Timeslot->end->getDateTime('UTC') !== $event_timeslot['timeslot_end'] ) {
									// rather than delete or cancel the previous timeslot, we can just extend the end-time and let the admin decide whether to cancel bookings etc. so we avoid leaving cancelled events with conflicting times
									$wpdb->update( EM_EVENT_TIMESLOTS_TABLE, [ 'timeslot_end' => $Timeslot->end->getDateTime('UTC') ], [ 'timeslot_id' => absint( $event_timeslot['timeslot_id'] ) ], '%s', '%d' );
								}
								// check if the timerange_id has changed, we don't need to delete/cancel the timeslot, just reassign the id of what it belongs to
								if ( (int) $event_timeslot['timerange_id'] !== (int) $Timeslot->timerange_id ) {
									$timerange_id = absint( $Timeslot->timerange_id );
									if ( !isset( $events_timerange_id_updates[ $timerange_id ] ) ) {
										$events_timerange_id_updates[ $timerange_id ] = [];
									}
									$events_timerange_id_updates[ $timerange_id ][] = absint( $event_timeslot['timeslot_id'] );
								}
								// add a status update mechanism too
								if ( (int) $event_timeslot['timeslot_status'] !== (int) $event_active_status ) {
									if ( !isset( $events_timerange_status_updates ) ) {
										$events_timerange_status_updates = [];
									}
									$events_timerange_status_updates[] = absint( $Timeslot->timerange_id );
								}
								break;
							}
						}
						// Did we find a match? If not, we need to delete or cancel it from the event timeslots table
						if ( !$found_match ) {
							$events_timeslots_unmatched[] = absint( $event_timeslot['timeslot_id'] );
						}
					}
					// Alter status of unmacehd event timeslots
					if ( !empty( $events_timeslots_unmatched ) ) {
						$edit_action ??= $this->delete_action;
						if ( $edit_action === 'delete' || !$this->event->get_option( 'dbem_event_status_enabled' ) ) {
							$sql = 'DELETE FROM ' . EM_EVENT_TIMESLOTS_TABLE . ' WHERE timeslot_id IN (' . implode( ',', $events_timeslots_unmatched ) . ')';
							$wpdb->query( $sql );
						} else {
							// Update the timeslot_status to 0 for cancelled events
							$sql = 'UPDATE ' . EM_EVENT_TIMESLOTS_TABLE . ' SET timeslot_status=0 WHERE timeslot_id IN (' . implode( ',', $events_timeslots_unmatched ) . ')';
							$wpdb->query( $sql );
							// Instantiate events and trigger a status change
							foreach ( $events_timeslots_unmatched as $timeslot_id ) {
								$Timeslot = new Timeslot( $timeslot_id, $this->event );
								$this->event->cancel();
								apply_filters('em_event_set_active_status', true, 0, $Timeslot->get_event() );
							}
						}
					}
					// update timerange_id for timeslots that have changed, since we don't need to delete the Timeslot itself
					if ( !empty( $events_timerange_id_updates ) ) {
						foreach ( $events_timerange_id_updates as $timerange_id => $timeslot_ids ) {
							$sql = "UPDATE " . EM_EVENT_TIMESLOTS_TABLE . " SET timerange_id = $timerange_id WHERE timeslot_id IN (" . implode( ',', $timeslot_ids ) . ")";
							$wpdb->query( $sql );
						}
					}
					// update timeslot statuses for timeslots that have changed, since we don't need to delete the Timeslot itself
					if ( !empty( $events_timerange_status_updates ) ) {
						$sql = "UPDATE " . EM_EVENT_TIMESLOTS_TABLE . " SET timeslot_status = ". (int) $event_active_status ." WHERE timerange_id IN (" . implode( ',', $events_timerange_status_updates ) . ")";
						$wpdb->query( $sql );
					}
					// add new timeslots
					if ( $Timeslots ) {
						// build SQL insert statement
						$sql = "INSERT INTO " . EM_EVENT_TIMESLOTS_TABLE . " (event_id, timeslot_start, timeslot_end, timerange_id, timeslot_status) VALUES ";
						$sqls = [];
						foreach ( $Timeslots as $Timeslot ) {
							$sqls[] = $wpdb->prepare( "(%d, %s, %s, %d, %d)", $event_id, $Timeslot->start->getDateTime('UTC'), $Timeslot->end->getDateTime('UTC'), $Timeslot->timerange_id, $event_active_status );
						}
						$sql .= implode( ', ', $sqls );
						if ( $wpdb->query( $sql ) === false ) {
							$this->add_error( __( 'There was a problem saving the event timeslots to the database. Please contact an administrator if the issue persists.', 'events-manager' ) );
						}
					}
				}
				return apply_filters( 'em_event_timeslots_save', !$this->errors, $this );
			} elseif ( $has_timeslots ) {
				// Timeslots are wanted but did not validate, so the stored rows are still the truth; dropping them here would discard the event's whole timeslot grid on a validation failure.
				return apply_filters( 'em_event_timeslots_save', false, $this );
			} else {
				// remove all timerange entries from the DB, we only need the one in the event table which can generate a simple timerange without advanced rules dynamically
				$wpdb->query( "DELETE FROM " . EM_TIMERANGES_TABLE . " WHERE timerange_group_id='event_" . $this->event->event_id . "'" );
				$wpdb->query( "DELETE FROM " . EM_EVENT_TIMESLOTS_TABLE . " WHERE event_id=" . absint( $this->event->event_id ) );
			}
		}
	}

	public function set_status( $status, $db = true ) {
		global $wpdb;
		// we can just set status in one SQL status where all timerange ids are included
		$this->status = (int) $status;
		foreach ( $this->timeranges as $Timerange ) {
			if ( $Timerange->timerange_id ) {
				$timerange_ids[] = absint($Timerange->timerange_id);
			}
			$Timerange->status = $this->status;
			foreach ( $Timerange->timeslots as $Timeslot ) {
				$Timeslot->timeslot_status = $this->status;
			}
		}
		if ( $db ) {
			if ( !empty( $timerange_ids ) ) {
				$sql = "UPDATE " . EM_EVENT_TIMESLOTS_TABLE . " SET timeslot_status = " . $this->status . " WHERE timerange_id IN (" . implode( ',', $timerange_ids ) . ")";
				$wpdb->query( $sql );
			}
		}
		return $this;
	}
}
include( __DIR__ . '/event-timerange.php');
include( __DIR__ . '/event-timeslot.php');