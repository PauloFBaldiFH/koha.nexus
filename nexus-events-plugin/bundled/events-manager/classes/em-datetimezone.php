<?php
/**
 * Extends the native DateTimeZone object by allowing for UTC manual offsets as supported by WordPress, along with eash creation of a DateTimeZone object with the blog's timezone.
 * @since 5.8.2
 */
class EM_DateTimeZone extends DateTimeZone {
	
	public $utc_offset = false;
	
	public function __construct( $timezone ){
		//if we're not suppiled a DateTimeZone object, create one from string or implement manual offset
		if( $timezone != 'UTC' ){
			$timezone = preg_replace('/^UTC ?/', '', $timezone);
			if( is_numeric($timezone) ){
				if( absint($timezone) == 0 ){
					$timezone = 'UTC';
				}else{
					// convert this to an offset, taken from wp_timezone
					$offset  = (float) $timezone;
					$hours   = (int) $offset;
					$minutes = ( $offset - $hours );
					$sign      = ( $offset < 0 ) ? '-' : '+';
					$abs_hour  = abs( $hours );
					$abs_mins  = abs( $minutes * 60 );
					$timezone = sprintf( '%s%02d%02d', $sign, $abs_hour, $abs_mins );
				}
			}
		}
		parent::__construct($timezone);
	}
	
	/**
	 * Special function which converts a timezone string, UTC offset or DateTimeZone object into a valid EM_DateTimeZone object.
	 * If no value supplied, a EM_DateTimezone with the default WP environment timezone is created.
	 * @param mixed $timezone
	 * @return EM_DateTimeZone
	 */
	public static function create( $timezone = false ){
		//if we're not suppiled a DateTimeZone object, create one from string or implement manual offset
		if( !empty($timezone) && !is_object($timezone) ){
			//create EM_DateTimeZone object if valid, otherwise allow defaults to override later
			try {
				$timezone = new EM_DateTimeZone($timezone);
			}catch( Exception $e ){
				$timezone = null;
			}
		}elseif( is_object($timezone) && get_class($timezone) == 'DateTimeZone'){
			//if supplied a regular DateTimeZone, convert it to EM_DateTimeZone
			$timezone = new EM_DateTimeZone($timezone->getName());
		}
		if( !is_object($timezone) ){
			//if no valid timezone supplied, get the default timezone in EM environment, otherwise the WP timezone or offset
			$timezone = get_option( 'timezone_string' );
			if( !$timezone ) $timezone = get_option('gmt_offset');
			$timezone = new EM_DateTimeZone($timezone);
		}
		return $timezone;
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * {@inheritDoc}
	 * @see DateTimeZone::getName()
	 */
	public function getName(){
		if( $this->isUTC() ){
			return 'UTC'.parent::getName();
		}
		return parent::getName();
	}

	/**
	 * Gets the name of the city this timezone is in, without the continent, e.g. Europe/Madrid returns just 'Madrid'
	 * @return string
	 */
	public function getCity(){
		$name = $this->getName();
		if( !$this->isUTC() ){
			$names = explode('/', $name);
			$name = array_pop($names);
		}
		return $name;
	}
	
	public function isUTC(){
		$name = parent::getName();
		return $name[0] === '-' || $name[0] === '+';
	}
	
	/**
	 * Returns WP-friendly timezone value, which accounts for UTC offsets and modifies accoridnly so that minute offsets also work.
	 * @return string
	 */
	public function getValue(){
		if( $this->isUTC() ){
			$time = explode(':', parent::getName());
			if( !empty($time[1]) ){
				$mins = $time[1] / 60;
				$hours = (int) $time[0];
				if( $hours > 0 ){
					$time_int = '+' . ($hours + $mins);
				}else{
					$time_int = $hours - $mins;
				}
				return 'UTC'.$time_int;
			}
		}
		return $this->getName();
	}
	
	#[\ReturnTypeWillChange]
	/**
	 * If the timezone has a manual UTC offset, then an empty array of transitions is returned.
	 * {@inheritDoc}
	 * @see DateTimeZone::getTransitions()
	 */
	public function getTransitions( $timestamp_begin = 0, $timestamp_end = 0 ){
		if( $timestamp_end === 0 ) $timestamp_end = time() * YEAR_IN_SECONDS;
		if( $this->utc_offset !== false ){
			return array();
		}
		return parent::getTransitions($timestamp_begin, $timestamp_end);
	}
}