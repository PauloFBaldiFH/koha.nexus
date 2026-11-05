<?php
class EM_Calendar extends EM_Object {

	public static function init(){
		//nothing to init anymore
	}

	public static function get( $args ){

		global $wpdb, $wp_rewrite;

		$calendar_array = array();
		$calendar_array['cells'] = array();

		$args = apply_filters('em_calendar_get_args', $args);
		$original_args = $args;
		$args = self::get_default_search($args);
		if( !empty($args['format']) ) {
			if( !empty($_REQUEST['format']) ) {
				// placeholders such as #_CONTACTMETA and #_ATTENDEESLIST expand server-side, so a request may only send back a format this site signed when it output the calendar
				$args['format'] = wp_unslash( $args['format'] );
				$format_sig = !empty($_REQUEST['format_sig']) && is_string($_REQUEST['format_sig']) ? $_REQUEST['format_sig'] : '';
				if( !is_string($args['format']) || !hash_equals( static::get_format_signature($args['format']), $format_sig ) ) {
					$args['format'] = '';
				}
			}
			// escape a signed format too, we are abundantly cautious here in case there's any kind of difference due to escaping, encoding etc.
			if( !empty($args['format']) && !empty($_REQUEST['format']) ) {
				global $allowedposttags;
				// for optimal performance, if you do not need to use HTML in your formats (for example, if just outputting #_EVENTIMAGE for example), we recommend you add this to your functions.php or similar:
				// add_filter('em_calendar_allowed_format_html', '__return_empty_array');
				// this will use sanitize_textarea_field instead, which is much faster than wp_kses
				$allowed_format_html = apply_filters('em_calendar_allowed_format_html', array(), $args);
				if( $allowed_format_html === false ) {
					$allowed_format_html = $allowedposttags;
				}
				if( empty($allowed_format_html) || !is_array($allowed_format_html) ) {
					$args['format'] = sanitize_textarea_field( $args['format'] );
				} else {
					$args['format'] = wp_kses( $args['format'], $allowed_format_html );
				}
			}
		}
		if( !empty($args['format']) ) {
			$calendar_array['format'] = $args['format'];
		} else {
			// get the default format, future iterations will also deduce the format for different display styles.
			$calendar_array['format'] = em_get_option('dbem_calendar_large_pill_format');
		}
		$timezone = $args['calendar_timezone'] ?: false;

		//figure out what month to look for, if we need to
		$EM_DateTime = new EM_DateTime('now', $timezone);
		$today = $EM_DateTime->copy();
		if( empty($args['month']) && is_array($args['scope']) ){
			//if a scope is supplied, figure out the month/year we're after, which will be between these two dates.
			$EM_DateTime = new EM_DateTime($args['scope'][0], $timezone);
			$scope_start = $EM_DateTime->getTimestamp();
			$scope_end = $EM_DateTime->modify($args['scope'][1])->getTimestamp();
			$EM_DateTime->setTimestamp( $scope_start + ($scope_end - $scope_start)/2 );
			$month = $args['month'] = $EM_DateTime->format('n');
			$year = $args['year'] = $EM_DateTime->format('Y');
		}else{
			if( !empty($args['month']) && !empty($args['year']) ){
				// check if we're looking for a future date, in which case we don't force anything
				if( $args['scope'] == 'future' ){
					$search_date = $EM_DateTime->copy()->setDate($args['year'], $args['month'], $EM_DateTime->format('d'))->setTime(23, 59, 59);
					if( $search_date > $today ) {
						$month = $args['month'];
						$year = $args['year'];
					}
				}else{
					$month = $args['month'];
					$year = $args['year'];
				}
			}
			if( !isset($month) ){
				// if empty_month is defined, we first check the next future event and show that month
				if ( empty($args['empty_months']) ) {
					$months_args = array_merge( $args, [ 'limit' => 1, 'month' => false, 'year' => false, 'scope' => 'future', 'orderby' => 'event_start_date', 'order' => 'ASC' ] );
					add_filter( 'pre_option_dbem_events_current_are_past', empty($args['long_events']) ? '__return_true' : '__return_false' );
					$events = EM_Events::get( $months_args );
					remove_filter( 'pre_option_dbem_events_current_are_past', empty($args['long_events']) ? '__return_true' : '__return_false' );
					if ( $events ) {
						$EM_Event = current($events);
						if ( $EM_Event->start() < $today ) {
							$month = (int) $today->format('m');
							$year = (int) $today->format('Y');
						} else {
							$month = (int) $EM_Event->start()->format('m');
							$year = (int) $EM_Event->start()->format('Y');
						}
					}
				}
				if( !isset($month) ){
					$month = $args['month'] = $EM_DateTime->format('m');
					$year = $args['year'] = $EM_DateTime->format('Y');
				}
			}
		}
		$long_events = $args['long_events'];
		$limit = $args['limit']; //limit arg will be used per day and not for events search

		$start_of_week = em_get_option('start_of_week');

		if( !(is_numeric($month) && $month <= 12 && $month > 0) )   {
			$month = date('m', current_time('timestamp'));
		}
		if( !( is_numeric($year) ) ){
			$year = date('Y', current_time('timestamp'));
		}

		// Get the first day of the month
		$month_start = mktime(0,0,0,$month, 1, $year);
		$calendar_array['month_start'] = $month_start;

		// Figure out which day of the week
		// the month starts on.
		$month_start_day = date('D', $month_start);

	  	switch($month_start_day){
			case "Sun": $offset = 0; break;
			case "Mon": $offset = 1; break;
			case "Tue": $offset = 2; break;
			case "Wed": $offset = 3; break;
			case "Thu": $offset = 4; break;
			case "Fri": $offset = 5; break;
			case "Sat": $offset = 6; break;
		}
		//We need to go back to the WP defined day when the week started, in case the event day is near the end
		$offset -= $start_of_week;
		if($offset<0)
			$offset += 7;

		// determine how many days are in the last month.
		$month_last = ( $month == 1 ) ? 12 : $month - 1;
		$month_next = ( $month == 12 ) ? 1 : $month + 1;
		$year_last = ( $month == 1 ) ? $year - 1 : $year;
		$year_next = ( $month == 12 ) ? $year + 1 : $year;
		$calendar_array['month_next'] = $month_next;
		$calendar_array['month_last'] = $month_last;
		$calendar_array['year_last'] = $year_last;
		$calendar_array['year_next'] = $year_next;

		$num_days_last = self::days_in_month($month_last, $year_last);

		// determine how many days are in the current month.
		$num_days_current = self::days_in_month($month, $year);
		// Build an array for the current days
		// in the month
		for($i = 1; $i <= $num_days_current; $i++){
		   $num_days_array[] = mktime(0,0,0,$month, $i, $year);
		}
		// Build an array for the number of days
		// in last month
		for($i = 1; $i <= $num_days_last; $i++){
		    $num_days_last_array[] = mktime(0,0,0,$month_last, $i, $year_last);
		}
		// If the $offset from the starting day of the
		// week happens to be Sunday, $offset would be 0,
		// so don't need an offset correction.

		if($offset > 0){
		    $offset_correction = array_slice($num_days_last_array, -$offset, $offset);
		    $new_count = array_merge($offset_correction, $num_days_array);
		    $offset_count = count($offset_correction);
		} else { // The else statement is to prevent building the $offset array.
		    $offset_count = 0;
		    $new_count = $num_days_array;
		}
		// count how many days we have with the two
		// previous arrays merged together
		$current_num = count($new_count);

		// Since we will have 5 HTML table rows (TR)
		// with 7 table data entries (TD)
		// we need to fill in 35 TDs
		// so, we will have to figure out
		// how many days to appened to the end
		// of the final array to make it 35 days.
		if( !empty($args['number_of_weeks']) && is_numeric($args['number_of_weeks']) ){
			$num_weeks = $args['number_of_weeks'];
		}elseif($current_num > 35){
			$num_weeks = 6;
		}else{
			$num_weeks = 5;
		}
		$outset = ($num_weeks * 7) - $current_num;
		// Outset Correction
		for($i = 1; $i <= $outset; $i++){
		   $new_count[] = mktime(0,0,0,$month_next, $i, $year_next);
		}
		// Now let's "chunk" the $all_days array
		// into weeks. Each week has 7 days
		// so we will array_chunk it into 7 days.
		$weeks = array_chunk($new_count, 7);
		// Set up weekday headers
	 	$weekdays = array(
			'small' => array('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'),
		    'large' => array('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'),
		);
        if( em_get_option('dbem_full_calendar_abbreviated_weekdays') ) $weekdays['large'] = array('Sun','Mon','Tue','Wed','Thu','Fri','Sat');
		if( em_get_option('dbem_small_calendar_abbreviated_weekdays') ) $weekdays['small'] = array('Sun','Mon','Tue','Wed','Thu','Fri','Sat');
		$day_initials_lengths = array('large' => em_get_option('dbem_full_calendar_initials_length'), 'small' => em_get_option('dbem_small_calendar_initials_length'));

		foreach( $day_initials_lengths as $size => $day_initials_length ){
			// re-order weekdays for start day of week being first in array
			for( $n = 0; $n < $start_of_week; $n++ ) {
				$last_day = array_shift($weekdays[$size]);
				$weekdays[$size][] = $last_day;
			}
			$days_initials_array = array();
			//translate day names, some languages may have special circumstances
			if( $day_initials_length == 1 && in_array(EM_ML::$current_language, array('zh_CN', 'zh_TW')) ){
				//Chinese single initial day names are different, we resort it here as per above
				$weekdays = array('日','一','二','三','四','五','六');
				for( $n = 0; $n < $start_of_week; $n++ ) { $last_day = array_shift($weekdays); $weekdays[]= $last_day; }
				$calendar_array['row_headers_'.$size] = array('日','一','二','三','四','五','六');
			}else{
				//all other languages
				foreach($weekdays[$size] as $weekday) {
					$days_initials_array[] = esc_html(self::translate_and_trim($weekday, $day_initials_length));
				}
				$calendar_array['row_headers_'.$size] = $days_initials_array;
			}
		}
		if( $args['calendar_size'] === 'large' ) {
			$calendar_array['row_headers'] = $calendar_array['row_headers_large'];
		}else{
			$calendar_array['row_headers'] = $calendar_array['row_headers_small'];
		}

		// Now we break each key of the array
		// into a week and create a new table row for each
		// week with the days of that week in the table data
		$i = 0;
		$current_date = date('Y-m-d', current_time('timestamp'));
		$week_count = 0;
		foreach ( $weeks as $week ) {
			foreach ( $week as $d ) {
				$date = date('Y-m-d', $d);
				$calendar_array['cells'][$date] = array('date'=>$d, 'events'=>array(), 'events_count'=>0); //set it up so we have the exact array of dates to be filled
				if ($i < $offset_count) { //if it is PREVIOUS month
					$calendar_array['cells'][$date]['type'] = 'pre';
				}
				if (($i >= $offset_count) && ($i < ($num_weeks * 7) - $outset)) { // if it is THIS month
					if ( $current_date == $date ){
						$calendar_array['cells'][$date]['type'] = 'today';
					}
				} elseif (($outset > 0)) { //if it is NEXT month
					if (($i >= ($num_weeks * 7) - $outset)) {
						$calendar_array['cells'][$date]['type'] = 'post';
					}
				}
				$i ++;
			}
			$week_count++;
		}

		//query the database for events in this time span with $offset days before and $outset days after this month to account for these cells in the calendar
		$scope = $args['scope'] ?? false;
		// we're looking for start of month - offset
		$scope_datetime_start = new EM_DateTime("{$year}-{$month}-1");
		$scope_datetime_end = new EM_DateTime($scope_datetime_start->format('Y-m-t')); // get it here before we subtract
		if( $scope === 'future' ){
			// if month is this month, start datetime must be today
			$scope_datetime_today = new EM_DateTime();
			if( $scope_datetime_start < $scope_datetime_today ){
				$scope_datetime_start = $scope_datetime_today;
			}
			$scope_datetime_end->add('P'.$outset.'D');
		} elseif ( is_array($scope) ) {
			$scope_datetime_start = new EM_DateTime($args['scope'][0]);
			$scope_datetime_end = new EM_DateTime($args['scope'][1]);
		} else {
			$scope_datetime_start->sub('P'.$offset.'D');
			$scope_datetime_end->add('P'.$outset.'D');
		}
		// remove ordering
		$args['array'] = true; //we're getting an array first to avoid extra queries during object creation
		unset($args['month']);
		unset($args['year']);
		unset($args['limit']); //limits in the events search won't help
		$args['orderby'] = 'event_start'; // allows for folding all-day and multi-days on top of each other above regular events
		//we have two methods here, one for high-volume event sites i.e. many thousands of events per month, and another for thousands or less per month.
		if( defined('EM_CALENDAR_OPT') && EM_CALENDAR_OPT ){
			//here we loop through each day, query that specific date, and then compile a list of event objects
			//in this mode the count will never be accurate, we're grabing at most (31 + 14 days) * (limit + 1) events to reduce memory loads
			$args['limit'] = $limit + 1;
			$scope_datetime_loop = $scope_datetime_start->format('U');
			$events = array();
			while( $scope_datetime_loop <= $scope_datetime_end->format('U') ){
				$args['scope'] = date('Y-m-d', $scope_datetime_loop);
				foreach( EM_Events::get($args) as $event ){
					$events[$event['event_id']] = $event;
				}
				$scope_datetime_loop += (86400); //add a day
			}
		}else{
			//just load all the events for this time-range, or just future events
			$args['scope'] = array( $scope_datetime_start->format('Y-m-d'), $scope_datetime_end->format('Y-m-d'));
			$events = EM_Events::get($args);
		}
		//back to what it was
		$args['scope'] = $scope;
		$args['month'] = $month;
		$args['year'] = $year;
		$args['limit'] = $limit;

		// prepare to output
		$event_title_format = em_get_option('dbem_small_calendar_event_title_format');
		$event_title_separator_format = em_get_option('dbem_small_calendar_event_title_separator');

		$eventful_days= array();
		$eventful_days_count = array();
		if( $events ){
			//Go through the events and slot them into the right d-m index
			foreach( $events as $event ) {
				$event = apply_filters('em_calendar_output_loop_start', $event);
				$event_id = !empty($args['timeslots']) && !empty($event['timeslot_id']) ? $event['event_id'] . ':' . $event['timeslot_id'] : $event['event_id'];
				// first, we will ignore any past events that are still loaded within the month (these would be 'earlier today')
				if( $args['scope'] === 'future' ){
					$event_cutoff = em_get_option('dbem_events_current_are_past') ? $event['event_start']:$event['event_end']; // remember, this is UTC, not local!
					$EM_DateTime = new EM_DateTime($event_cutoff, 'UTC');
					if( $scope_datetime_start > $EM_DateTime ){
						continue;
					}
				}
				if( $long_events ){
					//If $long_events is set then show a date as eventful if there is an multi-day event which runs during that day
					$event_start = new EM_DateTime($event['event_start_date'] . ' ' . $event['event_start_time'], $event['event_timezone']);
					$event_end = new EM_DateTime($event['event_end_date'] . ' ' . $event['event_end_time'], $event['event_timezone']);
					if ( $timezone ) {
						$event_start->setTimezone( $timezone );
						$event_end->setTimezone( $timezone );
					}
					// Clamp to the end of the last displayed day, not its midnight: a timed event on that day otherwise starts after the clamped end and never enters the loop below, so the last grid cell showed only all-day events.
					$range_end = $scope_datetime_end->copy()->setTime( 23, 59, 59 );
					if( $event_end->getTimestamp() > $range_end->getTimestamp() ) $event_end = $range_end;
					while( $event_start->getTimestamp() <= $event_end->getTimestamp() ){ //we loop until the last day of our time-range, not the end date of the event, which could be in a year
						//Ensure date is within event dates and also within the limits of events to show per day, if so add to eventful days array
						$event_eventful_date = $event_start->getDate();
						if( empty($eventful_days_count[$event_eventful_date]) || !$limit || $eventful_days_count[$event_eventful_date] < $limit ){
							//now we know this is an event that'll be used, convert it to an object
							$EM_Event = em_get_event( $event_id );
							if( empty($eventful_days[$event_eventful_date]) || !is_array($eventful_days[$event_eventful_date]) ) $eventful_days[$event_eventful_date] = array();
							//add event to array with a corresponding timestamp for sorting of times including long and all-day events
							$event_ts_marker = ($EM_Event->event_all_day || ($EM_Event->event_start_date != $EM_Event->event_end_date)) ? 0 : (int) $event_start->getTimestamp();
							while( !empty($eventful_days[$event_eventful_date][$event_ts_marker]) ){
								$event_ts_marker++; //add a second
							}
							$eventful_days[$event_eventful_date][$event_ts_marker] = $EM_Event;
						}
						//count events for that day
						$eventful_days_count[$event_eventful_date] = empty($eventful_days_count[$event_eventful_date]) ? 1 : $eventful_days_count[$event_eventful_date]+1;
						$event_start->add('P1D');
					}
				}else{
					//Only show events on the day that they start
					$EM_DateTime = new EM_DateTime( $event['event_start_date']  . ' ' . $event['event_start_time'], $event['event_timezone'] ); // get datetime to prevent unnecessary loading of EM_Event
					$event_eventful_date = $EM_DateTime->getDate( $timezone );
					if( empty($eventful_days_count[$event_eventful_date]) || !$limit || $eventful_days_count[$event_eventful_date] < $limit ){
						if( empty($eventful_days[$event_eventful_date]) || !is_array($eventful_days[$event_eventful_date]) ) $eventful_days[$event_eventful_date] = [];
						$EM_Event = em_get_event( $event_id );
						//add event to array with a corresponding timestamp for sorting of times including long and all-day events
						$event_ts_marker = $event['event_all_day'] ? 0 : (int) $EM_DateTime->getTimestamp();
						while( !empty($eventful_days[$event_eventful_date][$event_ts_marker]) ){
							$event_ts_marker++; //add a second
						}
						$eventful_days[$event_eventful_date][$event_ts_marker] = $EM_Event;
					}
					//count events for that day
					$eventful_days_count[$event_eventful_date] = empty($eventful_days_count[$event['event_start_date']]) ? 1 : $eventful_days_count[$event['event_start_date']]+1;
				}
			}
		}
		//generate a link argument string containing event search only
		$day_link_args = self::get_query_args( array_intersect_key($original_args, EM_Events::get_post_search($args, true) ));
		if( !empty($day_link_args['limit']) ) unset($day_link_args['limit']);
		//get event link
		if( em_get_option("dbem_events_page") > 0 ){
			$event_page_link = get_permalink(em_get_option("dbem_events_page")); //PAGE URI OF EM
		}else{
			if( $wp_rewrite->using_permalinks() ){
				$event_page_link = trailingslashit(home_url()).EM_POST_TYPE_EVENT_SLUG.'/'; //don't use EM_URI here, since ajax calls this before EM_URI is defined.
			}else{
			    //not needed atm anyway, but we use esc_url later on, in case you're wondering ;)
				$event_page_link = add_query_arg(array('post_type'=>EM_POST_TYPE_EVENT), home_url()); //don't use EM_URI here, since ajax calls this before EM_URI is defined.
			}
		}
		$event_page_link_parts = explode('?', $event_page_link); //in case we have other plugins (e.g. WPML) adding querystring params to the end
		foreach($eventful_days as $day_key => $events) {
			if( array_key_exists($day_key, $calendar_array['cells']) ){
				//Get link title for this date
				$events_titles = array();
				foreach($events as $event) {
					if( !$limit || count($events_titles) < $limit ){
						$events_titles[] = $event->output($event_title_format);
					}else{
						$events_titles[] = em_get_option('dbem_display_calendar_events_limit_msg');
						break;
					}
				}
				$calendar_array['cells'][$day_key]['link_title'] = implode( $event_title_separator_format, $events_titles);

				//Get the link to this calendar day
				if( $eventful_days_count[$day_key] > 1 || !em_get_option('dbem_calendar_direct_links')  ){
					if( $wp_rewrite->using_permalinks() && !defined('EM_DISABLE_PERMALINKS') ){
						$calendar_array['cells'][$day_key]['link'] = trailingslashit($event_page_link_parts[0]).$day_key."/";
						if( !empty($event_page_link_parts[1]) ) $calendar_array['cells'][$day_key]['link'] .= '?' . $event_page_link_parts[1];
    					//add query vars to end of link
    					if( !empty($day_link_args) ){
    						$calendar_array['cells'][$day_key]['link'] = esc_url_raw(add_query_arg($day_link_args, $calendar_array['cells'][$day_key]['link']));
    					}
					}else{
    					$day_link_args['calendar_day'] = $day_key;
						$calendar_array['cells'][$day_key]['link'] = esc_url_raw(add_query_arg($day_link_args, $event_page_link));
					}
				}else{
					foreach($events as $EM_Event){
						$calendar_array['cells'][$day_key]['link'] = $EM_Event->get_permalink();
					}
				}
				//Add events to array
				$calendar_array['cells'][$day_key]['events_count'] = $eventful_days_count[$day_key];
				$calendar_array['cells'][$day_key]['events'] = $events;
			}
		}

		// basic next url
		// now we have dates, check if there are more events in the future or past, to show correct (or no) links if empty_months = true
		if ( empty( $args['empty_months'] ) ) {
			// check if this next month we dealt with has events, if not then find next event to get next month
			$EM_DateTime = EM_DateTime::create( $day_key ?? 'now' );
			$months_args = array_merge( $args, [ 'limit' => 1, 'array' => false, 'month' => false, 'year' => false ] );
			if ( empty($day_key) || (int) $EM_DateTime->format('m') === (int) $month ) {
				$months_args = array_merge( $months_args, [ 'scope' => [ $EM_DateTime->setEndOfMonth()->add('P1D')->getDate(), false ], 'orderby' => 'event_start_date', 'order' => 'ASC' ] );
				add_filter( 'pre_option_dbem_events_current_are_past', empty($args['long_events']) ? '__return_true' : '__return_false' );
				$events = EM_Events::get( $months_args );
				remove_filter( 'pre_option_dbem_events_current_are_past', empty($args['long_events']) ? '__return_true' : '__return_false' );
				if ( $events ) {
					// we have a date
					$EM_Event = current($events);
					if ( $EM_Event->start() < $EM_DateTime ) {
						// we assume this is a long event if it was in the results since we searched for events next month
						$month_next = (int) $EM_DateTime->format('m');
						$year_next = (int) $EM_DateTime->format('Y');
					} else {
						$month_next = (int) $EM_Event->start()->format('m');
						$year_next = (int) $EM_Event->start()->format('Y');
					}
				} else {
					// no upcoming events
					$month_next = false;
				}
			}
			// now get start of month date to see if we have an event previous month, if not we search again
			$EM_DateTime = EM_DateTime::create( array_keys($eventful_days)[0] ?? 'now' );
			if ( $scope !== 'future' || $EM_DateTime > $today ) {
				if ( empty($eventful_days) || (int) $EM_DateTime->format('m') === (int) $month ) {
					$months_args = array_merge( $months_args, [ 'scope' => [ false, $EM_DateTime->setStartOfMonth()->sub('P1D')->getDate() ], 'orderby' => 'event_start_date', 'order' => 'DESC' ] );
					$events = EM_Events::get( $months_args );
					if ( $events ) {
						// we have a date
						$EM_Event = current($events);
						$month_last = (int) $EM_Event->start()->format('m');
						$year_last = (int) $EM_Event->start()->format('Y');
					} else {
						$month_last = false;
					}
				}
			}
		}
		//Get an array of arguments that don't include default valued args
		if ( $month_next ) {
			$next_url = esc_url_raw(add_query_arg( array('mo'=>$month_next, 'yr'=>$year_next, 'id' => null)) );
		}
		$calendar_array['links'] = array( 'previous_url'=>'', 'next_url'=> $next_url ?? '', 'today_url' => '');
		// add today and previous links if scope permits
		if( $today->format('Y-n') != $year.'-'.absint($month) ) {
			$calendar_array['links']['today_url'] = esc_url_raw(add_query_arg( array('mo'=>$today->format('m'), 'yr'=>$today->format('Y'), 'id' => null) ));
		}
		if( $month_last && ( $args['scope'] !== 'future' || $today->format('Y-n') !== $year.'-'.absint($month) ) ){ // don't show if future scope and this month
			$calendar_array['links']['previous_url'] = esc_url_raw(add_query_arg( array('mo'=>$month_last, 'yr'=>$year_last, 'id' => null)) );
		}
		$calendar_array['month'] = $month;
		$calendar_array['year'] = $year;
		$calendar_array['timezone'] = $timezone;
		$calendar_array['args'] = $args; // pass on args as well, as they've bene cleaned too
		return apply_filters('em_calendar_get',$calendar_array, $args);
	}

	public static function output($base_args = array(), $wrapper = true) {
		//Let month and year REQUEST override for non-JS users
		$base_args['limit'] = !empty($base_args['limit']) ? $base_args['limit'] : em_get_option('dbem_display_calendar_events_limit'); //limit arg will be used per day and not for events search
		if( !empty($_REQUEST['mo']) || !empty($base_args['mo']) ){
			$base_args['month'] = ($_REQUEST['mo']) ? $_REQUEST['mo']:$base_args['mo'];
		}
		if( !empty($_REQUEST['yr']) || !empty($base_args['yr']) ){
			$base_args['year'] = (!empty($_REQUEST['yr'])) ? $_REQUEST['yr']:$base_args['yr'];
		}
		if( !empty($_REQUEST['month_year']) && preg_match('/^[0-9]{4}\-[0-9]{2}$/', $_REQUEST['month_year']) ){
			$year_month = explode('-', $_REQUEST['month_year']);
			$base_args['month'] = absint($year_month[1]);
			$base_args['year'] = absint($year_month[0]);
		}
		if( empty($base_args['calendar_size']) && !empty($_REQUEST['calendar_size']) ){
			$base_args['calendar_size'] = $_REQUEST['calendar_size'];
		}
		// get request options for display methods:
		if( !empty($_REQUEST['calendar_preview_mode']) ) {
			$base_args['calendar_preview_mode'] = esc_attr($_REQUEST['calendar_preview_mode']);
		}
		if( !empty($_REQUEST['calendar_preview_mode_date']) ) {
			$base_args['calendar_preview_mode_date'] = esc_attr($_REQUEST['calendar_preview_mode_date']);
		}
		if( !empty($_REQUEST['calendar_event_style']) ) {
			$base_args['calendar_event_style'] = esc_attr($_REQUEST['calendar_event_style']);
		}
		if( isset($_REQUEST['has_advanced_trigger']) ) {
			$base_args['has_advanced_trigger'] = !empty($_REQUEST['has_advanced_trigger']);
		}

		// merge default, base and supplied search args and generate search
		$calendar_array  = self::get($base_args);
		$args = array_merge( $base_args, $calendar_array['args']);
		// get any template-specific $_REQUEST info here
		$args['has_advanced_trigger'] = ($args['has_search'] && !$args['show_search']) || !empty($base_args['has_advanced_trigger']); // override search trigger option if search is hidden
		// output main form
		ob_start();
		// do we output a search form first?
		if( !empty($args['has_search']) && empty($args['show_search']) ) {
			$args['search_scope'] = false; $args['search_scope_advanced'] = false;
			$args['show_advanced'] = true;
			$args['advanced_mode'] = 'modal';
			$args['advanced_hidden'] = true;
		}
		$args = em_get_search_form_defaults($args);
		if( !empty($args['has_search']) ) {
			em_locate_template( 'templates/events-search.php', true, array( 'args' => $args ) );
		}
		// re-assign classes (clean-up search assignments)
		$args['css_classes'] = false;
		/* START New Config Options */
			// sanitize calendar size
			if( !empty($args['calendar_size']) ){
				$allowed_sizes = apply_filters('em_calendar_output_sizes', array('large', 'medium', 'small'));
				$args['calendar_size'] = in_array($args['calendar_size'], $allowed_sizes) ? $args['calendar_size'] : null;
			}
			// sanitize event display style, falling back to the site-wide default if an unknown style is supplied
			$allowed_styles = apply_filters('em_calendar_output_event_styles', array('pill', 'dot', 'dots', 'ring'));
			if( empty($args['calendar_event_style']) || !in_array($args['calendar_event_style'], $allowed_styles, true) ){
				$args['calendar_event_style'] = em_get_option('dbem_calendar_event_style', 'pill');
			}
			// generate CSS classes based on $args
			$calendar_array['css'] = array(
				'calendar_classes' => array('preview-'.$args['calendar_preview_mode']),
				'dates_classes' => array('event-style-'.$args['calendar_event_style']),
			);
			if( $args['calendar_preview_mode_date'] !== 'none' && $args['calendar_preview_mode'] !== 'booking' ){
				$calendar_array['css']['calendar_classes'][] = 'responsive-dateclick-modal';
			}
			// add extra args
			$allowed_heights = apply_filters('em_calendar_output_dates_heights', array(
				'even' => 'even-height', // height of each row will adjust to match tallest cell in table
				'aspect' => 'even-aspect', // default - height will match width of cell, unless there is more content
				'auto' => 'auto-aspect', // each cell in a row will adjust height to tallest cell in that row
			));
			if( !empty($args['calendar_dates_height']) && isset($allowed_heights[$args['calendar_dates_height']]) ){
				$calendar_array['css']['dates_classes'][] = $allowed_heights[$args['calendar_dates_height']];
			}else{
				$calendar_array['css']['dates_classes'][] = 'even-aspect';
			}
			if( isset($args['calendar_size']) && $args['calendar_size'] ){
				// calendar won't switch responsively
				$calendar_array['css']['calendar_classes'][] = 'size-'.$args['calendar_size'];
				$calendar_array['css']['calendar_classes'][] = 'size-fixed';
			}else{
				$calendar_array['css']['calendar_classes'][] = 'size-small';
			}
			if ( !empty($args['class']) ) {
				$class = is_array($args['class']) ? implode(',', $args['class']) : $args['class'];
				$class = explode(',', esc_attr($class));
				$calendar_array['css']['calendar_classes'] += $class;
			}
			if( !empty($args['has_advanced_trigger']) ) $calendar_array['css']['calendar_classes'][] = 'with-advanced';
			$EM_DateTime = new EM_DateTime($calendar_array['month_start'], 'UTC');
			if( $EM_DateTime->format('Y-m') === date('Y-m') ) $calendar_array['css']['calendar_classes'][] = 'this-month';
		/* END New Config Options */

		?>
		<div class="<?php em_template_classes('view-container'); ?>" id="em-view-<?php echo absint($args['id']); ?>" data-view="calendar">
			<?php
			// output calendar
			$template = (!empty($args['full'])) ? 'templates/calendar-full.php':'templates/calendar-small.php';
			if( !em_locate_template($template) ) $template = 'calendar/calendar.php'; // backcompat
			em_locate_template($template, true, array('calendar'=>$calendar_array,'args'=>$args));
			// output vars that should persist on searches
			?>
			<div class="em-view-custom-data" id="em-view-custom-data-<?php echo absint($args['id']); ?>">
				<?php
				$ignore_keys = array('page','offset', 'pagination', 'array','ajax','month', 'year', 'search_url'); // stuff we don't need to consider
				$global_args_keys = array('has_advanced_trigger', 'id', 'view_id', 'calendar_size', 'scope'); // things both searches and caelendar navs need
				$default_search = static::get_default_search();
				$search_exclusive_args_keys = array_keys( array_diff_key( em_get_search_form_defaults(), $default_search )); //vars only searches need
				$calendar_exclusive_args_keys = array_keys( self::get_query_args($base_args) ); // vars only the calendar needs
				$custom_args = array('global' => array(), 'search' => array(), 'calendar' => array());
				foreach( $args as $name => $value ){
					if( in_array($name, $ignore_keys) ) continue;
					if( $name === 'scope' && !empty($value['name']) ) $value = $value['name'];
					if( is_array($value) ) $value = implode(',', $value);
					if( $value === true || $value === false ) $value = $value ? 1:0; // make sure we get a 1 or 0
					if( in_array($name, $global_args_keys) ){
						$custom_args['global'][$name] = $value;
					}elseif( in_array($name, $search_exclusive_args_keys) ){
						$custom_args['search'][$name] = $value;
					}elseif( in_array($name, $calendar_exclusive_args_keys) ){
						$custom_args['calendar'][$name] = $value;
					}
				}
				foreach( $custom_args as $group => $group_args ){
					if( !empty($group_args['format']) ) $custom_args[$group]['format_sig'] = static::get_format_signature( $group_args['format'] );
				}
				?>
				<form class="em-view-custom-data-search" id="em-view-custom-data-search-<?php echo absint($args['id']); ?>">
					<?php foreach( array_merge($custom_args['search'], $custom_args['global']) as $name => $value ): ?>
					<input type="hidden" name="<?php echo esc_attr($name); ?>" value="<?php echo esc_attr($value); ?>">
					<?php endforeach; ?>
				</form>
				<form class="em-view-custom-data-calendar" id="em-view-custom-data-calendar-<?php echo absint($args['id']); ?>">
					<?php foreach( array_merge($custom_args['calendar'], $custom_args['global']) as $name => $value ): ?>
						<input type="hidden" name="<?php echo esc_attr($name); ?>" value="<?php echo esc_attr($value); ?>">
					<?php endforeach; ?>
				</form>
			</div>
		</div>
		<?php

		// return the buffer
		return apply_filters('em_calendar_output', ob_get_clean(), $args);
	}


	/**
	 * Signs a calendar format so that it can be sent back by a request, such as when navigating months, without letting a request supply a format of its own.
	 * @param string $format
	 * @return string
	 */
	public static function get_format_signature( $format ){
		return wp_hash( 'em_calendar_format|' . $format );
	}

	public static function days_in_month($month, $year) {
		return date('t', mktime(0,0,0,$month,1,$year));
	}

	public static function translate_and_trim($string, $length = 1) {
	    if( $length > 0 ){
			if(function_exists('mb_substr')){ //fix for diacritic calendar names
			    return mb_substr(translate($string), 0, $length, 'UTF-8');
			}else{
	    		return substr(translate($string), 0, $length);
	    	}
	    }
	    return translate($string);
	}


	/**
	 * Gets all the EM-supported search arguments and removes the ones that aren't the default in the $args array. Returns the arguments that have non-default values.
	 * @param array $args
	 * @return array
	 */
	public static function get_query_args( $args ){
		unset($args['month']); unset($args['year']);
		$default_args = self::get_default_search(array());
		foreach($default_args as $arg_key => $arg_value){
			if( !isset($args[$arg_key]) ){
				unset($args[$arg_key]);
			}else{
				// fix scope default
				if( $arg_key == 'scope' && $args[$arg_key] === 'all' ){
					$args[$arg_key] = false;
				}
			    //check that argument doesn't match default
    		    $arg = array($args[$arg_key], $arg_value);
    		    foreach($arg as $k => $v){
        		    if( is_string($v) || is_numeric($v) ){
        		        //strings must be typecast to avoid false positive for something like 'string' == 0
        		        $arg[$k] = (string) $v;
        		    }elseif( is_bool($v) ){
        		        $arg[$k] = $v ? '1':'0';
        		    }
    		    }
			    if( $arg[0] == $arg[1] ){
			        //argument same as default so it's not needed in link
    				unset($args[$arg_key]);
    		    }
			}
		}
		//clean up post type conflicts in a URL
		if( !empty($args['event']) ){
			$args['event_id'] = $args['event'];
			unset($args['event']);
		}
		if( !empty($args['location']) ){
			$args['location_id'] = $args['location'];
			unset($args['location']);
		}
		return $args;
	}

	/**
	 * DEPRECATED - use EM_Calendar::get_query_args() instead and manipulate the array.
	 * Left only to prevent 3rd party add-ons from potentially breaking if they use this
	 * Helper function to create a link querystring from array which contains arguments with only values that aren't defuaults.
	 */
	public static function get_link_args($args = array(), $html_entities=true){
	    $args = self::get_query_args($args);
		$qs_array = array();
		foreach($args as $key => $value){
			if(is_array($value)){
				$value = implode(',',$value);
			}
			$qs_array[] = "$key=".urlencode($value);
		}
		return ($html_entities) ? implode('&amp;', $qs_array) : implode('&', $qs_array);
	}


	/*
	 * Adds custom calendar search defaults
	 * @param array $array_or_defaults may be the array to override defaults
	 * @param array $array
	 * @return array
	 * @uses EM_Object#get_default_search()
	 */
	public static function get_default_search( $array_or_defaults = array(), $array = array() ){
		//These defaults aren't for db queries, but flags for what to display in calendar output
		$defaults = array(
			'recurring' => false, //we don't initially look for recurring events only events and recurrences of recurring events
			//'full' => 0, //Will display a full calendar with event names
			'calendar_size' => em_get_option('dbem_calendar_size', 'auto'),
			'long_events' => 0, //Events that last longer than a day
			'scope' => 'all',
			'status' => 1, //approved events only
			'town' => false,
			'state' => false,
			'country' => false,
			'region' => false,
			'blog' => get_current_blog_id(),
			'orderby' => em_get_option('dbem_display_calendar_orderby'),
			'order' => em_get_option('dbem_display_calendar_order'),
			'number_of_weeks' => false, //number of weeks to be displayed in the calendar
		    'limit' => em_get_option('dbem_display_calendar_events_limit'),
			'post_id' => false,
			// calendar-specific overrides
			'view' => 'calendar',
			'has_view' => true,
			'views' => 'calendar',
			'show_search' => false, // don't show the search bar above by default, filters yes
			'has_search' => false, // by default no search
			'css_classes' => false,
			'calendar_event_style' => em_get_option('dbem_calendar_event_style', 'pill'), // pill, dot or ring; defaults to the site-wide setting
			'calendar_preview_mode' => em_get_option('dbem_calendar_preview_mode'), //modal, tooltips, none
			'calendar_preview_mode_date' => em_get_option('dbem_calendar_preview_mode_date'), //modal, none
			'calendar_nav_nofollow' => false,
			'calendar_nav' => true,
			'calendar_header' => 'normal',
			'calendar_month_nav' => true,
			'empty_months' => true, // if empty months are to be shown
			'calendar_timezone' => false, // if set to a timezone, we search and show dates/times in the specified timezone rather than local time
			'timeslots' => em_get_option('dbem_calendar_timeslots'),
		);

		//sort out whether defaults were supplied or just the array of search values
		if( empty($array) ){
			$array = $array_or_defaults;
		}else{
			$defaults = array_merge($defaults, $array_or_defaults);
		}

		// Set the calendar_size conditionally based on allowed sizes
		if( empty($array['calendar_size']) && isset($args['full']) ){ // legacy arg
			$array['calendar_size'] = !empty($args['full']) ? 'large' : 'small';
		} else {
			$allowed_sizes = apply_filters( 'em_calendar_output_sizes', array( 'large', 'medium', 'small' ) );
			if ( !empty( $array['calendar_size'] ) && in_array( $array['calendar_size'], $allowed_sizes ) ) {
				$defaults['calendar_size'] = $array['calendar_size'];
			}
		}
		// validate timezone
		if ( !empty($array['calendar_timezone']) ) {
			$array['calendar_timezone'] = EM_DateTimeZone::create( $array['calendar_timezone'] )->getValue();
		}

		// decide long events default based on size
		$defaults['long_events'] = !isset($array['calendar_size']) || $array['calendar_size'] === 'large' ? em_get_option('dbem_full_calendar_long_events') : em_get_option('dbem_small_calendar_long_events');
		if( !empty($array['calendar_size']) ){
			$defaults['long_events'] = $array['calendar_size'] == 'small' ? em_get_option('dbem_small_calendar_long_events') : em_get_option('dbem_full_calendar_long_events');
		}
		//specific functionality
		if(is_multisite()){
			global $bp;
			if( !is_main_site() && !array_key_exists('blog',$array) ){
				//not the main blog, force single blog search
				$array['blog'] = get_current_blog_id();
			}elseif( empty($array['blog']) && get_site_option('dbem_ms_global_events') ) {
				$array['blog'] = false;
			}
		}
		$atts = parent::get_default_search($defaults, $array);
		if( isset($array['full']) ) $atts['full'] = ($array['full']) ? 1:0; //deprecated, we're changing this now to calendar_size for display purposes
		$atts['long_events'] = ($atts['long_events']==true) ? 1:0;
		return apply_filters('em_calendar_get_default_search', $atts, $array, $defaults);
	}
}
add_action('init', array('EM_Calendar', 'init'));