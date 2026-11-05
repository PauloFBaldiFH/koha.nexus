<?php

namespace EM;

/**
 * Collection class for managing multiple Timerange objects.
 * Provides traversable, searchable functionality similar to Recurrence_Sets.
 *
 * @property int $length The number of timeranges in this collection.
 */
class Timeranges extends \EM_Object implements \Iterator, \ArrayAccess, \Countable {

	/**
	 * @var Timerange[] Array of Timerange objects
	 */
	public $timeranges = [];

	/**
	 * @var string The group ID these timeranges belong to
	 */
	public $group_id;

	/**
	 * @var array Timeranges that have been marked for deletion
	 */
	public $deleted_timeranges = [];

	/**
	 * @var bool Whether this collection allows more than one timerange.
	 */
	public $allow_timeranges = true;

	/**
	 * @var string The action to take when deleting a timerange, which is usually connected to associated events, bookings, etc.
	 */
	public $allow_edit = true;

	/**
	 * @var string The action to take when deleting a timerange, which is usually connected to associated events, bookings, etc.
	 */
	public $delete_action = 'cancel';

	/**
	 * @var Timeslot[] Array of timeslots generated from this collection
	 */
	public $generated_timeslots = [];

	/**
	 * Constructor to initialize the Timeranges collection.
	 * 
	 * @param string|null $group_id The group ID to load timeranges for
	 */
	public function __construct( $group_id = null ) {
		$this->group_id = $group_id;
	}

	/**
	 * Sets the group id of this set and recursively sets each group id in the timeranges
	 * @param $group_id
	 *
	 * @return void
	 */
	public function set_group_id( $group_id ) {
		$this->group_id = $group_id;
		foreach ( $this->timeranges as $Timerange ) {
			$Timerange->timerange_group_id = $group_id;
		}
	}

	/**
	 * @param $data
	 *
	 * @return Timerange
	 */
	public function get_timerange( $data = false ) {
		return new Timerange( $data );
	}

	/**
	 * Load timeranges from database for given group ID
	 */
	protected function load_timeranges( $padding = false ) {
		global $wpdb;
		if ( !$this->timeranges && $this->group_id ) {
			// Use the constant if available, otherwise construct table name
			$sql = $wpdb->prepare("SELECT * FROM ". EM_TIMERANGES_TABLE ." WHERE timerange_group_id = %s ORDER BY timerange_start ASC", $this->group_id);
			$timeranges_data = $wpdb->get_results($sql, ARRAY_A);

			foreach ($timeranges_data as $timerange_data) {
				$Timerange = $this->get_timerange($timerange_data);
				$this->timeranges[ $Timerange->timerange_id ] = $Timerange;
			}
		}
		if ( empty( $this->timeranges ) && $padding ) {
			$this->timeranges = [ $this->get_timerange() ];
		}
		return $this->timeranges;
	}

	public function get_timeranges( $padding = false ) {
		$this->load_timeranges( $padding );
		return $this->timeranges;
	}

	/**
	 * Return array of timeslots, in seconds since midnight for a day based on timerange rules in this set.
	 * @return Timeslot[]
	 */
	public function get_timeslots() {
		return $this->generate_timeslots();
	}

	/**
	 * Generates an array of timeslots, in minutes since midnight for a day based on timerange rules in this set.
	 * @param $reload
	 * @return Timeslot[]
	 */
	public function generate_timeslots( $reload = false ) {
		if ( !$this->generated_timeslots || $reload ) {
			$this->generated_timeslots = [];
			foreach ( $this->get_timeranges() as $timerange ) {
				$this->generated_timeslots = array_merge( $this->generated_timeslots, $timerange->generate_timeslots() );
			}
			// Remove duplicate start timeslots
			foreach ($this->generated_timeslots as $key1 => $Timeslot) {
				foreach ( $this->generated_timeslots as $key2 => $_Timeslot ) {
					// We only compare items that are after the current item in the array, given this is a numerically key-ordered array
					if ( $key1 < $key2 ) {
						if ( $Timeslot->start === $_Timeslot->start ) {
							unset( $this->generated_timeslots[ $key2 ] );
						}
					}
				}
			}
			// Re-index the array after removing elements with unset().
			$this->generated_timeslots = array_values($this->generated_timeslots);
		}
		return $this->generated_timeslots;
	}

	/**
	 * Gets the earliest time in the collection, in HH:MM:SS format or in WP localized format if $format is set to true
	 *
	 * @param bool $format
	 * @return string
	 */
	public function get_time_start( $format = false ) {
		$earliest_time = null; // latest is 24h
		foreach ( $this->get_timeranges() as $Timerange ) {
			$hour_start = $Timerange->timerange_start;
			$ts_start = strtotime('1970-01-01 ' . $hour_start);
			if ( $earliest_time === null || $ts_start < $earliest_time ) {
				$earliest_time = $ts_start;
			}
		}
		$date_format = $format ?: 'H:i:s';
		return date($date_format, $earliest_time ?? 0);
	}

	public function get_time_end( $format = false ) {
		$latest = null; // latest is 24h
		foreach ( $this->get_timeranges() as $timerange ) {
			$hour_start = $timerange->timerange_end;
			$ts_end = strtotime('1970-01-01 ' . $hour_start);
			if ( $ts_end > $latest ) {
				$latest = $ts_end;
			}
		}
		$date_format = $format ?: 'H:i:s';
		return date($date_format, $latest ?? 0);

	}

	public function is_all_day() {
		if ( $this->count() == 1 ) {
			foreach ( $this->get_timeranges() as $timerange ) {
				if ( $timerange->timerange_all_day ) {
					return true;
				}
			}
		}
		return false;
	}

	public function get_time_from_minutes( $minutes ) {
		return date('H:i:s', $minutes * 60 );
	}

	/**
	 * Static method to get timeranges data from database
	 *
	 * @return array
	 */
	public function get() {
		return $this->get_timeranges();
	}

	/**
	 * Add a new timerange to the collection
	 * 
	 * @param Timerange|array $timerange
	 * @return bool
	 */
	public function add($timerange) {
		if ( is_array($timerange) ) {
			$timerange = new Timerange($timerange);
		}

		if ( $timerange instanceof Timerange ) {
			$timerange->timerange_group_id = $this->group_id;
			$this->timeranges[] = $timerange;
			return true;
		}

		return false;
	}

	/**
	 * Remove a timerange from the collection
	 * 
	 * @param int|Timerange $timerange_id_or_object
	 * @return boolean
	 */
	public function remove( $timerange_id_or_object ) {
		$timerange_id = is_object($timerange_id_or_object) ? $timerange_id_or_object->timerange_id : $timerange_id_or_object;

		foreach ($this->timeranges as $key => $timerange) {
			if ($timerange->timerange_id == $timerange_id) {
				$this->deleted_timeranges[] = $timerange;
				unset($this->timeranges[$key]);
				// Reindex array
				$this->timeranges = array_values($this->timeranges);
				return true;
			}
		}
		return false;
	}

	/**
	 * Get POST data for all timeranges in the collection
	 *
	 * @param string|array $post_name
	 * @return boolean
	 */
	public function get_post( $post_name = 'timeranges' ) {
		do_action('em_timeranges_get_post_pre', $this);

		$result = true;
		$post_array = is_array( $post_name ) ? $post_name : $_POST[ $post_name ] ?? [];

		if ( !$this->group_id || $this->allow_edit || wp_verify_nonce( $post_array['edit_nonce'] ?? '', 'em_timeranges_edit_' . $this->group_id ) ) {
			$this->allow_edit = true;
			if ( is_array( $post_name ) || ( !empty( $_POST[ $post_name ] ) && is_array( $_POST[ $post_name ] ) ) ) {
				$this->load_timeranges();
				// remove default timerange
				if ( !empty($this->timeranges[0]) ) {
					unset( $this->timeranges[0] );
				}
				// add or update timeranges
				// A form rendered before this group had stored rows posts its entries with no timerange_id, so an id-less entry is matched positionally against whichever rows no other entry claimed. Appending it instead leaves a spurious extra timerange, which either trips the overlap validator or sends save() down the branch that drops the group's stored rows. Rows already marked for deletion are excluded so that deleting and re-adding in one submission cannot claim the row being deleted.
				$claimable = [];
				foreach ( $this->timeranges as $timerange_id => $Timerange ) {
					if ( empty( $post_array['delete'][ $timerange_id ] ) ) {
						$claimable[] = $timerange_id;
					}
				}
				foreach ( $post_array as $key => $timerange_data ) {
					if ( $key !== 'edit_nonce' && $key !== 'delete' ) {
						if ( isset( $timerange_data['timerange_id'] ) && array_key_exists( $timerange_data['timerange_id'], $this->timeranges ) ) {
							$Timerange = $this->timeranges[ $timerange_data['timerange_id'] ];
							$claimable = array_diff( $claimable, [ $timerange_data['timerange_id'] ] );
							// check for edit nonce or delete nonce
						} elseif ( empty( $timerange_data['timerange_id'] ) && $claimable ) {
							$Timerange = $this->timeranges[ array_shift( $claimable ) ];
						} else {
							$Timerange = $this->get_timerange( ['timerange_group_id' => $this->group_id ]);
							$this->timeranges[] = $Timerange;
						}
						$Timerange->get_post( $timerange_data );
					}
				}
				// process deleted ones and mark for deletion
				if ( !empty( $post_array['delete'] ) ) {
					foreach ( $post_array['delete'] as $timerange_id => $delete_nonce ) {
						if ( $delete_nonce && wp_verify_nonce( $delete_nonce, 'delete_timerange_' . $timerange_id ) ) {
							$this->deleted_timeranges[ $timerange_id ] = $this->timeranges[ $timerange_id ];
							unset( $this->timeranges[ $timerange_id ] );
						}
					}
				}
			}
		}

		return apply_filters('em_timeranges_get_post', $result, $this);
	}

	/**
	 * Validate all timeranges in the collection
	 * 
	 * @return boolean
	 */
	public function validate() {
		do_action('em_timeranges_validate_pre', $this);

		$result = true;

		foreach ($this->timeranges as $timerange) {
			if (!$timerange->validate()) {
				$this->add_error($timerange->get_errors());
				$result = false;
			}
		}

		// Check for overlapping timeranges (optional validation)
		if ($result && $this->has_overlapping_timeranges()) {
			$this->add_error(__('Timeranges cannot overlap with each other.', 'events-manager'));
			$result = false;
		}

		return apply_filters('em_timeranges_validate', $result, $this);
	}

	/**
	 * Check if any timeranges overlap with each other
	 * 
	 * @return boolean
	 */
	public function has_overlapping_timeranges() {
		foreach ( $this->timeranges as $i => $Timerange ) {
			foreach ( $this->timeranges as $j => $Timerange_2 ) {
				if ( $i !== $j ) {
					// If we detect an all day time range, return true as something is just wrong
					if ( $Timerange->timerange_all_day || $Timerange_2->timerange_all_day) {
						return true;
					}

					$start1 = strtotime('1970-01-01 ' . $Timerange->timerange_start);
					$end1 = strtotime('1970-01-01 ' . $Timerange->timerange_end);
					$start2 = strtotime('1970-01-01 ' . $Timerange_2->timerange_start);
					$end2 = strtotime('1970-01-01 ' . $Timerange_2->timerange_end);

					// Check for overlap, either same start time, or start/end time is within another start/end time
					if ($start1 === $start2 || ( $start1 < $end2 && $start1 > $start2 ) || ( $end1 > $start2 && $end1 < $end2 )) {
						return true;
					}
				}
			}
		}
		return false;
	}

	/**
	 * Checks all timeranges in set and returns true if at least one has timeslots
	 * @return bool
	 */
	public function has_timeslots() {
		if ( $this->count() > 1 ) {
			return true;
		} elseif ( $this->count() == 1 ) {
			return $this->get_first()->has_timeslots();
		}
		return false;
	}

	/**
	 * Save all timeranges in the collection
	 * 
	 * @return boolean
	 */
	public function save() {
		if ( $this->allow_edit ) {
			do_action( 'em_timeranges_save_pre', $this );

			$result = true;

			// Delete marked timeranges first
			foreach ( $this->deleted_timeranges as $timerange ) {
				if ( !$timerange->delete() ) {
					$this->add_error( $timerange->get_errors() );
					$result = false;
				}
			}

			// Save all timeranges
			foreach ( $this->timeranges as $timerange ) {
				if ( !$timerange->save() ) {
					$this->add_error( $timerange->get_errors() );
					$result = false;
				}
			}

			if ( $result ) {
				$this->deleted_timeranges = []; // Clear deleted list after successful save
				$this->feedback_message = sprintf( __( 'Successfully saved %d timeranges.', 'events-manager' ), count( $this->timeranges ) );
			}

			do_action( 'em_timeranges_save_post', $this, $result );

			return apply_filters( 'em_timeranges_save', $result, $this );
		}
	}

	/**
	 * Delete all timeranges in the collection
	 * 
	 * @return boolean
	 */
	public function delete() {
		do_action('em_timeranges_delete_pre', $this);

		$result = true;

		foreach ($this->timeranges as $timerange) {
			if ( !$timerange->delete() ) {
				$this->add_error($timerange->get_errors());
				$result = false;
			}
		}

		if ($result) {
			$this->timeranges = [];
			$this->feedback_message = __('Successfully deleted all timeranges.', 'events-manager');
		}

		do_action('em_timeranges_delete_post', $this, $result);

		return apply_filters('em_timeranges_delete', $result, $this);
	}

	/**
	 * Get the first timerange in the collection
	 * 
	 * @return Timerange|false
	 */
	public function get_first() {
		$this->load_timeranges();
		foreach ( $this->timeranges as $timerange ) {
			return $timerange;
		}
		return false;
	}

	/**
	 * Get the last timerange in the collection
	 * 
	 * @return Timerange|false
	 */
	public function get_last() {
		return !empty($this->timeranges) ? end($this->timeranges) : false;
	}

	/**
	 * Convert collection to API format
	 * 
	 * @return array
	 */
	public function to_api() {
		$api_data = array(
			'group_id' => $this->group_id,
			'timeranges' => array()
		);

		foreach ( $this->load_timeranges() as $timerange ) {
			$api_data['timeranges'][] = $timerange->to_api();
		}

		return apply_filters('em_timeranges_to_api', $api_data, $this);
	}

	// Iterator Implementation
	#[\ReturnTypeWillChange]
	public function rewind() {
		$this->load_timeranges();
		reset($this->timeranges);
	}

	#[\ReturnTypeWillChange]
	/**
	 * @return Timerange
	 */
	public function current() {
		$this->load_timeranges();
		return current($this->timeranges);
	}

	#[\ReturnTypeWillChange]
	public function key() {
		$this->load_timeranges();
		return key($this->timeranges);
	}

	#[\ReturnTypeWillChange]
	/**
	 * @return Timerange|false
	 */
	public function next() {
		$this->load_timeranges();
		return next($this->timeranges);
	}

	#[\ReturnTypeWillChange]
	public function valid() {
		$this->load_timeranges();
		$key = key($this->timeranges);
		return ($key !== null && $key !== false);
	}

	// ArrayAccess Implementation
	#[\ReturnTypeWillChange]
	/**
	 * @param mixed $offset
	 * @param Timerange $value
	 * @return void
	 */
	public function offsetSet($offset, $value) {
		$this->load_timeranges();
		if (is_null($offset)) {
			$this->timeranges[] = $value;
		} else {
			$this->timeranges[$offset] = $value;
		}
	}

	#[\ReturnTypeWillChange]
	public function offsetExists($offset) {
		$this->load_timeranges();
		return isset($this->timeranges[$offset]);
	}

	#[\ReturnTypeWillChange]
	public function offsetUnset($offset) {
		$this->load_timeranges();
		unset($this->timeranges[$offset]);
		// Reindex array to maintain sequential keys
		$this->timeranges = array_values($this->timeranges);
	}

	#[\ReturnTypeWillChange]
	/**
	 * @param mixed $offset
	 * @return Timerange|null
	 */
	public function offsetGet($offset) {
		$this->load_timeranges();
		return isset($this->timeranges[$offset]) ? $this->timeranges[$offset] : null;
	}

	// Countable Implementation
	#[\ReturnTypeWillChange]
	public function count() {
		$this->load_timeranges();
		return count($this->timeranges);
	}

	/*
	 * Possibly redundant methods
	 */


	/**
	 * Find a timerange by ID
	 *
	 * @param int $timerange_id
	 * @return Timerange|false
	 */
	public function find($timerange_id) {
		foreach ($this->timeranges as $timerange) {
			if ($timerange->timerange_id == $timerange_id) {
				return $timerange;
			}
		}
		return false;
	}

	/**
	 * Find timeranges by criteria
	 *
	 * @param array $criteria
	 * @return Timerange[]
	 */
	public function find_by($criteria) {
		$found = [];

		foreach ($this->timeranges as $timerange) {
			$match = true;

			foreach ($criteria as $field => $value) {
				if ($timerange->$field != $value) {
					$match = false;
					break;
				}
			}

			if ($match) {
				$found[] = $timerange;
			}
		}

		return $found;
	}

	/**
	 * Get timeranges that are all-day
	 *
	 * @return Timerange[]
	 */
	public function get_all_day() {
		return $this->find_by(['timerange_all_day' => 1]);
	}

	/**
	 * Get timeranges within a time range
	 *
	 * @param string $start_time
	 * @param string $end_time
	 * @return Timerange[]
	 */
	public function get_by_time_range($start_time, $end_time) {
		$found = [];

		foreach ($this->timeranges as $timerange) {
			if ($timerange->timerange_start >= $start_time && $timerange->timerange_end <= $end_time) {
				$found[] = $timerange;
			}
		}

		return $found;
	}

	/**
	 * Sort timeranges by specified field
	 *
	 * @param string $field
	 * @param string $order ASC or DESC
	 */
	public function sort_by($field = 'timerange_start', $order = 'ASC') {
		usort($this->timeranges, function($a, $b) use ($field, $order) {
			$result = strcmp($a->$field, $b->$field);
			return ($order === 'DESC') ? -$result : $result;
		});
	}
}
include( __DIR__ . '/timeslot.php' );
include( __DIR__ . '/timerange.php' );