<?php
use EM\Archetypes;
/**
 * Base class which others extend on. Contains functions shared across all EM objects.
 *
 */
class EM_Object {
	var $fields = array();
	/**
	 * @var array Associative array of shortname => property names for this object. For example, an EM_Event object will have a 'language' key to 'event_language' value.
	 */
	protected $shortnames = array();
	protected static $field_shortcuts = array();
	var $required_fields = array();
	var $feedback_message = "";
	var $errors = array();
	var $mime_types = array(1 => 'gif', 2 => 'jpg', 3 => 'png');
	
	private static $taxonomies_array; //see self::get_taxonomies()
	
	/**
	 * Provides context in searches where ambiguous field names may coincide between event and location database searches requiring a specific field name for each type.
	 * For example, status, location, taxonomy and language arguments are used interchangeably in event and location searches but both have different field names.
	 * Child classes such as EM_Events and EM_Locations will override this field with 'event' or 'location' respectively to determine context.
	 * @var string
	 */
	protected static $context = 'object_type';
	
	/**
	 * An array of dynamic properties which instead of being stored as a dynamic class property to prevent deprecated php 8.2 notices
	 * @var array
	 */
	protected $dynamic_properties = array();
	
	/**
	 * Takes the array and provides a clean array of search parameters, along with details
	 * @param array $defaults
	 * @param array $array
	 * @return array
	 */
	public static function get_default_search($defaults=array(), $array = array()){
		global $wpdb;
		//TODO accept all objects as search options as well as ids (e.g. location vs. location_id, person vs. person_id)
		//Create minimal defaults array, merge it with supplied defaults array
		$super_defaults = array(
			'id' => rand(),
			'limit' => false,
			'scope' => em_get_option('dbem_events_default_scope', 'future'),
			'timezone' => false, //default blog timezone
			'timezone_scope' => false, // search based on a specific timezone, rather than based off local times
			'order' => 'ASC', //hard-coded at end of this function
			'orderby' => false,
			'groupby' => false,
			'groupby_orderby' => false,
			'groupby_order' => 'ASC',
			'format' => '', 
			'format_header' => '', //custom html above the list
			'format_footer' => '', //custom html below the list
			'no_results_msg' => '', //default message if no results used in output() function
			'category' => 0,
			'tag' => 0,
			'location' => false,
			'event' => false,
			'event_status' => false, //automatically set to 'status' value if in EM_Events, useful only for EM_Locations
			'event_archetype' => false,
			'event_type' => false,
			'location_status' => false,  //automatically set to 'status' value if in EM_Locations, useful only for EM_Events
			'offset'=>0,
			'page'=>1,//basically, if greater than 0, calculates offset at end
			'page_queryvar'=>null,
			'recurrence' => 0, //look for a specific recurring event by ID
			'recurrences' => null, //if set, exclusively show (true) or omit (false) recurrences
			'recurring' => null, //if set to 'include' it'll only show recurring event templates, if set to false, it'll omit them from results, null or true will include in results
			'recurring_event' => null,
			'month'=>'',
			'year'=>'',
			'pagination'=>false,
			'array'=>false,
			'owner'=>false,
			'bookings' => false, //if set to true, only events with bookings enabled are returned
			'search'=>false,
			'geo'=>false, //reserved for future searching via name
			'near'=>false, //lat,lng coordinates in array or comma-separated format
			'near_unit'=> em_get_option('dbem_search_form_geo_unit_default'), //mi or km
			'near_distance'=> em_get_option('dbem_search_form_geo_distance_default'), //distance from near coordinates - currently the default is the same as for the search form
			'ajax'=> (defined('EM_AJAX') && EM_AJAX), //considered during pagination
			'language' => null, //for language searches in ML mode
		);
		//auto-add taxonomies to defaults
		foreach( self::get_taxonomies() as $item => $item_data ){ $super_defaults[$item] = false; }
		
		//Return default if nothing passed
		if( empty($defaults) && empty($array) ){
			return $super_defaults;
		}
		//TODO decide on search defaults shared across all objects and then validate here
		$defaults = array_merge($super_defaults, $defaults);
		
		if( is_array($array) ){
			//We are still dealing with recurrence_id, location_id, category_id in some place, so we do a quick replace here just in case
			if( array_key_exists('recurrence_id', $array) && !array_key_exists('recurring_event', $array) ) { $array['recurring_event'] = $array['recurrence_id']; }
			if( array_key_exists('recurrence', $array) && !array_key_exists('recurring_event', $array) ) { $array['recurring_event'] = $array['recurrence']; }
			if( array_key_exists('location_id', $array) && !array_key_exists('location', $array) ) { $array['location'] = $array['location_id']; }
			if( array_key_exists('category_id', $array) && !array_key_exists('category', $array) ) { $array['category'] = $array['category_id']; }
			if( array_key_exists('page', $array) ) { $array['page'] = absint($array['page']); }
		
			//Clean all id lists
			$clean_ids_array = array('location', 'event', 'active_status');
			if( !empty($array['owner']) && $array['owner'] != 'me') $clean_ids_array[] = 'owner'; //clean owner attribute if not 'me'
			// add post
			if ( !empty($array['post_id']) && !is_bool($array['post_id']) && $array['post_id'] !== 'true' ) {
				$clean_ids_array[] = 'post_id';
			}
			$array = self::clean_id_atts($array, $clean_ids_array);

			//Clean taxonomies
			$taxonomies = self::get_taxonomies();
			foreach( $taxonomies as $item => $item_data ){ //tags and cats turned into an array regardless
			    if( !empty($array[$item]) && !is_array($array[$item]) ){
			    	$array[$item] = str_replace(array('&amp;','&#038;'), '&', $array[$item]); //clean & modifiers
					$array[$item] = preg_replace(array('/^[&,]/','/[&,]$/'),'', $array[$item]); //trim , and & from ends
			    }
			}
					    
			//Near
			if( !empty($array['near']) ){
				if( is_array($array['near']) ){
					$array = self::clean_id_atts($array,array('near'));
				}elseif( is_string($array['near']) && preg_match('/^( ?[\-0-9\.]+ ?,?)+$/D', $array['near']) ){
					$array['near'] = explode(',',$array['near']);
				}else{
					//assume it's a string to geocode, not supported yet
					unset($array['near']);
				}
				$array['near_unit'] = !empty($array['near_unit']) && in_array($array['near_unit'], array('km','mi')) ? $array['near_unit']:$defaults['near_unit']; //default is 'mi'
				$array['near_distance'] = !empty($array['near_distance']) && is_numeric($array['near_distance']) ? absint($array['near_distance']) : $defaults['near_distance']; //default is 25
			}
			//Locations - Turn into array for multiple search if comma-separated
			$location_fields = array('country','town','state','region','postcode');
			foreach( $location_fields as $location_field ) {
				if( !empty($array[$location_field]) && is_string($array[$location_field]) && preg_match('/^( ?.+ ?,?)+$/', $array[$location_field]) ){
					$array[$location_field] = explode(',',$array[$location_field]);
				}
			}
			//TODO validate search query array
			//Clean the supplied array, so we only have allowed keys
			foreach( array_keys($array) as $key){
				if( !array_key_exists($key, $defaults) && !array_key_exists($key, $taxonomies) ) unset($array[$key]);		
			}
			//Timezone
			if( !empty($array['timezone']) ){
				if( !is_array($array['timezone']) ) {
					$array['timezone'] = str_replace(' ', '', $array['timezone']);
					$array['timezone'] = explode(',', $array['timezone']);
				}
			}
			if ( !empty($array['timezone_scope']) ) {
				// check we have a timezone-ish format, or just a boolean value
				if ( !preg_match('/^(([A-Za-z0-9-_]+\/[A-Za-z0-9-_]+)|([A-Za-z]{1,4})|(UTC|GMT)(\+|-)[0-9]{1,2}([\.:][0-9]{2})?)$/', $array['timezone_scope']) ) {
					$array = (bool) $array['timezone_scope'];
				}
			}
			// Language
			if( isset($array['language']) ){
				if( $array['language'] !== false && !in_array($array['language'], EM_ML::$langs) ){
					unset($array['language']);
				}
			}
			// Archetypes and Types
			if ( empty( $array['event'] ) ) {
				if ( !empty($array['event_archetype']) ) {
					// sanitize again, just in case
					if ( !is_array($array['event_archetype']) ) {
						$array['event_archetype'] = explode(',', str_replace(' ', '', $array['event_archetype']));
					}
					$array['event_archetype'] = array_intersect( Archetypes::get_cpts(), $array['event_archetype'] );
				}

				if ( !empty($array['event_type']) ) {
					// sanitize again, just in case
					if ( !is_array($array['event_type']) ) {
						$array['event_type'] = explode(',', str_replace(' ', '', $array['event_type']));
					}
					$allowed_event_types = ['recurring', 'repeating', 'recurrence', 'single'];
					$array['event_type'] = array_intersect( $allowed_event_types, $array['event_type'] );
				}
			} else {
				// we are looking for a specific event, so we know we don't need an archetype or type
				$array['event_archetype'] = false;
				$array['event_type'] = false;
			}
			//return clean array
			$defaults = array_merge ( $defaults, $array ); //No point using WP's cleaning function, we're doing it already.
		}
		
		//Do some spring cleaning for known values
		//Month & Year - may be array or single number
		$month_regex = '/^[0-9]{1,2}$/';
		$year_regex = '/^[0-9]{4}$/';
		if( is_array($defaults['month']) ){
			$defaults['month'] = ( preg_match($month_regex, $defaults['month'][0]) && preg_match($month_regex, $defaults['month'][1]) ) ? $defaults['month']:''; 
		}else{
			$defaults['month'] = preg_match($month_regex, $defaults['month']) ? $defaults['month']:'';	
		}
		if( is_array($defaults['year']) ){
			$defaults['year'] = ( preg_match($year_regex, $defaults['year'][0]) && preg_match($year_regex, $defaults['year'][1]) ) ? $defaults['year']:'';
		}else{
			$defaults['year'] = preg_match($year_regex, $defaults['year']) ? $defaults['year']:'';
		}
		//Deal with scope and date searches
		if ( !is_array($defaults['scope']) && preg_match ( "/^([0-9]{4}-[0-9]{1,2}-[0-9]{1,2})?,([0-9]{4}-[0-9]{1,2}-[0-9]{1,2})?$/D", $defaults['scope'] ) ) {
			//This is to become an array, so let's split it up
			$defaults['scope'] = explode(',', $defaults['scope']);
		}
		if( is_array($defaults['scope']) ){
			//looking for a date range here, so we'll verify the dates validate, if not get the default.
			if ( empty($defaults['scope'][0]) || !preg_match("/^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}$/D", $defaults['scope'][0]) ){
				$defaults['scope'][0] = '';
			}
			if( empty($defaults['scope'][1]) || !preg_match("/^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}$/D", $defaults['scope'][1]) ) {
				$defaults['scope'][1] = '';
			}
			if( empty($defaults['scope'][0]) && empty($defaults['scope'][1]) ){
				if( !empty($defaults['scope']['name']) && !is_array($defaults['scope']['name']) ) {
					$defaults['scope'] = $defaults['scope']['name'];
				}else{
					$defaults['scope'] = $super_defaults['scope'];
				}
			}
		}
		//ORDER and GROUP BY ORDER - split up string array, if just text do a quick validation and set to default if upon failure
		foreach( array('order', 'groupby_order') as $order_arg ){
			if( !is_array($defaults[$order_arg]) && preg_match('/,/', $defaults[$order_arg]) ) {
				$defaults[$order_arg] = str_replace(' ', '', $defaults[$order_arg]);
				$defaults[$order_arg] = explode(',', $defaults[$order_arg]);
			}elseif( !is_array($defaults[$order_arg]) && !in_array($defaults[$order_arg], array('ASC','DESC','asc','desc')) ){
				$defaults[$order_arg] = $super_defaults[$order_arg];
			}
		}
		//ORDER BY, GROUP BY and GROUP BY ORDER ensure we have a valid array, splitting by commas if present
		foreach( array('orderby', 'groupby', 'groupby_orderby') as $orderby_arg ){
			if( !is_array($defaults[$orderby_arg]) && preg_match('/,/', $defaults[$orderby_arg]) ) {
				$defaults[$orderby_arg] = str_replace( [' asc', ' desc'], [' ASC', ' DESC'], $defaults[$orderby_arg]); // uppercase ordering so we can correct later
				$defaults[$orderby_arg] = str_replace(' ', '', $defaults[$orderby_arg]);
				$defaults[$orderby_arg] = str_replace( ['ASC', 'DESC'], [' ASC', ' DESC'], $defaults[$orderby_arg]); // correct removed spaces
				$defaults[$orderby_arg] = explode(',', $defaults[$orderby_arg]);
			}elseif( !empty($defaults[$orderby_arg]) && !is_array($defaults[$orderby_arg]) ){
				$defaults[$orderby_arg] = array($defaults[$orderby_arg]);
			}
			if( is_array($defaults[$orderby_arg]) ) $defaults[$orderby_arg] = array_values($defaults[$orderby_arg]); //reset array keys because we want an index 0 present
		}
		//TODO should we clean format of malicious code over here and run everything through this?
		$defaults['array'] = is_array($defaults['array']) ? $defaults['array'] : ($defaults['array'] == true);
		$defaults['pagination'] = ($defaults['pagination'] == true);
		$defaults['limit'] = (is_numeric($defaults['limit'])) ? $defaults['limit']:$super_defaults['limit'];
		$defaults['offset'] = (is_numeric($defaults['offset'])) ? $defaults['offset']:$super_defaults['offset'];
		if( $defaults['recurring'] !== null ) $defaults['recurring'] = $defaults['recurring'] === 'include' ?  $defaults['recurring']:($defaults['recurring'] == true);
		$defaults['search'] = ( is_scalar($defaults['search']) && $defaults['search'] ) ? trim((string) $defaults['search']) : false;
		//Calculate offset if event page is set
		if($defaults['page'] > 1){
			$defaults['offset'] = $defaults['limit'] * ($defaults['page']-1);	
		}else{
			$defaults['page'] = ($defaults['limit'] > 0 ) ? floor($defaults['offset']/$defaults['limit']) + 1 : 1;
		}
		//return values
		return apply_filters('em_object_get_default_search', $defaults, $array, $super_defaults);
	}
	
	/**
	 * Builds an array of SQL query conditions based on regularly used arguments
	 * @param array $args
	 * @return array
	 */
	public static function build_sql_conditions( $args = array() ){
		global $wpdb;
		$events_table = EM_EVENTS_TABLE;
		$locations_table = EM_LOCATIONS_TABLE;
		
		$args = apply_filters('em_object_build_sql_conditions_args',$args);
		
		//Format the arguments passed on
		$scope = $args['scope'];//undefined variable warnings in ZDE, could just delete this (but dont pls!)
		$recurring = $args['recurring'];
		$recurrence = $args['recurring_event'];
		$recurrences = $args['recurrences'];
		$category = $args['category'];// - not used anymore, accesses the $args directly
		$tag = $args['tag'];// - not used anymore, accesses the $args directly
		$location = $args['location'];
		$owner = $args['owner'];
		$event = $args['event'];
		$month = $args['month'];
		$year = $args['year'];
		//Create the WHERE statement
		$conditions = array();
		
		//Statuses - we search for the 'status' based on the context of current object (i.e. is it an event or location for the moment)
		// if we define the alternative status such as location_status in event context, if set to true it matches the event 'status'
		// if a specific status search value is given i.e. not true and not false then that's used to generate the right condition for that specific field
		// e.g. if in events, search for 'publish' events and 0 location_status, it'll find events with a location pending review.
		foreach( array('event_status', 'location_status') as $status_type ){
			//find out whether the main status context we're after is an event or location i.e. are we running an events or location query
			$is_location_status = $status_type == "location_status" && static::$context == 'location';
			$is_event_status = $status_type == "event_status" && static::$context == 'event';
			//$is_joined_status decides whether this status we're dealing with is part of a joined table or the main table
			$is_joined_status = !$is_location_status && !$is_event_status && $args[$status_type] !== false;
			//we add a status condition if this is the main status context or if joining a table and joined status arg is not exactly false
			if( $is_location_status || $is_event_status || $args[$status_type] !== false ){
				$condition_status = $is_joined_status ? $status_type : 'status'; //the key for this condition type
				//if this is the status belonging to the joined table, if set to true we match the main context status otherwise we check the specific status
				$status_arg = $is_joined_status && $args[$status_type] !== true ? $args[$status_type] : $args['status'];
				//if joining by event or location, we may mistakenly omit any results without a complementing event or location, we need to account for that here
				//other parts of the condition can negate whether or not eventful locations or events with/without locations should be included
				$conditions[$condition_status] = "(`{$status_type}` >= 0 )"; //shows pending & published if not defined
				if( is_numeric($status_arg) ){
					$conditions[$condition_status] = "(`{$status_type}`={$status_arg})"; //pending or published
				}elseif( $status_arg == 'pending' ){
				    $conditions[$condition_status] = "(`{$status_type}`=0)"; //pending
				}elseif( $status_arg == 'publish' ){
				    $conditions[$condition_status] = "(`{$status_type}`=1)"; //published
				}elseif( $status_arg === null || $status_arg == 'draft' ){
				    $conditions[$condition_status] = "(`{$status_type}` IS NULL )"; //show draft items
				}elseif( $status_arg == 'trash' ){
				    $conditions[$condition_status] = "(`{$status_type}` = -1 )"; //show trashed items
				}elseif( $status_arg == 'all'){
					$conditions[$condition_status] = "(`{$status_type}` >= 0 OR `{$status_type}` IS NULL)"; //search all statuses that aren't trashed
				}elseif( $status_arg == 'everything'){
					unset($conditions[$condition_status]); //search all statuses
				}
			}
		}

		// Archetypes, Types and Recurrences
		if ( !$event ) {
			// archetypes, generally we'll want to display only one archetype at a time, but we can still be flexible
			if ( !empty($args['event_archetype']) ) {
				if ( !is_array($args['event_archetype']) ) {
					$args['event_archetype'] = explode(',', str_replace(' ', '', $args['event_archetype']));
				}
				$event_archetypes = array_intersect( Archetypes::get_cpts(), $args['event_archetype'] );
				if ( count($args['event_archetype']) > 1 ) {
					$conditions['event_archetype'] = "(`event_archetype` IN ('" . implode("','", $event_archetypes) . "'))";
				} else {
					$event_archetype = current($event_archetypes);
					$conditions['event_archetype'] = "(`event_archetype` = '$event_archetype')";
				}
			}

			//Recurrences
			// TODO Transition recurrences over time...
			if ( !empty($args['event_type']) ) {
				// sanitize again, just in case
				if ( !is_array($args['event_type']) ) {
					$args['event_type'] = explode(',', str_replace(' ', '', $args['event_type']));
				}
				$allowed_event_types = ['recurring', 'repeating', 'recurrence', 'single'];
				$event_types = array_intersect( $allowed_event_types, $args['event_type'] );
				$conditions['event_type'] = "(`event_type` IN ('" . implode("','", $event_types) . "'))";
			} else {
				if ( $recurring ) {
					//we show recurring event templates as well within results, if 'recurring' is 'include' then we show both recurring and normal events.
					if ( $recurring !== 'include' ) {
						$conditions['recurring'] = "`event_type` IN ('repeating','recurring')";
					}
				} elseif ( $recurrence > 0 ) {
					$conditions['recurrence'] = $wpdb->prepare( "(`recurrence_set_id` IN (SELECT recurrence_set_id FROM " . EM_EVENT_RECURRENCES_TABLE . " WHERE event_id=%d))", $recurrence );
				} else {
					//we choose to either exclusively show or completely omit recurrences, if not set then both are shown
					if ( $recurrences !== null ) {
						$conditions['recurrences'] = $recurrences ? "(`recurrence_set_id` > 0 )" : "(`recurrence_set_id` IS NULL OR `recurrence_set_id`=0 )";
					}
					//if we get here and $recurring is not exactly null (meaning ignored), it was set to false or 0 meaning recurring events shouldn't be included
					if ( $recurring !== null ) {
						$conditions['recurring'] = "(`event_type` NOT IN ('repeating','recurring'))";
					}
				}
			}
		}
		
		//Timezone - search for events in a specific timezone
		if( !empty($args['timezone']) ){
			if( !is_array($args['timezone']) ){
				$args['timezone'] = explode(',', $args['timezone']);
			}
			foreach( $args['timezone'] as $tz ) $timezones[] = $wpdb->prepare('%s', $tz);
			$conditions['timezone'] = '`event_timezone` IN ('.implode(',', $timezones).')';
		}
		
		//Dates - first check 'month', and 'year', and adjust scope if needed
		if( !($month=='' && $year=='') ){
			//Sort out month range, if supplied an array of array(month,month), it'll check between these two months
			if( self::array_is_numeric($month) ){
				$date_month_start = $month[0];
				$date_month_end = $month[1];
			}else{
				if( !empty($month) ){
					$date_month_start = $date_month_end = $month;					
				}else{
					$date_month_start = 1;
					$date_month_end = 12;				
				}
			}
			//Sort out year range, if supplied an array of array(year,year), it'll check between these two years
			if( self::array_is_numeric($year) ){
				$date_year_start = $year[0];
				$date_year_end = $year[1];
			}else{
				$date_year_start = $date_year_end = $year;
			}
			$date_start = $date_year_start."-".$date_month_start."-01";
			$date_end = date('Y-m-t', mktime(0,0,0,$date_month_end,1,$date_year_end));
			$scope = array($date_start,$date_end); //just modify the scope here
		}
		//Build scope query, first get search variables depending whether we're searching relative to a timezone or just dates in local times
		$timezone_scope = false;
		$cast = 'DATE';
		$event_start_col = 'event_start_date';
		$event_end_col = 'event_end_date';
		// override search variables if we are with a timezone scope
		if ( $args['timezone_scope'] ) {
			$timezone_scope = in_array( $args['timezone_scope'], [1,'1',true], true )  ? em_get_option( 'timezone_string', $args['event_archetype'] ) : $args['timezone_scope'];
			$cast = 'DATETIME';
			if ( !empty( $args['timeslots'] ) ) {
				// Timeslot rows are joined via the `ets` alias in EM_Events::get(). Scope on the timeslot's own datetime so cross-midnight rows from a neighbouring local day aren't included just because their parent event row happens to overlap the requested local date. Falls back to the parent event's datetime for rows the LEFT JOIN didn't match.
				$event_start_col = 'COALESCE(ets.timeslot_start, ' . EM_EVENTS_TABLE . '.event_start)';
				$event_end_col   = 'COALESCE(ets.timeslot_end, '   . EM_EVENTS_TABLE . '.event_end)';
			} else {
				$event_start_col = 'event_start';
				$event_end_col = 'event_end';
			}
		}
		if ( is_array($scope) ) {
			if ( $timezone_scope ) {
				// get the blog timezone
				// get dates in UTC time
				$date_start = !empty($scope[0]) ? EM_DateTime::create( $scope[0], $timezone_scope )->getDate('UTC') : '';
				$date_end = !empty($scope[1]) ? EM_DateTime::create( $scope[1], $timezone_scope )->getDate('UTC') : '';
			} else {
				//This is an array, let's split it up. Only validated dates may reach the CAST() clauses below, since they are concatenated into the query rather than prepared.
				$date_start = ( !empty($scope[0]) && preg_match("/^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}$/D", $scope[0]) ) ? $scope[0] : '';
				$date_end = ( !empty($scope[1]) && preg_match("/^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}$/D", $scope[1]) ) ? $scope[1] : '';
			}
			if( !empty($date_start) && empty($date_end) ){
				//do a from till infinity
				$conditions['scope'] = " $event_start_col >= CAST('$date_start' AS $cast)";
			}elseif( empty($date_start) && !empty($date_end) ){
				//do past till $date_end
				if( em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) ){
					$conditions['scope'] = " $event_start_col <= CAST('$date_end' AS $cast)";
				}else{
					$conditions['scope'] = " $event_end_col <= CAST('$date_end' AS $cast)";
				}
			}else{
				//date range
				if( em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) ){
					$conditions['scope'] = "( $event_start_col BETWEEN CAST('$date_start' AS $cast) AND CAST('$date_end' AS $cast) )";
				}else{
					$conditions['scope'] = "( $event_start_col <= CAST('$date_end' AS $cast) AND $event_end_col >= CAST('$date_start' AS $cast) )";
				}
				//$conditions['scope'] = " ( ( $event_start_col <= CAST('$date_end' AS $cast) AND $event_end_col >= CAST('$date_start' AS $cast) ) OR ($event_start_col BETWEEN CAST('$date_start' AS $cast) AND CAST('$date_end' AS $cast)) OR ($event_end_col BETWEEN CAST('$date_start' AS $cast) AND CAST('$date_end' AS $cast)) )";
			}
		} elseif ( preg_match ( "/^[0-9]{4}-[0-9]{2}-[0-9]{1,2}$/D", $scope ) ) {
			//Scope can also be a specific date. However, if 'day', 'month', or 'year' are set, that will take precedence
			if ( $timezone_scope ) {
				// get dates in UTC time
				$date_start = EM_DateTime::create( $scope . ' 00:00:00', $timezone_scope )->getDateTime('UTC');
				$date_end = EM_DateTime::create( $scope . ' 23:59:59', $timezone_scope )->getDateTime('UTC');
			}
			if( em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) ){
				if ( $timezone_scope ) {
					$conditions['scope'] = " ( $event_start_col BETWEEN CAST('$date_start' AS $cast) AND CAST('$date_end' AS $cast) )";
				} else {
					$conditions['scope'] = "$event_start_col = CAST('$scope' AS $cast)";
				}
			} else{
				if ( $timezone_scope ) {
					$conditions['scope'] = "( $event_start_col BETWEEN CAST('$date_start' AS $cast) AND CAST('$date_end' AS $cast) )";
					$conditions['scope'] = " ( {$conditions['scope']} OR ( $event_start_col <= CAST('$date_end' AS $cast) AND $event_end_col >= CAST('$date_start' AS $cast) ) )";
				} else {
					$conditions['scope'] = " ( $event_start_col = CAST('$scope' AS $cast) OR ( $event_start_col <= CAST('$scope' AS $cast) AND $event_end_col >= CAST('$scope' AS $cast) ) )";
				}
			}
		} else {
			$EM_DateTime = $timezone_scope ? new EM_DateTime('now', $timezone_scope) : new EM_DateTime(); //the time, now, in blog/site timezone
			$utc = $timezone_scope ? 'UTC' : null;
			if ($scope == "past"){
				if( em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) ){
					$conditions['scope'] = " event_start < '".$EM_DateTime->getDateTime('UTC')."'";
				}else{
					$conditions['scope'] = " event_end < '".$EM_DateTime->getDateTime('UTC')."'";
				}  
			}elseif ($scope == "today"){
				$conditions['scope'] = " ($event_start_col = CAST('".$EM_DateTime->getDateTime( $utc )."' AS $cast))";
				if( !em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) ){
					$conditions['scope'] .= " OR ($event_start_col <= CAST('".$EM_DateTime->getDateTime( $utc )."' AS $cast) AND $event_end_col >= CAST('$EM_DateTime' AS $cast))";
				}
			}elseif ($scope == "tomorrow"){
				$EM_DateTime->modify('+1 day');
				$conditions['scope'] = "($event_start_col = CAST('".$EM_DateTime->getDateTime( $utc )."' AS $cast))";
				if( !em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) ){
					$conditions['scope'] .= " OR ($event_start_col <= CAST('".$EM_DateTime->getDateTime( $utc )."' AS $cast) AND $event_end_col >= CAST('".$EM_DateTime->getDateTime( $utc )."' AS $cast))";
				}
			}elseif ($scope == "week" || $scope == 'this-week'){
				list($start_date, $end_date) = $EM_DateTime->get_week_dates( $scope );
				$conditions['scope'] = " ($event_start_col BETWEEN CAST('$start_date' AS $cast) AND CAST('$end_date' AS $cast))";
				if( !em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) ){
					$conditions['scope'] .= " OR ($event_start_col < CAST('$start_date' AS $cast) AND $event_end_col >= CAST('$start_date' AS $cast))";
				}
			}elseif ($scope == "month" || $scope == "next-month" || $scope == 'this-month'){
				if( $scope == 'next-month' ) $EM_DateTime->add('P1M');
				$start_month = $scope == 'this-month' ? $EM_DateTime->getDateTime( $utc ) : $EM_DateTime->modify('first day of this month')->getDateTime( $utc );
				$end_month = $EM_DateTime->modify('last day of this month')->getDateTime( $utc );
				$conditions['scope'] = " ($event_start_col BETWEEN CAST('$start_month' AS $cast) AND CAST('$end_month' AS $cast))";
				if( !em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) ){
					$conditions['scope'] .= " OR ($event_start_col < CAST('$start_month' AS $cast) AND $event_end_col >= CAST('$start_month' AS $cast))";
				}
			}elseif( preg_match('/([0-9]+)\-months/',$scope,$matches) ){ // next x months means this month (what's left of it), plus the following x months until the end of that month.
				$months_to_add = $matches[1];
				$start_month = $EM_DateTime->getDateTime( $utc );
				$end_month = $EM_DateTime->add('P'.$months_to_add.'M')->format('Y-m-t');
				$conditions['scope'] = " ($event_start_col BETWEEN CAST('$start_month' AS $cast) AND CAST('$end_month' AS $cast))";
				if( !em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) ){
					$conditions['scope'] .= " OR ($event_start_col < CAST('$start_month' AS $cast) AND $event_end_col >= CAST('$start_month' AS $cast))";
				}
			}elseif ($scope == "future"){
				$conditions['scope'] = " event_start >= '".$EM_DateTime->getDateTime(true)."'";
				if( !em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) ){
					$conditions['scope'] .= " OR (event_end >= '".$EM_DateTime->getDateTime(true)."')";
				}
			}
			if( !empty($conditions['scope']) ){
				$conditions['scope'] = '('.$conditions['scope'].')';
			}
		}
		
		//Filter by Location - can be object, array, or id
		$location_id_table = static::$context == 'event' ? $events_table:$locations_table;
		if ( is_numeric($location) && $location > 0 ) { //Location ID takes precedence
			$conditions['location'] = " {$location_id_table}.location_id = $location";
		}elseif ( $location === 0 ) { //only helpful is searching events
			$conditions['location'] = " {$events_table}.location_id = $location OR {$events_table}.location_id IS NULL";
		}elseif ( self::array_is_numeric($location) ){
			$conditions['location'] = "{$location_id_table}.location_id IN (" . implode(',', $location) .')';
		}elseif ( is_object($location) && get_class($location)=='EM_Location' ){ //Now we deal with objects
			$conditions['location'] = " {$location_id_table}.location_id = $location->location_id";
		}elseif ( is_array($location) && @get_class(current($location)=='EM_Location') ){ //we can accept array of ids or EM_Location objects
			foreach($location as $EM_Location){
				$location_ids[] = $EM_Location->location_id;
			}
			$conditions['location'] = "{$location_id_table}.location_id IN (" . implode(',', $location_ids) .')';
		}
		
		//Filter by Event - can be object, array, or id
		if ( is_numeric($event) && $event > 0 ) { //event ID takes precedence
			$conditions['event'] = " {$events_table}.event_id = $event";
		}elseif ( self::array_is_numeric($event) ){ //array of ids
			$conditions['event'] = "{$events_table}.event_id IN (" . implode(',', $event) .')';
		}elseif ( is_object($event) && get_class($event)=='EM_Event' ){ //Now we deal with objects
			$conditions['event'] = " {$events_table}.event_id = $event->event_id";
		}elseif ( is_array($event) && @get_class(current($event)=='EM_Event') ){ //we can accept array of ids or EM_event objects
			foreach($event as $EM_Event){
				$event_ids[] = $EM_Event->event_id;
			}
			$conditions['event'] = "{$events_table}.event_id IN (" . implode(',', $event_ids) .')';
		}

		//Location specific filters
		//if we're searching near something, country etc. becomes irrelevant
		if( !empty($args['near']) && self::array_is_numeric($args['near']) ){
			$distance = !empty($args['near_distance']) && is_numeric($args['near_distance']) ? absint($args['near_distance']) : absint( em_get_option( 'dbem_search_form_geo_units',25, $args['event_archetype'] ) );
			if( empty($args['near_unit']) ) $args['near_unit'] = em_get_option( 'dbem_search_form_geo_distance','mi', $args['event_archetype'] );
			$unit = ( !empty($args['near_unit']) && $args['near_unit'] == 'km' ) ? 6371 /* kilometers */ : 3959 /* miles */;
			$near_lat = (float) $args['near'][0];
			$near_lng = (float) $args['near'][1];
			$conditions['near'] = "( $unit * acos( cos( radians($near_lat) ) * cos( radians( location_latitude ) ) * cos( radians( location_longitude ) - radians($near_lng) ) + sin( radians($near_lat) ) * sin( radians( location_latitude ) ) ) ) < $distance";
		}else{
			//country lookup and cleanup
			if( !empty($args['country']) ){
				$countries = em_get_countries();
				$countries_search = array();
				//we can accept country codes or names so we need to change names to country codes
				$country_arg = !is_array($args['country']) ? explode(',', $args['country']) : $args['country'];
			    foreach( $country_arg as $country ){
					$country_clean = $country[0] === '-' ? substr($country, 1) : $country;
    			    if( array_key_exists($country_clean, $countries) ){
        					//we have a country code
        				$countries_search[] = $country;					
        			}elseif( in_array($country_clean, $countries) ){
        				//we have a country name, 
        				$countries_search[] = array_search($country, $countries);
    			    }
			    }
				$args['country'] = $countries_search;
			}
			$location_fields = array('country','town','state','region','postcode');
			foreach( $location_fields as $loc_field ) {
				if ( !empty( $args[$loc_field] ) ) {
					$search_arg = is_array( $args[$loc_field] ) ? $args[$loc_field] : explode( ',', $args[$loc_field] );
					// create array of include/exclude values
					$search_placeholders = array( 'include' => array(), 'exclude' => array() );
					$search_values = array( 'include' => array(), 'exclude' => array() );
					foreach( $search_arg as $search_value ) {
						if( $search_value[0] === '-' ) {
							$search_placeholders['exclude'][] = '%s';
							$search_values['exclude'][] = substr( $search_value, 1 );
						} else {
							$search_placeholders['include'][] = '%s';
							$search_values['include'][] = $search_value;
						}
					}
					if( !empty($search_values['include']) ) {
						$placeholders = implode( ', ', array_fill( 0, count( $search_placeholders['include'] ), '%s' ) );
						$conditions[$loc_field] = $wpdb->prepare( "location_{$loc_field} IN ($placeholders)", $search_values['include'] );
					} elseif( !empty($search_values['exclude']) ) {
						$placeholders = implode( ', ', array_fill( 0, count( $search_placeholders['exclude'] ), '%s' ) );
						$conditions[$loc_field] = $wpdb->prepare( "location_{$loc_field} NOT IN ($placeholders)", $search_values['exclude'] );
					}
				}
			}
		}
		
		//START TAXONOMY FILTERS - can be id, slug, name or comma separated ids/slugs/names, if negative or prepended with a - then considered a negative filter
		//convert taxonomies to arrays
		$taxonomies = self::get_taxonomies();
		foreach( $taxonomies as $item => $item_data ){ //tags and cats turned into an array regardless
		    if( !empty($args[$item]) && !is_array($args[$item]) ){
				if( preg_match('/[,&]/', $args[$item]) !== false ){ //accepts numbers or words
					$args[$item] = explode('&', $args[$item]);
					foreach($args[$item] as $k=>$v){
						$args[$item][$k] = trim($v);
						$args[$item][$k] = explode(',', $v);
						foreach($args[$item][$k] as $k_x=>$v_x) $args[$item][$k][$k_x] = trim($v_x);
					}
				}else{
				    $args[$item] = array(trim($args[$item]));
				}
		    }
		}
		foreach($taxonomies as $tax_name => $tax_data){
			if( !empty($args[$tax_name]) && is_array($args[$tax_name]) ){
			    if( !empty($tax_data['ms']) ) self::ms_global_switch(); //if in ms global mode, switch here rather than on each EM_Category instance
			    $tax_conds = array();
			    //if a single array is supplied then we treat it as an OR type of query, if an array of arrays is supplied we condsider it to be many ANDs of ORs
			    //so here we wrap a single array into another array and there is only one 'AND' condition (therefore no AND within this tax search) 
			    foreach($args[$tax_name] as $k=>$v) if( is_array($v) ) $contains_array = true;
			    if( empty($contains_array) ) $args[$tax_name] = array($args[$tax_name]);
			    //go through taxonomy arg and generate relevant SQL
			    foreach($args[$tax_name] as $tax_id_set){
					//build array of term ids and negative ids from supplied argument
					$term_tax_ids = $term_ids = array();
					$term_tax_not_ids = $term_not_ids = array();
					foreach($tax_id_set as $tax_id){
					    $tax_id_clean = preg_replace('/^-/', '', $tax_id);
						if( !is_numeric($tax_id_clean) ){
							$term = get_term_by('slug', $tax_id_clean, $tax_data['query_var']);
							if( empty($term) ){
								$term = get_term_by('name', $tax_id_clean, $tax_data['query_var']);
							}
						}else{
							$term = get_term_by('id', $tax_id_clean, $tax_data['query_var']);
						}
						if( !empty($term->term_taxonomy_id) ){
							if( !preg_match('/^-/', $tax_id) ){
								$term_tax_ids[] = $term->term_taxonomy_id;
								if( EM_MS_GLOBAL && !empty($tax_data['ms']) ) $term_ids[] = $term->term_id;
							}else{
								$term_tax_not_ids[] = $term->term_taxonomy_id;
								if( EM_MS_GLOBAL && !empty($tax_data['ms']) ) $term_not_ids[] = $term->term_id;
							}
						}elseif( preg_match('/^-/', $tax_id) ){
						    //if they supply a negative term for a nonexistent custom taxonomy e.g. -1, we should still  
						    $ignore_cancel_cond = true;
						}
					}
					//create sql conditions
					if( count($term_tax_ids) > 0 || count($term_tax_not_ids) > 0 ){
					    //figure out context - what table/field to search
					    $post_context = EM_EVENTS_TABLE.".post_id";
					    $ms_context = EM_EVENTS_TABLE.".event_id";
					    if( !empty($tax_data['context']) && static::$context == 'location' && in_array( static::$context, $tax_data['context']) ){
					        //context can be either locations or events, since those are the only two CPTs we deal with
						    $post_context = EM_LOCATIONS_TABLE.".post_id";
						    $ms_context = EM_LOCATIONS_TABLE.".event_id";
					    }
					    //build conditions
						if( EM_MS_GLOBAL && !empty($tax_data['ms']) ){ //by default only applies to categories
						    //we're directly looking for tax ids from within the em_meta table
							if( count($term_ids) > 0 ){
								$tax_conds[] = "$ms_context IN ( SELECT object_id FROM ".EM_META_TABLE." WHERE meta_value IN (".implode(',',$term_ids).") AND meta_key='{$tax_data['ms']}' )";
							}
							if( count($term_not_ids) > 0 ){
								$tax_conds[] = "$ms_context NOT IN ( SELECT object_id FROM ".EM_META_TABLE." WHERE meta_value IN (".implode(',',$term_not_ids).") AND meta_key='{$tax_data['ms']}' )";			
							} 
						}else{
					    	//normal taxonomy filtering
							if( count($term_tax_ids) > 0 ){
								$tax_conds[] = "$post_context IN ( SELECT object_id FROM ".$wpdb->term_relationships." WHERE term_taxonomy_id IN (".implode(',',$term_tax_ids).") )";
							}
							if( count($term_tax_not_ids) > 0 ){
								$tax_conds[] = "$post_context NOT IN ( SELECT object_id FROM ".$wpdb->term_relationships." WHERE term_taxonomy_id IN (".implode(',',$term_tax_not_ids).") )";			
							}
						}
					}elseif( empty($ignore_cancel_cond) ){
					    $tax_conds[] = '2=1'; //force a false, supplied taxonomies don't exist
					    break; //no point continuing this loop
					}
			    }
				if( count($tax_conds) > 0 ){
					$conditions[$tax_name] = '('. implode(' AND ', $tax_conds) .')';
				}
			    if( !empty($tax_data['ms']) ) self::ms_global_switch_back(); //if in ms global mode, switch back from previous switch
			}
		}
		//END TAXONOMY FILTERS
	
		//If we want rsvped items, we usually check the event
		if( isset($args['bookings']) && $args['bookings'] !== false ){
			$bookings = absint($args['bookings']);
			if( $args['bookings'] === 'user' && is_user_logged_in()) {
				//get bookings of user
				$EM_Person = new EM_Person(get_current_user_id());
				$booking_ids = $EM_Person->get_bookings(true);
				if (count($booking_ids) > 0) {
					$conditions['bookings'] = "(event_id IN (SELECT event_id FROM " . EM_BOOKINGS_TABLE . " WHERE booking_id IN (" . implode(',', $booking_ids) . ")))";
				} else {
					$conditions['bookings'] = "(event_id = 0)";
				}
			}elseif( $bookings == 1 ){
				$conditions['bookings'] = 'event_rsvp=1';
			}elseif( $bookings == 0 && $bookings !== false ){
				$conditions['bookings'] = 'event_rsvp=0';
			}
		}
		//Default ownership belongs to an event, child objects can just overwrite this if needed.
		if( is_numeric($owner) ){
			$conditions['owner'] = 'event_owner='.$owner;
		}elseif( $owner == 'me' && is_user_logged_in() ){
			$conditions['owner'] = 'event_owner='.get_current_user_id();
		}elseif( $owner == 'me' && !is_user_logged_in() ){
		    $conditions = array('owner'=>'1=2'); //no events to be shown
		}elseif( self::array_is_numeric($owner) ){
			$conditions['owner'] = 'event_owner IN ('.implode(',',$owner).')';
		}
		
		// Language searches, only relevant if ML is activated via a third party plugin
		if( EM_ML::$is_ml && $args['language'] ){ // language ignored if null or false
			if( static::$context == 'event'){
				$conditions['language'] = $wpdb->prepare('event_language = %s', EM_ML::$current_language);
			}elseif( static::$context == 'location'){
				$conditions['language'] = $wpdb->prepare('location_language = %s', EM_ML::$current_language);
			}
		}
		//return values
		return apply_filters('em_object_build_sql_conditions', $conditions);
	}
	
	public static function get_taxonomies(){
	    if( empty(self::$taxonomies_array) ){
	        //default taxonomies
	        $taxonomies_array = array(
        		'category' => array( 'name' => EM_TAXONOMY_CATEGORY, 'slug'=>EM_TAXONOMY_CATEGORY_SLUG, 'ms' => 'event-category', 'context'=> array(), 'query_var'=>EM_TAXONOMY_CATEGORY ),
        		'tag' => array( 'name'=> EM_TAXONOMY_TAG, 'slug'=>EM_TAXONOMY_TAG_SLUG, 'context'=> array(), 'query_var'=>EM_TAXONOMY_TAG )
	        );
	        //get additional taxonomies associated with locations and events and set context for default taxonomies
	        foreach( get_taxonomies(array(),'objects') as $tax_name => $tax){
                $event_tax = in_array(EM_POST_TYPE_EVENT, $tax->object_type);
                $loc_tax = in_array(EM_POST_TYPE_LOCATION, $tax->object_type);
	            if( $tax_name == EM_TAXONOMY_CATEGORY || $tax_name == EM_TAXONOMY_TAG ){
	            	//set the context for the default taxonomies, as they're already in the array
	                $tax_name = $tax_name == EM_TAXONOMY_CATEGORY ? 'category':'tag';
                    if( $event_tax ) $taxonomies_array[$tax_name]['context'][] = EM_POST_TYPE_EVENT;
                    if( $loc_tax ) $taxonomies_array[$tax_name]['context'][] = EM_POST_TYPE_LOCATION;
	            }else{
	            	//non default taxonomy, so create new item for the taxonomies array
	                $tax_name = str_replace('-','_',$tax_name);
					$prefix = !array_key_exists($tax_name, $taxonomies_array) ? '':'post_';
	                if( is_array($tax->object_type) && !empty($tax->rewrite) ){
	                    if( $event_tax || $loc_tax ){
		                    $taxonomies_array[$prefix.$tax_name] = array('name'=>$tax_name, 'context'=>array(), 'slug'=> $tax->rewrite['slug'], 'query_var'=> $tax->query_var );
	                    }
	                    if( $event_tax ) $taxonomies_array[$prefix.$tax_name]['context'][] = EM_POST_TYPE_EVENT;
	                    if( $loc_tax ) $taxonomies_array[$prefix.$tax_name]['context'][] = EM_POST_TYPE_LOCATION;
	                }	                
	            }
	        }
	        //users can add even more to this if needed, e.g. MS compatability
	        self::$taxonomies_array = apply_filters('em_object_taxonomies', $taxonomies_array);
	    }
	    return self::$taxonomies_array;
	}
	
	/**
	 * WORK IN PROGRESS - not recommended for production use due to lack of syncing with regular condition builder and timezones feature
	 * Builds an array of SQL query conditions based on regularly used arguments
	 * @param array $args
	 * @return array
	 */
	public static function build_wpquery_conditions( $args, $wp_query ){
		global $wpdb;
		
		$args = apply_filters('em_object_build_sql_conditions_args',$args);
		
		//Format the arguments passed on
		$scope = $args['scope'];//undefined variable warnings in ZDE, could just delete this (but dont pls!)
		$recurring = $args['recurring'];
		$recurrence = $args['recurrence'];
		$category = $args['category'];
		$tag = $args['tag'];
		$location = $args['location'];
		$owner = $args['owner'];
		$event = $args['event'];
		$month = $args['month'];
		$year = $args['year'];
		//Create the WHERE statement
		
		//Recurrences
		$query = array();
		if( $recurrence > 0 ){
			$query[] = array( 'key' => '_recurrence_set_id', 'value' => $recurrence, 'compare' => '=' );
		}
		//Dates - first check 'month', and 'year', and adjust scope if needed
		if( !($month=='' && $year=='') ){
			//Sort out month range, if supplied an array of array(month,month), it'll check between these two months
			if( self::array_is_numeric($month) ){
				$date_month_start = $month[0];
				$date_month_end = $month[1];
			}else{
				if( !empty($month) ){
					$date_month_start = $date_month_end = $month;					
				}else{
					$date_month_start = 1;
					$date_month_end = 12;				
				}
			}
			//Sort out year range, if supplied an array of array(year,year), it'll check between these two years
			if( self::array_is_numeric($year) ){
				$date_year_start = $year[0];
				$date_year_end = $year[1];
			}else{
				$date_year_start = $date_year_end = $year;
			}
			$date_start = $date_year_start."-".$date_month_start."-01";
			$date_end = date('Y-m-t', mktime(0,0,0,$date_month_end,1,$date_year_end));
			$scope = array($date_start,$date_end); //just modify the scope here
		}
		//No date requested, so let's look at scope
		if ( is_array($scope) || preg_match( "/^[0-9]{4}-[0-9]{2}-[0-9]{2},[0-9]{4}-[0-9]{2}-[0-9]{2}$/D", $scope ) ) {
			if( !is_array($scope) ) $scope = explode(',',$scope);
			if( !empty($scope[0]) ){
				$EM_DateTime = new EM_DateTime($scope[0]); //create default time in blog timezone
				$start_date = $EM_DateTime->getDate();
				$end_date = $EM_DateTime->modify($scope[1])->getDate();
				if( em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) && $wp_query->query_vars['post_type'] != 'event-recurring' ){
					$query[] = array( 'key' => '_event_start_date', 'value' => array($start_date,$end_date), 'type' => 'DATE', 'compare' => 'BETWEEN');
				}else{
					$query[] = array( 'key' => '_event_start_date', 'value' => $end_date, 'compare' => '<=', 'type' => 'DATE' );
					$query[] = array( 'key' => '_event_end_date', 'value' => $start_date, 'compare' => '>=', 'type' => 'DATE' );
				}
			}
		}elseif ( $scope == 'today' || $scope == 'tomorrow' || preg_match ( "/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/D", $scope ) ) {
			$EM_DateTime = new EM_DateTime($scope); //create default time in blog timezone
			if( em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) && $wp_query->query_vars['post_type'] != 'event-recurring' ){
				$query[] = array( 'key' => '_event_start_date', 'value' => $EM_DateTime->getDate() );
			}else{
				$query[] = array( 'key' => '_event_start_date', 'value' => $EM_DateTime->getDate(), 'compare' => '<=', 'type' => 'DATE' );
				$query[] = array( 'key' => '_event_end_date', 'value' => $EM_DateTime->getDate(), 'compare' => '>=', 'type' => 'DATE' );
			}				
		}elseif ($scope == "future" || $scope == 'past' ){
			$EM_DateTime = new EM_DateTime(); //create default time in blog timezone
			$EM_DateTime->setTimezone('UTC');
			$compare = $scope == 'future' ? '>=' : '<';
			if( em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) && $wp_query->query_vars['post_type'] != 'event-recurring' ){
				$query[] = array( 'key' => '_event_start', 'value' => $EM_DateTime->getDateTime(), 'compare' => $compare, 'type' => 'DATETIME' );
			}else{
				$query[] = array( 'key' => '_event_end', 'value' => $EM_DateTime->getDateTime(), 'compare' => $compare, 'type' => 'DATETIME' );
			}
		}elseif ($scope == "month" || $scope == "next-month" ){
			$EM_DateTime = new EM_DateTime(); //create default time in blog timezone
			if( $scope == 'next-month' ) $EM_DateTime->add('P1M');
			$start_month = $EM_DateTime->modify('first day of this month')->getDate();
			$end_month = $EM_DateTime->modify('last day of this month')->getDate();
			if( em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) && $wp_query->query_vars['post_type'] != 'event-recurring' ){
				$query[] = array( 'key' => '_event_start_date', 'value' => array($start_month,$end_month), 'type' => 'DATE', 'compare' => 'BETWEEN');
			}else{
				$query[] = array( 'key' => '_event_start_date', 'value' => $end_month, 'compare' => '<=', 'type' => 'DATE' );
				$query[] = array( 'key' => '_event_end_date', 'value' => $start_month, 'compare' => '>=', 'type' => 'DATE' );
			}
		}elseif( preg_match('/(\d\d?)\-months/',$scope,$matches) ){ // next x months means this month (what's left of it), plus the following x months until the end of that month.
			$EM_DateTime = new EM_DateTime(); //create default time in blog timezone
			$months_to_add = $matches[1];
			$start_month = $EM_DateTime->getDate();
			$end_month = $EM_DateTime->add('P'.$months_to_add.'M')->format('Y-m-t');
			if( em_get_option('dbem_events_current_are_past', $args['event_archetype'] ) && $wp_query->query_vars['post_type'] != 'event-recurring' ){
				$query[] = array( 'key' => '_event_start_date', 'value' => array($start_month,$end_month), 'type' => 'DATE', 'compare' => 'BETWEEN');
			}else{
				$query[] = array( 'key' => '_event_start_date', 'value' => $end_month, 'compare' => '<=', 'type' => 'DATE' );
				$query[] = array( 'key' => '_event_end_date', 'value' => $start_month, 'compare' => '>=', 'type' => 'DATE' );
			}
		}
		
		//Filter by Location - can be object, array, or id
		if ( is_numeric($location) && $location > 0 ) { //Location ID takes precedence
			$query[] = array( 'key' => '_location_id', 'value' => $location, 'compare' => '=' );
		}elseif ( self::array_is_numeric($location) ){
			$query[] = array( 'key' => '_location_id', 'value' => $location, 'compare' => 'IN' );
		}elseif ( is_object($location) && get_class($location)=='EM_Location' ){ //Now we deal with objects
			$query[] = array( 'key' => '_location_id', 'value' => $location->location_id, 'compare' => '=' );
		}elseif ( is_array($location) && @get_class(current($location)=='EM_Location') ){ //we can accept array of ids or EM_Location objects
			foreach($location as $EM_Location){
				$location_ids[] = $EM_Location->location_id;
			}
			$query[] = array( 'key' => '_location_id', 'value' => $location_ids, 'compare' => 'IN' );
		}
		
		//Filter by Event - can be object, array, or id
		if ( is_numeric($event) && $event > 0 ) { //event ID takes precedence
			$query[] = array( 'key' => '_event_id', 'value' => $event, 'compare' => '=' );
		}elseif ( self::array_is_numeric($event) ){ //array of ids
			$query[] = array( 'key' => '_event_id', 'value' => $event, 'compare' => 'IN' );
		}elseif ( is_object($event) && get_class($event)=='EM_Event' ){ //Now we deal with objects
			$query[] = array( 'key' => '_event_id', 'value' => $event->event_id, 'compare' => '=' );
		}elseif ( is_array($event) && @get_class(current($event)=='EM_Event') ){ //we can accept array of ids or EM_event objects
			foreach($event as $EM_Event){
				$event_ids[] = $EM_Event->event_id;
			}
			$query[] = array( 'key' => '_event_id', 'value' => $event_ids, 'compare' => 'IN' );
		}
		//country lookup
		if( !empty($args['country']) ){
			$countries = em_get_countries();
			//we can accept country codes or names
			if( in_array($args['country'], $countries) ){
				//we have a country name
				$country = array_search($args['country'], $countries);
			}elseif( array_key_exists($args['country'], $countries) ){
				//we have a country code
				$country = $args['country'];					
			}
			if(!empty($country)){
				//get loc ids
				$ids = $wpdb->get_col( $wpdb->prepare("SELECT post_id FROM ".$wpdb->postmeta." WHERE meta_key='_location_country' AND meta_value=%s", $country) );
				$query[] = array( 'key' => '_location_id', 'value' => $ids, 'compare' => 'IN' );
			}
		}
		//state lookup
		if( !empty($args['state']) ){
			$ids = $wpdb->get_col($wpdb->prepare("SELECT post_id FROM ".$wpdb->postmeta." WHERE meta_key='_location_country' AND meta_value='%s'", $args['state']));
			if( is_array($wp_query->query_vars['post__in']) ){
				//remove values not in this array.
				$wp_query->query_vars['post__in'] = array_intersect($wp_query->query_vars['post__in'], $ids);
			}else{
				$wp_query->query_vars['post__in'] = $ids;
			}
		}
		//state lookup
		if( !empty($args['town']) ){			
			$ids = $wpdb->get_col($wpdb->prepare("SELECT post_id FROM ".$wpdb->postmeta." WHERE meta_key='_location_town' AND meta_value='%s'", $args['town']));
			if( is_array($wp_query->query_vars['post__in']) ){
				//remove values not in this array.
				$wp_query->query_vars['post__in'] = array_intersect($wp_query->query_vars['post__in'], $ids);
			}else{
				$wp_query->query_vars['post__in'] = $ids;
			}
		}
		//region lookup
		if( !empty($args['region']) ){	
			$ids = $wpdb->get_col($wpdb->prepare("SELECT post_id FROM ".$wpdb->postmeta." WHERE meta_key='_location_region' AND meta_value='%s'", $args['region']));
			if( is_array($wp_query->query_vars['post__in']) ){
				//remove values not in this array.
				$wp_query->query_vars['post__in'] = array_intersect($wp_query->query_vars['post__in'], $ids);
			}else{
				$wp_query->query_vars['post__in'] = $ids;
			}
		}
		//Add conditions for category selection
		//Filter by category, can be id or comma separated ids
		//TODO create an exclude category option
		if ( is_numeric($category) && $category > 0 ){
			//get the term id directly
			$term = new EM_Category($category);
			if( !empty($term->term_id) ){
				if( EM_MS_GLOBAL ){
					$event_ids = $wpdb->get_col($wpdb->prepare("SELECT object_id FROM ".EM_META_TABLE." WHERE meta_value=%d AND meta_key='event-category'", $term->term_id));
					$query[] = array( 'key' => '_event_id', 'value' => $event_ids, 'compare' => 'IN' );
				}else{
					if( !is_array($wp_query->query_vars['tax_query']) ) $wp_query->query_vars['tax_query'] = array();
					$wp_query->query_vars['tax_query'] = array('taxonomy' => EM_TAXONOMY_CATEGORY, 'field'=>'id', 'terms'=>$term->term_id);
				}
			} 
		}elseif( self::array_is_numeric($category) ){
			$term_ids = array();
			foreach($category as $category_id){
				$term = new EM_Category($category_id);
				if( !empty($term->term_id) ){
					$term_ids[] = $term->term_taxonomy_id;
				}
			}
			if( count($term_ids) > 0 ){
				if( EM_MS_GLOBAL ){
					$event_ids = $wpdb->get_col("SELECT object_id FROM ".EM_META_TABLE." WHERE meta_value IN (".implode(',',$term_ids).") AND meta_name='event-category'");
					$query[] = array( 'key' => '_event_id', 'value' => $event_ids, 'compare' => 'IN' );
				}else{
					if( !is_array($wp_query->query_vars['tax_query']) ) $wp_query->query_vars['tax_query'] = array();
					$wp_query->query_vars['tax_query'] = array('taxonomy' => EM_TAXONOMY_CATEGORY, 'field'=>'id', 'terms'=>$term_ids);
				}
			}
		}		
		//Add conditions for tags
		//Filter by tag, can be id or comma separated ids
		if ( !empty($tag) && !is_array($tag) ){
			//get the term id directly
			$term = new EM_Tag($tag);
			if( !empty($term->term_id) ){
				if( !is_array($wp_query->query_vars['tax_query']) ) $wp_query->query_vars['tax_query'] = array();
				$wp_query->query_vars['tax_query'] = array('taxonomy' => EM_TAXONOMY_TAXONOMY, 'field'=>'id', 'terms'=>$term->term_taxonomy_id);
			} 
		}elseif( is_array($tag) ){
			$term_ids = array();
			foreach($tag as $tag_data){
				$term = new EM_Tag($tag_data);
				if( !empty($term->term_id) ){
					$term_ids[] = $term->term_taxonomy_id;
				}
			}
			if( count($term_ids) > 0 ){
				if( !is_array($wp_query->query_vars['tax_query']) ) $wp_query->query_vars['tax_query'] = array();
				$wp_query->query_vars['tax_query'] = array('taxonomy' => EM_TAXONOMY_TAXONOMY, 'field'=>'id', 'terms'=>$term_ids);
			}
		}
	
		//If we want rsvped items, we usually check the event
		if( $args['bookings'] == 1 ){
			$query[] = array( 'key' => '_event_rsvp', 'value' => 1, 'compare' => '=' );
		}
		//Default ownership belongs to an event, child objects can just overwrite this if needed.
		if( is_numeric($owner) ){
			$wp_query->query_vars['author'] = $owner;
		}elseif( $owner == 'me' && is_user_logged_in() ){
			$wp_query->query_vars['author'] = get_current_user_id();
		}
	  	if( !empty($query) && is_array($query) ){
			$wp_query->query_vars['meta_query'] = $query;
	  	}
		return apply_filters('em_object_build_wp_query_conditions', $wp_query);
	}
	
	/**
	 * Sanitizes the ORDER BY part of the SQL statement so only valid fields are supplied for ordering.
	 * Also combines default orders which can be an array which is applied to each specific ordering field, or just one value applied to all ordering fields.
	 * @uses EM_Object::build_sql_x_by_helper()
	 * @param array $args
	 * @param array $accepted_fields
	 * @param string|array $default_order
	 * @return array
	 */
	public static function build_sql_orderby( $args, $accepted_fields, $default_order = 'ASC' ){
		//First, ORDER BY
		$args = apply_filters('em_object_build_sql_orderby_args', $args, $accepted_fields, $default_order );
		$orderby = self::build_sql_x_by_helper($args['orderby'], $args['order'], $accepted_fields, $default_order);
		return apply_filters('em_object_build_sql_orderby', $orderby, $args, $accepted_fields, $default_order );
	}
	
	/**
	 * Returns a set of further fields this query should be grouped by. Not required for straight-forward GROUP BY SQL queries. 
	 * This is supplementary for build_sql_groupby in cases such as events, where ordering and grouping are mixed due to complex SQL sub-queries and partitions. 
	 * @uses EM_Object::build_sql_x_by_helper()
	 * @param unknown $args
	 * @param unknown $accepted_fields
	 * @param string $default_order
	 * @return mixed|unknown
	 */
	public static function build_sql_groupby_orderby( $args, $accepted_fields, $default_order = 'ASC' ){
		$args = apply_filters('em_object_build_sql_groupby_orderby_args', $args, $accepted_fields, $default_order );
		$orderby = self::build_sql_x_by_helper($args['groupby_orderby'], $args['groupby_order'], $accepted_fields, $default_order);
		return apply_filters('em_object_build_sql_groupby_orderby', $orderby, $args, $accepted_fields, $default_order );
	}
	
	/**
	 * Sanitizes the group by statement so it includes only accepted fields. Returns an array of valid field names to group by.
	 * Optionally, if a $groupby_order value is provided then ASC/DESC values will be added to each field similar to EM_Object::build_sql_orderby
	 * @uses EM_Object::build_sql_x_by_helper()
	 * @param unknown $args
	 * @param unknown $accepted_fields
	 * @param string $groupby_order
	 * @param string $default_order
	 * @return mixed|unknown
	 */
	public static function build_sql_groupby( $args, $accepted_fields, $groupby_order = false, $default_order = 'ASC' ){
		//First, ORDER BY
		$args = apply_filters('em_object_build_sql_groupby_args', $args);
		$groupby = self::build_sql_x_by_helper($args['groupby'], $groupby_order, $accepted_fields, $default_order);
		return apply_filters('em_object_build_sql_groupby', $groupby, $args, $accepted_fields);
	}
	
	/**
	 * Helper for building arrays of fields 
	 * @param unknown $x_by_field
	 * @param unknown $order
	 * @param unknown $accepted_fields
	 * @param string $default_order
	 * @return array
	 */
	protected static function build_sql_x_by_helper($x_by_field, $order, $accepted_fields, $default_order = 'ASC' ){
		$x_by = array();
		if(is_array($x_by_field)){
			//Clean orderby array so we only have accepted values
			foreach( $x_by_field as $key => $field ){
				if( array_key_exists($field, $accepted_fields) ){
					//maybe cases we're given an array where keys are shortcut names e.g. id => event_id - this way will be deprecated at one point
					$x_by[] = $accepted_fields[$field];
				}elseif( in_array($field,$accepted_fields) ){
					$x_by[] = $field;
				}elseif( !is_numeric($key) && array_key_exists( $key, $accepted_fields) ){
					$x_by[] = $field;
				}else{
					unset($x_by[$key]);
				}
			}
		}elseif( $x_by_field != '' && array_key_exists($x_by_field, $accepted_fields) ){
			$x_by[] = $accepted_fields[$x_by_field];
		}elseif( $x_by_field != '' && in_array($x_by_field, $accepted_fields) ){
			$x_by[] = $x_by_field;
		}
		//ORDER
		if( $order !== false ){
			foreach($x_by as $i => $field){
				$x_by[$i] .= ' ';
				if(is_array($order)){
					//If order is an array, we'll go through the orderby array and match the order values (in order of array) with orderby values
					if( in_array($order[$i], array('ASC','DESC','asc','desc')) ){
						$x_by[$i] .= $order[$i];
					}else{
						//If orders don't match up, or it's not ASC/DESC, the default events search in EM settings/options page will be used.
						$x_by[$i] .= $default_order;
					}
				}else{
					$x_by[$i] .= ( in_array($order, array('ASC','DESC','asc','desc')) ) ? $order : $default_order;
				}
			}
		}
		return $x_by;
	}
	
	/**
	 * Fixes ambiguous fields in a given array (which can contain prefixed ASC/DESC arguments) and give them scope of events table
	 * @param array $fields
	 * @return array
	 */
	protected static function build_sql_ambiguous_fields_helper( $fields, $reserved_fields = array(), $prefix = 'table_name' ){
		foreach($fields as $k => $v){
			$needle = trim(str_replace(array('ASC','DESC'), '', $v)); //remove ASC DESC for searching/comparison arrays such as order by
			if( in_array($needle, $reserved_fields) ){
				$fields[$k] = $prefix.'.'.$v;
			}
		}
		return $fields;
	}
	
	/**
	 * Gets array of searchable variables that should be considered in a $_REQUEST variable
	 *
	 * WARNING: $args must never contain unsanitized data. This method vets $request, not $args — anything already in
	 * $args is taken as trusted and returned as-is. Never pass $_REQUEST, $_GET, $_POST or cookie data in as $args
	 * (array_merge($args, $_REQUEST) included); pass it as $request and let this method extract what is allowed.
	 *
	 * @param array $args Arguments to include in returned array, from trusted code only - see warning above
	 * @param string $filter Filters out any unrecognized arguments already passed into $args
	 * @param array $request defaults to $_REQUEST if empty but can be an array of items to go through instead
	 * @param array $accepted_searches defaults to EM_Object::get_search_defaults(), objects should call self::get_search_defaults() to get around late static binding problems
	 * @return array
	 */
	public static function get_post_search($args = array(), $filter = false, $request = array(), $accepted_searches = array()){
		if( empty($request) ) $request = $_REQUEST;
		if( !empty($request['em_search']) && empty($args['search']) ) $request['search'] = $request['em_search']; //em_search is included to circumvent wp search GET/POST clashes
		$accepted_searches = !empty($accepted_searches) ? $accepted_searches : static::get_default_search();
		// header_format and date_format are display templates too, despite the inverted naming.
		$display_templates = array('format', 'format_header', 'format_footer', 'header_format', 'date_format');
		$accepted_searches = array_diff($accepted_searches, $display_templates);
		$accepted_searches = apply_filters('em_accepted_searches', $accepted_searches, $args);
		// templates are echoed as HTML, so a request may only name one and get the format registered under that name
		foreach( $display_templates as $display_template ){
			if( !empty($request[$display_template]) ){
				$format = EM_Formats::get_registered_format( $request[$display_template] );
				if( $format !== false ) $args[$display_template] = $format;
			}
		}
		//merge variables from the $request into $args
		foreach($request as $post_key => $post_value){
			if( in_array($post_key, $accepted_searches) && !empty($post_value) ){
				if(is_array($post_value)){
					$post_value = implode(',',$post_value);
				}else{
				    $post_value =  wp_unslash($post_value);
				}
				if($post_value != ',' ){
					$args[$post_key] = $post_value;
				}elseif( $post_value == ',' && $post_key == 'scope' && (empty($args['scope']) || $args['scope'] == array('','')) ){
					//unset the scope if no value is provided - ',' is an empty value
					unset($args['scope']);
				}
			}
		}
		if( $filter ){
			foreach($args as $arg_key => $arg_value){
				if( !in_array($arg_key, $accepted_searches) ){
					unset($args[$arg_key]);
				}
			}
		}
		return apply_filters('em_get_post_search', $args);
	}
	
	/**
	 * Generates pagination for classes like EM_Events based on supplied arguments and whether AJAX is enabled.
	 * 
	 * @param array $args The arguments being searched for
	 * @param integer $count The number of total items to paginate through
	 * @param string $search_action The name of the action query var used to trigger a search - used in AJAX requests and normal searches
	 * @param array $default_args The default arguments and values this object accepts, used to compare against $args to create a querystring
	 * @return string
	 * @uses em_paginate()
	 */
	public static function get_pagination_links($args, $count, $search_action = 'search_events', $default_args = array()){
		$limit = ( !empty($args['limit']) && is_numeric($args['limit']) ) ? $args['limit']:false;
		$page = ( !empty($args['page']) && is_numeric($args['page']) ) ? $args['page']:1;
		$pno = !empty($args['page_queryvar']) ? $args['page_queryvar'] : 'pno';
		$default_pag_args = array($pno=>'%PAGE%', 'page'=>null, 'search'=>null, 'action'=>null, 'pagination'=>null); //clean out the bad stuff, set up page number template
		$page_url = $_SERVER['REQUEST_URI'];
		//$default_args are values that can be added to the querystring for use in searching events in pagination either in searches or ajax pagination
		if( !empty($_REQUEST['action']) && $_REQUEST['action'] == $search_action && empty($default_args) ){
			//due to late static binding issues in PHP, this'll always return EM_Object::get_default_search so this is a fall-back
			$default_args = static::get_default_search();
		}
		//go through default arguments (if defined) and build a list of unique non-default arguments that should go into the querystring
		$unique_args = array(); //this is the set of unique arguments we'll add to the querystring
		$ignored_args = array('offset', 'ajax', 'array', 'pagination','format','format_header','format_footer','header_format','date_format','page');
		foreach( $default_args as $arg_key => $arg_default_val){
			if( array_key_exists($arg_key, $args) && !in_array($arg_key, $ignored_args) ){
				//if array exists, implode it in case one value is already imploded for matching purposes
				$arg_val = is_array($args[$arg_key]) ? implode(',', $args[$arg_key]) : $args[$arg_key];
				$arg_default_val = is_array($arg_default_val) ? implode(',',$arg_default_val) : $arg_default_val;
				if( $arg_val != $arg_default_val ){
					$unique_args[$arg_key] = $arg_val;
				}
			}
		}
		if( !empty($unique_args['search']) ){ 
			$unique_args['em_search'] = $unique_args['search']; //special case, since em_search is used in links rather than search, which we remove below
			unset($unique_args['search'], $default_pag_args['search']);
		}
		//build general page link with all arguments
		$pag_args = array_merge($unique_args, $default_pag_args);
		//if we're using ajax or already did an events search via a form, add the action here for pagination links
		if( !empty($args['ajax']) || (!empty($_REQUEST['action']) && $_REQUEST['action'] == $search_action ) ){
			$unique_args['action'] = $pag_args['action'] = $search_action;
		}
		//if we're in an ajax call, make sure we aren't calling admin-ajax.php
		if( defined('DOING_AJAX') ) $page_url = em_wp_get_referer();
		//finally, glue the url with querystring and pass onto pagination function
		$page_args_escaped = array();
		foreach( $pag_args as $key => $val ){
			$page_args_escaped[$key] = $val && is_string($val) ? urlencode($val) : $val;
		}
		$page_link_template = em_add_get_params($page_url, $page_args_escaped, false, false); //don't html encode, so em_paginate does its thing;
		//if( empty($args['ajax']) || defined('DOING_AJAX') ) $unique_args = array(); //don't use data method if ajax is disabled or if we're already in an ajax request (SERP irrelevenat)
		$return = apply_filters('em_object_get_pagination_links', em_paginate( $page_link_template, $count, $limit, $page, $unique_args, !empty($args['ajax']) ), $page_link_template, $count, $limit, $page);
		//if PHP is 5.3 or later, you can specifically filter by class e.g. em_events_output_pagination - this replaces the old filter originally located in the actual child classes
		if( function_exists('get_called_class') ){
			$return = apply_filters(strtolower(get_called_class()).'_output_pagination', $return, $page_link_template, $count, $limit, $page);
		}
		return $return;
	}
	
	public function __get( $prop ){
		if ( !empty(static::$field_shortcuts[$prop]) ){
			$property = static::$field_shortcuts[$prop];
			return $this->{$property};
		} elseif ( !empty($this->shortnames[$prop]) ){
			$property = $this->shortnames[$prop];
			return $this->{$property};
		} elseif ( isset($this->dynamic_properties[$prop]) ) {
			return $this->dynamic_properties[$prop];
		}
		return null;
	}
	
	/**
	 * Sets a property of this object, either in the object itself or in the dynamic_properties array. Accepts shortcut names for properties as mapped by the $field_shortcuts or $shortnames array.
	 * @param string $prop
	 * @param mixed $val
	 */
	public function __set($prop, $val ){
		if ( !empty(static::$field_shortcuts[$prop]) ) {
			$property = static::$field_shortcuts[$prop];
			if( !empty($this->fields[$property]['type']) && $this->fields[$property]['type'] == '%d' ){
				$val = (int) $val;
			}
			$this->{$property} = $val;
		} elseif ( !empty($this->shortnames[$prop]) ) {
			$property = $this->shortnames[$prop];
			if( !empty($this->fields[$property]['type']) && $this->fields[$property]['type'] == '%d' ){
				$val = (int) $val;
			}
			$this->{$property} = $val;
		} else {
			// save it to an declared array property to avoid 8.2 errors, access it the same way
			$this->dynamic_properties[$prop] = $val;
		}
	}
	
	/**
	 * Checks if a property has been set, either in the object itself or in the dynamic_properties array.
	 * @param string $prop
	 * @return boolean
	 */
	public function __isset( $prop ){
		if( !empty($this->shortnames[$prop]) ){
			$property = $this->shortnames[$prop];
			return !empty($this->{$property});
		} elseif( !empty(static::$field_shortcuts[$prop]) ){
			$property = static::$field_shortcuts[$prop];
			return !empty($this->{$property});
		} elseif ( isset($this->dynamic_properties[$prop]) ) {
			return isset($this->dynamic_properties[$prop]);
		}
		return !empty($this->{$prop});
	}
	
	/**
	 * Returns the id of a particular object in the table it is stored, be it Event (event_id), Location (location_id), Tag, Booking etc.
	 * @return int 
	 */
	function get_id(){
	    switch( get_class($this) ){
	        case 'EM_Event':
	            return $this->event_id;
	        case 'EM_Location':
	            return $this->location_id;
	        case 'EM_Category':
	            return $this->term_id;
	        case 'EM_Tag':
	            return $this->term_id;
	        case 'EM_Ticket':
	            return $this->ticket_id;
	        case 'EM_Ticket_Booking':
	            return $this->ticket_booking_id;
	    }
	    return 0;
	}
	
	/**
	 * Returns the user id for the owner (author) of a particular object in the table it is stored, be it Event (event_owner) or Location (location_owner).
	 * This function accounts for the fact that previously the property $this->owner was used by objects as a shortcut and consequently in code in EM_Object, which should now use this method instead.
	 * Extending classes should override this and provide the relevant user id that owns this object instance. 
	 * @return int
	 */	
	function get_owner(){
		if( !empty($this->owner) ) return $this->owner;
	    switch( get_class($this) ){
	        case 'EM_Event':
	            return $this->event_owner;
	        case 'EM_Location':
	            return $this->location_owner;
	    }
	    return 0;
	}
	
	/**
	 * Used by "single" objects, e.g. bookings, events, locations to verify if they have the capability to edit this or someone else's object. Relies on the fact that the object has an owner property with id of user (or admin capability must pass).
	 * @param string $owner_capability If the object has an owner property and the user id matches that, this capability will be checked for.
	 * @param string $admin_capability If the user isn't the owner of the object, this capability will be checked for.
	 * @return boolean
	 */
	function can_manage( $owner_capability = false, $admin_capability = false, $user_to_check = false ){
		global $em_capabilities_array;
		//if multisite and super admin, just return true
		if( is_multisite() && em_wp_is_super_admin() ){ return true; }
		//set user to the desired user we're verifying, otherwise default to current user
	    if( $user_to_check ){
	    	$user = new WP_User($user_to_check);	
	    }
	    if( empty($user->ID) ) $user = wp_get_current_user();
		//do they own this?
		$owner_id = $this->get_owner();
		$is_owner = ( (!empty($owner_id) && ($owner_id == get_current_user_id()) || !$this->get_id() || (!empty($user) && $owner_id == $user->ID)) );
		//now check capability
		$can_manage = false;
		if( $is_owner && $owner_capability && $user->has_cap($owner_capability) ){
			//user owns the object and can therefore manage it
			$can_manage = true;
		}elseif( $owner_capability && array_key_exists($owner_capability, $em_capabilities_array) ){
			//currently user is not able to manage as they aren't the owner
			$error_msg = $em_capabilities_array[$owner_capability];
		}
		//admins have special rights
		if( !$admin_capability ) $admin_capability = $owner_capability;
		if( $admin_capability && $user->has_cap($admin_capability) ){
			$can_manage = true;
		}elseif( $admin_capability && array_key_exists($admin_capability, $em_capabilities_array) ){
			$error_msg = $em_capabilities_array[$admin_capability];
		}
		$can_manage = apply_filters('em_object_can_manage', $can_manage, $this, $owner_capability, $admin_capability, $user_to_check);
		if( !$can_manage && !$is_owner && !empty($error_msg) ){
			$this->add_error($error_msg);
		}
		return $can_manage;
	}

	
	public static function ms_global_switch(){
		if( EM_MS_GLOBAL ){
			//If in multisite global, then get the main blog
			global $current_site;
			switch_to_blog($current_site->blog_id);
		}
	}
	
	public static function ms_global_switch_back(){
		if( EM_MS_GLOBAL ){
			restore_current_blog();
		}
	}
	
	/**
	 * Save an array into this class.
	 * If you provide a record from the database table corresponding to this class type it will add the data to this object.
	 * @param array $array
	 * @return null
	 */
	function to_object( $array = array(), $addslashes = false ){
		//Save core data
		if( is_array($array) ){
			$array = apply_filters('em_to_object', $array);
			foreach ( array_keys($this->fields) as $key ) {
				if(array_key_exists($key, $array)){
					if( !is_object($array[$key]) && !is_array($array[$key]) ){
						$array[$key] = ($addslashes) ? wp_unslash($array[$key]):$array[$key];
					}elseif( is_array($array[$key]) ){
						$array[$key] = ($addslashes) ? wp_unslash_deep($array[$key]):$array[$key];
					}
					$this->$key = $array[$key];
				}
			}
		}
	}
	
	/**
	 * Copies all the properties to shorter property names for compatability, do not use the old properties.
	 */
	function compat_keys(){
		foreach($this->fields as $key => $fieldinfo){
			if( !empty($fieldinfo['name']) ){
			    $field_name = $fieldinfo['name'];
				if(!empty($this->$key)) $this->$field_name = $this->$key;
			}
		}
	}

	/**
	 * Returns this object in the form of an array, useful for saving directly into a database table.
	 * @return array
	 */
	function to_array($db = false){
		$array = array();
		foreach ( $this->fields as $key => $val ) {
			if($db){
				// TODO - This could and probably should check for false values too, but wider implications need extensive testing
				if( !empty($this->$key) || $this->$key === 0 || $this->$key === '0' || $this->$key === 0.0 || empty($val['null']) ){
					$array[$key] = $this->$key;
				}elseif( $this->$key === null && !empty($val['null']) ){
					$array[$key] = null;
				}
			}else{
				$array[$key] = $this->$key;
			}
		}
		return apply_filters('em_to_array', $array);
	}
	

	/**
	 * Function to retreive wpdb types for all fields, or if you supply an assoc array with field names as keys it'll return an equivalent array of wpdb types
	 * @param array $array
	 * @return array:
	 */
	function get_types($array = array()){
		$types = array();
		if( count($array)>0 ){
			//So we look at assoc array and find equivalents
			foreach ($array as $key => $val){
				$types[] = $this->fields[$key]['type'];
			}
		}else{
			//Blank array, let's assume we're getting a standard list of types
			foreach ($this->fields as $field){
				$types[] = $field['type'];
			}
		}
		return apply_filters('em_object_get_types', $types, $this, $array);
	}	
	
	function get_fields( $inverted_array=false ){
		if( is_array($this->fields) ){
			$return = array();
			foreach($this->fields as $fieldName => $fieldArray){
				if($inverted_array){
					if( !empty($fieldArray['name']) ){
						$return[$fieldArray['name']] = $fieldName;
					}else{
						$return[$fieldName] = $fieldName;
					}
				}else{
					$return[$fieldName] = $fieldArray['name'];
				}
			}
			return apply_filters('em_object_get_fields', $return, $this, $inverted_array);
		}
		return apply_filters('em_object_get_fields', array(), $this, $inverted_array);
	}
	
	/**
	 * Cleans arrays that contain id lists. Takes an array of items and will clean the keys passed in second argument so that if they keep numbers, explode comma-separated numbers, and unsets the key if there's any other value
	 * @param array $array
	 * @param array $id_atts
	 */
	public static function clean_id_atts( $array = array(), $id_atts = array() ){
		if( is_array($array) && is_array($id_atts) ){
			foreach( $array as $key => $string ){
				if( in_array($key, $id_atts) ){
					//This is in the list of atts we want cleaned
					if( is_numeric($string) ){
						$array[$key] = (int) $string;
					}elseif( self::array_is_numeric($string) ){
						$array[$key] = $string;
					}elseif( $string && !is_array($string) && preg_match('/^( ?[\-0-9] ?,?)+$/D', $string) ){
					    $array[$key] = explode(',', str_replace(' ','',$string));
					}else{
						//No format we accept
						unset($array[$key]);
					}
				}
			}
		}
		return $array;
	}
		
	/**
	 * Send an email and log errors in this object
	 * @param string $subject
	 * @param string $body
	 * @param string $email
	 * @param array $attachments
	 * @param array $args
	 * @return string
	 */
	function email_send($subject, $body, $email, $attachments = array(), $args = array() ){
		global $EM_Mailer;
		if( !empty($subject) ){
			if( !is_object($EM_Mailer) ){
				$EM_Mailer = new EM_Mailer();
			}
			if( !$EM_Mailer->send($subject,$body,$email, $attachments, $args) ){
				if( is_array($EM_Mailer->errors) ){
					foreach($EM_Mailer->errors as $error){
						$this->errors[] = $error;
					}
				}else{
					$this->errors[] = $EM_Mailer->errors;
				}
				return false;
			}
		}
		return true;
	}
	
	/**
	 * Will return true if this is a simple (non-assoc) numeric array, meaning it has at one or more numeric entries and nothing else
	 * @param mixed $array
	 * @return boolean
	 */
	public static function array_is_numeric($array){
		$results = array();
		if(is_array($array)){
			foreach($array as $key => $item){
				$results[] = (is_numeric($item)&&is_numeric($key));
			}
		}
		return (!in_array(false, $results) && count($results) > 0);
	}

	/**
	 * Checks and returns a sanitized array of integer numbers
	 * @param $array
	 *
	 * @return array
	 */
	public static function sanitize_numeric_array( $array ) {
		$sanitized_array = array();
		if ( !is_array( $array ) ) {
			$array = explode( ',', $array );
		}
		if( static::array_is_numeric( $array ) ) {
			foreach ( $array as $key => $value ) {
				if ( is_numeric( $value ) ) {
					$sanitized_array[ $key ] = intval($value);
				}
			}
		}
		return $sanitized_array;
	}
	
	/**
	 * Returns an array of errors in this object
	 * @return array 
	 */
	function get_errors(){
		if(is_array($this->errors)){
			return $this->errors;
		}else{
			return array();
		}
	}
	
	/**
	 * Adds an error to the object, if $errors is an array then multiple error strings can be added, WP_Error object will also add all messages.
	 *
	 * @param string|array|WP_Error|EM_Exception $errors
	 *
	 * @return void
	 */
	function add_error($errors){
		if( !is_array($errors) ) {
			//make errors var an array if it isn't already
			if ( is_wp_error($errors) ) {
				$errors = $errors->get_error_messages();
			} elseif ( $errors instanceof EM_Exception ) {
				$errors = $errors->get_messages();
			} else {
				$errors = array($errors);
			}
		}
		if(!is_array($this->errors)){ $this->errors = array(); } //create empty array if this isn't an array
		foreach($errors as $key => $error){			
			if( !in_array($error, $this->errors) ){
			    if( !is_array($error) ){
					$this->errors[] = $error;
			    }else{
			        $this->errors[] = array($key => $error);
			    }
			}
		}
	}
	
	/**
	 * Converts an array to JSON format, useful for outputting data for AJAX calls. Uses a PHP4 fallback function, given it doesn't support json_encode().
	 * @param array $array
	 * @return string
	 */
	public static function json_encode($array){
	    $array = apply_filters('em_object_json_encode_pre',$array);
		if( function_exists("json_encode") ){
			$return = json_encode($array);
		}else{
			$return = self::array_to_json($array);
		}
		if( isset($_REQUEST['callback']) && preg_match("/^jQuery[_a-zA-Z0-9]+$/", $_REQUEST['callback']) ){
			$return = $_REQUEST['callback']."($return)";
		}
		return apply_filters('em_object_json_encode', $return, $array);
	}
	
	/**
	 * Outputs array as JSON format as per EM_Object::json_encode()
	 * @param $array
	 *
	 * @return void
	 * @see EM_Object::json_encode()
	 */
	public static function json_encode_e($array){
		echo static::json_encode($array);
	}
	
	/**
	 * Compatible json encoder function for PHP4
	 * @param array $array
	 * @return string
	 */
	function array_to_json($array){
		//PHP4 Comapatability - This encodes the array into JSON. Thanks go to Andy - http://www.php.net/manual/en/function.json-encode.php#89908
		if( !is_array( $array ) ){
	        $array = array();
	    }
	    $associative = count( array_diff( array_keys($array), array_keys( array_keys( $array )) ));
	    if( $associative ){
	        $construct = array();
	        foreach( $array as $key => $value ){
	            // We first copy each key/value pair into a staging array,
	            // formatting each key and value properly as we go.
	            // Format the key:
	            if( is_numeric($key) ){
	                $key = "key_$key";
	            }
	            $key = "'".addslashes($key)."'";
	            // Format the value:
	            if( is_array( $value )){
	                $value = self::array_to_json( $value );
	            }else if( is_bool($value) ) {
	            	$value = ($value) ? "true" : "false";
	            }else if( !is_numeric( $value ) || is_string( $value ) ){
	                $value = "'".addslashes($value)."'";
	            }
	            // Add to staging array:
	            $construct[] = "$key: $value";
	        }
	        // Then we collapse the staging array into the JSON form:
	        $result = "{ " . implode( ", ", $construct ) . " }";
	    } else { // If the array is a vector (not associative):
	        $construct = array();
	        foreach( $array as $value ){
	            // Format the value:
	            if( is_array( $value )){
	                $value = self::array_to_json( $value );
	            } else if( !is_numeric( $value ) || is_string( $value ) ){
	                $value = "'".addslashes($value)."'";
	            }
	            // Add to staging array:
	            $construct[] = $value;
	        }
	        // Then we collapse the staging array into the JSON form:
	        $result = "[ " . implode( ", ", $construct ) . " ]";
	    }		
	    return $result;
	}	
	
	/*
	 * START IMAGE UPlOAD FUNCTIONS
	 * Used for various objects, so shared in one place 
	 */
	/**
	 * Returns the type of image in lowercase, if $path is true, a base filename is returned which indicates where to store the file from the root upload folder.
	 * @param unknown_type $path
	 * @return mixed|mixed
	 */
	function get_image_type($path = false){
		$type = false;
		switch( get_class($this) ){
			case 'EM_Event':
				$dir = (EM_IMAGE_DS == '/') ? 'events/':'';
				$type = 'event';
				break;
			case 'EM_Location':
				$dir = (EM_IMAGE_DS == '/') ? 'locations/':'';
				$type = 'location';
				break;
			case 'EM_Category':
				$dir = (EM_IMAGE_DS == '/') ? 'categories/':'';
				$type = 'category';
				break;
		} 	
		if($path){
			return apply_filters('em_object_get_image_type',$dir.$type, $path, $this);
		}
		return apply_filters('em_object_get_image_type',$type, $path, $this);
	}
	
	function get_image_url($size = 'full'){
		$image_url = $this->image_url;
		if( !empty($this->post_id) && (empty($this->image_url) || $size != 'full') ){
			$post_thumbnail_id = get_post_thumbnail_id( $this->post_id );
			$src = wp_get_attachment_image_src($post_thumbnail_id, $size);
			if( !empty($src[0]) && $size == 'full' ){
				$image_url = $this->image_url = $src[0];
			}elseif(!empty($src[0])){
				$image_url = $src[0];
			}
			//legacy image finder, annoying, but must be done
			if( empty($image_url) ){
				$type = $this->get_image_type();
				if( get_class($this) == "EM_Location" ){
				    $id = $this->location_id;
				}else{
				    $id = $this->id;
				}
				if( $type ){
				  	foreach($this->mime_types as $mime_type) {
						$file_name = $this->get_image_type(true)."-{$id}.$mime_type";
						if( file_exists( EM_IMAGE_UPLOAD_DIR . $file_name) ) {
				  			$image_url = $this->image_url = EM_IMAGE_UPLOAD_URI.$file_name;
						}
					}
				}
			}
		}
		return apply_filters('em_object_get_image_url', $image_url, $this);
	}
	
	/**
	 * @param $force_delete
	 *
	 * @return mixed|null
	 * @uses EM\Uploads\Uploader::post_image_delete()
	 * @deprecated use EM\Uploads\Uploader::post_image_delete() sinstead.
	 */
	function image_delete( $force_delete=true ) {
		return apply_filters('em_object_get_image_url', EM\Uploads\Uploader::post_image_delete( $this->post_id, $force_delete ), $this);
	}
	
	/**
	 * Handles uploading event and location images
	 *
	 * @return mixed|null
	 * @deprecated use EM\Uploads\Uploader::post_image_upload() sinstead.
	 * @uses EM\Uploads\Uploader::post_image_upload()
	 */
	function image_upload(){
		$type = $this->get_image_type();
		$user_to_check = ( !is_user_logged_in() && $this->get_option('dbem_events_anonymous_submissions') ) ? $this->get_option('dbem_events_anonymous_user'):false;
		if ( $this->can_manage('upload_event_images','upload_event_images', $user_to_check) ) {
			// proceed with upload
			try {
				EM\Uploads\Uploader::post_image_upload( $type . '_image', $this->post_id );
				return apply_filters( 'em_object_image_upload', true, $this );
			} catch ( EM_Exception $e ) {
				$this->add_error( $e );
			}
		}
		return apply_filters( 'em_object_image_upload', false, $this );
	}
	
	/**
	 * Handles uploading event and location images
	 *
	 * @return mixed|null
	 * @deprecated use EM\Uploads\Uploader::validate() sinstead.
	 * @uses EM\Uploads\Uploader::validate()
	 */
	function image_validate(){
		$type = $this->get_image_type();
		try {
			EM\Uploads\Uploader::prepare( $type . '_image' );
			$max_filesize = $this->get_option('dbem_image_max_size') > wp_max_upload_size() ? wp_max_upload_size() : $this->get_option('dbem_image_max_size');
			$result = EM\Uploads\Uploader::validate( $type . '_image', ['type' => 'image', 'max_file_size' => $max_filesize] ) !== false; // no false returned, error thrown if not true/null
		} catch ( EM_Exception $e ) {
			$this->add_error( $e );
			$result = false;
		}
		return apply_filters('em_object_image_validate', $result, $this, $result);
	}
	
	/*
	 * END IMAGE UPlOAD FUNCTIONS
	 */
	
	function output_excerpt($excerpt_length = 55, $excerpt_more = '[...]', $cut_excerpt = true){
		if( !empty($this->post_excerpt) ){
			$replace = $this->post_excerpt;
		}else{
			$replace = $this->post_content;
		}
		if( empty($this->post_excerpt) || $cut_excerpt ){
			if ( preg_match('/<!--more(.*?)?-->/', $replace, $matches) ) {
				$content = explode($matches[0], $replace, 2);
				$replace = force_balance_tags($content[0]);
			}
			if( !empty($excerpt_length) ){
				//shorten content by supplied number - copied from wp_trim_excerpt
				$replace = strip_shortcodes( $replace );
				$replace = str_replace(']]>', ']]&gt;', $replace);
				$replace = wp_trim_words( $replace, $excerpt_length, $excerpt_more );
			}
		}
		return $replace;
	}

	function sanitize_time( $time ){
		if( !empty($time) && preg_match ( '/^([01]?\d|2[0-3]):([0-5]\d) ?(AM|PM)?$/', $time, $match ) ){
			if( !empty($match[3]) && $match[3] == 'PM' && $match[1] != 12 ){
				$match[1] = 12+$match[1];
			}elseif( !empty($match[3]) && $match[3] == 'AM' && $match[1] == 12 ){
				$match[1] = '00';
			} 
			$time = $match[1].":".$match[2].":00";
			return $time;
		}
		return '00:00:00';
	}

	/**
	 * Formats a price according to settings and currency
	 * @param double $price
	 * @return string
	 */
	function format_price( $price ){
		return em_get_currency_formatted( $price );
	}
	
	/**
	 * Returns contextual tax rate of object, which may be global or instance-specific. By default a number representing percentage is provided, e.g. 21% returns 21. 
	 * If $decimal is set to true, 21% is returned as 0.21  
	 * @param boolean $decimal If set to true, a decimal representation will be returned.
	 * @return float
	 */
	function get_tax_rate( $decimal = false ){
		$tax_rate = $this->get_option('dbem_bookings_tax');
		$tax_rate = str_replace(',', '.', (string) $tax_rate);
		$tax_rate = (float) preg_replace('/[^0-9.]/', '', $tax_rate);
		$tax_rate = ($tax_rate > 0) ? $tax_rate : 0;
		if( $decimal && $tax_rate > 0 ) $tax_rate = $tax_rate / 100;
		return $tax_rate;
	}
	
	/**
	 * Untility function, generates a UUIDv4 without dashes.
	 * @return string
	 */
	function generate_uuid(){
		return str_replace('-', '', wp_generate_uuid4());
	}

	/**
	 * maybe_unserialize() variant that never instantiates objects (allowed_classes => false).
	 */
	public static function maybe_unserialize( $original ){
		if ( is_serialized( $original ) ) {
			return @unserialize( trim( $original ), array( 'allowed_classes' => false ) );
		}
		return $original;
	}
	
	/**
	 * Process meta stored in a meta table. Meta stored without a preceding _ are considered as-is values and added as a key/value pair to returned meta array, otherwise they are considered as arrays and parsed accordingly, so that each array item is stored as a separate row in the database and rebuilt when loaded.
	 *
	 * Prior to EM 6.4.5.1, arrays were stored by delimiting the key and subkey by an underscore, but this will cause issues if the key itself contains an underscore. As of 6.5 a keys will be delimited by a pipe instead, to allow for underscore use as needed.
	 * Backward compatibility is still supported for older records that weren't stored with a pipe and the last underscore is considered the delimiter for the subkey. Developers should ensure if they have keys and subkeys with underscores to find a way to migrate that info with SQL to add a pipe in between.
	 * This decision was taken because tickets in our core code do not have any subkeys contaning underscores, therefore considered a 'safe' approach.
	 *
	 * @param $raw_meta
	 *
	 * @return array
	 */
	function process_meta( $raw_meta ){
		$processed_meta = array();
		foreach( $raw_meta as $meta ){
			$meta_value = self::maybe_unserialize($meta['meta_value']);
			$meta_key = $meta['meta_key'];
			if( preg_match('/^_([a-zA-Z\-0-9 _]+)\|([^\|]+)?$/', $meta_key, $match) || preg_match('/^_([a-zA-Z\-0-9]+)_(.+)$/', $meta_key, $match) ){
				$key = $match[1];
				if( empty($processed_meta[$key]) ) $processed_meta[$key] = array();
				$subkey = isset($match[2]) ? $match[2] : count($processed_meta[$key]); // allows for storing arrays without a key, such as _beverage_choice| can be stored multiple times in a row if key is not relevant
				if( !empty($processed_meta[$key][$subkey]) && preg_match('/\|$/', $meta_key) ){
					if( !is_array($processed_meta[$key][$subkey]) ) {
						$processed_meta[$key][$subkey] = array($processed_meta[$key][$subkey]);
					}
					$processed_meta[$key][$subkey][] = $meta_value;
				}else{
					$processed_meta[$key][$subkey] = $meta_value;
				}
			}else{
				$processed_meta[$meta_key] = $meta_value;
			}
		}
		return $processed_meta;
	}

	public function log_db_error( $type, $table ) {
		global $wpdb;
		$error = sprintf(__('Something went wrong saving your %s to the index table. Please inform a site administrator about this.','events-manager'), $type);
		$this->add_error( $error );
		if ( $wpdb->last_error != '' ) {
			error_log( $table . ' SQL failed: '. $wpdb->last_error );
		}
		if ( is_super_admin() ) {
            // check if post_content is not utf8mb4
			$error = '';
			if ( !empty($wpdb->last_error) ) {
				$error .= '<strong>Admins Further Info:</strong><br>' . $wpdb->last_error;
			}
			$cols = $wpdb->get_row("SHOW FULL COLUMNS FROM ". $table ." WHERE FIELD='post_content'", ARRAY_A);
			if ( !empty($cols['Collation']) && !preg_match('/^utf8mb4/', $cols['Collation']) ) {
				$error .= '<br>' . sprintf( 'Please convert the %s table to utf8mb4 to avoid problems with this event.' , '<code>'.$table.'</code>' );;
			}
			if ( $error ) {
				$this->add_error( $error );
			}
		}
	}

	/**
	 * Override in child objects.
	 *
	 * @param $option
	 * @param $default
	 *
	 * @return mixed|null
	 */
	public function get_option( $option, $default = null ) {
		return em_get_option( $option, $default );
	}
}