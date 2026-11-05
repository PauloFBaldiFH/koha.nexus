<?php
/**
 * Extends DateTime allowing supplied timezone to be a string, which can also be a UTC offset.
 * Also prevents an exception being thrown. Some additional shortcuts added so less coding is required for regular tasks.
 * By doing this, we support WP's option to manually offset time with a UTC timezone name e.g. UTC+1.5, which isn't supported by PHP (it only supports numerical offsets which represent UTC offsets)
 *
 * @since 5.8.2
 */
class EM_DateTime extends DateTime {
	
	/**
	 * The name of this timezone. For example, America/New_York or UTC+3.5
	 * @var string
	 */
	protected $timezone_name = false;
	/**
	 * @var bool Whether or not string is UTC offset with a UTC+-d timezone name pattern, which isn't supported in PHP normally.
	 */
	protected $timezone_utc = false;
	/**
	 * Flag for validation purposes, so we can still have a real EM_DateTime and extract dates but know if the intended datetime failed validation.
	 * A completely invalid date and time will become 1970-01-01 00:00:00 in local timezone, however a valid time can still exist with the 1970-01-01 date.
	 * If the date is invalid, only local timezones should be used since the time will not accurately convert timezone switches.
	 * @var string
	 */
	public $valid = true;
	
	/**
	 * @see DateTime::__construct()
	 * @param string $time
	 * @param string|EM_DateTimeZone $timezone Unlike DateTime this also accepts string representation of a valid timezone, as well as UTC offsets in form of 'UTC -3' or just '-3'
	 */
	public function __construct( $time = 'now', $timezone = null ){
		//get our EM_DateTimeZone
		$timezone = EM_DateTimeZone::create($timezone);
		//save timezone name for use in getTimezone()
		$this->timezone_name = $timezone->getName();
		$this->timezone_utc = $timezone->utc_offset !== false;
		//fix DateTime error if a regular timestamp is supplied without prepended @ symbol
		if( is_numeric($time) ){
			$time = '@'.$time;
		}elseif( is_null($time) ){
			$time = 'now';
		}
		//finally, run parent function with our custom timezone
		try{
			@parent::__construct( (string) $time, $timezone);
			if( substr($time,0,1) == '@' || $time == 'now' ) $this->setTimezone($timezone);
			$this->valid = true; //if we get this far, supplied time is valid
			if( (int) parent::format('Y') < 1000 ){
				// zero dates such as 0000-00-00 00:00:00 do not throw, they parse to year -0001, so treat an impossible year as a failed date
				$this->setDate(1970,1,1);
				$this->setTime(0,0,0);
				$this->valid = false; // setDate() and setTime() mark themselves valid, so this stays last
			}
		}catch( Exception $e ){
			//get current date/time in relevant timezone and set valid flag to false
			try {
				parent::__construct('@0');
			}catch( Exception $e ){
				// do nothing
			}finally{
				$this->setTimezone($timezone);
				$this->setDate(1970,1,1);
				$this->setTime(0,0,0);
				$this->valid = false;
			}
		}
	}

	/**
	 * Shortcut for creating a EM_DateTime instance and having it returned for chained methods.
	 *
	 * @param $time
	 * @param $timezone
	 *
	 * @see EM_DateTime::__construct()
	 * @return EM_DateTime
	 */
	public static function create( $time = 'now', $timezone = null ){
		return new EM_DateTime($time, $timezone);
	}

	#[\ReturnTypeWillChange]
	/**
	 * {@inheritDoc}
	 * @see DateTime::format()
	 */
	public function format( $format = 'Y-m-d H:i:s', $timezone = null ){
		// if we want a timezone, copy and format the copy
		if ( $timezone ) {
			$EM_DateTime = $this->copy();
			if ( $timezone === true ) {
				$timezone = 'UTC';
			}
			$EM_DateTime->setTimezone( $timezone );
			return $EM_DateTime->format( $format );
		}
		// format normally
		if( !$this->valid && ($format == 'Y-m-d' || $format == em_get_date_format())) return '';
		if( $format !== 'Y-m-d H:i:s' ) $format = $this->formatTimezones($format); // format UTC timezones
		return parent::format($format);
	}

	/**
	 * Formats timezone name/abbreviation placeholders when there is a manual offset, which would be passed onto date formatting functions and usually output UTC timezone information.
	 * @param string $format The format to be parsed.
	 * @return string
	 */
	public function formatTimezones($format){
		if( $this->timezone_utc ){
			$timezone_formats = array( 'T', 'e' );
			foreach ( $timezone_formats as $timezone_format ) {
				if ( false !== strpos( $format, $timezone_format ) ) {
					$format = ' '.$format;
					$format = preg_replace( "/([^\\\])$timezone_format/", "\\1" . backslashit( $this->timezone_name ), $format );
					$format = substr( $format, 1, strlen( $format ) -1 );
				}
			}
		}
		return $format;
	}
	
	/**
	 * Returns a date and time representation in the format stored in Events Manager settings.
	 * @param bool $include_hour
	 * @return string
	 */
	public function formatDefault( $include_hour = true ){
		$format = $include_hour ? em_get_date_format() . ' ' . em_get_hour_format() : em_get_date_format();
		$format = apply_filters( 'em_datetime_format_default', $format, $include_hour );
		return $this->i18n( $format );
	}
	
	/**
	 * Provides a translated date and time according to the current blog language.
	 * Useful if using formats that provide date-related names such as 'Monday' or 'January', which should be translated if displayed in another language.
	 * @param string $format
	 * @return string
	 */
	public function i18n( $format = 'Y-m-d H:i:s' ){
		if( !$this->valid && $format == em_get_date_format()) return '';
		// since we use WP's date functions which don't use DateTime (and if so, don't inherit our timezones), we need to preformat timezone related formats, adapted from date_i18n
		$format = $this->formatTimezones( $format );
		// support for < WP 5.3.0
		if( function_exists('wp_date') ){
			return wp_date( $format, $this->getTimestamp(), $this->getTimezone() );
		}else{
			return date_i18n( $format, $this->getTimestampWithOffset(true) );
		}
	}
	
	/**
	 * Outputs a default mysql datetime formatted string.
	 * @return string
	 */
	public function __toString(){
		return $this->format('Y-m-d H:i:s');
	}
	
	/**
	 * Modifies the time of this object, if a mysql TIME valid format is provided (e.g. 14:30:00).
	 * Returns EM_DateTime object in all cases, but $this->valid will be set to false if unsuccessful
	 * @param string $hour
	 * @return EM_DateTime Returns object for chaining.
	 */
	public function setTimeString( $hour ){
		if( preg_match('/^\d{2}:\d{2}:\d{2}$/', $hour) ){
			$time = explode(':', $hour);
			$this->setTime($time[0], $time[1], $time[2]);
		}else{
			$this->valid = false;
		}
		return $this;
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * Sets timestamp and returns EM_DateTime object in all cases, but $this->valid will be set to false if unsuccessful
	 * @param int $timestamp
	 * @see DateTime::setTimestamp()
	 * @return EM_DateTime
	 */
	public function setTimestamp( $timestamp ){
		$return = parent::setTimestamp( $timestamp );
		$this->valid = $return !== false;
		return $this;
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * Extends DateTime functionality by accepting a false or string value for a timezone. If set to false, default WP timezone will be used.
	 * Returns EM_DateTime object in all cases, but $this->valid will be set to false if unsuccessful
	 * @param string|false $timezone
	 * @see DateTime::setTimezone()
	 * @return EM_DateTime Returns object for chaining.
	 */
	public function setTimezone( $timezone = false ){
		if( $timezone == $this->getTimezone()->getName() ) return $this;
		$timezone = EM_DateTimeZone::create($timezone);
		$return = parent::setTimezone($timezone);
		$this->timezone_name = $timezone->getName();
		$this->timezone_utc = $timezone->utc_offset !== false;
		$this->valid = $this->valid && $return !== false; // only ever valid if previously valid
		return $this;
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * Sets time along and returns EM_DateTime object in all cases, but $this->valid will be set to false if unsuccessful
	 * {@inheritDoc}
	 * @see DateTime::setTime()
	 */
	public function setTime( $hour, $minute, $second = NULL, $microseconds = NULL ){
		$return = parent::setTime( (int) $hour, (int) $minute, (int) $second );
		$this->valid = $return !== false;
		return $this;
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * Sets date along and returns EM_DateTime object in all cases, but $this->valid will be set to false if unsuccessful
	 * {@inheritDoc}
	 * @see DateTime::setDate()
	 */
	public function setDate( $year, $month, $day ){
		$return = parent::setDate( $year, $month, $day );
		$this->valid = $return !== false;
		return $this;
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * Returns EM_DateTime object in all cases, but $this->valid will be set to false if unsuccessful
	 * {@inheritDoc}
	 * @see DateTime::setISODate()
	 */
	public function setISODate( $year, $week, $day = NULL ){
		$return = parent::setISODate( $year, $week, $day );
		$this->valid = $return !== false;
		return $this;
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * Returns EM_DateTime object in all cases, but $this->valid will be set to false if unsuccessful
	 * {@inheritDoc}
	 * @see DateTime::modify()
	 * @noinspection \PhpDocRedundantThrowsInspection
	 */
	public function modify( $modifer ){
		try {
			$result = parent::modify($modifer);
			$this->valid = $result !== false;
		} catch ( Exception $e ) {
			$this->valid = false;
		}
		return $this;
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * Extends DateTime function to allow string representation of argument passed to create a new DateInterval object.
	 * Returns EM_DateTime object in all cases, but $this->valid will be set to false if unsuccessful
	 * @see DateTime::add()
	 * @param string|DateInterval $DateInterval
	 * @return EM_DateTime Returns object for chaining.
	 * @throws Exception
	 */
	public function add( $DateInterval ){
		if( is_object($DateInterval) ){
			$result = parent::add($DateInterval);
		} else {
			if ( $DateInterval[0] !== 'P' ) {
				$DateInterval = 'P' . $DateInterval;
			}
			$result = parent::add( new DateInterval($DateInterval) );
		}
		$this->valid = $result !== false;
		return $this;
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * Extends DateTime function to allow string representation of argument passed to create a new DateInterval object.
	 * Returns EM_DateTime object in all cases, but $this->valid will be set to false if unsuccessful
	 * @see DateTime::sub()
	 * @param string|DateInterval $DateInterval
	 * @return EM_DateTime
	 * @throws Exception
	 */
	public function sub( $DateInterval ){
		if( is_object($DateInterval) ){
			$result = parent::sub($DateInterval);
		}else{
			$result = parent::sub( new DateInterval($DateInterval) );
		}
		$this->valid = $result !== false;
		return $this;
	}
	
	/**
	 * @return EM_DateTime
	 * @throws Exception
	 */
	public function setStartOfWeek(){
		$day = $this->format('w');
		$start_of_week = em_get_option('start_of_week');
		$offset = $day - $start_of_week;
		if( $offset<0) {
			$offset += 7;
		}
		if( $offset > 0 ) {
			$this->sub( 'P' . $offset . 'D' );
		}
		return $this;
	}
	
	/**
	 * Sets the date to the first day of the current month
	 * @return EM_DateTime Returns object for chaining.
	 */
	public function setStartOfMonth () {
		$this->setDate( $this->format( 'Y' ), $this->format( 'm' ), 1 );
		return $this;
	}

	/**
	 * Sets the date to the last day of the current month
	 * @return EM_DateTime Returns object for chaining.
	 */
	public function setEndOfMonth () {
		$this->setDate( $this->format( 'Y' ), $this->format( 'm' ), $this->format( 't' ) );

		return $this;
	}


	/**
	 * Easy chainable cloning function, useful for situations where you may want to manipulate the current date,
	 * such as adding a month and getting the DATETIME string without changing the original value of this object.
	 * @return EM_DateTime
	 */
	public function copy(){
		return clone $this;
	}
	
	/**
	 * Gets a timestamp with an offset, which will represent the local time equivalent in UTC time.
	 * If using this to supply to a date() function, set $server_localized to true which will account for any rogue code
	 * that sets the server default timezone to something other than UTC (which is WP sets it to at the start)
	 * @param boolean $server_localized
	 * @return int
	 */
	public function getTimestampWithOffset( $server_localized = false ){
		//aside from the actual offset from the timezone, we also have a local server offset we need to deal with here...
		$server_offset = $server_localized ? date('Z',$this->getTimestamp()) : 0;
		return $this->getOffset() + $this->getTimestamp() - $server_offset;
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * Returns an EM_DateTimeZone object instead of the default DateTimeZone object.
	 * @see DateTime::getTimezone()
	 * @return EM_DateTimeZone
	 */
	public function getTimezone(){
		return new EM_DateTimeZone($this->timezone_name);
	}
	
	/**
	 * Returns a MySQL TIME formatted string, with the option of providing the UTC equivalent.
	 * @param bool $utc If set to true a UTC relative time will be provided.
	 * @return string
	 */
	public function getTime( $utc = false ){
		if( $utc ){
			$current_timezone = $this->getTimezone()->getName();
			$this->setTimezone('UTC');
		}
		$return = $this->format('H:i:s');
		if( $utc ) $this->setTimezone($current_timezone);
		return $return;
	}
	
	/**
	 * Returns a MySQL DATE formatted string. If a timezone name is supplied, the date returned will be relative to that timezone.
	 *
	 * For example, if you have a date 2000-01-01 20:00:00 UTC and provide America/Los_Angeles, the date will be 2000-01-02 because it's 2am next day UTC-time.
	 *
	 * @param bool|string $timezone
	 * @return string
	 */
	public function getDate( $timezone = null ){
		return $this->format('Y-m-d', $timezone);
	}
	
	/**
	 * Returns a MySQL DATETIME formatted string. If a timezone name is supplied, the date returned will be relative to that timezone.
	 *
	 * For example, if you have a date 2000-01-01 20:00:00 UTC and provide America/Los_Angeles, the date will be 2000-01-02 because it's 2am next day UTC-time.
	 *
	 * @return string
	 */
	public function getDateTime( $timezone = null ){
		$return = $this->format('Y-m-d H:i:s', $timezone);
		return $return;
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * Extends the DateTime::createFromFormat() function by setting the timezone to the default blog timezone if none is provided.
	 * @param string $format
	 * @param string $time
	 * @param string|EM_DateTimeZone $timezone
	 * @return false|EM_DateTime
	 */
	public static function createFromFormat( $format, $time, $timezone = null ){
		$timezone = EM_DateTimeZone::create($timezone);
		$DateTime = parent::createFromFormat($format, $time, $timezone);
		if( $DateTime === false ) return false;
		return new EM_DateTime($DateTime->format('Y-m-d H:i:s'), $timezone);
	}
	
	/**
	 * Gets a set of start/end dates for the relative week of this $EM_DateTime, until the day before the starting weekday as per WP Settings.
	 *
	 * Accepts two scopes for $scope, both which calculate relative dates until the day before next start day of week.:
	 * 'this-week' - events for the rest of the week starting 'today'
	 * 'week' - events from start of relative week since previous start day of week
	 *
	 * @param string $scope
	 * @return string[]
	 */
	public function get_week_dates( $scope = 'week' ) {
		$start_of_week = em_get_option('start_of_week');
		$days_of_week = array( 0 => 'Sunday', 1 => 'Monday', 2 => 'Tuesday', 3 => 'Wednesday', 4 => 'Thursday', 5 => 'Friday', 6 => 'Saturday');
		$EM_DateTime = $this->copy(); // so we don't modify this $EM_DateTime
		$today_day_of_week = $EM_DateTime->format('w');
		$end_of_week = $start_of_week > 0 ? $start_of_week-1 : 6;
		$end_of_week_name = $days_of_week[$end_of_week];
		// get stat date, either today if it's start of week or 'this-week' scope, or the previous start day of week
		if( $scope == 'this-week' || $today_day_of_week == $start_of_week ){
			$start_date = $EM_DateTime->getDate();
		}else{
			$start_of_week_name = $days_of_week[$start_of_week];
			$start_date = $EM_DateTime->modify('last '. $start_of_week_name)->getDate();
		}
		$end_date = $start_date; // set as today in event it's the last day of week
		if( $scope == 'week' || $today_day_of_week != $end_of_week ){
			// if we're looking for whole week, $EM_DateTime is set to start of week, so get relative end of week even if it's today
			$end_date = $EM_DateTime->modify('next '. $end_of_week_name)->getDate();
		}
		return array($start_date, $end_date);
	}
}