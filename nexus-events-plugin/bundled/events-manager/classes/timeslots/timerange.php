<?php
namespace EM;
use EM_Object;

/**
 * Timerange class
 *
 * @property int $id
 * @property string $group_id
 * @property string $start
 * @property string $end
 * @property int $all_day
 * @property string $frequency
 * @property string $buffer
 * @property string $duration
 */
class Timerange extends EM_Object {

	protected $table = 'em_timeranges';
	protected $id_field = 'timerange_id';

	public $timerange_id;
	public $timerange_group_id;
	public $timerange_start = '00:00:00';
	public $timerange_end = '00:00:00';
	public $timerange_all_day = 0;
	public $timeslot_frequency;
	public $timeslot_buffer;
	public $timeslot_duration;

	/**
	 * Field definitions mapping to database columns.
	 */
	public $fields = array(
		'timerange_id' => array('type' => '%d', 'null' => true),
		'timerange_group_id' => array('type' => '%s', 'null' => false),
		'timerange_start' => array('type' => '%s', 'null' => false),
		'timerange_end' => array('type' => '%s', 'null' => false),
		'timerange_all_day' => array('type' => '%d', 'null' => false),
		'timeslot_frequency' => array('type' => '%s', 'null' => true),
		'timeslot_buffer' => array('type' => '%s', 'null' => true),
		'timeslot_duration' => array('type' => '%s', 'null' => true),
	);

	/**
	 * Field shortcuts for external API references.
	 */
	public static $field_shortcuts = array(
		'id' => 'timerange_id',
		'group_id' => 'timerange_group_id',
		'start' => 'timerange_start',
		'end' => 'timerange_end',
		'all_day' => 'timerange_all_day',
		'frequency' => 'timeslot_frequency',
		'buffer' => 'timeslot_buffer',
		'duration' => 'timeslot_duration',
	);

	/**
	 * @var bool Whether to allow timeslots within time ranges in this collection.
	 */
	public $allow_timeslots = true;

	/**
	 * Constructor: Initializes the timerange, loading data if an ID is provided.
	 * 
	 * @param mixed $data Either a timerange_id to fetch from DB, an array of timerange data, or a timerange object
	 */
	public function __construct($data = false) {
		global $wpdb;

		if( is_array($data) ){
			$this->to_object($data);
		}elseif( is_numeric($data) && $data > 0 ){
			$this->timerange_id = absint($data);
			$sql = $wpdb->prepare("SELECT * FROM " . EM_TIMERANGES_TABLE . " WHERE timerange_id = %d", $this->timerange_id);
			$result = $wpdb->get_row($sql, ARRAY_A);
			if( $result ){
				$this->to_object($result);
			}
		}elseif( is_object($data) && get_class($data) == 'EM\Timerange' ){
			$this->to_object($data->to_array());
		}

		// Set defaults
		foreach($this->get_defaults() as $key => $default){
			if( empty($this->$key) && $this->$key !== 0 ){
				$this->$key = $default;
			}
		}

		// Type casting
		if( $this->timerange_id ) $this->timerange_id = absint($this->timerange_id);
		$this->timerange_all_day = (bool) $this->timerange_all_day;
	}

	public function get_timeslot( $data ) {
		return new Timeslot( $data );
	}

	public function get_defaults() {
		return array(
			'timerange_start' => '00:00:00',
			'timerange_end' => '23:59:59',
			'timerange_all_day' => 0,
			'timeslot_frequency' => '',
			'timeslot_buffer' => '',
			'timeslot_duration' => '',
			'timerange_group' => '',
		);
	}

	/**
	 * Retrieve timerange information via POST
	 * @param array $post $POST data
	 * @return boolean
	 */
	public function get_post( $post ) {
		do_action('em_timerange_get_post_pre', $this);

		if ( isset($post['all_day']) ) {
			$this->timerange_all_day = true;
			$this->timerange_start = '00:00:00';
			$this->timerange_end = '23:59:59';
		} else {
			$this->timerange_all_day = 0;
			foreach( ['start', 'end'] as $timeName ){
				$match = array();
				if( !empty($post[$timeName]) && preg_match ( '/^([01]\d|[0-9]|2[0-3])(:([0-5]\d))?(?::[0-5]\d)? ?(AM|PM)?$/', $post[$timeName], $match ) ){
					if( empty($match[3]) ) $match[3] = '00';
					if( strlen($match[1]) == 1 ) $match[1] = '0'.$match[1];
					if( !empty($match[4]) && $match[4] == 'PM' && $match[1] != 12 ){
						$match[1] = 12+$match[1];
					}elseif( !empty($match[4]) && $match[4] == 'AM' && $match[1] == 12 ){
						$match[1] = '00';
					}
					$this->$timeName = $match[1].":".$match[3].":00";
				}else{
					$this->$timeName = ($timeName == 'start') ? "00:00:00":$this->timerange_start;
				}
			}
		}

		// Advanced rules - only process if enabled
		if ( !empty($post['timeslots']) ) {
			foreach ( ['frequency', 'buffer', 'duration'] as $field ) {
				if (isset($post[$field])) {
					$qty = absint($post[$field]['qty']);
					$unit = $post[$field]['unit'];
					$field = 'timeslot_' . $field;
					$this->$field = $qty ? $qty . $unit : null;
				}
			}
		} else {
			// Clear advanced rules if not enabled
			$this->timeslot_frequency = null;
			$this->timeslot_buffer = null;
			$this->timeslot_duration = null;
		}

		return apply_filters('em_timerange_get_post', true, $this);
	}

	/**
	 * Validate timerange data
	 * @return boolean
	 */
	public function validate() {
		do_action( 'em_timerange_validate_pre', $this );

		// Required field validation
		if ( empty( $this->timerange_start ) ) {
			$this->add_error( __( 'Start time is required.', 'events-manager' ) );
		}

		if ( empty( $this->timerange_end ) ) {
			$this->add_error( __( 'End time is required.', 'events-manager' ) );
		}

		// Validate frequency format
		foreach ( [ 'timeslot_frequency', 'timeslot_buffer', 'timeslot_duration' ] as $field ) {
			if ( !empty( $this->$field ) && !preg_match( '/^[0-9]+[HMS]*$/', $this->$field ) ) {
				$this->add_error( sprintf( __( 'Invalid interval format for %s', 'events-manager' ), $field ) );
			}
		}

		return apply_filters( 'em_timerange_validate', !$this->errors, $this );
	}

	/**
	 * Save the timerange to the database
	 * @return boolean
	 */
	public function save() {
		global $wpdb;

		if ( !$this->can_manage( 'edit_events', 'edit_others_events' ) ) {
			return apply_filters( 'em_timerange_save', false, $this );
		}

		do_action( 'em_timerange_save_pre', $this );

		// Prepare data for database
		$data = $this->to_array( true );
		unset( $data['timerange_id'] ); // Remove ID for insert/update determination

		$formats = array ();
		foreach ( $this->fields as $field => $field_info ) {
			if ( $field !== 'timerange_id' ) {
				$formats[] = $field_info['type'];
			}
		}

		if ( !empty( $this->timerange_id ) ) {
			// Update existing timerange
			$result = $wpdb->update( EM_TIMERANGES_TABLE, $data, array ( 'timerange_id' => $this->timerange_id ), $formats, array ( '%d' ) );
			if ( $result !== false ) {
				$this->feedback_message = sprintf( __( 'Successfully updated %s', 'events-manager' ), __( 'Timerange', 'events-manager' ) );
			}
		} else {
			// Insert new timerange
			$result = $wpdb->insert( EM_TIMERANGES_TABLE, $data, $formats );
			if ( $result !== false ) {
				$this->timerange_id = $wpdb->insert_id;
				$this->feedback_message = sprintf( __( 'Successfully saved %s', 'events-manager' ), __( 'Timerange', 'events-manager' ) );
			}
		}

		if ( $result === false ) {
			$this->add_error( __( 'There was a problem saving the timerange.', 'events-manager' ) );
		}

		return apply_filters( 'em_timerange_save', $result !== false, $this );
	}

	/**
	 * Delete the timerange from the database
	 * @return boolean
	 */
	public function delete() {
		global $wpdb;
		do_action('em_timerange_delete_pre', $this);

		$result = $wpdb->delete(
			EM_TIMERANGES_TABLE, 
			array('timerange_id' => $this->timerange_id), 
			array('%d')
		);

		if ($result === false) {
			$this->add_error(__('There was a problem deleting the timerange.', 'events-manager'));
		}

		return apply_filters('em_timerange_delete', $result !== false, $this);
	}

	/**
	 * Check if user can manage this timerange
	 * @param string $owner_capability
	 * @param string $admin_capability  
	 * @param mixed $user_to_check
	 * @return boolean
	 */
	public function can_manage($owner_capability = 'edit_events', $admin_capability = 'edit_others_events', $user_to_check = false) {
		return apply_filters('em_timerange_can_manage', parent::can_manage($owner_capability, $admin_capability, $user_to_check), $this, $owner_capability, $admin_capability, $user_to_check);
	}

	/**
	 * Convert timerange to array
	 * @param boolean $db whether this is for database operations
	 * @return array
	 */
	public function to_array($db = false) {
		$timerange_array = array();
		foreach($this->fields as $field => $field_info) {
			$timerange_array[$field] = $this->$field;
		}

		// Handle null values for database
		if ($db) {
			foreach($timerange_array as $field => $value) {
				if ($this->fields[$field]['null'] && empty($value) && $value !== 0) {
					$timerange_array[$field] = null;
				}
			}
		}

		return apply_filters('em_timerange_to_array', $timerange_array, $this);
	}

	/**
	 * Check if this timerange is all day
	 * @return boolean
	 */
	public function is_all_day() {
		return !empty($this->timerange_all_day);
	}

	/**
	 * Get formatted start time
	 * @param string $format
	 * @return string
	 */
	public function get_start_time( $format = null ) {
		if (!$format) {
			$format = get_option('time_format');
		}
		return date($format, strtotime('1970-01-01 ' . $this->timerange_start));
	}

	/**
	 * Get formatted end time
	 * @param string $format
	 * @return string
	 */
	public function get_end_time( $format = null ) {
		if (!$format) {
			$format = get_option('time_format');
		}
		return date($format, strtotime('1970-01-01 ' . $this->timerange_end));
	}

	/**
	 * Get formatted time range
	 * @param string $format
	 * @param string $separator
	 * @return string
	 */
	public function get_time_range( $format = null, $separator = ' - ' ) {
		if ($this->is_all_day()) {
			return __('All Day', 'events-manager');
		}
		return $this->get_start_time($format) . $separator . $this->get_end_time($format);
	}

	/*
	 * Timerange generation/interpretation functions
	 */

	/**
	 * Generates an array of Timeslot objects based on current timerange rules.
	 * @return Timeslot[]
	 */
	public function get_timeslots() {
		if ( $this->has_timeslot_rules()  ) {
			$timeslots = $this->generate_timeslots();
		} else {
			$timeslots = [ $this->get_timeslot( [ 'start' => $this->timerange_start, 'end' => $this->timerange_end, 'timerange_id' => $this->timerange_id ] ) ];
		}
		return $timeslots;
	}

	public function has_timeslots() {
		if ( $this->has_timeslot_rules()  ) {
			$timeslots = $this->generate_timeslots_data();
		}
		return count( $timeslots ?? [] ) > 1;
	}

	public function has_timeslot_rules() {
		return !empty($this->timeslot_frequency) || !empty($this->timeslot_buffer) || !empty($this->timeslot_duration);
	}

	/**
	 * Generates sequential slot start times within this timerange window as integer seconds since midnight.
	 *
	 * @return Timeslot[]
	 */
	public function generate_timeslots() {
		$timeslots = $this->generate_timeslots_data();
		$slots = [];
		foreach ( $timeslots as $slot ) {
			$slots[] = $this->get_timeslot( $slot );
		}
		return $slots;
	}

	/**
	 * Genearates array of timeslots in array format for use to create Timeslot objects, or for counting/previewing.
	 * @return array
	 */
	public function generate_timeslots_data() {
		$startMinutes = $this->timeTimestamp($this->timerange_start);
		$endMinutes = $this->timeTimestamp($this->timerange_end);

		$duration = $this->intervalTimestamp($this->timeslot_duration);
		$buffer = $this->intervalTimestamp($this->timeslot_buffer);
		$frequency = $this->intervalTimestamp($this->timeslot_frequency);

		$slots = [];

		if ($endMinutes >= $startMinutes) {
			$currentStart = $startMinutes;

			if ($currentStart == $endMinutes) {
				$slots[] = [ 'start' => $currentStart, 'end' => $currentStart, 'timerange_id' => $this->timerange_id, ];
			} else {
				$interval = $frequency > 0 ? $frequency : ($duration > 0 ? ($duration + $buffer) : 0);
				if ($interval <= 0) $interval = $endMinutes; // prevent infinite loop

				for ($i = 0; $currentStart < $endMinutes; $i++) {
					$slots[] = [
						'start' => $currentStart,
						'end' => $duration > 0 ? $currentStart + $duration : $endMinutes,
						'timerange_id' => $this->timerange_id,
					];
					$currentStart += $interval;
				}
			}
		}
		return $slots;
	}

	/**
	 * Get time value in appropriate units
	 * @param string $field Field name (frequency/buffer/duration)
	 * @return array Array with 'value' and 'unit' keys
	 */
	public function get_time_value ( $field ) {
		$field_name = 'timeslot_' . $field;

		// Parse the time string (e.g. "30I" or "1H")
		preg_match( '/(\d+)([HMS])/', $this->$field_name, $matches );
		if ( empty( $matches ) ) {
			return array ( 'value' => 0, 'unit' => 'minutes' );
		}

		return array (
			'value' => $matches[1],
			'unit' => $matches[2]
		);
	}

	/**
	 * Parses a time in "HH:MM[:SS]" format and returns number of minutes since midnight.
	 * @param string $time
	 * @return int
	 */
	protected function timeTimestamp ( $time ) {
		$parts = explode(':', $time);
		$hours = isset($parts[0]) ? intval($parts[0]) : 0;
		$minutes = isset($parts[1]) ? intval($parts[1]) : 0;
		return ( $hours * 3600 ) + ( $minutes * 60 );
	}

	/**
	 * Parse interval string (like "30I", "1H", "15S") to minutes.
	 * Returns 0 if not set or invalid.
	 * @param string $interval
	 * @return int
	 */
	protected function intervalTimestamp ( $interval ) {
		if (empty($interval)) return 0;
		if (is_numeric($interval)) return intval($interval); // for simple numbers
		$totalSeconds = 0;
		preg_match_all('/(\d+)([HMS])/', $interval, $matches, PREG_SET_ORDER);
		foreach ($matches as $m) {
			$value = intval($m[1]);
			$unit = isset($m[2]) ? $m[2] : 'I';
			switch($unit) {
				case 'H': $totalSeconds += $value * 3600; break;
				case 'M': $totalSeconds += $value * 60; break;
				case 'S': $totalSeconds += $value; break;
				default:  $totalSeconds += $value * 60; // fallback to minutes
			}
		}
		return (int) $totalSeconds;
	}


	/**
	 * Convert to API format
	 * @return array
	 */
	public function to_api() {
		$api_data = array(
			'id' => $this->timerange_id,
			'group' => $this->timerange_group,
			'start' => $this->timerange_start,
			'end' => $this->timerange_end,
			'all_day' => (bool) $this->timerange_all_day,
			'frequency' => $this->timeslot_frequency,
			'buffer' => $this->timeslot_buffer,
			'duration' => $this->timeslot_duration,
		);

		return apply_filters('em_timerange_to_api', $api_data, $this);
	}
	
	
}