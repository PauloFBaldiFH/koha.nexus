<?php
namespace EM;

use EM_DateTime;

/**
 * @property EM_DateTime $start
 * @property EM_DateTime $end
 */
class Timeslot extends \EM_Object {
	/**
	 * @var int
	 */
	public $timerange_id;
	/**
	 * Start time of timeslot,
	 * @var EM_DateTime
	 */
	public $start;
	/**
	 * End time of timeslot,
	 * @var EM_DateTime
	 */
	public $end;

	/**
	 * Accepts start and end times of the same format, which can be a EM_DateTime object, a number (seconds from midnight) or string (DateTime or Time string).
	 *
	 * Numbers are considered as the number of seconds from midnight, in local timezone time. For example, 0 with timezone UTC+1 would actually equate to 12pn UTC+1, which becomes 11pm UTC the day before.
	 *
	 * Times strings are treated as starting from 1970-01-01 meaning the number of seconds since 12:00am UTC, but are considered to be in the supplied timezone in $args.
	 *
	 * DateTime strings (YYYY-MM-DD HH:MM:SS) are treated as UTC timestamps and are subsequently converted to the supplied timezone in $args.
	 *
	 * EM_DateTime objects are treated as is, relative to its own timezone.
	 *
	 * Timezones are optional and default to UTC
	 *
	 * $timerange_id is optional and can be used to link timeslots to a specific timerange.
	 *
	 * @param array $args
	 */
	public function __construct( $args ) {
		$start = $args['start'] ?? $args['timeslot_start'];
		$end = $args['end'] ?? $args['timeslot_end'];
		if ( $start instanceof EM_DateTime ) {
			$this->start = $start;
			$this->end = $end;
		} elseif ( is_numeric( $start ) ) {
			// timestamp, which is UTC
			$this->start = new EM_DateTime( '@' . $start, 'UTC' );
			$this->end = new EM_DateTime( '@' . $end, 'UTC' );
			if ( !empty($args['timezone']) ) {
				// but we're expecting it to be in timezone supplied, therefore we "transcribe" the UTC time first into a relative string, and build it as a string with timezone
				$start_time = $this->start->getTime();
				$end_time = $this->end->getTime();
				$this->start = new EM_DateTime( "1970-01-01 $start_time", $args['timezone'] );
				$this->end = new EM_DateTime( "1970-01-01 $end_time", $args['timezone'] );
			}
			// check if it's a datetime format
		} elseif ( preg_match( '/^[0-9]{4}\-[0-9]{2}\-[0-9]{2} ([0-9]{2}:){2}00$/', $start ) && preg_match( '/^[0-9]{4}\-[0-9]{2}\-[0-9]{2} ([0-9]{2}:){2}00$/', $end ) ) {
			$this->start = new EM_DateTime( $start, 'UTC' );
			$this->end = new EM_DateTime( $end, 'UTC' );
			if ( $args['timezone'] ) {
				$this->start->setTimezone( $args['timezone'] );
				$this->end->setTimezone( $args['timezone'] );
			}
		} else {
			$this->start = new EM_DateTime( '1970-01-01 ' . $start, $args['timezone'] ?? 'UTC' );
			$this->end = new EM_DateTime( '1970-01-01 ' . $end, $args['timezone'] ?? 'UTC' );
		}
		$this->timerange_id = $args['timerange_id'] ?? null;
	}

	public function to_array( $db = false ) {
		return [
			'timerange_id' => $this->timerange_id,
			'start' => $this->start->getTime(),
			'end' => $this->end->getTime(),
		];
	}
}