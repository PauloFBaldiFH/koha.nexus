<?php
namespace EM\Recurrences;
use EM_DateTime;
use EM_DateTimeZone;
use EM_Event;
use EM_Ticket;

/**
 * @property int $length The number of recurrence sets in this object.
 */
class Recurrence_Sets extends \EM_Object implements \Iterator, \ArrayAccess, \Countable {

	/**
	 * Associative array of times where events occur, used for avoiding collisions created by a preceding set in this recurring event.
	 *
	 *  Each recurrence is stored in $this->recurrences as:
	 *  [
	 *    'start'    => start_timestamp,
	 *    'end'      => end_timestamp,
	 *    'event_id' => 123   // present for inclusions, omitted for exclusions
	 *  ]
	 *
	 * @var array
	 */
	public $recurrences;
	/**
	 * Array of Recurrence_Set objects, keyed by recurrence_set_id if not already saved.
	 * @var Recurrence_Set[]
	 */
	public $include = [];
	/**
	 * Array of Recurrence_Set objects representing blackout date/time patterns, keyed by recurrence_set_id if not already saved.
	 * @var Recurrence_Set[]
	 */
	public $exclude = [];
	/**
	 * The primary/default recurrence set, which other recurrences can take settings from if not defined (for example, the starT/end dates of the recurrence pattern, timezone, etc.)
	 * @var Recurrence_Set
	 */
	public $default;

	/**
	 * @var int Event ID of the recurring event
	 */
	public $event_id;
	/**
	 * @var EM_Event $event The recurring Event object
	 */
	public $event;

	// Rescheduling - flags to help identify when rescheduing is to take place upon save

	/**
	 * If 'cancel' or 'delete', all recurrence sets will be rescheduled and recurrences will be handled accordingly, if true the recurrences will be cancelled if possible otherwise deleted.
	 * @var boolean|string
	 */
	public $reschedule = false;
	/**
	 * Action to be taken to currently created events if rescheduling this set is authorized. This would be 'cancel' or 'delete' depending if cancellations are allowed.
	 * @var string
	 */
	public $reschedule_exclude;
	/**
	 * Returns a multi-dimensional array of recurrences, indexed by UTC start date then start_time, which can be used for collision detection.
	 *
	 * Within a start time record, it can be an array containg an event array, or an array of events in case there are multiple events on the same time.
	 *
	 * @return array
	 */
	/**
	 * @var bool Flag to track if recurrences have been modified and need resorting
	 */
	public $recurrences_modified = true;
	/**
	 * @var int Last count of recurrences array, used to detect modifications
	 */
	protected $recurrences_count = 0;

	// Booking flags - detect when to modify bookings in recurrences

	 /**
	 * @var array{
	 *     tickets: array{
	 *         added: array<string, EM_Ticket>, // Keyed by EM_Ticket::ticket_uuid
	 *         modified: array<int, EM_Ticket>, // Keyed by EM_Ticket::ticket_id
	 *         deleted: array<int, EM_Ticket>, // Keyed by EM_Ticket::ticket_id
	 *         unchanged: array<int, EM_Ticket> // Keyed by EM_Ticket::ticket_id
	 *     }
	 * } Map of things to be updated/deleted in bookings when recurrences are saved.
	 */
	public $booking_updates = [ 'tickets' => [ 'added' => [], 'modified' => [], 'deleted' => [], 'unchanged' => [] ] ];
	/**
	 * Flag used for when saving a recurring event that previously had bookings enabled and then subsequently disabled.
	 * If set to true, and $this->recreate_bookings is false, bookings and tickets of recurrences will be deleted.
	 * @var boolean
	 */
	public $update_bookings = false;

	/**
	 * Constructor to initialize the Recurrence_Sets object.
	 * Accepts an EM_Event object and loads its recurrence sets.
	 *
	 * @param EM_Event $event
	 */
	public function __construct ( $event ) {
		// add event data to this object
		if ( $event instanceof EM_Event ) {
			$this->event_id = $event->event_id;
			$this->event = $event;
		} else {
			$this->event_id = $event;
		}
		if ( $this->event_id ) {
			// load recurrence sets
			global $wpdb;
			$results = $wpdb->get_results( $wpdb->prepare( "SELECT * FROM " . EM_EVENT_RECURRENCES_TABLE . " WHERE event_id = %d ORDER BY recurrence_order, recurrence_set_id ASC", $this->event_id ), ARRAY_A );
			foreach ( $results as $row ) {
				$Recurrence_Set = new Recurrence_Set( $row );
				if ( $Recurrence_Set->type == 'include' ) {
					$this->include[ $Recurrence_Set->id ] = $Recurrence_Set;
					if ( !$this->default ) {
						$this->default = $Recurrence_Set;
					}
				} elseif ( $Recurrence_Set->type == 'exclude' ) {
					$this->exclude[ $Recurrence_Set->id ] = $Recurrence_Set;
				}
				if ( $event instanceof EM_Event ) {
					$Recurrence_Set->event = $event;
				}
			}
		}
	}

	public function __get ( $prop ) {
		if ( $prop === 'length' ) {
			return count( $this->include );
		}

		return parent::__get( $prop );
	}

	public function add_empty_set () {
		if ( count( $this->include ) === 0 ) {
			$Recurrence_Set = new Recurrence_Set();
			$this->include[] = $Recurrence_Set;
			$this->default = $Recurrence_Set;
		}
	}

	/**
	 * Returns a multi-dimensional array of recurrences, indexed by UTC start date then start_time, which can be used for collision detection.
	 *
	 * Within a start time record, it can be an array containg an event array, or an array of events in case there are multiple events on the same time.
	 *
	 * @return array
	 */
	public function get_recurrences() {
	    if ($this->recurrences === null) {
	        $this->recurrences = [];
	        // excludes take priority since we don't want events on that day
	        foreach ($this->exclude as $Recurrence_Set) {
	            $this->recurrences += $Recurrence_Set->get_recurrences();
	        }
	        foreach ($this->include as $Recurrence_Set) {
	            $this->recurrences += $Recurrence_Set->get_recurrences();
	        }
	        $this->recurrences_modified = true;
	        $this->recurrences_count = count($this->recurrences);
	    } else {
	        // Check if the array size changed, which indicates modification
	        $current_count = count($this->recurrences);
	        if ($current_count !== $this->recurrences_count) {
	            $this->recurrences_modified = true;
	            $this->recurrences_count = $current_count;
	        }
	    }

	    // Only sort if modifications have been made
	    if ($this->recurrences_modified) {
	        ksort($this->recurrences);
	        reset($this->recurrences);
	        $this->recurrences_modified = false;
	    }

	    return $this->recurrences;
	}

	public function get_recurrence_days() {
		$recurrence_days = [];
		foreach ($this->include as $Recurrence_Set) {
			$recurrence_days = array_merge($recurrence_days, $Recurrence_Set->get_recurrence_days());
		}
		return array_values(array_unique($recurrence_days));
	}

	/**
	 * Check if a given interval overlaps any recurrence rule. A collision can be from an exclusion or an overlapping event.
	 *
	 * @param int $start Unix timestamp for the start of the query interval.
	 * @param int $end Unix timestamp for the end of the query interval.
	 * @param int $type If supplied, only checks for the specific type of collision is checked, values can be 'exclude' or 'include'
	 *
	 * @return false|string Recurrence type (include|exclude) of an overlapping recurrence if found, false otherwise.
	 */
	public function has_collision ( $start, $end, $type = null ) {
		// Assume $this->recurrences is sorted by start timestamp.
		$this->get_recurrences();
		if ( defined('EM_DEBUG') && EM_DEBUG ) {
			$start_dt = new EM_DateTime( $start, 'UTC' );
			$end_dt = new EM_DateTime( $end, 'UTC' );
		}
		foreach ( $this->recurrences as $recurrence ) {
			// If this recurrence starts after the query interval ends,
			// no subsequent recurrences can overlap.
			if ( $recurrence['start'] > $end ) {
				break;
			}
			// Check if there is an overlap.
			if ( $start < $recurrence['end'] && $end > $recurrence['start'] ) {
				$type_found = !empty($recurrence['event_id']) ? 'include' : 'exclude';
				// overlap found, return if it matches type needed or if none specified
				if ( !$type || $type_found === $type ) {
					return $type_found;
				}
			}
		}

		return false;
	}

	/**
	 * Returns a string representation of this recurrence. Will return false if not a recurrence
	 * @return string
	 */
	function get_recurrence_description ( $include_dates = true ) {
		$EM_Event = $this->get_event();
		$descriptions = [];
		if ( $EM_Event ) {
			if ( !empty($this->default) ) {
				if ( $include_dates ) {
					$descriptions[] = sprintf( __( 'From %1$s to %2$s', 'events-manager' ), $EM_Event->start()->i18n( em_get_date_format() ), $EM_Event->end()->i18n( em_get_date_format() ) );
				}
				$pattern = ucfirst( $this->default->get_recurrence_description() );
				$count = count( $this->include );
				if ( $count > 1 ) {
					$pattern .= ' + ' . sprintf( _n( '%d Pattern', '%d Patterns', $count - 1, 'events-manager' ), $count - 1 );
				}
				$descriptions[] = $pattern;
			}
		}

		return implode( ', ', $descriptions );
	}

	/**
	 * Smart event locator, saves a database read if possible. Note that if an event doesn't exist, a blank object will be created to prevent duplicates.
	 */
	function get_event () {
		global $EM_Event;
		if ( $this->event && $this->event->event_id == $this->event_id ) {
			return $this->event;
		}
		if ( is_object( $EM_Event ) && $EM_Event->event_id == $this->event_id ) {
			$this->event = $EM_Event;
		} else {
			$this->event = em_get_event( $this->event_id );
		}

		return $this->event;
	}

	/**
	 * Gets the first and last date/time that this recurring event spans from/to,
	 * accounting for potentially different timezones between recurrence sets.
	 *
	 * @return array An associative array with start_date, end_date, start_time, end_time
	 */
	public function get_datetime_range () {
		// Initialize with null values
		$DateTime['start'] = null;
		$DateTime['end'] = null;
		// get all recurrences, and loop from the start until we find first event_id
		foreach ( $this->get_recurrences() as $recurrence ) {
			if ( !empty( $recurrence['event_id'] ) ) {
				// it's an event, grab the date and break
				$DateTime['start'] = new EM_DateTime( $recurrence['start'], 'UTC' );
				break;
			}
		}
		// get keys of recurrences and loop backwards to find the last event_id
		$keys = array_keys( $this->recurrences );
		for ($i = count($keys) - 1; $i >= 0; $i--) {
			$ts = $keys[$i];
			if ( !empty( $this->recurrences[$ts]['event_id'] ) ) {
				$DateTime['end'] = new EM_DateTime( $this->recurrences[$ts]['end'], 'UTC' );
				break;
			}
		}
		// build result array
		$result = [];
		// Before returning, standardize timezone to the default recurrence set timezone
		$default_timezone = !empty( $this->default->timezone ) ? $this->default->timezone : EM_DateTimeZone::create();
		foreach ( $DateTime as $when => $EM_DateTime ) {
			if ( $EM_DateTime instanceof EM_DateTime ) {
				$EM_DateTime->setTimezone( $default_timezone );
			}
			$result[ $when . '_date' ] = $EM_DateTime ? $EM_DateTime->getDate() : null;
			$result[ $when . '_time' ] = $EM_DateTime ? $EM_DateTime->getTime() : null;
		}
		// Determine if this is an all-day event, which must correspond to the current timezone, otherwise even if all-day it's starting/ending at a specific local time and not midnight
		$result['all_day'] = ( $result['start_time'] === '00:00:00' && $result['end_time'] === '23:59:59' );

		return $result;
	}

	public function get_post () {
		if ( !$this->get_event() ) {
			return false;
		}
		//Get original recurring event so we can tell whether event recurrences or bookings will be recreated or just modified
		$EM_Event = $this->get_event();

		// first go through all requested values and mark those for deletion
		if ( !empty( $_REQUEST['recurrences'] ) && is_array( $_REQUEST['recurrences'] ) ) {
			// $order is only populated from include sets below, but the uksort() further down runs unconditionally — initialise it here so a payload with no include sets (e.g. exclude-only, or a malformed recurrences array with no include/exclude keys) can't pass null to uksort() and fatal.
			$order = array();
			// we go through all the recurrences that are set to delete, we must have a nonce to set this to delete, as a fail-safe
			foreach ( $_REQUEST['recurrences'] as $type => $type_sets ) {
				if ( !in_array( $type, [ 'include', 'exclude' ] ) ) {
					continue;
				}
				foreach ( $type_sets as $data ) {
					$set_id = !empty( $data['recurrence_set_id'] ) ? absint( $data['recurrence_set_id'] ) : false;
					if ( !empty( $data['delete'] ) && $set_id ) {
						// check we have a valid set ID present, and that the nonce checks out
						if ( !empty( $this->{$type}[ $set_id ] ) ) {
							if ( wp_verify_nonce( $data['delete'], 'delete_recurrence_' . $set_id . '_' . get_current_user_id() ) ) {
								$this->{$type}[ $set_id ]->delete = $data['delete'];
							} else {
								$this->add_error( sprintf( 'Cannot delete set ID %d, invalid nonce provided.', $set_id ) );
							}
						} else {
							$this->add_error( sprintf( 'Cannot find set ID to delete - %d', $set_id ) );
						}
					} else {
						if ( !$set_id || empty( $this->{$type}[ $set_id ] ) ) {
							// if this is a new exclude type to a previously-created event, and we're adding an exclusion, we need to double-check that we have confirmed the rescheduling and what action would be taken
							if ( $type == 'exclude' && $EM_Event->event_id ) {
								// we need to potentially reschedule, check nonce is good and set flags
								$nonce = $_REQUEST['recurrences']['exclude_reschedule']['nonce'] ?? false;
								if ( !$nonce || !wp_verify_nonce( $nonce, 'reschedule_exclude_' . get_current_user_id() ) ) {
									// not adding the new exclusion as nonce not met
									continue;
								}
							}
							// add a recurrence pattern
							$Recurrence_Set = new Recurrence_Set( $this->get_event(), $type );
							$this->{$type}[] = $Recurrence_Set;
							// set this as default if we haven't added any sets yet
							if ( $type == 'include' && count($this->include) === 1 ) {
								$this->default = $Recurrence_Set;
							}
						} else {
							$Recurrence_Set = $this->{$type}[ $set_id ];
						}
						if ( !$Recurrence_Set->get_post( $data ) ) {
							$this->add_error( $Recurrence_Set->get_errors() );
						}
						if ( $type == 'include' ) {
							// Use the initial recurrence_order as a string key
							$orderKey = (string) $Recurrence_Set->order ?: 99999;
							// If this key already exists, append a suffix to differentiate it
							if ( isset( $order[ $orderKey ] ) ) {
								$suffix = 1;
								// Increment the suffix until we find a unique key (e.g., "1.1", "1.2", etc.)
								while ( isset( $order[ $orderKey . '.' . $suffix ] ) ) {
									$suffix ++;
								}
								$orderKey .= '.' . $suffix;
							}
							$order[ $orderKey ] = $Recurrence_Set;
						}
					}
				}
			}
			// make sure we have a numerical ordering system, 1 onwwards, and designate the default recurrence set
			uksort( $order, function ( $a, $b ) {
				return floatval( $a ) <=> floatval( $b );
			} );
			$i = 1;
			foreach ( $order as $Recurrence_Set ) {
				$Recurrence_Set->order = $i;
				if ( $i === 1 ) {
					$this->default = $Recurrence_Set;
				}
				$i ++;
			}
			// now we know the recurrences we're dealing with, we can check for set-wide rescheduling
			if ( $this->reschedule ) {
				// reschedule everything
				$reschedule_action = static::get_reschedule_action( $this->reschedule );
				foreach ( $this->include as $Recurrence_Set ) {
					$Recurrence_Set->set_reschedule( true );
					$Recurrence_Set->reschedule_action = $reschedule_action;
				}
				$this->reschedule_exclude = $reschedule_action;
			} elseif ( $this->default->has_reschedule('dates') ) {
				// check the primary recurrence for changes to dates and make sure any subsequent recurrences depending on the primary are set for reschedule too if applicable
				foreach ( $this->include as $Recurrence_Set ) {
					if ( $Recurrence_Set !== $this->default ) {
						// if the recurrence has either of the start/end dates unset then we mark it for rescheduling
						if ( empty( $Recurrence_Set->recurrence_start_date ) || empty( $Recurrence_Set->recurrence_end_date ) ) {
							if ( !$Recurrence_Set->has_reschedule() ) {
								// copy the rescheduling action if the set isn't already set to be rescheduled
								$Recurrence_Set->reschedule_action = $this->default->reschedule_action;
							}
							$Recurrence_Set->reschedule['dates'] = true; // set to be rescheduled
						}
					}
				}
			}
			// check for exclusion rescheduling
			if ( !empty( $_REQUEST['recurrences']['exclude_reschedule']['nonce'] ) ) {
				if ( wp_verify_nonce( $_REQUEST['recurrences']['exclude_reschedule']['nonce'], 'reschedule_exclude_' . get_current_user_id() ) ) {
					// assign the flags to allow recurrences to be rescheduled
					$this->reschedule_exclude = static::get_reschedule_action( $_REQUEST['recurrences']['exclude_reschedule']['action'] ?? null );
				}
			}
		}

		return apply_filters( 'em_recurrence_sets_get_post', count( $this->errors ) === 0, $this );
	}

	/**
	 * Handle saving booking-related information such as RSVP-by cutt-offs and checking ticket changes, this is triggered after EM_Event::get_post() has fully processed booking information.
	 * @return void
	 */
	public function get_post_bookings() {
		$EM_Event = $this->get_event();
		// Create timestamps and set rsvp date/time rules for recurrences.
		// We will save this for now on the primary recurrence for all recurrences, we can address overriding this on per-set basis
		if ( $this->get_event()->can_manage('manage_bookings','manage_others_bookings') ) {
			if ( $EM_Event->event_rsvp ) {
				if ( !empty($_REQUEST['modify_recurring_tickets']) && wp_verify_nonce( $_REQUEST['modify_recurring_tickets'], 'modify_recurring_tickets' ) ) {
					/* WIP for a later date, overridable per-set cut-off dates could be done if a requested feature
					//recurring events may have a cut-off date x days before or after the recurrence start dates
					$this->default->recurrence_rsvp_days = null;
					$this->default->recurrence_rsvp_time = null;
					if ( em_get_option( 'dbem_bookings_tickets_single' ) && count( $EM_Event->get_tickets()->tickets ) == 1 ) {
						//if in single ticket mode then ticket cut-off date determines event cut-off date
						$EM_Ticket = $EM_Event->get_tickets()->get_first();
						if ( !empty( $EM_Ticket->ticket_meta['recurrences'] ) ) {
							$this->default->recurrence_rsvp_days = $EM_Ticket->ticket_meta['recurrences']['end_days'];
							$this->default->recurrence_rsvp_time = $EM_Ticket->ticket_meta['recurrences']['end_time'];
						}
					} else {
						if ( isset( $_POST['recurrence_rsvp_days'] ) ) {
							if ( !empty( $_POST['recurrence_rsvp_days_when'] ) && $_POST['recurrence_rsvp_days_when'] == 'after' ) {
								$this->default->recurrence_rsvp_days = absint( $_POST['recurrence_rsvp_days'] );
							} else { //by default the start date is the point of reference
								$this->default->recurrence_rsvp_days = absint( $_POST['recurrence_rsvp_days'] ) * - 1;
							}
						}
					}
					*/
					// check for added or modified tickets
					$EM_Tickets = $EM_Event->get_tickets();
					foreach ( $EM_Tickets->tickets as $EM_Ticket ) {
						if ( $EM_Ticket->ticket_id ) {
							// check if ticket has been modified in any way
							$ticket = new EM_Ticket( $EM_Ticket->ticket_id );
							$original = $ticket->to_array();
							$modified = $EM_Ticket->to_array();
							$key_changes = [];
							foreach (['ticket_name', 'ticket_order', 'ticket_meta'] as $key) {
							    if ( $original[$key] !== $modified[$key]) {
							        $key_changes[$key] = true;
							    }
							}
							if ( !empty($key_changes) ) {
								$this->booking_updates['tickets']['modified'][$EM_Ticket->ticket_id] = $EM_Ticket;
							} else {
								$this->booking_updates['tickets']['unchanged'][$EM_Ticket->ticket_id] = $EM_Ticket;
							}
						} else {
							// added
							$this->booking_updates['tickets']['added'][$EM_Ticket->ticket_uuid] = $EM_Ticket;
						}
					}
					$this->booking_updates['tickets']['deleted'] = $EM_Tickets->deleted_tickets;
				} else {
					foreach ( $EM_Event->get_tickets()->tickets as $EM_Ticket ) {
						$this->booking_updates['tickets']['unchanged'][$EM_Ticket->ticket_id] = $EM_Ticket;
					}
				}
			}
		}
	}

	/**
	 * Saves events and replaces old ones. Returns true if sucecssful or false if not.
	 * @return boolean
	 */
	public function validate () {
		foreach ( $this->include as $Recurrence_Set ) {
			if ( !$Recurrence_Set->validate() ) {
				$this->add_error( $Recurrence_Set->get_errors() );
			}
		}

		return apply_filters( 'em_recurrence_sets_validate', empty( $this->errors ), $this );
	}

	public function save () {
		if ( $this->get_event() ) {
			$this->event_id = $this->get_event()->event_id;
			foreach ( [ 'include', 'exclude' ] as $type ) {
				foreach ( $this->{$type} as $Recurrence_Set ) { /* @var Recurrence_Set $Recurrence_Set */
					$Recurrence_Set->event_id = $this->event_id; // in case of a new save
					if ( $this->reschedule && !$Recurrence_Set->has_reschedule() ) {
						$Recurrence_Set->set_reschedule(true);
					}
					if ( !$Recurrence_Set->save() ) {
						$this->add_error( $Recurrence_Set->get_errors() );
					}
				}
			}
		} else {
			$this->add_error( 'Recurrence sets do not have a linked Event to save from.' ); // this'd be a bug, therefore no translation
		}

		return apply_filters( 'em_recurrence_sets_save', empty( $this->errors ), $this );
	}


	/**
	 * Saves events and replaces old ones. Returns true if sucecssful or false if not.
	 * @return boolean
	 */
	public function save_recurrences () {
		// TODO - If a recurrence with higher priority is rescheduled and results in a deleted event that preivously collided/overrode with a lower prio recurrence set, that lower prio event recurrence isn't created unless the lower prio is also rescheduled in some way.
		$result = true;
		$this->recurrences = []; // remove all recurrence records, since we're loading or recreating in both cases
		// add negative recurrence sets
		foreach ( $this->exclude as $Recurrence_Set ) {
			$this->recurrences += $Recurrence_Set->get_recurrences();
		}
		// save each recurrence set, highest priority first, and keep adding them to recurrences array to build collision detection as we go
		foreach ( $this->include as $Recurrence_Set ) {
			if ( $Recurrence_Set->save_recurrences() === false ) {
				$this->add_error( $Recurrence_Set->get_errors() );
				$result = false;
			} else {
				$this->recurrences += $Recurrence_Set->recurrences;
			}
		}

		// get the range of dates from all events, times, default timezone, etc. and apply it to the event now that we've saved everything
		$EM_Event = $this->get_event();
		$dates = $this->get_datetime_range();
		$EM_Event->event_start_date = $dates['start_date'];
		$EM_Event->event_start_time = $dates['start_time'];
		$EM_Event->event_end_date = $dates['end_date'];
		$EM_Event->event_end_time = $dates['end_time'];
		$EM_Event->event_all_day = $dates['all_day'];

		// Save the event data we just modified here
		$event = $EM_Event->to_array( true );
		// update the database row directly, and the post meta (if there's a post_id)
		global $wpdb;
		$keys = [ 'event_start', 'event_end', 'event_start_date', 'event_start_time', 'event_end_date', 'event_end_time', 'event_all_day' ];
		$event_data = array_intersect_key( $event, array_flip( $keys));
		$wpdb->update( EM_EVENTS_TABLE, $event_data, ['event_id' => $this->event_id] );
		if ( $EM_Event->post_id ) {
			$event_data['event_start_local'] = $EM_Event->start()->getDateTime();
			$event_data['event_end_local'] = $EM_Event->end()->getDateTime();
			// update post meta
			foreach ( $event_data as $key => $value ) {
				update_post_meta( $EM_Event->post_id, '_' . $key, $value );
			}
		}
		// return final result
		return apply_filters( 'em_recurrence_sets_save_recurrences', $result, $this );
	}

	/**
	 * Deletes recurrences, bookings and anything associated with this set
	 * @return boolean
	 */
	public function delete() {
		foreach ( $this->include as $Recurrence_Set ) {
			$results[] = $Recurrence_Set->delete();
		}
		foreach( $this->exclude as $Recurrence_Set ) {
			$results[] = $Recurrence_Set->delete();
		}
		return !in_array( false, $results ?? [] );
	}

	/**
	 * Saves events and replaces old ones. Returns true if sucecssful or false if not.
	 * @return boolean
	 */
	public function delete_events () {
		$result = true;
		foreach ( $this->include as $Recurrence_Set ) {
			if ( !$Recurrence_Set->delete_events() ) {
				$this->add_error( $Recurrence_Set->get_errors() );
				$result = false;
			}
		}

		return apply_filters( 'em_recurrence_sets_delete_events', $result, $this );
	}

	// create a booking deletion function for all recurrences
	/**
	 * Deletes events and replaces old ones. Returns true if sucecssful or false if not.
	 * @return boolean
	 */
	public function delete_bookings () {
		$result = true;
		foreach ( $this->include as $Recurrence_Set ) {
			if ( !$Recurrence_Set->delete_bookings() ) {
				$this->add_error( $Recurrence_Set->get_errors() );
				$result = false;
			}
		}
		return apply_filters( 'em_recurrence_sets_delete_bookings', $result, $this );
	}

	/**
	 * Saves events and replaces old ones. Returns true if sucecssful or false if not.
	 * @return boolean
	 */
	public function set_status_events ( $status ) {
		$result = true;
		foreach ( $this->include as $Recurrence_Set ) {
			if ( !$Recurrence_Set->set_status_recurrences( $status ) ) {
				$this->add_error( $Recurrence_Set->get_errors() );
				$result = false;
			}
		}

		return apply_filters( 'em_recurrence_sets_delete_events', $result, $this );
	}

	/**
	 * Validates and returns the currently supplied reschedule action, if null or invalid the default action is returned.
	 * @param $action
	 *
	 * @return string
	 */
	public static function get_reschedule_action ( $action = null ) {
		$can_cancel = em_get_option( 'dbem_event_status_enabled' ) && array_key_exists( 0, EM_Event::get_active_statuses() );
		$reschedule_possibilities = $can_cancel ? [ 'delete', 'cancel' ] : [ 'delete' ];
		// cancel if not defined, delete if cancellations not possible
		return in_array( $action, $reschedule_possibilities ) ? $action : ( $can_cancel ? 'cancel' : 'delete' );
	}

	public static function add_js_vars() {
		$notices = [
			'deleteSet' => sprintf( __( 'When you save this %s, all recurrences of this set will be deleted. Would you like to proceed?', 'events-manager' ), __( 'event', 'events-manager' ) ),
			'rescheduleDatesPrimary' => __( 'By editing your primary recurrence set, you will change all subsequent default values of your other recurrences.', 'events-manager' ),
			'reschedule' => __( 'You have chosen to edit your recurrence date ranges. If you shorten the date range, any recurrences falling outside the new date range will be cancelled or deleted.', 'events-manager' ),
		];
		\EM\Scripts_and_Styles::add_js_var('recurrenceNotices', $notices);
	}

	/**
	 * Returns an API-friendly representation
	 * @return array
	 */
	public function to_api () {
		$api = [
			'sets' => [],
			'event_id' => $this->event_id,
		];
		foreach ( $this->include as $Recurrence_Set ) {
			$api['sets'][] = $Recurrence_Set->to_api();
		}
		// Excludes were dropped historically — surface them too (discriminated by `type`) so the write contract can round-trip them.
		foreach ( $this->exclude as $Recurrence_Set ) {
			$api['sets'][] = $Recurrence_Set->to_api();
		}

		return $api;
	}

	/**
	 * Gets first recurrence set in the array of sets, without resetting internal pointer.
	 * @return Recurrence_Set|false
	 */
	public function get_first () {
		return $this->default;
	}

	//Iterator Implementation
	#[\ReturnTypeWillChange]
	public function rewind () {
		reset( $this->include );
	}

	#[\ReturnTypeWillChange]
	/**
	 * @return Recurrence_Set
	 */
	public function current () {
		return current( $this->include );
	}

	#[\ReturnTypeWillChange]
	public function key () {
		return key( $this->include );
	}

	#[\ReturnTypeWillChange]
	/**
	 * @return Recurrence_Set|false
	 */
	public function next () {
		return next( $this->include );
	}

	#[\ReturnTypeWillChange]
	public function valid () {
		$key = key( $this->include );

		return ( $key !== null && $key !== false );
	}

	// ArrayAccess Implementation
	#[\ReturnTypeWillChange]
	/**
	 * @param $offset
	 * @param $value
	 *
	 * @return void
	 */
	public function offsetSet ( $offset, $value ) {
		if ( is_null( $offset ) ) {
			$this->include[] = $value;
		} else {
			$this->include[ $offset ] = $value;
		}
	}

	#[\ReturnTypeWillChange]
	public function offsetExists ( $offset ) {
		return isset( $this->include[ $offset ] );
	}

	#[\ReturnTypeWillChange]
	public function offsetUnset ( $offset ) {
		unset( $this->include[ $offset ] );
	}

	#[\ReturnTypeWillChange]
	/**
	 * @param $offset
	 *
	 * @return Recurrence_Set|null
	 */ public function offsetGet ( $offset ) {
		return isset( $this->include[ $offset ] ) ? $this->include[ $offset ] : null;
	}

	#[\ReturnTypeWillChange]
	public function count () {
		return count( $this->include );
	}
}