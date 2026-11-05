<?php
namespace EM\Recurrences;
use EM_DateTime, EM_DateTimeZone, EM\Event\Timeranges, EM\Event\Timerange;
use EM_Object, EM_Event, EM_Events, EM_Tickets, EM_Bookings, EM_ML;

// TODO - If an event is cancelled, just update the event
// TODO - If event date range is changed, reschedule tentatively (i.e. remove/delete non-existent dates) if approved via nonce or just add new dates before/after
// TODO - rescheduling primary recurrence will overlap a cancelled recurrence between the dates rid 71
// TODO - rename old filters (like em_event_save_events...)
// TODO - set Recurrence_Set::$reschedule_unchanged back to false

/**
 * @property int $id Alias for recurrence_set_id
 * @property int $order Alias for recurrence_order
 * @property string $type Alias for recurrence_type
 * @property int $interval Alias for recurrence_interval
 * @property string $freq Alias for recurrence_freq
 * @property string $byday Alias for recurrence_byday
 * @property int $byweekno Alias for recurrence_byweekno
 * @property array $dates Alias for recurrence_dates
 * @property int $duration Number of days each recurrence lasts, but will reference the main recurrence of this set if no value defined.
 * @property string $start_date Alias for recurrence_start_date, but will reference the main recurrence of this set if no value defined.
 * @property string $end_date Alias for recurrence_end_date, but will reference the main recurrence of this set if no value defined.
 * @property string $start_time Alias for recurrence_start_time, but will reference the main recurrence of this set if no value defined.
 * @property string $end_time Alias for recurrence_end_time, but will reference the main recurrence of this set if no value defined.
 * @property int $timezone Alias for recurrence_timezone, but will reference the main recurrence of this set if no value defined.
 * @property string $all_day Alias for recurrence_all_day, but will reference the main recurrence of this set if no value defined.
 * @property int $status Alias for recurrence_status, but will reference the main recurrence of this set if no value defined.
 * @property EM_DateTime $start Start EM_DateTime object for the recurrence which includes the start date, time and timezone.
 * @property EM_DateTime $end End EM_DateTime object for the recurrence which includes the start date, time and timezone.
 *
 * @property int $event_id The recurring event ID associated with this recurrence set.
 * @property int $recurrence_set_id Unique identifier for the recurrence set
 * @property int $recurrence_order Order of the recurrence instance within the set
 * @property string $recurrence_type Type of recurrence ('include', 'exclude', etc.)
 * @property int $recurrence_interval Interval between recurrences (e.g., every 2 weeks)
 * @property string $recurrence_freq Frequency unit of recurrence ('daily', 'weekly', 'monthly', 'yearly' or  'on')
 * @property string $recurrence_byday Specific days recurrence occurs on, assigned by day number and comma-delimited (e.g., '0,1,2' = 'Sun,Mon,Tue')
 * @property int $recurrence_byweekno Week number(s) within a month the recurrence occurs on when 'monthly'
 * @property array $recurrence_dates Specific dates included in recurrence set when freq is set to 'on'
 * @property int $recurrence_duration Number of days each recurrence instance lasts
 * @property string $recurrence_start_date Start date of recurrence series (YYYY-MM-DD)
 * @property string $recurrence_end_date End date of recurrence series (YYYY-MM-DD)
 * @property string $recurrence_start_time Start time of each recurrence instance (HH:MM:SS)
 * @property string $recurrence_end_time End time of each recurrence instance (HH:MM:SS)
 * @property int $recurrence_all_day Whether recurrence instances are all-day events ('0' or '1')
 * @property int $recurrence_timezone Timezone identifier used for recurrence instances
 * @property int $recurrence_status Status indicating if the recurrence is active or cancelled
 *
 * These are WIP and will potentially be added in future versions, these will revert back to the event values for the time being. For the time being we recommend directly referring the event.
 * @property int $rsvp_days Alias for EM_Event::recurrence_rsvp_days, but will reference the main recurrence of this set if no value defined.
 * @property int $recurrence_rsvp_days Number of days before/after each recurrence an RSVP is required, currently refers to EM_Event::recurrence_rsvp_days
 */
class Recurrence_Set extends EM_Object {

	// Properties corresponding to the wp_em_event_recurrences table columns
	protected $recurrence_set_id;
	protected $recurrence_order;
	protected $event_id;
	protected $recurrence_type = 'include';
	protected $recurrence_interval;
	protected $recurrence_freq = 'daily';
	protected $recurrence_byday;
	protected $recurrence_byweekno;
	/**
	 * @var int Number of days each recurrence lasts
	 */
	protected $recurrence_duration;
	protected $recurrence_dates = [];
	protected $recurrence_start_date;
	protected $recurrence_end_date;
	protected $recurrence_start_time;
	protected $recurrence_end_time;
	protected $recurrence_all_day;
	protected $recurrence_timezone;
	/*
	protected $recurrence_rsvp_days;
	protected $recurrence_rsvp_time;
	*/
	protected $recurrence_status;
	/**
	 * @var int Previous status of recurrence in event of any change made.
	 */
	protected $recurrence_previous_status;

	/**
	 * EM_DateTime of start date/time in local timezone.
	 * @var EM_DateTime
	 */
	protected $start;
	/**
	 * EM_DateTime of end date/time in local timezone.
	 * @var EM_DateTime
	 */
	protected $end;

	// TODO 1.0 add reschedule flag to individual recurrences (related to 1.2)
	// TODO 1.1 rescheduling should be limited only to 'on' events and weekday choosing events, or changing the date range which may delete or add events, but not recreate completely
	// TODO 1.1.1 any setting that can delete events will need to warn users of the action before setting the flag to reschedule
	// TODO 1.1.2 maybe provide setting to cancel instead?
	// TODO - DONE - 1.2 add forced date ranges/times etc. to events if recurring based off main recurrence
	// TODO 1.3 sort out RSVP days/times which requires double-checking if this is recurring/repeating in get_post where we process booking settings
	// TODO 2.x Add Luxon JS and use that to properly determine estimates and possibly recurrences for fast front-end editing.

	/**
	 * @var string The event type to save recurrences as.
	 */
	public $event_type = 'recurrence';
	/**
	 * If set to true, recurring events will delete and recreate recurrences when saved.
	 * @var boolean
	 */
	public $reschedule = [
		'general' => false,
		'pattern' => false,
		'dates' => false,
	];
	/**
	 * Action to take if rescheduling a recurrence set. Defaults to cancel, but re-evaluated if cancelling is possible during get_post()
	 * @var string
	 */
	public $reschedule_action = 'cancel';
	/**
	 * @var bool Force rescheduling even if recurrences are unchanged, mainly for debugging or edge use cases, leave set to false.
	 */
	public static $reschedule_unchanged = false;
	/**
	 * Flag to indicate this set of recurrences should be deleted, including all associated events.
	 *
	 * @var boolean
	 */
	public $delete = false;

	/**
	 * @var array recurrences stored by local date, then local start time, then an array representation of an event record
	 */
	public $recurrences;

	/**
	 * @var Timeranges
	 */
	protected $timeranges;

	/**
	 * The parent recurrence sets this set belongs to. Used for reference such as when creating events, to look for duplicates or negations.
	 * @var Recurrence_Sets
	 */
	public $parent;
	/**
	 * If set, when saving tickets, all overriding settings of a recurrence ticket will be wiped out, and non-existent tickets will be recreated.
	 *
	 * This will not delete any recurrence-specific tickets that may have been created.
	 *
	 * @var bool
	 */
	public $regenerate_tickets = false;

	/**
	 * @var array Field definitions mapping to database columns.
	 */
	public $fields = [
		'recurrence_set_id'    => ['type' => '%d', 'required' => true],
		'recurrence_order'    => ['type' => '%d', 'default' => 0],
		'event_id'             => ['type' => '%d', 'required' => true],
		'recurrence_type'      => ['type' => '%s', 'default' => 'include'],
		'recurrence_interval'  => ['type' => '%d', 'default' => 0],
		'recurrence_freq'      => ['type' => '%s', 'default' => ''],
		'recurrence_byday'     => ['type' => '%s', 'default' => ''],
		'recurrence_byweekno'  => ['type' => '%d', 'default' => 0],
		'recurrence_duration'  => ['type' => '%d', 'default' => ''],
		'recurrence_dates'      => ['type' => '%s', 'default' => ''],
		'recurrence_start_date'=> ['type' => '%s', 'default' => ''],
		'recurrence_end_date'  => ['type' => '%s', 'default' => ''],
		'recurrence_start_time'=> ['type' => '%s', 'default' => ''],
		'recurrence_end_time'  => ['type' => '%s', 'default' => ''],
		'recurrence_all_day'   => ['type' => '%d', 'default' => 0],
		'recurrence_timezone' => ['type'=>'%s', 'null'=>true],
		'recurrence_status'    => ['type'=>'%d', 'null'=>true ],
		//'recurrence_rsvp_days' => ['type' => '%d', 'default' => 0],
		//'recurrence_rsvp_time' => ['type' => '%s'],
	];

	/**
	 * Field shortcuts for external API references.
	 */
	public static $field_shortcuts = [
		'id' => 'recurrence_set_id',
		'order' => 'recurrence_order',
		'type' => 'recurrence_type',
		'interval' => 'recurrence_interval',
		'freq' => 'recurrence_freq',
		'byday' => 'recurrence_byday',
		'byweekno' => 'recurrence_byweekno',
		'duration' => 'recurrence_duration',
		'dates' => 'recurrence_dates',
		'start_date' => 'recurrence_start_date',
		'end_date' => 'recurrence_end_date',
		'start_time' => 'recurrence_start_time',
		'end_time' => 'recurrence_end_time',
		'all_day' => 'recurrence_all_day',
		'timezone' => 'recurrence_timezone',
		'status' => 'recurrence_status',
		//'rsvp_days' => 'recurrence_rsvp_days',
		//'rsvp_time' => 'recurrence_rsvp_time',
		'previous_status' => 'recurernce_previous_status',
	];

	/**
	 * @var EM_Event The event this recurrence set belongs to.
	 */
	public $event;
	/**
	 * @var bool Recurrence was just added if true
	 */
	public $just_added = false;
	/**
	 * @var bool Debugging flag for testing/development, may eventually delete so devs should not rely on it long-term.
	 */
	public $debug;
	/**
	 * Map of modified events upon saving, categorized by action taken for later reference.
	 *
	 * All array items in 'events' are keyed by event_id, added and updated indexes contain array of event data insterted into the events table, cancelled/deleted contain the EM_Event objects
	 *
	 * @var array{
	 *     events: array{
	 *         added: array<int, array>,
	 *         updated: array<int, array>,
	 *         cancelled: array<int, EM_Event>,
	 *         deleted: array<int, EM_Event>
	 *     }
	 * }
	 */
	public $save_status = [
		'events' => [
			'added' => [], // int event_id => mixed[] event_data
			'updated' => [], // int event_id => mixed[] event_data
			'cancelled' => [], // int event_id => EM_Event[]
			'deleted' => [], // int event_id => EM_Event[]
		],
	];

	/**
	 * Constructor: Initializes the recurrence set, loading data if an ID is provided.
	 *
	 * @param int|EM_Event $data Either a recurrence_set_id to fetch from DB or an EM_Event object to extract recurrence sets from.
	 * @param string $type The type of recurrence this is, defaults to 'include'
	 */
	public function __construct ( $data = null, $type = null ) {

		if ( is_numeric( $data ) ) {
			$this->recurrence_set_id = absint( $data );
		} elseif ( $data instanceof EM_Event ) {
			$EM_Event = $data;
			if ( $EM_Event->is_recurring( true ) ) {
				$this->recurrence_set_id = $EM_Event->recurrence_set_id;
				$this->event = $EM_Event; // add reference to EM_Event already
			} elseif ( $EM_Event->is_recurrence( true ) ) {
				$this->recurrence_set_id = $EM_Event->recurrence_set_id;
			}
		} elseif ( is_array($data) ) {
			$this->to_object( $data );
		}
		if ( !empty($this->recurrence_set_id) ) {
			global $wpdb;
			$table = EM_EVENT_RECURRENCES_TABLE;
			$sql = $wpdb->prepare( "SELECT * FROM $table WHERE recurrence_set_id = %d", $this->recurrence_set_id );
			$result = $wpdb->get_row( $sql, ARRAY_A );
			if ( $result ) {
				$this->to_object( $result );
			}
		}
		if ( !is_array($this->recurrence_dates) ) {
			$this->recurrence_dates = explode(',', $this->recurrence_dates ?? '');
		}
		if ( $this->recurrence_set_id ) $this->recurrence_set_id = absint($this->recurrence_set_id);
		$this->debug = defined('EM_DEBUG') && EM_DEBUG;
	}

	public function __get( $prop ) {
		$value = null;
		// we allow shortnamed properties to lookup default property values if not defined from the main recurrence set belonging to the associated event
		$overridable_options = ['start_date', 'end_date', 'start_time', 'end_time', 'all_day', 'duration', 'timezone', 'status'];
		if ( in_array( $prop, $overridable_options ) && !empty( static::$field_shortcuts[$prop] ) ) {
			$property = static::$field_shortcuts[$prop];
			if ( $this->{$property} === null ) {
				if ( $this->recurrence_freq == 'on' && in_array($prop, ['start_date', 'end_date']) ) {
					// we are dealing with On frequency, which is a definitive set of dates, cannot be overriden by a parent by definition
					// get the first and last date, and we're done
					$value = $prop === 'start_date' ? $this->recurrence_dates[0] : $this->recurrence_dates[ count($this->recurrence_dates ?? ['null']) - 1 ] ?? null;
				} else {
					if ( $this->recurrence_type === 'include' ) {
						if ( $this->recurrence_order == 1 ) {
							// get default prop value from master recurrence set if not defined in this recurrence set
							$value = $this->{$property};
						} else {
							$value = $this->get_event()->get_recurrence_set()->{$property};
						}
						if ( $value === null && in_array($prop, ['start_date', 'end_date', 'start_time', 'end_time', 'all_day', 'timezone']) ) {
							$value = $this->get_event()->{'event_'.$prop};
						}
					} else {
						// exclusion patterns will default to the whole range of dates, which is stored at an event level after get_post()
						if ( in_array($prop, ['start_date', 'end_date', 'start_time', 'end_time', 'all_day', 'timezone']) ) {
							$value = $this->get_event()->{'event_'.$prop};
						} else {
							$value = $this->get_event()->get_recurrence_set()->{$prop};
						}
					}
				}
			} else {
				$value = $this->{$property};
			}
		} elseif ( !empty($this->fields[$prop]) ) {
			// allow read to protected values
			if ( $this->recurrence_freq == 'on' && in_array($prop, ['recurrence_start_date', 'recurrence_end_date']) && $this->{$prop} === null ) {
				// we are dealing with On frequency, which is a definitive set of dates, if not defined we default to first/last dates of this set
				$value = $prop === 'recurrence_start_date' ? $this->recurrence_dates[0] : $this->recurrence_dates[ count($this->recurrence_dates ?? ['null']) - 1 ] ?? null;
			} else {
				$value = $this->{$prop};
			}
		} elseif ( in_array( $prop, ['rsvp_days', 'recurrence_rsvp_days'] ) ) {
			// for now, in future we could let recurrence sets have their own rsvp settings
			return $this->get_event()->recurrence_rsvp_days;
		}
		if( $prop == 'start' ) return $this->start();
		if( $prop == 'end' ) return $this->end();
		return $value === null ? parent::__get( $prop ) : $value;
	}

	public function __set ( $prop, $val ) {
		// allow direct write to protected values
		if ( !empty($this->fields[$prop]) ) {
			$this->{$prop} = $val;
		}
		$datetime_properties = ['start_date', 'end_date', 'start_time', 'end_time', 'all_day'];
		if ( in_array($prop, $datetime_properties ) || in_array('recurrence_' . $prop, $datetime_properties) ) {
			$this->start = $this->end = null; // reset datetime objects
		}
		parent::__set( $prop, $val );
	}

	public function __isset( $prop ) {
		$overridable_options = ['start_date', 'end_date', 'start_time', 'end_time', 'all_day', 'duration', 'timezone', 'status'];
		if ( in_array( $prop, $overridable_options ) ) {
			$value = $this->{$prop};
			return !empty( $value );
		} elseif ( in_array( $prop, ['rsvp_days', 'recurrence_rsvp_days'] ) ) {
			return !empty( $this->get_event()->recurrence_rsvp_days );
		}
		return parent::__isset( $prop );
	}

	/**
	 * Checks if recurrence is set to be rescheduled upon saving, which will resolve to truthy automatically if this is a new recurrence set.
	 * Additional checks for specific rescheduling types can be passed as $type, such as 'pattern' which allows the recurrence pattern or 'dates' for the range of dates within recurrences occur.
	 *
	 * @param $type
	 * @return bool
	 */
	public function has_reschedule( $type = null ) {
		if ( $this->recurrence_set_id ) {
			if ( $type ) {
				// check if specific type is set to reschedule, truthy value accepted
				$reschedule = $this->reschedule[ $type ] ?? false;
			} else {
				// returns true if any truthy values are in array, false otherwise
				$reschedule = (bool) array_filter( $this->reschedule );
			}
		} else {
			$reschedule = true;
		}
		return $reschedule;
	}


	public function set_reschedule ( $type_or_flag, $value = null ) {
		if ( is_bool( $type_or_flag ) ) {
			// If a boolean is passed as the first parameter, set all keys to true
			foreach ( $this->reschedule as $key => $val ) {
				$this->reschedule[ $key ] = $type_or_flag;
			}
		} elseif ( is_string( $type_or_flag ) && $value !== null ) {
			// If a key and value are provided, set the specific key
			$this->reschedule[ $type_or_flag ] = (bool) $value;
		}
	}

	/**
	 * Returns an EM_DateTime object of the event start date/time in local timezone of event.
	 * @param bool $utc_timezone Returns EM_DateTime with UTC timezone if set to true, returns local timezone by default.
	 * @return EM_DateTime
	 * @see EM_Event::get_datetime()
	 */
	public function start( $utc_timezone = false ){
		return apply_filters('em_recurrence_start', $this->get_datetime('start', $utc_timezone), $this);
	}

	/**
	 * Returns an EM_DateTime object of the event end date/time in local timezone of event
	 * @param bool $utc_timezone Returns EM_DateTime with UTC timezone if set to true, returns local timezone by default.
	 * @return EM_DateTime
	 * @see EM_Event::get_datetime()
	 */
	public function end( $utc_timezone = false ){
		return apply_filters('em_recurrence_end', $this->get_datetime('end', $utc_timezone), $this);
	}

	/**
	 * Generates an EM_DateTime for the the start/end date/times of the event in local timezone, as well as setting a valid flag if dates and times are valid.
	 * The generated object will be derived from the local date and time values. If no date exists, then 1970-01-01 will be used, and 00:00:00 if no valid time exists.
	 * If date is invalid but time is, only use local timezones since a UTC conversion will provide inaccurate timezone differences due to unknown DST status.	 *
	 * @param string $when 'start' or 'end' date/time
	 * @param bool $utc_timezone Returns EM_DateTime with UTC timezone if set to true, returns local timezone by default. Do not use if EM_DateTime->valid is false.
	 * @return EM_DateTime
	 */
	public function get_datetime( $when = 'start', $utc_timezone = false ){
		if( $when != 'start' && $when != 'end') return new EM_DateTime(); //currently only start/end dates are relevant
		//Initialize EM_DateTime if not already initialized, or if previously initialized object is invalid (e.g. draft event with invalid dates being resubmitted)
		$when_date = $when.'_date';
		$when_time = $when.'_time';
		//we take a pass at creating a new datetime object if it's empty, invalid or a different time to the current start date
		if( empty($this->{$when}) || !$this->{$when}->valid ){
			$when_utc = 'event_'.$when;
			$date_regex = '/^\d{4}-\d{2}-\d{2}$/';
			$valid_time = !empty($this->{$when_time}) && preg_match('/^\d{2}:\d{2}:\d{2}$/', $this->{$when_time});
			//If there now is a valid date string for local or UTC timezones, create a new object which will set the valid flag to true by default
			if( !empty($this->{$when_date}) && preg_match($date_regex, $this->{$when_date}) && $valid_time ){
				$EM_DateTime = new EM_DateTime(trim($this->{$when_date}.' '.$this->{$when_time}), $this->timezone);
				if( $EM_DateTime->valid && empty($this->{$when_utc}) ){
					$EM_DateTime->setTimezone('UTC');
					$this->{$when_utc} = $EM_DateTime->format();
				}
			}
			//If we didn't attempt to create a date above, or it didn't work out, create an invalid date based on time.
			if( empty($EM_DateTime) || !$EM_DateTime->valid ){
				//create a new datetime just with the time (if set), fake date and set the valid flag to false
				$time = $valid_time ? $this->{$when_time} : '00:00:00';
				$EM_DateTime = new EM_DateTime('1970-01-01 '.$time, $this->timezone);
				$EM_DateTime->valid = false;
			}
			//set new datetime
			$this->{$when} = $EM_DateTime;
		}else{
			/* @var EM_DateTime $EM_DateTime */
			$EM_DateTime = $this->{$when};
		}
		//Set to UTC timezone if requested, local by default
		$tz = $utc_timezone ? 'UTC' : $this->timezone;
		$EM_DateTime->setTimezone($tz);
		return $EM_DateTime;
	}

	/**
	 * @return Timeranges
	 */
	public function get_timeranges() {
		if ( empty( $this->timeranges ) ) {
			$this->timeranges = new Timeranges( $this->recurrence_set_id ? 'recurrence_set_' . $this->recurrence_set_id : null, $this->get_event() );
			$this->timeranges->load_timeranges();
			// change start/end times so they match recurrence set rather than event
			if ( $this->recurrence_set_id ) {
				if ( $this->recurrence_start_time === null ) {
					// This must be a non-primary recurrence set, so we can copy the timeranges from the primary recurrence set
					$this->timeranges = $this->get_event()->get_recurrence_set()->get_timeranges();
				}
			}
		}
		// double-check we have a group id set in case we just saved this recurrence set
		if ( $this->timeranges->group_id === null && $this->recurrence_set_id ) {
			$this->timeranges->set_group_id( 'recurrence_set_' . $this->recurrence_set_id );
		}
		return $this->timeranges;
	}

	/**
	 * Returns a multi-dimensional array of recurrences, indexed by local start date, start_time
	 *
	 * If a recurrence set is exclusive, then each array value will be an array containing dates and times each exclusion covers.
	 *
	 * If inclusive each array value will be an $event array item.
	 *
	 * @return array
	 */
	public function get_recurrences( $event_id = null) {
		global $wpdb;
		if ( $this->recurrences === null ) {
			$this->recurrences = [];
			if ( $this->recurrence_type == 'exclude' ) {
				// populate timestamps to recurrences
				foreach ( $this->get_recurrence_days() as $day ) {
					$event = [];
					$start = EM_DateTime::create( $day, $this->timezone )->setTimeString( $this->start_time );
					$end = EM_DateTime::create( $day, $this->timezone )->setTimeString( $this->end_time );
					// start timestamp
					$event['start'] = $start->getTimestamp(); // adjust time for start date
					$event['end'] = $end->getTimestamp(); // adjust time for start date
					if ( $this->debug ) {
						$event['start_date'] = $start->format( '(D) F d, Y H:i:s' );
						$event['end_date'] = $end->format( '(D) F d, Y H:i:s' );
						$event['set_id'] = $this->recurrence_set_id;
					}
					$this->recurrences[ $event['start'] ] = $event;
				}
			} else {
				// if an event was already created, then even prioritized rescheduled recurrences with newly created events won't collide with previously created events with less priority
				$sql = $wpdb->prepare('SELECT event_id, event_start, event_end, post_id FROM ' . EM_EVENTS_TABLE . ' WHERE recurrence_set_id = %d', $this->recurrence_set_id);
				$results = $wpdb->get_results( $sql, ARRAY_A );
				foreach ( $results as $event ) {
					$event_data = $this->get_event_recurrence_data( $event );
					$this->recurrences[ $event_data['start'] ] = $event_data;
					if ( $event_id === $event_data['event_id'] ) {
						return $event_data;
					}
				}
			}
		}
		if ( $this->recurrence_type === 'include' && $event_id ) {
			// get the array value with event_id = $event_id
			foreach ( $this->recurrences as $recurrence ) {
				if ( isset( $recurrence['event_id'] ) && $recurrence['event_id'] == $event_id ) {
					return $recurrence;
				}
			}
		}
		return $this->recurrences;
	}

	/**
	 * Helper function that returns an array of post IDs keyed by the start timestamp of that event.
	 *
	 * Note that for recurrences without their own posts, i.e. regular recurrences, not repeated events (as of EM 7.0), no post IDs will be supplied
	 *
	 * @return array
	 */
	public function get_post_ids() {
		$recurrences = $this->get_recurrences();
		$ids = [];
		foreach ( $recurrences as $recurrence ) {
			if ( isset( $recurrence['post_id'] ) ) {
				$ids[ $recurrence['start'] ] = $recurrence['post_id'];
			}
		}
		return $ids;
	}

	public function get_event_recurrence_data( $event ) {
		$start = new EM_DateTime( $event['event_start'], 'UTC' ); // event_start/end are already in UTC time
		$end = new EM_DateTime( $event['event_end'], 'UTC' );
		$event_data = [
			'start' => $start->getTimestamp(),
			'end' => $end->getTimestamp(),
		];
		if ( !empty( $event['event_id'] ) ) {
			$event_data['event_id'] = $event['event_id'];
		}
		if ( !empty( $event['post_id'] ) ) {
			$event_data['post_id'] = $event['post_id'];
		}
		if ( $this->debug ) {
			$event_data['start_date'] = $start->format( '(D) F d, Y H:i:s' );
			$event_data['end_date'] = $end->format( '(D) F d, Y H:i:s' );
			$event_data['set_id'] = $this->recurrence_set_id;
		}
		return $event_data;
	}

	/**
	 * Returns a string representation of this recurrence. Will return false if not a recurrence
	 * @return string
	 */
	function get_recurrence_description() {
		$EM_Event = $this->get_event();
		$output = '';
		if ( $EM_Event ) {
			$weekdays_name = array( translate('Sunday'),translate('Monday'),translate('Tuesday'),translate('Wednesday'),translate('Thursday'),translate('Friday'),translate('Saturday'));
			$monthweek_name = array('1' => __('the first %s of the month', 'events-manager'),'2' => __('the second %s of the month', 'events-manager'), '3' => __('the third %s of the month', 'events-manager'), '4' => __('the fourth %s of the month', 'events-manager'), '5' => __('the fifth %s of the month', 'events-manager'), '-1' => __('the last %s of the month', 'events-manager'));
			if ($this->freq == 'daily')  {
				$freq_desc =__('everyday', 'events-manager');
				if ($this->interval > 1 ) {
					$freq_desc = sprintf (__("every %s days", 'events-manager'), $this->interval);
				}
			}elseif ($this->freq == 'weekly')  {
				$weekday_array = explode(",", $this->byday);
				$natural_days = array();
				foreach($weekday_array as $day){
					$natural_days[] = $weekdays_name[ $day ];
				}
				$output .= implode(", ", $natural_days);
				$freq_desc = " " . __("every week", 'events-manager');
				if ($this->interval > 1 ) {
					$freq_desc = " ".sprintf (__("every %s weeks", 'events-manager'), $this->interval);
				}

			}elseif ($this->freq == 'monthly')  {
				$weekday_array = explode(",", $this->byday);
				$natural_days = array();
				foreach($weekday_array as $day){
					if( is_numeric($day) ){
						$natural_days[] = $weekdays_name[ $day ];
					}
				}
				$freq_desc = sprintf (($monthweek_name[$this->byweekno]), implode(" and ", $natural_days));
				if ($this->interval > 1 ) {
					$freq_desc .= ", ".sprintf (__("every %s months",'events-manager'), $this->interval);
				}
			}elseif ($this->freq == 'yearly')  {
				$freq_desc = __("every year", 'events-manager');
				if ($this->interval > 1 ) {
					$freq_desc .= sprintf (__("every %s years",'events-manager'), $this->interval);
				}
			}elseif ($this->freq == 'on')  {
				$freq_desc = __("multiple dates", 'events-manager');
			}else{
				$freq_desc = "[ERROR: corrupted database record]";
			}
			$output .= $freq_desc;
		}
		return  $output;
	}

	/**
	 * Retrieves an EM\Recurrences\Recurrence_Set object by ID, using cache.
	 *
	 * @param int|Recurrence_Set $id
	 *
	 * @return Recurrence_Set
	 */
	public static function get ( $id ) {
		if ( is_object( $id ) && get_class( $id ) == 'Recurrence_Set' ) {
			return apply_filters( 'em_get_recurrence_set', $id );
		} elseif ( !defined( 'EM_CACHE' ) || EM_CACHE ) {
			$recurrence_set_id = is_numeric( $id ) ? absint( $id ) : false;
			if ( $recurrence_set_id ) {
				$recurrence_set = wp_cache_get( $recurrence_set_id, 'em_recurrence_sets' );
				if ( is_object( $recurrence_set ) && !empty( $recurrence_set->recurrence_set_id ) ) {
					return apply_filters( 'em_get_recurrence_set', $recurrence_set );
				}
			}
		}

		return apply_filters( 'em_get_recurrence_set', new Recurrence_Set( $id ) );
	}

	/**
	 * Retrieves the associated recurring event.
	 *
	 * @return EM_Event
	 */
	public function get_event () {
		if ( !empty( $this->event ) && is_object( $this->event ) ) {
			return $this->event;
		}
		if ( !empty( $this->event_id ) ) {
			$this->event = em_get_event( $this->event_id );
			return $this->event;
		}

		return new EM_Event;
	}

	/**
	 * @param array $_DATA  contained subsection of $_REQUEST['recurrences'] array of this recurrence set data
	 *
	 * @return void
	 */
	public function get_post( $_DATA ) {
		// Check rescheduling options
		if ( $this->recurrence_set_id ) {
			$this->reschedule_action = Recurrence_Sets::get_reschedule_action( $_DATA['reschedule']['action'] ?? null ); // excludes will likely hit a default, since they're global actions handled upstream
			if ( !empty($_DATA['reschedule']['pattern']) ) {
				$this->reschedule['pattern'] = (bool) wp_verify_nonce( $_DATA['reschedule']['pattern'], 'reschedule-pattern-'. $this->recurrence_set_id );
			}
			if ( !empty($_DATA['reschedule']['dates']) ) {
				$this->reschedule['dates'] = (bool) wp_verify_nonce( $_DATA['reschedule']['dates'], 'reschedule-dates-'. $this->recurrence_set_id );
			}
			if ( !empty($_DATA['reschedule']['times']) ) {
				$this->reschedule['times'] = (bool) wp_verify_nonce( $_DATA['reschedule']['times'], 'reschedule-times-'. $this->recurrence_set_id );
				$this->get_timeranges()->allow_edit = $this->reschedule['times'];
				$this->get_timeranges()->delete_action = $this->reschedule_action;
			}
		} else {
			// we 'reschedule' i.e. create a new recurrence set
			$this->reschedule['pattern'] = true;
			$this->reschedule['dates'] = true;
			$this->reschedule['times'] = true;
		}

		// certain things can only be saved first-time around
		if ( !$this->recurrence_set_id ) {
			$this->recurrence_type = ( !empty($_DATA['recurrence_type']) && in_array($_DATA['recurrence_type'], ['include','exclude']) ) ? $_DATA['recurrence_type']: $this->recurrence_type;
		}
		// TODO - add nonces and checks to exclude recurrences because if we check the global one the disabled fields aren't disabled and values arnen't passed on properly.
		if ( $this->has_reschedule('pattern') ) {
			// determine frequency and reset pattern-specific values if different
			$recurrence_freq = ( !empty($_DATA['recurrence_freq']) && in_array($_DATA['recurrence_freq'], ['daily','weekly','monthly','yearly','on']) ) ? $_DATA['recurrence_freq']:$this->recurrence_freq;
			if ( $this->recurrence_freq !== $recurrence_freq ) {
				// set all things to null if frequency is different
				$this->recurrence_interval = null;
				$this->recurrence_byday = null;
				$this->recurrence_byweekno = null;
				$this->recurrence_dates = null;
			}
			$this->recurrence_freq = $recurrence_freq;
			if ( $this->recurrence_freq === 'on' ) {
				$this->recurrence_dates = ( !empty($_DATA['recurrence_dates']) && preg_match('/^\d{4}-\d{2}-\d{2}( ?, ?\d{4}-\d{2}-\d{2})*$/', $_DATA['recurrence_dates']) ) ? explode(',', str_replace(' ', '', $_DATA['recurrence_dates'])): null;
				sort($this->recurrence_dates); // so they are sorted in ascending order
			} else {
				// interval is only saved/applicable if frequency is not 'on' i.e. not on specific user-defined dates
				$this->recurrence_interval = ( !empty($_DATA['recurrence_interval']) && is_numeric($_DATA['recurrence_interval']) ) ? absint($_DATA['recurrence_interval']) : 1;
				// check frequency type and save the specific pattern for the frequency
				if( $this->recurrence_freq == 'weekly' ) {
					// validate/save days of week per week to store
					if ( !empty($_DATA['recurrence_bydays']) && self::array_is_numeric($_DATA['recurrence_bydays']) ) {
						$this->recurrence_byday = str_replace(' ', '', implode( ",", $_DATA['recurrence_bydays'] ));
					}
				} else if( $this->recurrence_freq == 'monthly' ){
					// only new recurrence sets can save monthly byday, daily/yearly already dealt with by interval
					$this->recurrence_byday = isset($_DATA['recurrence_byday']) ? absint($_DATA['recurrence_byday']) : null;
					$this->recurrence_byweekno = !empty($_DATA['recurrence_byweekno']) ? (int) $_DATA['recurrence_byweekno'] : null;
				}
			}
		}
		// advanced reschedulable date range
		if ( $this->has_reschedule('dates') ) {
			if ( $this->recurrence_freq === 'on' ) {
				// save start and end dates for this set
				$this->recurrence_start_date = is_array($this->recurrence_dates) ? $this->recurrence_dates[0] : null;
				$this->recurrence_end_date = is_array($this->recurrence_dates) ? end($this->recurrence_dates) : null;
			} else {
				$this->recurrence_start_date = ( !empty($_DATA['recurrence_start_date']) && preg_match('/^\d{4}-\d{2}-\d{2}$/', $_DATA['recurrence_start_date']) ) ? $_DATA['recurrence_start_date']:null;
				$this->recurrence_end_date = ( !empty($_DATA['recurrence_end_date']) && preg_match('/^\d{4}-\d{2}-\d{2}$/', $_DATA['recurrence_end_date']) ) ? $_DATA['recurrence_end_date']:null;
			}
		}
		// order
		$this->recurrence_order = ( !empty($_DATA['recurrence_order']) && is_numeric($_DATA['recurrence_order']) ) ? (int) $_DATA['recurrence_order']:0;
		// duration in days of each event
		$old_duration = $this->recurrence_duration;
		$new_duration = ( !empty($_DATA['recurrence_duration']) && is_numeric($_DATA['recurrence_duration']) && $this->recurrence_type === 'include' ) ? (int) $_DATA['recurrence_duration']:null;
		$this->recurrence_duration = $new_duration;
		// On an existing recurrence set, a duration change re-derives each parent event's end date in update_recurrence() but does NOT trigger timeslot regeneration on its own — the timeslot save path is gated on reschedule['times']/allow_edit, neither of which the duration field flips. Force a times-reschedule when the value actually changed so the existing update_recurrence() path rewrites stale timeslot_end values that were anchored to the previous duration.
		if ( $this->recurrence_set_id && (int) $old_duration !== (int) $new_duration ) {
			$this->reschedule['times'] = true;
			$this->get_timeranges()->allow_edit = true;
		}
		// Sort out event times
		if ( $this->has_reschedule('times') ) {
			if ( !empty($_DATA['override_time']) || $this->is_primary() ) {
				if ( !empty($_DATA['timeranges']) && $this->get_timeranges()->get_post( $_DATA['timeranges'] ) ) {
					$this->recurrence_all_day = $this->get_timeranges()->is_all_day();
					if ( $this->recurrence_all_day ) {
						$this->recurrence_start_time = '00:00:00';
						$this->recurrence_end_time = '23:59:59';
					} else {
						$this->recurrence_start_time = $this->get_timeranges()->get_time_start();
						$this->recurrence_end_time = $this->get_timeranges()->get_time_end();
					}
				}
			} else {
				$this->recurrence_all_day = null;
				$this->recurrence_start_time = null;
				$this->recurrence_end_time = null;
			}
		}
		//Set Event Timezone to supplied value or alternatively use blog timezone value by default.
		$this->recurrence_timezone = null;
		if( !empty($_DATA['recurrence_timezone']) ){
			$this->recurrence_timezone = EM_DateTimeZone::create($_DATA['recurrence_timezone'])->getName();
		} elseif( $this->is_primary() ){ //if timezone was already set but not supplied, we don't change it
			$this->recurrence_timezone = EM_DateTimeZone::create()->getName();
		}
		// set status, if supplied
		if ( isset($_DATA['recurrence_status']) && array_key_exists( $_DATA['recurrence_status'], EM_Event::get_active_statuses() ) ) {
			$this->recurrence_previous_status = $this->recurrence_status; // store previous status if not null, otherwise it'll revert to parent if we check ->previous_status
			$this->recurrence_status = absint($_DATA['recurrence_status']);
		} else {
			$this->recurrence_status = 1;
		}
		$this->start = $this->end = null; // reset datetime objects

		//here we do a comparison between new and old event data to see if we are to reschedule events or recreate bookings
		if( $this->recurrence_set_id !== null ){ //only needed if this is an existing recurrence set needing rescheduling/recreation
			if ( $this->has_reschedule() && !static::$reschedule_unchanged ) {
				$this->reschedule['general'] = true; // so that general rescheduling is always true, but maybe not specifics
				$Recurrence_Set = new Recurrence_Set( $this->recurrence_set_id );
				//first check event times
				$reschedule_flags = array(
					'pattern' => ['recurrence_freq', 'recurrence_type', 'recurrence_byday', 'recurrence_byweekno', 'recurrence_interval', 'recurrence_dates'],
					'dates' => ['recurrence_start_date', 'recurrence_end_date']
				);
				//check previously saved event info compared to current recurrence info to see if we actually do need to reschedule
				foreach ( $reschedule_flags as $type => $properties ) {
					$this->reschedule[$type] = false; // we don't reschedule unless something/anything has changed
					foreach ( $properties as $k ) {
						if( $this->{$k} != $Recurrence_Set->{$k} ){
							$this->reschedule[$type] = true; //something changed, so we reschedule
							break;
						}
					}
				}
			}
		} else {
			$this->set_reschedule( true );
		}
		return apply_filters( 'em_recurrence_set_get_post', empty($this->errors), $this);
	}

	public function validate() {
		if( $this->recurrence_freq == 'weekly' && !preg_match('/^[0-9](,[0-9])*$/',$this->recurrence_byday) ){
			$this->add_error( __( 'Please specify what days of the week this event should occur on.', 'events-manager'));
		}
		// check the start/end dates and times match up
		if ( $this->recurrence_start_date && $this->recurrence_end_date ) {
			if ( strtotime( $this->recurrence_start_date ) > strtotime( $this->recurrence_end_date ) ){
				$this->add_error( sprintf( __('Recurrence %s cannot start after they end.','events-manager'), __('dates', 'events-manager') ) );
			}
		} elseif ( $this->is_primary() && $this->recurrence_order === 1 ) {
			// main recurrence set needs values
			$this->add_error( sprintf( __('Main recurrence set %s are required.','events-manager'), __('dates', 'events-manager') ) );
		}
		// check the start/end dates and times match up
		if ( !$this->get_timeranges()->validate() ) {
			$this->add_error( $this->get_timeranges()->errors );
		}
		if ( $this->recurrence_start_time && $this->recurrence_end_time ) {
			if ( $this->recurrence_duration === 0 && strtotime( '2000-01-01 ' . $this->recurrence_start_time ) > strtotime( '2000-01-01 ' . $this->recurrence_end_time ) ){
				$this->add_error( sprintf( __('Recurrence %s cannot start after they end.','events-manager'), __('times', 'events-manager') ) );
			}
		} elseif ( $this->is_primary() ) {
			// main recurrence set needs values
			$this->add_error( sprintf( __('Main recurrence set %s are required.','events-manager'), __('times', 'events-manager') ) );
		}
		return apply_filters('em_recurrence_validate', empty($this->errors), $this );
	}

	function is_primary() {
		return $this->get_event()->get_recurrence_sets()->default === $this;
	}

	/**
	 * Saves or updates the recurrence set in the database.
	 *
	 * @return bool True on success, false on failure.
	 */
	public function save() {
		global $wpdb;
		$data = $this->to_array( true );
		$data['recurrence_dates'] = !empty($data['recurrence_dates']) ? implode(',', $data['recurrence_dates']) : null;
		$formats = array_column( $this->fields, 'type' );

		if ( !empty( $this->recurrence_set_id ) ) {
			if ( $this->delete ) {
				$result = $wpdb->delete( EM_EVENT_RECURRENCES_TABLE, ['recurrence_set_id' => $this->recurrence_set_id], ['%d'] );
			} else {
				$result = $wpdb->update( EM_EVENT_RECURRENCES_TABLE, $data, ['recurrence_set_id' => $this->recurrence_set_id], $formats, ['%d'] );
			}
		} else {
			$result = $wpdb->insert( EM_EVENT_RECURRENCES_TABLE, $data, $formats );
			if ( $result ) {
				$this->recurrence_set_id = $wpdb->insert_id;
			}
			$this->just_added = true;
		}
		$this->get_timeranges()->save();

		return apply_filters('em_recurrence_set_save', $result !== false, $this );
	}

	private function get_recurrence_saving_fields() {
		global $wpdb;
		$EM_Event = $this->get_event();
		$event = $EM_Event->to_array( true ); //event template - for index
		// set up event data
		if ( !empty( $event['event_attributes'] ) ) {
			$event['event_attributes'] = serialize( $event['event_attributes'] );
		}
		//remove id and we have a event template to feed to wpdb insert
		unset( $event['event_id'], $event['post_id'] );
		//Set the recurrence ID of first item
		$event['recurrence_set_id'] = $this->recurrence_set_id;
		$event['event_type'] = $this->event_type;

		// set times, timezone and status of this event
		$event['event_timezone'] = $meta_fields['_event_timezone'] = $this->timezone;
		$event['event_active_status'] = $meta_fields['_event_active_status'] = $this->status;
		$event['event_start_time'] = $meta_fields['_event_start_time'] = $this->start_time;
		$event['event_end_time'] = $meta_fields['_event_end_time'] =$this->end_time;

		// set up repeating post data
		$post_fields = $meta_fields = [];
		if ( $EM_Event->is_repeating() ) {
			$post_fields = $wpdb->get_row( 'SELECT * FROM ' . $wpdb->posts . ' WHERE ID=' . $EM_Event->post_id, ARRAY_A ); //post to copy
			$post_fields['post_type'] = $EM_Event->event_archetype; //make sure we'll save events, not recurrence templates
			$meta_fields_map = $wpdb->get_results( 'SELECT meta_key,meta_value FROM ' . $wpdb->postmeta . ' WHERE post_id=' . $EM_Event->post_id, ARRAY_A );
			$meta_fields = array ();
			//convert meta_fields into a cleaner array
			foreach ( $meta_fields_map as $meta_data ) {
				$meta_fields[ $meta_data['meta_key'] ] = $meta_data['meta_value'];
			}
			if ( isset( $meta_fields['_edit_last'] ) ) {
				unset( $meta_fields['_edit_last'] );
			}
			if ( isset( $meta_fields['_edit_lock'] ) ) {
				unset( $meta_fields['_edit_lock'] );
			}
			unset( $post_fields['ID'] );
			unset( $meta_fields['_event_id'] );
			if ( isset( $meta_fields['_post_id'] ) ) {
				unset( $meta_fields['_post_id'] );
			} //legacy bugfix, post_id was never needed in meta table
			//Set the recurrence ID of first item
			$meta_fields['_recurrence_set_id'] = $this->recurrence_set_id;
			$meta_fields['_event_type'] = $this->event_type;
		}

		// return fields for use during saving
		return [ $event, $post_fields, $meta_fields ];
	}

	/**
	 * Saves events and replaces old ones. Returns true if sucecssful or false if not.
	 * @return boolean
	 */
	public function save_recurrences() {
		global $wpdb;
		$EM_Event = $this->get_event();
		if ( $this->delete ) {
			// just delete the events, this recurrence set is scheduled to be deleted entirely
			$this->recurrences = [];
			$this->delete_events();
			$result = true;
		} else {
			if ( $EM_Event ) {
				if ( !$this->can_manage( 'edit_events', 'edit_others_events' ) ) {
					return apply_filters( 'em_recurrence_set_save_recurrences', false, $this );
				}
				if ( $EM_Event->is_published() || 'future' == $EM_Event->post_status ) {
					//check if there's any events already created, if not (such as when an event is first submitted for approval and then published), force a reschedule.
					if ( !$this->recurrence_set_id ) {
						$this->set_reschedule( true );
					} elseif ( $wpdb->get_var( 'SELECT COUNT(event_id) FROM ' . EM_EVENTS_TABLE . ' WHERE recurrence_set_id=' . absint( $this->recurrence_set_id ) ) == 0 ) {
						// no events created, are we publishing for first time, or are the just no applicable recurrences?
						$matching_days = $this->get_recurrence_days();
						$filtered_events = $this->filter_current_recurrences( $matching_days );
						// if there are no matches, then this was probably created previously but either there's no matches, or more likely recurrences are excluded
						if ( !$filtered_events['matched'] ) {
							// matches found, but no events existing yet, so we force a reschedule
							$this->set_reschedule( true );
						}
					}
					do_action( 'em_recurrence_set_save_recurrences_pre', $this ); //actions/filters only run if event is recurring

					$event_saves = $meta_inserts = [];

					// handle exclusions if we're rescheduling exclusions, create the same variables if we're rescheduling whilst we're at it
					if ( $this->has_reschedule() || $this->get_event()->get_recurrence_sets()->reschedule_exclude ) {
						$matching_days = $matching_days ?? $this->get_recurrence_days(); // get matching days if not already obtained
						$filtered_events = $filtered_events ?? $this->filter_current_recurrences( $matching_days );
						if ( $this->debug ) $formatted_matching_days = $this->debug_dates( $matching_days ); // IDE debugging // TODO - Delete?
						// exclude events if any match
						if ( $filtered_events['excluded'] ) {
							$this->handle_invalid_recurrences( $filtered_events['excluded'], $this->get_event()->get_recurrence_sets()->reschedule_exclude );
						}
					}

					// prep recurrences and clean out events
					$this->recurrences = []; // reset the recurrences as we'll now recreate them as we update or add recurrences

					//Let's start saving!
					if ( $this->has_reschedule() ) {
						// update matched ones, same as updating non-rescheduled ones
						if ( !empty( $filtered_events['matched'] ) ) {
							if ( $this->debug ) $formatted_matched_days = $this->debug_dates( array_keys($filtered_events['matched']) ); // IDE debugging // TODO - Delete?
							$this->update_recurrences( $filtered_events['matched'] );
						}
						// handle missing events here
						if ( !empty( $filtered_events['missing'] ) ) {
							if ( $this->debug ) $formatted_missing_days = $this->debug_dates( array_keys($filtered_events['missing']) ); // IDE debugging // TODO - Delete?
							$this->handle_invalid_recurrences( $filtered_events['missing'], $this->reschedule_action );
						}

						//Make template event index, post, and meta (we change event dates, timestamps, rsvp dates and other recurrence-relative info whilst saving each event recurrence)
						list( $event, $post_fields, $meta_fields ) = $this->get_recurrence_saving_fields();
						// post_name is overwritten with the dated slug on every iteration below, so the un-dated base has to be kept separately
						$base_post_name = $post_fields['post_name'] ?? '';
						$recurring_date_format = apply_filters( 'em_event_save_events_format', 'Y-m-d' );
						// modify some field values we don't need for a recreation
						$event['event_date_created'] = current_time( 'mysql' ); //since the recurrences are recreated
						unset( $event['event_date_modified'] );

						// Now, we need to create new recurrences that aren't already exisiting
						$matching_days = $matching_days ?? $this->get_recurrence_days(); // get matching days if not already obtained
						if ( !empty( $matching_days ) ) {
							//first save event post data
							$EM_DateTime = new EM_DateTime( 'now', $this->timezone );
							// go through matching days and save the new events
							foreach ( $matching_days as $day ) {
								// skip updated events
								if ( !empty( $filtered_events['matched'][ $day ] ) ) {
									continue;
								}
								// reset ids
								unset( $event['event_id'], $event['post_id'] );

								// set start date/time to $EM_DateTime for relative use further on
								$EM_DateTime->setTimestamp( $day )->setTimeString( $this->start_time );
								$start_timestamp = $EM_DateTime->getTimestamp(); //for quick access later
								//set start date
								$event['event_start_date'] = $meta_fields['_event_start_date'] = $EM_DateTime->getDate();
								$event['event_start_time'] = $meta_fields['_event_start_time'] = $EM_DateTime->getTime();
								$event['event_start'] = $meta_fields['_event_start'] = $EM_DateTime->getDateTime( true );

								// rewrite post fields if needed
								//set post slug, which may need to be sanitized for length as we pre/postfix a date for uniqueness
								if ( $EM_Event->is_repeating() ) {
									$event_slug_date = $EM_DateTime->format( $recurring_date_format );
									$event_slug = $this->sanitize_recurrence_slug( $base_post_name, $event_slug_date );
									$event_slug = apply_filters( 'em_event_save_events_recurrence_slug', $event_slug . '-' . $event_slug_date, $event_slug, $event_slug_date, $day, $EM_Event, $this ); //use this instead
									$post_fields['post_name'] = $event['event_slug'] = apply_filters( 'em_event_save_events_slug', $event_slug, $post_fields, $day, $matching_days, $EM_Event, $this ); //deprecated filter
								}

								//set end date
								$end_DateTime = $EM_DateTime->setTimeString( $this->end_time );
								if ( $this->duration > 0 && $this->recurrence_type === 'include' ) {
									//$EM_DateTime modified here, and used further down for UTC end date
									$event['event_end_date'] = $meta_fields['_event_end_date'] = $end_DateTime->add( 'P' . $this->duration . 'D' )->getDate();
								} else {
									$event['event_end_date'] = $meta_fields['_event_end_date'] = $event['event_start_date'];
								}
								$end_timestamp = $end_DateTime->getTimestamp(); //for quick access later

								//we have date timestamps - do a check now to make sure we aren't overlapping
								if ( $this->get_event()->get_recurrence_sets()->has_collision( $start_timestamp, $end_timestamp ) ) {
									continue;
								}

								// continue with dates
								$event['event_end_time'] = $meta_fields['_event_end_time'] = $EM_DateTime->getTime();
								$event['event_end'] = $meta_fields['_event_end'] = $end_DateTime->getDateTime( true );
								//add extra date/time post meta
								$meta_fields['_event_start_local'] = $event['event_start_date'] . ' ' . $event['event_start_time'];
								$meta_fields['_event_end_local'] = $event['event_end_date'] . ' ' . $event['event_end_time'];

								//add rsvp date/time restrictions
								if ( !empty( $this->rsvp_days ) && is_numeric( $this->rsvp_days ) ) {
									if ( $this->rsvp_days > 0 ) {
										$event_rsvp_date = $EM_DateTime->copy()->add( 'P' . absint( $this->rsvp_days ) . 'D' )->getDate(); //cloned so original object isn't modified
									} elseif ( $this->rsvp_days < 0 ) {
										$event_rsvp_date = $EM_DateTime->copy()->sub( 'P' . absint( $this->rsvp_days ) . 'D' )->getDate(); //cloned so original object isn't modified
									} else {
										$event_rsvp_date = $EM_DateTime->getDate();
									}
									$event['event_rsvp_date'] = $meta_fields['_event_rsvp_date'] = $event_rsvp_date;
								} else {
									$event['event_rsvp_date'] = $meta_fields['_event_rsvp_date'] = $event['event_start_date'];
								}
								$event['event_rsvp_time'] = $meta_fields['_event_rsvp_time'] = $this->recurrence_rsvp_time ?: $this->start_time;

								//create the event post id if applicable
								if ( $EM_Event->is_repeating() ) {
									if ( $wpdb->insert( $wpdb->posts, $post_fields ) ) {
										$event['post_id'] = $post_id = $wpdb->insert_id; //post id saved into event and also as a var for later user
										// Set GUID and event slug as per wp_insert_post
										$wpdb->update( $wpdb->posts, array ( 'guid' => get_permalink( $post_id ) ), array ( 'ID' => $post_id ) );
									}
								}
								// add event data to em tables
								$event_save = $wpdb->insert( EM_EVENTS_TABLE, $event );
								if ( $event_save !== false ) {
									//insert into events index table
									$event['event_id'] = $wpdb->insert_id;
									// save into here so it can be referenced by others for collisions
									$event_data = $this->get_event_recurrence_data( $event );
									$this->recurrences[ $event_data['start'] ] = $event_data;
									// add the save status
									$this->save_status['events']['added'][ $event['event_id'] ] = $event;
									$event_saves[ $event['event_id'] ] = true;
								} else {
									$event_saves[] = false;
								}
								// prepare post meta - create the meta inserts for each event
								if ( $EM_Event->is_repeating() ) {
									$meta_fields['_event_id'] = $event['event_id'];
									foreach ( $meta_fields as $meta_key => $meta_val ) {
										$meta_inserts[] = $wpdb->prepare( "(%d, %s, %s)", array (
											$post_id,
											$meta_key,
											$meta_val
										) );
									}
								}
								// save timeslots if there are any, switch the timerange object event_id by supplying the $event context
								if ( $this->get_timeranges()->has_timeslots() ) {
									// copy delete and edit permissions from this
									$this->get_timeranges()->save( $event, $this->reschedule_action );
								}
							}
							//insert the metas in one go, faster than one by one
							if ( count( $meta_inserts ) > 0 ) {
								$result = $wpdb->query( "INSERT INTO " . $wpdb->postmeta . " (post_id,meta_key,meta_value) VALUES " . implode( ',', $meta_inserts ) );
								if ( $result === false ) {
									$this->add_error( esc_html__( 'There was a problem adding custom fields to your recurring events.', 'events-manager' ) );
								}
							}
						} else {
							$this->add_error( esc_html__( 'You have not defined a date range long enough to create a recurrence.', 'events-manager' ) );
						}
					} else {
						// update matched recurrences, if $filtered_events['matched'] is defined already, then we had some exclusion rescheduling further up
						if ( empty($filtered_events) ) {
							$matching_days = $matching_days ?? $this->get_recurrence_days(); // get matching days if not already obtained
							$filtered_events = $this->filter_current_recurrences( $matching_days );
						}
						$this->update_recurrences( $filtered_events['matched'] );
					}
					// Handle bookings
					$this->save_recurrences_bookings();
					//copy the event tags and categories, which are automatically deleted/recreated by WP and EM_Categories
					if ( !empty($this->recurrences) ) {
						$this->save_recurrence_taxonomies();
						$this->handle_future_posts();
					}
					// for recurring events, we go through all the recurrences and trigger save filters/actions to let other plugins deal
					if ( $EM_Event->is_recurring() ) {
						foreach ( ['updated', 'added'] as $status ) {
							foreach ( $this->save_status['events'][ $status ] as $event_id => $event_array ) {
								$event = em_get_event( $event_id );
								if ( $event->event_id === $event_id ) {
									if ( $this->just_added ) {
										do_action( 'em_event_save_new', $this );
										do_action( 'em_event_added', $event );
									}
									apply_filters( 'em_event_save_meta', true, $event );
									apply_filters( 'em_event_save', true, $event );
									if ( $event->errors ) {
										$this->add_error( $event->errors );
										$event_saves[ $event_id ] = false;
									}
								}
							}
						}
					}
					$result = !in_array( false, $event_saves );
				} elseif ( !$EM_Event->is_published() && $EM_Event->get_previous_status() != $EM_Event->get_status() ) {
					// event isn't published, but status is changed, so we change status of any recurrences we previously created to the same status
					$this->set_status_recurrences( $EM_Event->get_status() );
					$result = false;
				}

				// Log the actions taken
				if ( !empty( $this->save_status['events']['cancelled'] ) ) {
					$this->feedback_message = sprintf( __( '%d events have been %s as they no longer match the recurrence pattern.', 'events-manager' ), count( $this->save_status['events']['cancelled'] ), __( 'cancelled', 'events-manager' ) );
				}
				if ( !empty( $this->save_status['events']['deleted'] ) ) {
					$this->feedback_message = sprintf( __( '%d events have been %s as they no longer match the recurrence pattern.', 'events-manager' ), count( $this->save_status['events']['deleted'] ), __( 'deleted', 'events-manager' ) );
				}
			}
		}
		return apply_filters('em_recurrence_set_save_recurrences', !empty($result) && empty($this->errors), $this);
	}

	/**
	 * Match existing event recurrences against a list of days to identify
	 * which days have existing events and which existing events don't match any days.
	 *
	 * Returns an array with keys containing different categories of events which currently exist
	 *                 'matched'  => [ timestamp (int) => $event (array), ... ],
	 *                 'missing'  => [ timestamp (int => event_id (int), ... ],
	 *                 'excluded' => [ timestamp (int => event_id (int), ... ],
	 *
	 * @param array $matching_days Array of timestamps for days that should have recurrences
	 *
	 * @return array
	 */
	public function filter_current_recurrences( $matching_days = null) {
		$result = [
			'matched' => [],
			'missing' => [],
			'excluded' => [],
		];
		if ( !empty( $this->recurrence_set_id ) ) {
			if ( $matching_days === null ) {
				$matching_days = $this->get_recurrence_days();
			}
			// Get all existing events for this recurrence set
			$events = EM_Events::get( [
				'recurrence_set' => $this->recurrence_set_id,
				'scope' => 'all',
				'status' => 'everything',
				'array' => true,
			] );

			// Only process if we have existing events
			if ( !empty( $events ) ) {
				$Recurrence_Sets = $this->get_event()->get_recurrence_sets();

				if ( $this->debug ) $formatted_matching_days = $this->debug_dates( $matching_days );
				// Process all events in a single loop
				foreach ( $events as $event ) {
					// Get start timestamp of the event at midnight
					$event_start = new EM_DateTime( $event['event_start_date'], $this->timezone );
					$start_timestamp = $event_start->getTimestamp();
					if ( $this->debug ) list($formatted_event_start) = $this->debug_dates( [$start_timestamp] );

					// Check if this event matches one of our target days
					if ( in_array( $start_timestamp, $matching_days ) ) {
						// Event matches a day in our recurrence pattern, now check for exclude collisions, since this then gets added to excluded
						$type = 'matched';
						if ( $Recurrence_Sets->reschedule_exclude ) {
							// check for exclusion collisions specifically
							$event_start = new EM_DateTime( $event['event_start'], 'UTC' );
							$event_end = new EM_DateTime( $event['event_end'], 'UTC' );
							if ( $Recurrence_Sets->has_collision( $event_start->getTimestamp(), $event_end->getTimestamp(), 'exclude' ) ) {
								// Collision detected, change type to 'excluded'
								$type = 'excluded';
							}
						}
						if ( $type === 'excluded' ) {
							$result['excluded'][ $start_timestamp ] = $event['event_id'];
						} else {
							$result['matched'][ $start_timestamp ] = $event;
						}
					} else {
						// Event doesn't match any day in our recurrence pattern
						$result['missing'][ $event_start->getTimestamp() ] = $event['event_id'];
					}
				}
			}
		}
		return $result;
	}

	/**
	 * Handles invalid recurrences by either canceling or deleting events based on the specified action.
	 *
	 * The Recurrence_Set::$save_status['events'] array gets populated with an array of affected event IDs in the 'cancelled' or 'deleted' key.
	 *
	 * @param int[] $event_ids Array of event IDs that need to be processed.
	 * @param string $action The action to be taken for invalid recurrences. Acceptable values are 'cancel' for canceling events
	 *                       or any other value to delete events.
	 */
	public function handle_invalid_recurrences( $event_ids, $action ) {
		foreach ( $event_ids as $event_id ) {
			// Instantiate the event object
			$EM_Event = em_get_event( $event_id );
			// Check if the event exists and belongs to this recurrence set
			if ( $EM_Event && $EM_Event->recurrence_set_id == $this->recurrence_set_id ) {
				if ( $action === 'cancel' ) {
					// Set the event status to cancelled (0) instead of deleting it
					$EM_Event->cancel();
					$this->save_status['events']['cancelled'][$EM_Event->event_id] = $EM_Event;
				} else {
					// Delete the event, keep for reference
					$EM_Event->delete( true );
					$this->save_status['events']['deleted'][$EM_Event->event_id] = $EM_Event;
				}
			}
		}
	}


	/**
	 * Updates the recurrences for a given recurrence set by modifying the event data and metadata.
	 *
	 * @param array|null $events An optional array of event data to update. If null, the events are retrieved automatically based on the recurrence set ID.
	 */
	private function update_recurrences( $events = null ) {
		list( $event, $post_fields, $meta_fields ) = $this->get_recurrence_saving_fields();
		$meta_inserts = [];
		//we go through all event main data and metadata, we delete and recreate all metadata
		//now unset some vars we don't need to deal with since we're just updating data in the wp_em_events and posts table
		unset( $event['event_date_created'], $event['recurrence_id'], $event['recurrence'], $event['event_start_date'], $event['event_end_date'], $event['event_parent'] );
		$event['event_date_modified'] = current_time( 'mysql' ); //since the recurrences are modified but not recreated
		unset( $post_fields['comment_count'], $post_fields['guid'], $post_fields['menu_order'] );
		unset( $meta_fields['_event_parent'] ); // we'll ignore this and add it manually
		//now we go through the recurrences and check whether things relative to dates need to be changed
		if ( $events === null || !is_array( $events ) ) {
			$events = EM_Events::get( array (
				'recurrence_set' => $this->recurrence_set_id,
				'scope' => 'all',
				'status' => 'everything',
				'array' => true
			) );
		}
		$is_repeating = $this->get_event()->is_repeating();
		foreach ( $events as $event_array ) {
			$event_meta_inserts = $this->update_recurrence( $event_array, [ $event, $post_fields, $meta_fields ] );
			if ( $is_repeating ) {
				$meta_inserts = array_merge( $meta_inserts, $event_meta_inserts );
			}
		}
		if ( $is_repeating ) {
			$this->update_recurrence_meta( $meta_inserts );
		}
		if ( $this->get_timeranges()->has_timeslots() && !$this->get_timeranges()->allow_edit ) {
			// update status for timeslots
			$this->get_timeranges()->set_status( $this->recurrence_status );
		}
	}

	/**
	 * Updates the recurrence details of an event, including both event and post information,
	 * and prepares meta fields for insertion into the database.
	 *
	 * @param array $event_array Event data, such as event ID, post ID, and start/end dates.
	 * @param array $fields Array of field data, typically returned by {@see Recurrence_Set::get_recurrence_saving_fields()}.
	 *
	 * @return array Returns an array of prepared meta field insertion queries for the database.
	 *
	 * @see Recurrence_Set::get_recurrence_saving_fields()
	 */
	private function update_recurrence( $event_array, $fields ) {
		global $wpdb;
		list( $event, $post_fields, $meta_fields ) = $fields;
		$EM_Event = $this->get_event();

		//set new start/end times to obtain accurate timestamp according to timezone and DST
		$EM_DateTime = EM_DateTime::create( $event_array['event_start_date'] . ' ' . $this->start_time, $this->timezone );
		$start_timestamp = $EM_DateTime->getTimestamp();
		$event['event_start_date'] = $event_array['event_start_date'];
		$event['event_start'] = $meta_fields['_event_start'] = $EM_DateTime->getDateTime( true );
		// calculate the end date by duration
		if ( $this->duration > 0 ) {
			$event['event_end_date'] = $EM_DateTime->add( 'P' . $this->duration . 'D' )->getDate();
		} else {
			$event['event_end_date'] = $event_array['event_start_date'];
		}
		$event['event_end'] = $meta_fields['_event_end'] = $EM_DateTime->setTimeString($this->end_time)->getDateTime( true );
		//add meta fields we deleted and are specific to this event
		$meta_fields['_event_start_date'] = $event_array['event_start_date']; // refer to original, we're not changing the start dates
		$meta_fields['_event_start_local'] = $event_array['event_start_date'] . ' ' . $this->start_time; // refer to original, we're not changing the start dates
		$meta_fields['_event_end_date'] = $event['event_end_date'];
		$meta_fields['_event_end_local'] = $event['event_end_date'] . ' ' . $this->end_time;

		//do we need to change the slugs?
		if ( $EM_Event->is_repeating() ) {
			// (re)set post slug, which may need to be sanitized for length as we pre/postfix a date for uniqueness
			$EM_DateTime->setTimestamp( $start_timestamp ); // set time back to start date for formatting the slug
			$recurring_date_format = apply_filters( 'em_event_save_events_format', 'Y-m-d' );
			$event_slug_date = $EM_DateTime->format( $recurring_date_format );
			$event_slug = $this->sanitize_recurrence_slug( $post_fields['post_name'], $event_slug_date );
			$event_slug = apply_filters( 'em_event_save_events_recurrence_slug', $event_slug . '-' . $event_slug_date, $event_slug, $event_slug_date, $start_timestamp, $EM_Event, $this ); //use this instead
			$post_fields['post_name'] = $event['event_slug'] = apply_filters( 'em_event_save_events_slug', $event_slug, $post_fields, $start_timestamp, [], $EM_Event, $this ); //deprecated filter
		}

		//adjust certain meta information relative to RSVP dates and times
		if ( !empty( $this->rsvp_days ) && is_numeric( $this->rsvp_days ) ) {
			$event_rsvp_days = $this->rsvp_days >= 0 ? '+' . $this->rsvp_days : $this->rsvp_days;
			$event_rsvp_date = $EM_DateTime->setTimestamp( $start_timestamp )->modify( $event_rsvp_days . ' days' )->getDate();
			$event['event_rsvp_date'] = $meta_fields['_event_rsvp_date'] = $event_rsvp_date;
		} else {
			$event['event_rsvp_date'] = $meta_fields['_event_rsvp_date'] = $event_array['event_start_date'];
		}
		$event['event_rsvp_time'] = $meta_fields['_event_rsvp_time'] = $event['event_rsvp_time'];

		//overwrite event and post tables
		$wpdb->update( EM_EVENTS_TABLE, $event, array ( 'event_id' => $event_array['event_id'] ) );

		// record the save for further usage
		$event['event_id'] = $event_array['event_id'];
		// save post and update post_id in case
		if ( $EM_Event->is_repeating() ) {
			$wpdb->update( $wpdb->posts, $post_fields, array ( 'ID' => $event_array['post_id'] ) );
			$event['post_id'] = $event_array['post_id'] ?? null;
		}
		// save event data to temp status history
		$this->save_status['events']['updated'][$event['event_id']] = $event;

		//save meta field data for insertion in one go
		$meta_inserts = [];
		if ( $EM_Event->is_repeating() ) {
			foreach ( $meta_fields as $meta_key => $meta_val ) {
				$meta_inserts[] = $wpdb->prepare( "(%d, %s, %s)", array (
					$event_array['post_id'],
					$meta_key,
					$meta_val
				) );
			}
		}

		if ( $this->get_timeranges()->has_timeslots() ) {
			if ( $this->get_timeranges()->allow_edit ) {
				$this->get_timeranges()->save( $event );
			}
		}

		// add this to the recurrences, we'd overwrite it if it already exists anyway, if we're rescheduling we'd have cleared earlier stuff
		$this->recurrences[ $start_timestamp ] = $this->get_event_recurrence_data( $event );
		return $meta_inserts;
	}

	/**
	 * Updates recurrence meta data for specific events by deleting outdated meta and inserting new meta values.
	 * This method ensures that only necessary meta fields are updated while preserving others as specified.
	 *
	 * @param array $meta_inserts An array of meta data insert queries, formatted for bulk insertion into the postmeta table.
	 *
	 * @return void This method does not return a value but performs database operations directly.
	 */
	private function update_recurrence_meta( $meta_inserts ) {
		global $wpdb;
		// clean the meta fields array to contain only the fields we actually need to overwrite i.e. delete and recreate, to avoid deleting unecessary individula recurrence data
		$exclude_meta_update_keys = apply_filters( 'em_event_save_events_exclude_update_meta_keys', array ( '_parent_id' ), $this->get_event(), $this );
		// delete all meta we'll be updating
		$post_ids = $this->get_post_ids();
		if ( !empty( $post_ids ) ) {
			$sql = "DELETE FROM {$wpdb->postmeta} WHERE post_id IN (" . implode( ',', $post_ids ) . ")";
			if ( !empty( $exclude_meta_update_keys ) ) {
				$sql .= " AND meta_key NOT IN (";
				$i = 0;
				foreach ( $exclude_meta_update_keys as $k ) {
					$sql .= ( $i > 0 ) ? ',%s' : '%s';
					$i ++;
				}
				$sql .= ")";
				$sql = $wpdb->prepare( $sql, $exclude_meta_update_keys );
			}
			$wpdb->query( $sql );
			// insert the metas in one go, faster than one by one
			if ( count( $meta_inserts ) > 0 ) {
				$result = $wpdb->query( "INSERT INTO " . $wpdb->postmeta . " (post_id,meta_key,meta_value) VALUES " . implode( ',', $meta_inserts ) );
				if ( $result === false ) {
					$this->add_error( esc_html__( 'There was a problem adding custom fields to your recurring events.', 'events-manager' ) );
				}
			}
		}
	}

	/**
	 * Adds, modifies and removes tickets from current and new recurrences. Bookings would only get deleted if a ticket was actually set to be deleted.
	 *
	 * @return void
	 * @see \EM_Ticket::delete() Deleted tickets are handled directly by the parent ticket.
	 */
	private function save_recurrences_bookings() {
		$EM_Event = $this->get_event();
		// bookings are not deleted unless events are actually deleted
		if ( $EM_Event->event_rsvp && EM_ML::is_original( $this ) ) {
			// go through all the bookings and see
			$ticket_updates = $EM_Event->get_recurrence_sets()->booking_updates['tickets'];
			// deal with newly added events - add all except newly added tickets
			foreach ( ['modified', 'unchanged'] as $status ) {
				foreach ( $ticket_updates[ $status ] as $EM_Ticket ) {
					$ticket_recurrence_data = [];
					// get added data - it's stored as an array
					foreach ( $this->save_status['events']['added'] as $event_data ) {
						// insert these as new tickets to the newly added events
						$recurrence = $this->get_event_recurrence_data( $event_data );
						$ticket_recurrence_data[] = $this->get_save_recurrences_ticket_recurrence_data( $EM_Ticket, $recurrence );
					}
					// insert tickets now, so the following bit won't double-create tickets
					$this->save_recurrences_tickets_insert( $ticket_recurrence_data, $EM_Ticket );
					// find any events that don't have this ticket and add it too
					global $wpdb;
					$sql = $wpdb->prepare("SELECT event_id, event_start, event_end, post_id FROM " . EM_EVENTS_TABLE . " WHERE recurrence_set_id = %d AND event_id NOT IN ( SELECT event_id FROM " . EM_TICKETS_TABLE . " WHERE ticket_parent = %d )", $this->recurrence_set_id, $EM_Ticket->ticket_id);
					$events = $wpdb->get_results( $sql, ARRAY_A );
					if ( $events ) {
						foreach ( $events as $event_data ) {
							$recurrence = $this->get_event_recurrence_data( $event_data );
							$ticket_recurrence_data[] = $this->get_save_recurrences_ticket_recurrence_data( $EM_Ticket, $recurrence );
						}
						// insert tickets
						$this->save_recurrences_tickets_insert( $ticket_recurrence_data, $EM_Ticket );
					}
				}
			}
			// deal with updated tickets for non-new events - we only need to deal with
			foreach ( $ticket_updates[ 'modified' ] as $EM_Ticket ) {
				$ticket_recurrence_data = [];
				// get added data - it's stored as an array
				foreach ( $this->save_status['events']['updated'] as $event_array ) {
					$recurrence = $this->get_event_recurrence_data( $event_array );
					$ticket_recurrence_data[ $event_array['event_id'] ] = $this->get_save_recurrences_ticket_recurrence_data( $EM_Ticket, $recurrence );
				}
				// get cancelled data - in EM_Event format
				foreach ( $this->save_status['events']['cancelled'] as $EM_Event ) {
					// build the recurrence array directly and pass it to build ticket-specific data
					$recurrence = [
						'start' => $EM_Event->start()->getTimestamp(),
						'event_id' => $EM_Event->event_id,
					];
					$ticket_recurrence_data[ $EM_Event->event_id ] = $this->get_save_recurrences_ticket_recurrence_data( $EM_Ticket, $recurrence );
				}
				// Process and execute the bulk update using the built $ticket_data
				$this->save_recurrences_ticket_update( $ticket_recurrence_data, $EM_Ticket);
			}
			// deal with newly added tickets - add to all events, including newly added events
			if ( !empty( $ticket_updates['added'] ) ) {
				foreach ( $ticket_updates['added'] as $EM_Ticket ) { /* @var \EM_Ticket $EM_Ticket */
					$ticket_recurrence_data = [];
					// we're adding this to all events, so we loop the recurrences entirely
					foreach ( $this->get_recurrences() as $recurrence ) {
						$ticket_recurrence_data[] = $this->get_save_recurrences_ticket_recurrence_data( $EM_Ticket, $recurrence );
					}
					// save complied data in one go as an insert
					$this->save_recurrences_tickets_insert( $ticket_recurrence_data, $EM_Ticket );
				}
			}
		} elseif ( !$EM_Event->event_rsvp && $EM_Event->just_disabled_rsvp ) {
			// RSVP disabled, so we delete bookings for each recurrence
			foreach ( $this->get_recurrences() as $recurrence ) {
				$event = em_get_event( $recurrence['event_id'] );
				$event->get_bookings()->delete();
				$event->get_tickets()->delete( true );
			}
		}
	}

	public function save_recurrences_tickets_insert( $ticket_recurrence_data, $EM_Ticket ) {
		global $wpdb;
		//prep ticket meta for insertion with relative info for each event date
		if ( !empty( $ticket_recurrence_data ) ) {
			$ticket_data = $this->get_save_recurrences_ticket_data_template( $EM_Ticket );
			$meta_inserts = $ticket = [];
			foreach ( $ticket_recurrence_data as $ticket_array ) {
				$ticket = array_merge( $ticket_data, $ticket_array );
				// get the type value from $this->fields from the key that matches each value in $ticket_keys
				if ( empty($ticket_types) ) {
					$ticket_types = [];
					foreach ( $ticket as $key => $value ) {
						$ticket_types[ $key ] = $EM_Ticket->fields[ $key ]['type'] ?? '%s';
					}
				}
				$meta_inserts[] = $wpdb->prepare( "(" . implode( ",", $ticket_types ) . ")", $ticket );
			}
			$keys = "(" . implode( ",", array_keys( $ticket ) ) . ")";
			$values = implode( ',', $meta_inserts );
			$sql = "INSERT INTO " . EM_TICKETS_TABLE . " $keys VALUES $values";
			$result = $wpdb->query( $sql );
			if ( !$result ) {
				$this->add_error( esc_html__( 'There was a problem adding tickets to your recurrences.', 'events-manager' ) );
			}
		}
	}

	/**
	 * Updates ticket information across recurring events based on provided ticket and recurrence data.
	 *
	 * @param array $recurrence_data Nested array of recurrence-specific ticket data, organized by event ID and ticket field.
	 * @param object $EM_Ticket Ticket object representing the parent ticket that was updated and pushing out other updates.
	 *
	 * @return void This method does not return anything but performs update operations on the database.
	 */
	public function save_recurrences_ticket_update( $recurrence_data, $EM_Ticket ) {
		global $wpdb;
		//prep ticket meta for insertion with static info for each event date, we don't need much as null values default to base ticket value
		$ticket_data = $this->get_save_recurrences_ticket_data_template( $EM_Ticket );
		$updates = [];
		// create the rest of the update statement based on ticket_id = $EM_Ticket->ticket_id
		foreach ( $ticket_data as $key => $value ) {
			$type = $this->fields[ $key ]['type'] ?? '%s';
			$updates[] = $wpdb->prepare("$key=$type", $value);
		}
		// create array unique per-event data for use in CASE conditionals
		$case_data = [];
		foreach ( $recurrence_data as $event_id => $recurrence_ticket_data ) {
			foreach ( $recurrence_ticket_data as $key => $value ) {
				if ( $key !== 'event_id') {
					$case_data[ $key ][ $event_id ] = $value;
				}
			}
		}
		// create a case conditional for each $key in $ticket_data based on $event_id setting the $value
		foreach ( $case_data as $key => $recurrence_case_data ) {
			$updates[$key] = PHP_EOL . " $key = CASE event_id " . PHP_EOL;
			foreach ( $recurrence_case_data as $event_id => $value ) {
				$updates[$key] .= $wpdb->prepare("  WHEN " . absint($event_id) . " THEN %s", $value) . PHP_EOL;
			}
			$updates[$key] .= ' END';
		}
		$update_cases = implode( ',', $updates );
		$sql = "UPDATE " . EM_TICKETS_TABLE . " SET $update_cases WHERE ticket_parent = " . absint( $EM_Ticket->ticket_id ) . " AND event_id IN ( SELECT event_id FROM " . EM_EVENTS_TABLE . " WHERE recurrence_set_id = ". absint($this->recurrence_set_id) .")";
		$result = $wpdb->query( $sql );
		if ( $result === false ) {
			$this->add_error( esc_html__( 'There was a problem updating tickets to your recurrences.', 'events-manager' ) );
		}
	}

	/**
	 * Gets the template for saving ticket data for recurrences, providing only the necessary fields that aren't overriden
	 * @param $EM_Ticket
	 *
	 * @return array
	 */
	public function get_save_recurrences_ticket_data_template( $EM_Ticket ) {
		return [
			'ticket_name' => $EM_Ticket->ticket_name,
			'ticket_parent' => absint( $EM_Ticket->ticket_id ),
			'ticket_order' => absint( $EM_Ticket->ticket_order ),
		];
	}

	public function get_save_recurrences_ticket_recurrence_data( $EM_Ticket, $recurrence ) {
		$EM_DateTime = new EM_DateTime( $recurrence['start'], $this->timezone );
		$ticket = [
			'event_id' => $recurrence['event_id'],
		];
		$ticket_meta_recurrences = $EM_Ticket->ticket_meta['recurrences'] ?? false;
		//sort out cut-off dates
		if ( !empty( $ticket_meta_recurrences ) ) {
			$EM_DateTime->setTimestamp( $recurrence['start'] ); //by using EM_DateTime we'll generate timezone aware dates
			if ( array_key_exists( 'start_days', $ticket_meta_recurrences ) && $ticket_meta_recurrences['start_days'] !== false && $ticket_meta_recurrences['start_days'] !== null ) {
				$ticket_start_days = $ticket_meta_recurrences['start_days'] >= 0 ? '+' . $ticket_meta_recurrences['start_days'] : $ticket_meta_recurrences['start_days'];
				$ticket_start_date = $EM_DateTime->modify( $ticket_start_days . ' days' )->getDate();
				$ticket['ticket_start'] = $ticket_start_date . ' ' . $ticket_meta_recurrences['start_time'];
			}
			if ( array_key_exists( 'end_days', $ticket_meta_recurrences ) && $ticket_meta_recurrences['end_days'] !== false && $ticket_meta_recurrences['end_days'] !== null ) {
				$ticket_end_days = $ticket_meta_recurrences['end_days'] >= 0 ? '+' . $ticket_meta_recurrences['end_days'] : $ticket_meta_recurrences['end_days'];
				$EM_DateTime->setTimestamp( $recurrence['start'] );
				$ticket_end_date = $EM_DateTime->modify( $ticket_end_days . ' days' )->getDate();
				$ticket['ticket_end'] = $ticket_end_date . ' ' . $ticket_meta_recurrences['end_time'];
			}
		}
		return $ticket;
	}

	/**
	 * Handle taxonomies and scheduled publishing for events
	 *
	 * @param array $event_ids Event IDs with key mapping of corresponding post ids
	 */
	private function save_recurrence_taxonomies() {
		$EM_Event = $this->get_event();
		if ( $EM_Event->is_repeating() ) {
			foreach ( EM_Event::get_taxonomies() as $tax_name => $tax_data ) {
				//In MS Global mode, we also save category meta information for global lookups so we use our objects
				if ( $tax_name == 'category' ) {
					//we save index data for each category in MS Global mode
					foreach ( $this->recurrences as $recurrence ) {
						if ( !empty( $recurrence['post_id'] ) ) {
							//set and trick category event and post ids so it saves to the right place
							$EM_Event->get_categories()->event_id = $recurrence['event_id'];
							$EM_Event->get_categories()->post_id = $recurrence['post_id'];
							$EM_Event->get_categories()->save();
						}
					}
					// TODO - is this necessary?
					$EM_Event->get_categories()->event_id = $EM_Event->event_id;
					$EM_Event->get_categories()->post_id = $EM_Event->post_id;
				} else {
					//general taxonomies including event tags
					$terms = get_the_terms( $EM_Event->post_id, $tax_data['name'] );
					$term_slugs = array ();
					if ( is_array( $terms ) ) {
						foreach ( $terms as $term ) {
							if ( !empty( $term->slug ) ) {
								$term_slugs[] = $term->slug;
							} //save of category will soft-fail if slug is empty
						}
					}
					foreach ( $this->recurrences as $recurrence ) {
						if ( !empty( $recurrence['post_id'] ) ) {
							wp_set_object_terms( $recurrence['post_id'], $term_slugs, $tax_data['name'] );
						}
					}
				}
			}
		}
	}

	private function handle_future_posts() {
		$EM_Event = $this->get_event();
		if ( $EM_Event->is_repeating() && 'future' == $EM_Event->post_status ) {
			$time = strtotime( $EM_Event->post_date_gmt . ' GMT' );
			foreach ( $this->get_post_ids() as $post_id ) {
				wp_clear_scheduled_hook( 'publish_future_post', array ( $post_id ) ); // clear anything else in the system
				wp_schedule_single_event( $time, 'publish_future_post', array ( $post_id ) );
			}
		}
	}

	/**
	 * Ensures a post slug is the correct length when the date postfix is added, which takes into account multibyte and url-encoded characters and WP unique suffixes.
	 * If a url-encoded slug is nearing 200 characters (the data character limit in the db table), adding a date to the end will cause issues when saving to the db.
	 * This function checks if the final slug is longer than 200 characters and removes one entire character rather than part of a hex-encoded character, until the right size is met.
	 * @param string $post_name
	 * @param string $post_slug_postfix
	 * @return string
	 */
	public function sanitize_recurrence_slug( $post_name, $post_slug_postfix ){
		if( strlen($post_name.'-'.$post_slug_postfix) > 200 ){
			if( preg_match('/^(.+)(\-[0-9]+)$/', $post_name, $post_name_parts) ){
				$post_name_decoded = urldecode($post_name_parts[1]);
				$post_name_suffix =  $post_name_parts[2];
			}else{
				$post_name_decoded = urldecode($post_name);
				$post_name_suffix = '';
			}
			$post_name_maxlength = 200 - strlen( $post_name_suffix . '-' . $post_slug_postfix);
			if ( $post_name_parts[0] === $post_name_decoded.$post_name_suffix ){
				$post_name = substr( $post_name_decoded, 0, $post_name_maxlength );
			}else{
				$post_name = utf8_uri_encode( $post_name_decoded, $post_name_maxlength );
			}
			$post_name = rtrim( $post_name, '-' ) . $post_name_suffix;
		}
		return apply_filters('em_event_sanitize_recurrence_slug', $post_name, $post_slug_postfix, $this->get_event(), $this );
	}

	/**
	 * Deletes all
	 * @return bool
	 */
	public function delete() {
		$this->delete_events();
		$this->delete_bookings();
		$this->get_timeranges()->delete();
		return apply_filters('em_recurrence_set_delete', true, $this );
	}

	/**
	 * Removes all recurrences of a recurring event.
	 * @return null
	 */
	public function delete_events(){
		global $wpdb;
		$EM_Event = $this->get_event();
		if ( $EM_Event ) {
			do_action('em_event_delete_events_pre', $EM_Event, $this);
			//So we don't do something we'll regret later, we could just supply the get directly into the delete, but this is safer
			$result = false;
			$events_array = array();
			if( $EM_Event->can_manage('delete_events', 'delete_others_events') ){
				//delete events from em_events table
				$sql = $wpdb->prepare('SELECT event_id FROM '.EM_EVENTS_TABLE.' WHERE event_type=%s AND recurrence_set_id=%d', 'recurrence', $this->recurrence_set_id);
				$events = $wpdb->get_col( $sql );
				// go through each event and delete individually so individual hooks are fired appropriately
				foreach( $events as $event_id ){
					$event = em_get_event( $event_id );
					if( $event->recurrence_set_id == $this->recurrence_set_id ){
						$event->delete(true);
						$events_array[] = $event;
					}
				}
				$result = !empty($events_array) || (is_array($events) && empty($events)); // success if we deleted something, or if there was nothing to delete in the first place
			}
			$result = apply_filters('delete_events', $result, $EM_Event, $events_array, $this); //Deprecated, use em_event_delete_events
			return apply_filters('em_event_delete_events', $result, $EM_Event, $events_array, $this);
		}
		return false;
	}

	/**
	 * Deletes all bookings associated with the specified recurrences of an event.
	 *
	 * Iterates through all recurrences linked to the current recurrence set and deletes the bookings associated with each event in the database.
	 * 
	 * If an error occurs during the deletion process, an appropriate error message is logged to this object.
	 *
	 * @return bool
	 */
	public function delete_bookings () {
		global $wpdb;
		$result = true;
		foreach ( $this->get_recurrences() as $recurrence ) {
			$event_id = $recurrence['event_id'];
			// EM_Bookings only recognizes an EM_Event object or an array of bookings, not a bare event id
			$EM_Bookings = new EM_Bookings( em_get_event( $event_id ) );
			if ( !$EM_Bookings->delete() ) {
				$this->add_error( esc_html__( 'There was a problem deleting bookings for the event.', 'events-manager' ) );
				$result = false;
			}
		}
		return $result;
	}

	/**
	 * Returns the days that match this recurrence set. Array of values are unix timestams for times events occur, IN THE TIMEZONE OF THIS RECURRENCE SET
	 *
	 * For example, if an event happens yearly on the 1st Januay at 12am in Madrid time (GMT+2 with DST), the timestamps would always correspond to years on December 31st at 10pm UTC, therefore, 2 hours before midnight UTC
	 *
	 * @return int[]
	 */
	function get_recurrence_days(){
		$EM_Event = $this->get_event();
		if ( $EM_Event ) {
			//get timestampes for start and end dates, both at 12AM
			$EM_DateTime = new EM_DateTime( $this->start_date, $this->timezone );
			$start_date = $EM_DateTime->getTimestamp();
			$end_EM_DateTime = new EM_DateTime( $this->end_date, $this->timezone );
			$end_date = $end_EM_DateTime->getTimestamp();
			$matching_days = array (); //the days we'll be returning in timestamps

			//generate matching dates based on frequency type
			switch ( $this->freq ) {
				/* @var \EM_DateTime $EM_DateTime */ case 'daily':
				//If daily, it's simple. Get start date, add interval timestamps to that and create matching day for each interval until end date.
				$current_timestamp = $EM_DateTime->getTimestamp();
				while ( $current_timestamp <= $end_date ) {
					$matching_days[] = $current_timestamp;
					$EM_DateTime->add( 'P' . $this->interval . 'D' );
					$current_timestamp = $EM_DateTime->getTimestamp();
				}
				break;
				case 'weekly':
					//sort out week one, get starting days and then days that match time span of event (i.e. remove past events in week 1)
					$start_of_week = em_get_option( 'start_of_week' ); //Start of week depends on WordPress
					//then get the timestamps of weekdays during this first week, regardless if within event range
					$start_weekday_dates = array (); //Days in week 1 where there would events, regardless of event date range
					$weekdays = explode( ",", $this->byday ); //what days of the week (or if monthly, one value at index 0)
					for ( $i = 0; $i < 7; $i ++ ) {
						if ( in_array( $EM_DateTime->format( 'w' ), $weekdays ) ) {
							$start_weekday_dates[] = $EM_DateTime->getTimestamp(); //it's in our starting week day, so add it
						}
						$EM_DateTime->add( 'P1D' ); //add a day
					}
					//for each day of eventful days in week 1, add 7 days * weekly intervals
					foreach ( $start_weekday_dates as $weekday_date ) {
						//Loop weeks by interval until we reach or surpass end date
						$EM_DateTime->setTimestamp( $weekday_date );
						while ( $EM_DateTime->getTimestamp() <= $end_date ) {
							if ( $EM_DateTime->getTimestamp() >= $start_date && $EM_DateTime->getTimestamp() <= $end_date ) {
								$matching_days[] = $EM_DateTime->getTimestamp();
							}
							$EM_DateTime->add( 'P' . ( $this->interval * 7 ) . 'D' );
						}
					}//done!
					break;
				case 'monthly':
					//loop months starting this month by intervals
					$EM_DateTime->modify( $EM_DateTime->format( 'Y-m-01 00:00:00' ) ); //Start date on first day of month, done this way to avoid 'first day of' issues in PHP < 5.6
					while ( $EM_DateTime->getTimestamp() <= $EM_Event->end()->getTimestamp() ) {
						$last_day_of_month = $EM_DateTime->format( 't' );
						//Now find which day we're talking about
						$current_week_day = $EM_DateTime->format( 'w' );
						$matching_month_days = array ();
						//Loop through days of this years month and save matching days to temp array
						for ( $day = 1; $day <= $last_day_of_month; $day ++ ) {
							if ( (int) $current_week_day == $this->byday ) {
								$matching_month_days[] = $day;
							}
							$current_week_day = ( $current_week_day < 6 ) ? $current_week_day + 1 : 0;
						}
						//Now grab from the array the x day of the month
						$matching_day = false;
						if ( $this->byweekno > 0 ) {
							//date might not exist (e.g. fifth Sunday of a month) so only add if it exists
							if ( !empty( $matching_month_days[ $this->byweekno - 1 ] ) ) {
								$matching_day = $matching_month_days[ $this->byweekno - 1 ];
							}
						} else {
							//last day of month, so we pop the last matching day
							$matching_day = array_pop( $matching_month_days );
						}
						//if we have a matching day, get the timestamp, make sure it's within our start/end dates for the event, and add to array if it is
						if ( !empty( $matching_day ) ) {
							$matching_date = $EM_DateTime->setDate( $EM_DateTime->format( 'Y' ), $EM_DateTime->format( 'm' ), $matching_day )->getTimestamp();
							if ( $matching_date >= $start_date && $matching_date <= $end_date ) {
								$matching_days[] = $matching_date;
							}
						}
						//add the monthly interval to the current date, but set to 1st of current month first so we don't jump months where $current_date is 31st and next month there's no 31st (so a month is skipped)
						$EM_DateTime->modify( $EM_DateTime->format( 'Y-m-01' ) ); //done this way to avoid 'first day of ' PHP < 5.6 issues
						$EM_DateTime->add( 'P' . $this->interval . 'M' );
					}
					break;
				case 'yearly':
					//Yearly is easy, we get the start date as a cloned EM_DateTime and keep adding a year until it surpasses the end EM_DateTime value.
					while ( $EM_DateTime <= $EM_Event->end() ) {
						$matching_days[] = $EM_DateTime->getTimestamp();
						$EM_DateTime->add( 'P' . absint( $this->interval ) . 'Y' );
					}
					break;
				case 'on':
					foreach ( $this->dates as $recurrence_date ) {
						$recurrence_date = explode( '-', $recurrence_date );
						$EM_DateTime->setDate( $recurrence_date[0], $recurrence_date[1], $recurrence_date[2] );
						$matching_days[] = $EM_DateTime->getTimestamp();
					}
					break;
			}
			sort( $matching_days );

			return apply_filters( 'em_events_get_recurrence_days', $matching_days, $EM_Event, $this );
		}
	}

	public function get_recurrence_timeslots( $matching_days, $EM_DateTime, $end_time = null ) {
		if ( empty($end_time) ) {
			$end_time = $this->end_time;
		}
		if ( $this->get_timeranges()->has_timeslots() ) {
			foreach ( $this->get_timeranges()->generate_timeslots() as $Timeslot ) {
				$start = $EM_DateTime->copy()->setTimeString( $Timeslot->start->getTime() );
				$end = $EM_DateTime->copy()->add('P'. $this->duration .'D')->setTimeString( $Timeslot->end->getTime() );
				if ( empty( $matching_days[ $Timeslot->start->getTimestamp() ] ) ) {
					$matching_days[ $Timeslot->start->getTimestamp() ] = [ $start, $end ];
				}
			}
		} elseif ( empty( $matching_days[ $EM_DateTime->getTimestamp() ] ) ) {
			$matching_days[ $EM_DateTime->getTimestamp() ] = [ $EM_DateTime->copy(), $EM_DateTime->copy()->add('P'. $this->duration .'D')->setTimeString( $end_time ) ];
		}
		return $matching_days;
	}

	/**
	 * If event is recurring, set recurrences to same status as template
	 * @param $status
	 */
	public function set_status_recurrences( $status ){
		//give sub events same status
		global $wpdb;
		$EM_Event = $this->get_event();
		if ( $EM_Event ) {
			//decide on what status to set and update wp_posts in the process
			if ( $status === null ) {
				$set_status = 'NULL'; //draft post
				$post_status = 'draft'; //set post status in this instance
			} elseif ( $status == - 1 ) { //trashed post
				$set_status = - 1;
				$post_status = 'trash'; //set post status in this instance
			} else {
				$set_status = $status ? 1 : 0; //published or pending post
				$post_status = $set_status ? 'publish' : 'pending';
			}
			if ( $EM_Event->is_repeating() ) {
				if ( EM_MS_GLOBAL ) {
					switch_to_blog( $EM_Event->blog_id );
				}
				$result = $wpdb->query( $wpdb->prepare( "UPDATE " . $wpdb->posts . " SET post_status=%s WHERE ID IN ( SELECT post_id FROM " . EM_EVENTS_TABLE . ' WHERE post_id > 0 AND recurrence_set_id = %d )', [ $post_status, $this->recurrence_set_id ] ) ) !== false;
				if ( EM_MS_GLOBAL ) {
					restore_current_blog();
				}
			}
			$result = ( $result ?? true ) && $wpdb->query( $wpdb->prepare( "UPDATE " . EM_EVENTS_TABLE . " SET event_status=%s WHERE recurrence_set_id = %d", [ $set_status, $this->recurrence_set_id ] ) ) !== false;
			$timeslot_sql = 'UPDATE ' . EM_EVENT_TIMESLOTS_TABLE . ' SET timeslot_status=%s WHERE event_id IN ( SELECT event_id FROM ' . EM_EVENTS_TABLE . ' WHERE recurrence_set_id = %d )';
			$result = $result && ( $wpdb->query( $wpdb->prepare( $timeslot_sql, [ $set_status, $this->recurrence_set_id ] ) ) !== false );
			return apply_filters( 'em_recurrence_set_set_status_recurrences', $result, $status, $this );
		}
	}

	/**
	 * Converts the recurrence set to an API-compatible array.
	 *
	 * @return array
	 */
	public function to_api () {
		$api = [
			'set_id' => $this->recurrence_set_id,
			'event_id' => $this->event_id,
			'type' => $this->type,
			'interval' => $this->interval,
			'freq' => $this->freq,
			'days' => $this->duration,
			'byday' => $this->byday,
			'byweekno' => $this->byweekno,
			//'rsvp_days' => $this->rsvp_days,
			'start_date' => $this->start_date,
			'end_date' => $this->end_date,
			'start_time' => $this->start_time,
			'end_time' => $this->end_time,
			// `all_day` and `timezone` apply to EVERY set, excludes included: timezone interprets the dates, and all_day distinguishes a whole-day skip from a timed one (recurrence_all_day=1 => whole day; otherwise start_time/end_time bound a timed window). `status` and `timeranges` are include-only — an exclude has no active status and (in the read shape) carries its single time window via start_time/end_time/all_day rather than a timeslot list. `dates` only carries values for freq=on.
			'all_day' => (bool) $this->all_day,
			'status' => $this->type === 'exclude' ? null : $this->status,
			'timezone' => $this->timezone,
			'dates' => $this->freq === 'on' ? array_values( (array) $this->dates ) : null,
			'timeranges' => $this->type === 'exclude' ? array() : $this->get_timeranges()->to_api()['timeranges'],
		];

		return apply_filters( 'em_recurrence_set_to_api', $api, $this );
	}

	public function debug_dates ( $matching_days ) {
		// First, we need to handle recurrences that fell out of the pattern, and update ones that remain.
		$EM_DateTime = new EM_DateTime( 'now', $this->timezone ); // Ensure EM_DateTime is initialized before use.
		$formatted_matching_days = [];
		foreach ( $matching_days as $day ) {
			$EM_DateTime->setTimestamp( $day );
			$formatted_matching_days[] = $EM_DateTime->format( '(D) F d, Y H:i:s' );
		}

		return $formatted_matching_days;
	}
}

// legacy filters previously in EM_Event, will eventually be phased out
add_filter('em_recurrence_set_save_recurrences',
	/**
	* @param bool $result
	* @param Recurrence_Set $Recurrence_Set
	* @returns bool
	*/
	function( $result, $Recurrence_Set ){
	if ( has_filter('em_event_save_events') ) {
		$result = $result === false ? false : [];
		// generate $event_ids and $post_ids directly from recurrences
		$event_ids = $post_ids = [];
		foreach ( $Recurrence_Set->get_recurrences() as $recurrence ) {
			// change $result into $event_dates a legacy array of event_id => start_timestamp
			if ( $result !== false ) {
				$result[ $recurrence['event_id'] ] = $recurrence['start'];
			}
			$event_ids[] = $recurrence['event_id'];
			if ( !empty( $recurrence['post_id'] ) ) {
				$post_ids[] = $recurrence['post_id'];
			}
		}
		$result = apply_filters('em_event_save_events', $result, $Recurrence_Set->get_event(), $event_ids, $post_ids ) !== false;
	}
	return $result;
}, 1, 4 );

add_action('em_recurrence_set_save_recurrences_pre', function( $EM_Recurrence_Set ) {
	do_action('em_event_save_events_pre', $EM_Recurrence_Set->get_event() );
}, 1, 1 );

add_filter('em_recurrence_set_set_status_recurrences', function( $result, $status, $EM_Recurrence_Set ) {
	if ( has_filter('em_event_set_status_events') ) {
		// rebuild event_ids and $post_ids
		$event_ids = $post_ids = [];
		foreach ( $EM_Recurrence_Set->recurrences as $recurrence ) {
			$event_ids[] = $recurrence['event_id'];
			if ( !empty($recurrence['post_id']) ) {
				$post_ids[ $recurrence['start'] ] = $recurrence['post_id'];
			}
		}
		$result = apply_filters('em_event_set_status_events', $result, $status, $EM_Recurrence_Set->get_event(), $event_ids, $post_ids );
	}
	return $result;
}, 1, 3);