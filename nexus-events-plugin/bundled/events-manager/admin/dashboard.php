<?php
namespace EM\Admin;
use EM\Archetypes;
use EM_DateTime;

class Dashboard {
	
	protected static $footer_js;
	
	public static function init() {
		if( em_get_option('dbem_booking_charts_wpdashboard') ){
			add_action( 'wp_dashboard_setup', array( static::class, 'wp_dashboard_setup') );
			add_action( 'admin_print_scripts', array( static::class, 'enqueue_scripts'), 10, 1 );
		}
		if( em_get_option('dbem_booking_charts_frontend') && !is_admin() ){
			add_action( 'em_enqueue_scripts', array( static::class, 'enqueue_scripts'), 10, 1 );
		}
		add_action( 'wp_ajax_em_chart_bookings', array( static::class, 'ajax'), 10, 1 );
	}

	public static function wp_dashboard_setup() {
		wp_add_dashboard_widget('em_booking_stats', __('Events Manager Bookings', 'events-manager'), array( static::class, 'stats_widget'));
	}
	
	public static function enqueue_scripts( $hook_suffix = false ){
		if( is_admin() ) {
			$screen = get_current_screen();
			if ( $screen->id == 'dashboard' ) {
				$min = \EM_Scripts_and_Styles::min_suffix();
				wp_enqueue_script( 'chart-js', EM_DIR_URI . 'includes/external/chartjs/chart.umd' . $min . '.js', array(), EM_VERSION );
				\EM_Scripts_and_Styles::admin_enqueue( true );
				//wp_enqueue_script( 'chart-js', 'https://cdn.jsdelivr.net/npm/chart.js@4.0.1/dist/chart.umd.min.js', array(), EM_VERSION);
				//wp_enqueue_script( 'chart-js-utils', 'https://www.chartjs.org/samples/2.9.4/utils.js', array());
			} elseif ( !empty( $_REQUEST['page'] ) && $_REQUEST['page'] == 'events-manager-bookings' ) {
				// we need to call this before enqueue, otherwise it'll get enqueued at footer and possibly dependent EM stuff isn't loaded
				$min = \EM_Scripts_and_Styles::min_suffix();
				wp_enqueue_script( 'chart-js', EM_DIR_URI . 'includes/external/chartjs/chart.umd' . $min . '.js', array( 'moment' ), EM_VERSION );
			} elseif ( $hook_suffix === true ) {
				// we need to call this before enqueue, otherwise it'll get enqueued at footer and possibly dependent EM stuff isn't loaded
				$min = \EM_Scripts_and_Styles::min_suffix();
				wp_enqueue_script( 'chart-js', EM_DIR_URI . 'includes/external/chartjs/chart.umd' . $min . '.js', array(), EM_VERSION, true );
				\EM_Scripts_and_Styles::admin_enqueue( true );
			}
		} elseif ( em_get_option( 'dbem_booking_charts_frontend' ) ) {
			// we assume it's the bookings admin page if this class was loaded
			$min = \EM_Scripts_and_Styles::min_suffix();
			wp_enqueue_script( 'chart-js', EM_DIR_URI . 'includes/external/chartjs/chart.umd' . $min . '.js', array( 'moment' ), EM_VERSION );
		}
	}
	
	public static function stats_widget(){
		static::output( 'wp-dashboard' );
	}
	
	public static function ajax(){
		if( !empty($_REQUEST['_nonce']) && !empty($_REQUEST['view']) ) {
			if( em_get_option('dbem_booking_charts_wpdashboard') || em_get_option('dbem_booking_charts_dashboard') || em_get_option('dbem_booking_charts_event') ){
				$args = static::get_post_args();
				$nonce_action = 'em-chart-'.$args['view'];
				if( $args['view'] === 'event' || $args['view'] === 'ticket' ){
					$nonce_action = 'em-chart-'.$args['view'].'-'.$args[$args['view']];
				}
				if( wp_verify_nonce($_REQUEST['_nonce'], $nonce_action) ) {
					static::save_view( $args );
					static::output_chart( $args );
					die();
				}
			}
		}
	}
	
	public static function save_view($args){
		$views = get_user_meta( get_current_user_id(), 'em_charts_views', true );
		if( !is_array($views) ) $views = array('bookings' => array());
		$views['bookings'][$args['view']] = $args;
		update_user_meta( get_current_user_id(), 'em_charts_views', $views);
	}
	
	public static function get_post_args(){
		$args = static::get_default_args();
		if ( Archetypes::is_event( $_REQUEST['event_archetype'] ?? '' ) ) {
			$args['event_archetype'] = $_REQUEST['event_archetype'];
		}
		if( !empty($_REQUEST['mode']) && in_array($_REQUEST['mode'], array('day','week','month','year')) ){
			$args['mode'] = $_REQUEST['mode'];
		}
		if( !empty($_REQUEST['range_dates']) && is_array($_REQUEST['range_dates']) ){
			$date_regex = '/^[0-9]{4}\-[0-9]{2}\-[0-9]{2}$/';
			if( !empty($_REQUEST['range_dates'][0][0]) && preg_match($date_regex, $_REQUEST['range_dates'][0][0]) ){
				$args['range_dates'][0][0] = $_REQUEST['range_dates'][0][0];
				if( !empty($_REQUEST['range_dates'][0][1]) && preg_match($date_regex, $_REQUEST['range_dates'][0][1]) ){
					$args['range_dates'][0][1] = $_REQUEST['range_dates'][0][1];
				}
			}
			if( !empty($_REQUEST['range_dates'][1]) && preg_match($date_regex, $_REQUEST['range_dates'][1]) ){
				$args['range_dates'][1] = $_REQUEST['range_dates'][1];
			}
		}
		$args['range_type'] = !empty($_REQUEST['range_type']) && preg_match('/^[a-zA-Z0-9 ]+$/', $_REQUEST['range_type']) ? $_REQUEST['range_type'] : '3 months';
		if( isset($_REQUEST['compare']) ) {
			$args['compare'] = sanitize_key($_REQUEST['compare']);
		}
		if( !empty($_REQUEST['unit']) && in_array($_REQUEST['unit'], array('price', 'spaces', 'bookings')) ){
			$args['unit'] = $_REQUEST['unit'];
		}
		if( !empty($_REQUEST['type']) && in_array($_REQUEST['type'], array('pie', 'line', 'bar')) ){
			$args['type'] = $_REQUEST['type'];
		}
		$args['subgroup'] = !empty($_REQUEST['stacked']) ? $_REQUEST['stacked']:false;
		$args['status'] = 'all';
		if( !empty($_REQUEST['status']) ){
			$status = explode(',', $_REQUEST['status']);
			if( \EM_Object::array_is_numeric($status) ){
				$args['status'] = $status;
			}
		}
		if( !empty($_REQUEST['summaries']) && is_array($_REQUEST['summaries']) ) {
			$args['summaries'] = array_intersect( $_REQUEST['summaries'], $args['summaries'] );
			foreach( $args['summaries'] as $k => $v ){
				$args['summaries'][$k] = $v == true;
			}
		}
		if( !empty($_REQUEST['view']) ){
			$args['view'] = sanitize_key($_REQUEST['view']);
		}
		if( $args['view'] === 'event' && !empty($_REQUEST['event']) && preg_match('/^(\d+)(:\d+)?$/', $_REQUEST['event']) ){
			$args['event'] = $_REQUEST['event'];
		}elseif( $args['view'] === 'ticket' && !empty($_REQUESt['ticket']) ){
			$args['ticket'] = absint($_REQUEST['ticket']);
		}
		$args['show_filters'] = !empty($_REQUEST['show_filters']);
		return $args;
	}
	
	public static function get_default_args( $view = 'dashboard' ){
		$views = get_user_meta( get_current_user_id(), 'em_charts_views', true );
		$args = array('view' => $view);
		if( is_array($views) && !empty($views['bookings'][$view]) ){
			$args = $views['bookings'][$view];
		}
		$default_scope = $view === 'event' || $view === 'ticket' ? 'all':'3 months';
		$default_compare = $view === 'event' || $view === 'ticket' ? false:'previous';
		return array_merge( array(
			'mode' => 'month',
			'unit' => 'price',
			'compare' => $default_compare,
			'range_type' => $default_scope,
			'range_dates' => array( array(), '' ),
			'summaries' => array(
				'price' => true,
				'spaces' => true,
				'bookings' => $view !== 'wp-dashboard',
				'price_avg' => $view !== 'wp-dashboard',
				'spaces_avg' => $view !== 'wp-dashboard',
				'tickets_avg' => true,
			),
			'show_filters' => false,
			'status' => array('1'),
			'type' => 'line',
			'event_archetype' => Archetypes::get_current(),
		), $args);
	}
	
	public static function get_compare_options(){
		$options = array(
			'time' => array(
				'label' => __('Earlier Dates', 'events-manager'),
				'options' => array(
					'previous' => __('Previous Period', 'events-manager'),
					'year' => __('Previous Year', 'events-manager'),
					'custom' => __('Custom Dates', 'events-manager'),
				),
			),
			'units' => array(
				'label' => __('Metrics', 'events-manager'),
				'options' => array(
					'spaces' => __('Spaces', 'events-manager'),
					'price' => __('Sales', 'events-manager'),
					'bookings' => __('Bookings', 'events-manager'),
				)
			),
		);
		return apply_filters('em_chart_compare_options', $options);
	}
	
	public static function get_range_types(){
		$range_types = array(
			'all' => __('All Time', 'events-manager'),
			'today'=> __('Today', 'events-manager'),
			'yesterday' => __('Yesterday', 'events-manager'),
			'this month' => __('This Month', 'events-manager'),
			'last month' => __('Last Month', 'events-manager'),
			'3 months' => sprintf(__('Last %d Months', 'events-manager'),3),
			'6 months' => sprintf(__('Last %d Months', 'events-manager'),6),
			'12 months' => sprintf(__('Last %d Months', 'events-manager'),12),
			'this year' => __('This Year', 'events-manager'),
			'last year' => __('Last Year', 'events-manager'),
		);
		return apply_filters('em_chart_range_types', $range_types);
	}

	public static function get_range_dates(){
		$today = date('Y-m-d');
		$day = 0;
		$ranges = array(
			'all' => array('1970-01-01', $today),
			'today'=> $today,
			'yesterday'=> date('Y-m-d', strtotime('yesterday')),
			'this month'=> array( date('Y-m-01'), $today ),
			'last month'=> array( date('Y-m-01', strtotime('last month')), date('Y-m-t', strtotime('last month')) ),
			'3 months'=> array( date('Y-m-d', strtotime('-3 months')+$day), $today ),
			'6 months'=> array( date('Y-m-d', strtotime('-6 months')+$day), $today ),
			'12 months'=> array( date('Y-m-d', strtotime('-12 months')+$day), $today ),
			'this year'=> array( date('Y-01-01'), $today ),
			'last year'=> array( date('Y-01-01', strtotime('last year')), date('Y-12-31', strtotime('last year')) ),
		);
		return apply_filters('em_chart_range_dates', $ranges);
	}
	
	public static function get_stats( $args ){
		global $wpdb;
		$conditions = array();
		if( !current_user_can('manage_bookings') ){
			return array(); // no permissions for bookings, should have not even got here!
		}elseif( !current_user_can('manage_others_bookings') ) {
			// get current user bookings
			$conditions['owner'] = $wpdb->prepare( ' event_id IN (SELECT event_id FROM ' . EM_EVENTS_TABLE . ' WHERE event_owner=%d )', get_current_user_id() );
		}
		if( !empty($args['event']) ){
			$EM_Event = em_get_event($args['event']);
			if( $EM_Event->can_manage('manage_bookings', 'manage_others_bookings') ) {
				if ( ! empty( $conditions['owner'] ) ) {
					unset( $conditions['owner'] );
				}
				if ( $EM_Event->is_recurring() ) {
					$conditions['event'] = $wpdb->prepare( ' event_id IN ( SELECT event_id FROM '. EM_EVENTS_TABLE .' WHERE recurrence_set_id IN ( SELECT recurrence_set_id fROM '.EM_EVENT_RECURRENCES_TABLE.' WHERE event_id = %d ) )', $EM_Event->get_event_id() );
				} else {
					$conditions['event'] = $wpdb->prepare( ' event_id = %d ', $EM_Event->get_event_id() );
				}
				if ( $EM_Event->timeslot_id ) {
					$conditions['timeslot'] = $wpdb->prepare( ' timeslot_id = %d ', $EM_Event->timeslot_id );
				}
			}
		} elseif ( !empty($args['event_archetype']) && Archetypes::is_event($args['event_archetype'], false) ){
			$conditions['event_archetype'] = $wpdb->prepare( ' event_id IN ( SELECT event_id FROM '. EM_EVENTS_TABLE .' WHERE event_archetype=%s )', $args['event_archetype'] );
		}
		if( !empty($args['status']) && \EM_Object::array_is_numeric($args['status']) ){
			$conditions['status'] = $wpdb->prepare( ' booking_status IN ('. implode(',', array_fill(0,count($args['status']), '%d')) .')', $args['status'] );
		}
		// determine unit of measurement
		$selectors = array();
		$averages = array(
			'spaces_avg' => 'AVG(booking_spaces) AS spaces_avg',
			'price_avg' => 'AVG(booking_price) AS price_avg',
		);
		$summaries = array(
			'spaces' => 'SUM(booking_spaces) AS spaces',
			'bookings' => 'COUNT(*) AS bookings',
			'price' => 'SUM(booking_price) AS price',
		);
		$selector_units = array('price', 'bookings', 'spaces');
		if( !empty($args['unit']) && in_array( $args['unit'], $selector_units) ){
			$units = $args['unit']; // array
			if( !is_array($args['unit']) ){
				$units = array($args['unit']);
			}
			if( !empty($args['compare']) && $args['unit'] !== $args['compare'] && in_array( $args['compare'], $selector_units) ){
				$units[] = $args['compare'];
			}
			foreach( $units as $unit ){
				if( !empty($summaries[$unit]) ){
					$selectors[$unit] = $summaries[$unit];
				}
			}
		}else{
			$selectors['price'] = $summaries['price'];
		}
		$unit_labels = array(
			'spaces' => __('Spaces', 'events-manager'),
			'bookings' => __('Bookings', 'events-manager'),
			'price' => __('Sales', 'events-manager'),
		);
		// get scopes
		$scopes = array(); // we'll get a range of dates here regardeless
		$today = date('Y-m-d');
		if( $args['range_type'] === 'custom' && !empty($args['range_dates'][0]) ){
			$scope_dates[0] = $args['range_dates'][0];
		}elseif( $args['range_type'] === 'all' ){
			// we need to get the first date of a booking according to conditions set further up without scope
			$where = count($conditions) > 0 ? ' WHERE '. implode(' AND ', $conditions):'';
			$sql = 'SELECT booking_date FROM '. EM_BOOKINGS_TABLE . $where ." ORDER BY booking_date ASC LIMIT 1";
			$first_booking_date = $wpdb->get_var( $sql );
			if( $first_booking_date ){
				$scope_dates[0][] = substr($first_booking_date, 0, 10);
				$sql = 'SELECT booking_date FROM '. EM_BOOKINGS_TABLE . $where ." ORDER BY booking_date DESC LIMIT 1";
				$last_booking_date = $wpdb->get_var( $sql );
				if( $last_booking_date ) {
					$scope_dates[0][] = substr($last_booking_date, 0, 10);
				}else{
					$scope_dates[0][] = $scope_dates[0][0];
				}
			}else{
				$scope_dates[0] = $today; // no results to find anyway
			}
		}else{
			// get the range of dates
			$range_dates = static::get_range_dates();
			if( empty( $range_dates[$args['range_type']] ) ){
				$args['range_type'] = '3 months'; // default
			}
			$scope_dates[0] = $range_dates[$args['range_type']];
		}
		
		// get compare data scopes
		if( $args['range_type'] !== 'all' && in_array( $args['compare'], array('custom', 'previous', 'year')) ) {
			// get difference of dates for first scope and add it to the base date via DateTime
			$start_scope_date = is_array($scope_dates[0]) ? $scope_dates[0][0] : $scope_dates[0];
			$end_scope_date   = is_array($scope_dates[0]) && !empty($scope_dates[0][1]) ? $scope_dates[0][1] : 'now';
			$base_start_scope = new EM_DateTime( $start_scope_date, 'UTC' );
			$base_end_scope   = new EM_DateTime( $end_scope_date, 'UTC' );
			$interval         = $base_end_scope->diff( $base_start_scope, true );
			if ( $args['compare'] === 'custom' && ! empty( $args['range_dates'][1] ) ) {
				// get custom dates, working off the given date and calculating the difference of first scope to determine same range of days
				$scope_dates[1] = array( $args['range_dates'][1] );
				$scope_date     = new EM_DateTime( $args['range_dates'][1] . ' 00:00:00', 'UTC' );
				$scope_date->add( $interval );
				$scope_dates[1][] = $scope_date->format( 'Y-m-d' );
			} elseif ( $args['compare'] === 'previous' ) {
				// get 1 day less than first scope day and then work backwards to difference
				$scope_date_end = $base_start_scope->sub( 'P1D' )->format( 'Y-m-d'); // extra day so we end day before first scope
				$base_start_scope->sub( 'P'. $interval->days .'D' ); // we want pure days, not months hours etc.
				$scope_dates[1] = array( $base_start_scope->format( 'Y-m-d' ), $scope_date_end );
			} elseif ( $args['compare'] === 'year' ) {
				// get end date and go back until we're earlier than start period, so we have exact same year periods. We subtract days difference to account for leap years
				while( $base_end_scope >= $base_start_scope ) {
					$base_end_scope->sub( 'P1Y' );
				}
				$scope_date_end = $base_end_scope->format( 'Y-m-d' );
				$base_end_scope->sub( 'P' . $interval->days . 'D' ); // we want pure days, not months hours etc.
				$scope_dates[1] = array( $base_end_scope->format( 'Y-m-d' ), $scope_date_end );
			}
		}
		
		// convert dates to SQL-able array
		foreach( $scope_dates as $scope_date ) {
			if ( is_array( $scope_date ) ) {
				$scope = array(
					'start' => new EM_DateTime($scope_date[0] . ' 00:00:00', 'UTC'),
					'end' => new EM_DateTime($scope_date[1] . ' 23:59:59', 'UTC')
				);
			} else {
				$scope = array(
					'start' => new EM_DateTime($scope_date . ' 00:00:00', 'UTC'),
					'end' => new EM_DateTime('now', 'UTC')
				);
				$scope['end']->setTime(23,59,59);
			}
			$scopes[] = $scope;
		}
		
		// group/split results by time frame
		$args['mode'] = in_array( $args['mode'], array('year', 'month', 'week', 'day') ) ? $args['mode'] : 'month';
		$groupby = static::get_sql_groupby($args['mode']);
		if( $args['mode'] !== 'year' ){
			$groupby .= ', YEAR(booking_date)';
		}
		
		// prep stats object to return all data
		if( empty($args['type']) ) $args['type'] = 'line';
		$stats = (object) array(
			'type' => $args['type'],
			'data' => (object) array(
				'labels' => array(),
				'datasets' => array(),
			),
			'currency' => em_get_option('dbem_bookings_currency'),
			'locale' => str_replace('_', '-', \EM_ML::$current_language),
			'compare' => count($scopes) > 1 || count($selectors) > 1,
			'compareType' => false,
			'scales' => (object) array(),
			'subgroups' => false,
			'nulls' => array(), // null datasets with no info (stacks) so we warn user
			'stackable' => true,
			'views' => array('pie' => true, 'line' => true, 'bar' => true),
		);
		
		// get chart title
		if( count($scopes) > 1 ){
			// same unit over a period of time, get difference from first scope
			$title = esc_html__('%s  |  %s  vs  %s');
			$sprintf = array($unit_labels[ $unit ]);
			foreach( $scopes as $scope ){
				$start_scope = $scope['start'];
				$end_scope = $scope['end'];
				$sprintf[] = static::get_date_range_i18n($start_scope, $end_scope);
			}
			$stats->chartTitle = vsprintf( $title, $sprintf );
			$stats->compareType = 'scope';
		}elseif( $args['range_type'] === 'all' ){
			$all_time = esc_html__('All Time', 'events-manager');
			if( count($selectors) > 1 ){
				// comparing units
				$title = esc_html__('%s  vs  %s  |  %s');
				$units = array_keys($selectors);
				$stats->chartTitle = sprintf( $title, $unit_labels[array_shift($units)], $unit_labels[array_shift($units)], $all_time);
				$stats->compareType = 'unit';
			}else{
				$title = esc_html__('%s  |  %s');
				$stats->chartTitle = sprintf( $title, $unit_labels[key($selectors)], $all_time);
			}
		}elseif( count($selectors) > 1 ){
			// comparing units
			$title = esc_html__('%s  vs  %s  |  %s');
			$dates = static::get_date_range_i18n( $scopes[0]['start'], $scopes[0]['end'] );
			$units = array_keys($selectors);
			$stats->chartTitle = sprintf( $title, $unit_labels[array_shift($units)], $unit_labels[array_shift($units)], $dates);
			$stats->compareType = 'unit';
		}else{
			$title = esc_html__('%s  |  %s');
			$dates = static::get_date_range_i18n( $scopes[0]['start'], $scopes[0]['end'] );
			$stats->chartTitle = sprintf( $title, $unit_labels[key($selectors)], $dates);
		}
		
		// set up subgroup values
		$subgroups = array(
			'day' => array('ticket'),
			'week' => array('day','ticket'),
			'month' => array('week','day','ticket'),
			'year' => array('month','week','day','ticket'),
		);
		if( !empty($args['subgroup']) && !empty($subgroups[$args['mode']]) && in_array($args['subgroup'], $subgroups[$args['mode']]) ){
			$subgroup = $args['subgroup'];
		}else{
			$subgroup = $args['subgroup'] = false;
		}
		$stats->subgroups = $subgroup !== false;
		
		// determine if we can show a line graph (if requested) or some other type, otherwise revert to bars which can accommodate all types
		if( $subgroup && $stats->compare ) {
			$stats->type = 'bar';
			$stats->views = array('pie' => false, 'line' => false, 'bar' => true);
		}elseif( $subgroup ){
			if( $stats->type == 'pie' ){
				$stats->type = 'bar';
			}
			$stats->views['pie'] = false;
		}
		$stats->stackable = !empty($subgroups[$subgroup]) && $stats->type !== 'pie';
		
		$datasets = static::build_dataset_template($scopes, $args, $subgroup);
		// duplicate stack if we're comparing units rather than scopes
		if( count($selectors) > 1 ){
			$datasets[1] = $datasets[0];
		}
		// fix siatuations where there's an extra label in comparison (since we're comparing fixed days some ranges will spill into an extra year or month)
		if( $stats->compare && count($datasets[0]['labels']) != count($datasets[1]['labels']) ){
			// we're altering the smallest dataset so they match up
			$i_smaller = count($datasets[0]['labels']) > count($datasets[1]['labels']) ? 1:0;
			// add blank key with a 0 index, so it always gets prepended to front of array, it doesn't matter since the value is null for sure so no index reference needed
			$datasets[$i_smaller]['labels'][0] = ' ';
			$datasets[$i_smaller]['compareLabels'][0] = '';
			$datasets[$i_smaller]['data'][0] = null;
			// resort labels since the loop above was chronologically ordered already
			ksort($datasets[$i_smaller]['labels']);
			ksort($datasets[$i_smaller]['compareLabels']);
			ksort($datasets[$i_smaller]['data']);
		}
		// now go through scopes, get results and fill in data
		foreach( $scopes as $stack => $scope ){
			// prepare data sql
			if( $args['range_type'] !== 'all' ){
				$conditions['scope'] = $wpdb->prepare(' booking_date BETWEEN %s AND %s ', $scope['start']->getDateTime(), $scope['end']->getDateTime());
			}
			// prepare WHERE condition
			$where = '';
			if( count($conditions) >  0 ){
				$where = ' WHERE ' . implode(' AND ', $conditions);
			}
			if( !empty($subgroup) ) {
				// determine how many sets of data we need here for this stack, e.g. for a year we'll need 12 months i.e. a stack will have 12 data arrays
				$subgroupby = static::get_sql_groupby($subgroup);
				$sql = 'SELECT '. implode(', ', $selectors) .', MONTH(booking_date) AS month, WEEK(booking_date) as week, YEAR(booking_date) as year, DAYOFYEAR(booking_date) as day, booking_date FROM '. EM_BOOKINGS_TABLE . $where ." GROUP BY $subgroupby , $groupby";
				$booking_data = $wpdb->get_results( $sql, ARRAY_A );
			}else{
				$sql = 'SELECT '. implode(', ', $selectors) .', MONTH(booking_date) AS month, WEEK(booking_date) as week, YEAR(booking_date) as year, DAYOFYEAR(booking_date) as day, booking_date FROM '. EM_BOOKINGS_TABLE . $where .' GROUP BY '.$groupby;
				$booking_data = $wpdb->get_results( $sql, ARRAY_A );
			}
			
			foreach( array_keys($selectors) as $unit ) {
				// we go through each found date and add it to an array, then we fill in potential blanks
				$dataset = (object) array(
					'label'         => $unit_labels[ $unit ],
					'data'          => array(),
					'format'        => $unit,
					'compareLabels' => $datasets[$stack]['compareLabels'],
					'stack'         => $stack,
					'skipNull'      => true,
					'fill'          => !empty($subgroup),
				);
				// add label for dataset
				if( $stats->compare ){
					$dataset->label = static::get_date_range_i18n($scope['start'], $scope['end']);
				}
				
				$dataset_data = $datasets[$stack]['data'];
				if( !empty($subgroup) ){
					// fill up each data array item with subgroup data
					foreach( $dataset_data as $k => $v ){
						$dataset_data[$k] = $datasets['subgroups']['data'];
					}
					// get a subgroup query and group up
					foreach ( $booking_data as $result ) {
						// change date into string meaningful info
						if( $result[$unit] > 0 ){
							$date = new EM_DateTime($result['booking_date'], 'UTC');
							$keys = static::get_date_indexes( $date, $args['mode'] );
							$subgroup_keys = static::get_date_indexes( $date, $subgroup, true );
							if( empty($dataset_data[ $keys[0] ][ $subgroup_keys[0] ]) ) {
								$dataset_data[ $keys[0] ][ $subgroup_keys[0] ] = $result[ $unit ];
							}else{
								$dataset_data[ $keys[0] ][ $subgroup_keys[0] ] += $result[ $unit ];
							}
						}
					}
					// add dataset
					$dataset->data = $dataset_data;
					$stats->data->datasets[$stack] = $dataset;
				}else{
					foreach ( $booking_data as $result ) {
						// change date into string meaningful info
						if( $result[$unit] > 0 ){
							$date = new EM_DateTime($result['booking_date'], 'UTC');
							$keys = static::get_date_indexes( $date, $args['mode'] );
							$dataset_data[$keys[0]] = $result[$unit];
						}
					}
					// add dataset
					$dataset->data = $dataset_data;
					$stats->data->datasets[$stack] = $dataset;
				}
				
				// if we're dealing with selectors, we can't compare scopes so we increase the stack count here, since they are essentially the stacks
				if( count($selectors) > 1 ){
					$stack++;
				}
			}
			// if we're dealing with selectors, we're done regardless of scope comparison
			if( count($selectors) > 1 ){
				break;
			}
		}
		// if there's only one point of data, then we default to bars since there isn't any lines just a dot
		if( count($stats->data->datasets[0]->data) === 1 && $stats->type !== 'pie' ){
			$stats->type = 'bar';
			// convert 0s to null so skipNull takes effect
			foreach( $stats->data->datasets as $k => $dataset ){
				$dataset->skipNull = true;
				// if subgrouped, $data will be objects and the null values are already applied, this will be skipped
				foreach( $dataset->data as $dk => $data ){
					if( $data === 0 ){
						$dataset->data[$dk] = null;
					}
				}
			}
			if( $stats->compare && count($stats->data->datasets[0]->data) === 1 ){ // both are objects with unique indexes, shared or unique
				// rebuild labels of previous period to front of labels
				$datasets[0]['labels'] = $datasets[1]['labels'] + $datasets[0]['labels'];
				// padd data so it matches labels
				foreach( $datasets[0]['labels'] as $k => $v ){
					foreach( $stats->data->datasets as $stack => $dataset ){
						$dataset->compareLabels = $datasets[1]['compareLabels'] + $datasets[0]['compareLabels'];
						if( !isset($dataset->data[$k]) ){
							if( $subgroup ){
								// force null values since it may have started as a line graph
								$dataset_data = $datasets['subgroups']['data'];
								foreach( $dataset_data as $dk => $dv ){
									$dataset_data[$dk] = null;
								}
								// save dataset array so it's sorted further down
								$dataset->data[$k] = $dataset_data;
							}else{
								// null i.e. non-existent so it's skipped
								$dataset->data[$k] = null;
							}
						}
					}
				}
				/* not needed anymore since it's sorted at the end
				// resort out data so they lign up with labels
				foreach( $datasets as $stack => $dataset ){
					ksort($dataset['data']);
					$stats->data->datasets[$stack]->data = array_values($dataset['data']);
				}
				// add labels to stats
				ksort($labels);
				$stats->data->labels = array_values($labels);
				 **/
			}
			// we unify the data for bars and pies, otherwise might as well just show a line
			
		}
		
		if ( $stats->type === 'pie' ) {
			// pies need all labels and all data, in corresponding order without 0s, that's about it!
			$pie_data = array( 'labels' => array(), 'data' => array() );
			foreach ( $stats->data->datasets as $stack => $dataset ) {
				foreach ( $dataset->data as $k => $v ) {
					$value = is_object($v) ? $v->y:$v;
					if( $value > 0 ) {
						if ( empty( $pie_data['data'][ $k ] ) ) {
							$pie_data['data'][ $k ] = $value;
						} else {
							$pie_data['data'][ $k ] += $value;
						}
						$pie_data['labels'][ $k ] = $datasets[$stack]['labels'][ $k ];
					}
				}
			}
			// now we have matching data and labels, reorder and pass ordered arrays
			ksort($pie_data['labels']);
			ksort($pie_data['data']);
			$stats->data->labels = array_values($pie_data['labels']);
			$stats->data->datasets = array( (object) array(
				'data' => array_values($pie_data['data']),
				'format' => $unit, // assumed same for a pie chart
			));
			$stats->scales = false;
		} else {
			// Add y axes, with a second one if units are different (i.e. price vs number)
			$multiscale = count($selectors) > 1 && !empty($selectors['price']);
			foreach( $stats->data->datasets as $stack => $dataset ){
				// add second axis to chart.js
				$scale_index = $multiscale ? 'y' . $stack : 'y0'; // we know we're comparing different scale types so we'll need two y-axes
				$dataset->yAxisID = $scale_index;
				if( empty($stats->scales->{$scale_index}) ) {
					$stats->scales->{$scale_index} = (object) array(
						'type' => $dataset->format,
						'stacked' => true, //empty($subgroup) && $stats->type === 'line'
					);
				}
				if( $subgroup ) {
					$stats->scales->x = (object) array( 'stacked' => true );
				}
			}
			
			// sort and match numerical indexes for compareLabel array
			foreach ( $stats->data->datasets as $dataset ) {
				ksort( $dataset->compareLabels );
				$dataset->compareLabels = array_values( $dataset->compareLabels );
			}
			// reorder, flatten dataset data structures and/or remove associative keys
			if( $subgroup ) {
				$datasets_data = array();
				foreach ( $stats->data->datasets as $stack => $dataset_stack ) {
					// subgroups will have an array for data, so we need to split this up into a group of datasets for each dataset
					$dataset_subgroups = array();
					$non_null_datasets = array();
					foreach ( $dataset_stack->data as $group_key => $dataset_group ) {
						// clone stack dataset, clear data prop and make it a single array
						foreach ( $dataset_group as $dataset_key => $subgroup_value ) {
							if ( empty( $dataset_subgroups[ $dataset_key ] ) ) {
								// set up dataset
								$dataset_subgroup = clone( $dataset_stack );
								$dataset_subgroup->data = array();
								$dataset_subgroup->label = $datasets['subgroups']['labels'][$dataset_key];
								/*
								foreach( $dataset_subgroup->compareLabels as $k => $v ){
									$dataset_subgroup->compareLabels[$k] = $dataset_subgroup->label;
								}
								*/
								$dataset_subgroups[ $dataset_key ] = $dataset_subgroup;
							}
							$null = $stats->type === 'line' ? 0 : null;
							$dataset_subgroups[ $dataset_key ]->data[$group_key] = $subgroup_value;
							if( $subgroup_value ){
								$non_null_datasets[$dataset_key] = true;
							}
						}
					}
					// sort out subgroups and remove indexes
					ksort( $dataset_subgroups );
					foreach( $dataset_subgroups as $dataset_key => $dataset_subgroup ){
						if( empty($non_null_datasets[$dataset_key]) ){
							unset($dataset_subgroups[$dataset_key]);
						}else{
							ksort($dataset_subgroup->data);
							$dataset_subgroup->data = array_values( $dataset_subgroup->data );
							$datasets_data[] = $dataset_subgroup;
						}
					}
					if( empty($dataset_subgroups) ){
						// empty data, add a warning
						$stats->nulls[$stack] = true;
					}
				}
				$stats->data->datasets = $datasets_data;
			}else{
				foreach ( $stats->data->datasets as $dataset_stack ) {
					ksort( $dataset_stack->compareLabels );
					$dataset_stack->compareLabels = array_values( $dataset_stack->compareLabels );
					// now we sort and remove keys from data array
					ksort( $dataset_stack->data );
					$dataset_stack->data = array_values( $dataset_stack->data );
				}
			}
			
			// add main labels
			ksort($datasets[0]['labels']);
			$stats->data->labels = array_values($datasets[0]['labels']);
		}
		// finally take some overview stats for below the graph, adding a previous range scope if not comparing
		/*
		if( count($scopes) === 1 ){
			// get 1 day less than first scope day and then work backwards to difference
			$interval = $scopes[0]['end']->diff( $scopes[0]['start'], true );
			$scopes[1]['end'] = $scopes[0]['start']->copy()->sub( 'P1D' ); // extra day so we end day before first scope
			$scopes[1]['start'] = $scopes[0]['start']->copy()->sub( 'P'. $interval->days .'D' )->setTime(23,59,59); // we want pure days, not months hours etc.
			$scopes[1]['previous'] = true;
		}
		*/
		foreach( $scopes as $stack => $scope ) {
			// prepare data sql
			if( $args['range_type'] !== 'all' ) {
				$conditions['scope'] = $wpdb->prepare( ' booking_date BETWEEN %s AND %s ', $scope['start']->getDateTime(), $scope['end']->getDateTime() );
			}
			// prepare WHERE
			$where = '';
			if( count($conditions) >  0 ){
				$where = ' WHERE ' . implode(' AND ', $conditions);
			}
			// get data
			$sql = 'SELECT ' . implode( ', ', $summaries) .' , '. implode( ', ', $averages ) . ' FROM ' . EM_BOOKINGS_TABLE . $where;
			$booking_data = $wpdb->get_row( $sql, ARRAY_A );
			// clean null data to 0 and add to stats
			if( $booking_data ) {
				foreach ( $booking_data as $k => $v ) {
					if ( $v === null ) {
						$booking_data[ $k ] = 0;
					}
				}
			} else {
				$keys = array_merge( array_keys($summaries), array_keys($averages) );
				$booking_data = array_combine( $keys, array_fill(0, count($keys), 0)  );
			}
			$stats->stats[$stack] = $booking_data;
		}
		return $stats;
	}
	
	public static function build_dataset_template($scopes, $args, $subgroup = false){
		
		// build datasets array with re-usable data for each x-Axis (stack) set
		$datasets = array();
		foreach( $scopes as $stack => $scope ){
			// before returning data, label and dataset will be reordered by index and converted to numeric array, so that all data lines up
			$start_scope = $scope['start']->copy();
			$end_scope = $scope['end']->copy();
			switch ( $args['mode'] ) {
				case 'year' :
					// get end of year
					$start_scope->modify('first day of this month');
					$end_scope->setDate($end_scope->format('Y'), 12, 31);
					break;
				case 'day' :
					// today (tomorrow further down)
					$end_scope->add('P1D');
					break;
				case 'week' :
					// get last day of week
					$end_scope->setStartOfWeek()->add('P6D');
					break;
				case 'month' :
				default :
					// last day of month
					$start_scope->modify('first day of this month');
					$end_scope = $end_scope->modify('last day of this month');
					break;
			}
			$end_scope->add('P1D')->setTime(0,0,0); // so any sec less than this is day before
			// loop through scope in units and set datasets
			$datasets[$stack] = array('labels' => array(), 'data' => array(), 'compareLabels' => array());
			while( $start_scope < $end_scope ){
				$keys = static::get_date_indexes( $start_scope, $args['mode'] );
				$datasets[$stack]['labels'][$keys[0]] = $keys[1];
				$datasets[$stack]['compareLabels'][$keys[0]] = $keys[2];
				$datasets[$stack]['data'][$keys[0]] = 0; // pies and bars don't look as nice with empty 0 vals
				// add time and loop
				$start_scope->modify('+1 '.$args['mode']);
			}
		}
		// now deal with subgroup data labels, for each group e.g. a year, we add the max number of subgroup items i.e. months in each stack key
		// this is fixed per grouping because we need symetrical arrays for the data prop, nulls are just ignored anyway
		if( $subgroup ){
			// we decide how to loop current bracket in parent scope, since we're not doing ranges here but subsets (e.g. months in a year, not months in 12 months - subtle profound difference)
			$datasets['subgroups'] = array('data' => array(), 'labels' => array());
			$default = $args['type'] === 'line' ? 0 : null;
			switch ( $subgroup ) {
				case 'day' :
					// 31 days, so all months are same length
					$translation = esc_html__('Day %d', 'events-manager');
					for( $i = 1; $i <= 31; $i++ ){
						$index = str_pad($i, 2, '0', STR_PAD_LEFT);
						$datasets['subgroups']['data'][$index] = $default;
						$datasets['subgroups']['labels'][$index] = sprintf($translation, $i);
					}
					break;
				case 'week' :
					// 5 weeks (starting from 1st of month, not weekdays, therefore we can compare groups evenly), so we have max week count for every month
					$translation = esc_html__('Week %d', 'events-manager');
					for( $i = 1; $i <= 5; $i++ ){
						$datasets['subgroups']['data']['0'.$i] = $default;
						$datasets['subgroups']['labels']['0'.$i] = sprintf($translation, $i);
					}
					break;
				case 'month' :
					// we know this now
					$datasets['subgroups'] = array(
						'data' =>  array('01' => $default,'02' => $default,'03' => $default,'04' => $default,'05' => $default,'06' => $default,'07' => $default,'08' => $default,'09' => $default,'10' => $default,'11' => $default,'12' => $default, ),
						'labels' => array('01' => __('January'),'02' => __('February'),'03' => __('March'),'04' => __('April'),'05' => __('May'),'06' => __('June'),'07' => __('July'),'08' => __('August'),'09' => __('September'),'10' => __('October'),'11' => __('November'),'12' => __('December'), ),
					);
					break;
			}
		}
		return $datasets;
	}
	
	/**
	 * @param EM_DateTime $start
	 * @param EM_DateTime $end
	 *
	 * @return string
	 */
	public static function get_date_range_i18n( $start, $end ){
		if( $start->format('Y-m-d') === $end->format('Y-m-d') ){
			// same day, one date
			$format = $start->i18n('M d, Y');
		}elseif( $start->format('Y') === $end->format('Y') ){
			if( $start->format('m') === $end->format('m') ) {
				$format = $start->i18n('d') . ' - ' . $end->i18n('d M Y');
			}else{
				$format = $start->i18n('M d') . ' - ' . $end->i18n('M d Y');
			}
		}else{
			$format = $start->i18n('M d, Y') . ' - ' . $end->i18n('M d, Y');
		}
		return $format;
	}
	
	public static function get_date_indexes( $date, $mode = 'month', $subgroup = false ){
		switch ( $mode ) {
			case 'year' :
				$label = $date->format('Y');
				$index = $label;
				$title = $date->format('Y');
				break;
			case 'day' :
				if( $subgroup ){
					$index = $date->format('d');
					$label = sprintf( esc_html__('Day %d'), $index );
					$title = $label;
				}else{
					$title = $date->format('Y-m-d');
					$label = $date->format('Y-m-d');
					$index = $date->format('z');
				}
				break;
			case 'week' :
				// get first/last day of weeks
				if( $subgroup ){
					// calculate week number based on days of month, not weekday etc. so we have comparative 7-day chunks, otherwise some months may have 1 day and others 7
					$day = $date->format('d');
					$index = '0'.ceil($day / 7);
					$label = sprintf( esc_html__('Week %d'), $index );
					$title = $label;
				}else{
					$date->setStartOfWeek();
					$week_start_date = $date->i18n('d');
					$week_start_month = $date->i18n('M');
					$week_end_date = $date->add('P6D')->i18n('d');
					$week_end_month = $date->i18n('M');
					if( $week_start_month === $week_end_month ){
						$label = "$week_start_date-$week_end_date $week_end_month";
					}else{
						$label = "$week_start_date $week_start_month - $week_end_date $week_end_month";
					}
					$index = $date->format('Y-W');
					$title = $label . $date->format(' Y');
				}
				break;
			case 'month' :
				if( $subgroup ){
					// we need only munth number and name to subgroup it
					$index = $date->format('m');
					$label = $date->i18n('M');
					$title = $label;
				}else {
					$index = $date->format( 'Y-m' );
					$label = $date->i18n( 'M' );
					if ( $date->format( 'Y' ) != date( 'Y' ) ) {
						$label .= ' \'' . $date->format( 'y' );
					}
					$title = $date->i18n( 'M Y' );
				}
				break;
		}
		return array($index, $label, $title);
	}
	
	public static function get_sql_groupby( $mode ){
		switch ( $mode ) {
			case 'year' :
				$groupby = 'YEAR(booking_date)';
				break;
			case 'day' :
				$groupby = 'DAYOFYEAR(booking_date)';
				break;
			case 'week' :
				// here we need to do a litle post-processing so that we can avoid problems with weekdays, starting days etc. missing out entries within a month
				$groupby = 'DAYOFMONTH(booking_date)';
				break;
			case 'month' :
			default :
				$groupby = 'MONTH(booking_date)';
				break;
		}
		return $groupby;
	}
	
	/**
	 * Outputs a chart with the provided view settings, or a set of args to use.
	 * @param array|string $view
	 *
	 * @return void
	 */
	public static function output( $view = 'dashboard', $item_id = null ) {
		$args = is_array($view) ? $view : static::get_default_args( $view );
		$id = rand(10,99999);
		$today = date('Y-m-d');
		$range_dates = static::get_range_dates();
		if( $view === 'event' ){
			$args['event'] = $item_id;
		}elseif( $view === 'ticket' ){
			$args['ticket'] = $item_id;
		}
		$stats = static::get_stats( $args );
		?>
		<div class="<?php em_template_classes('chart', 'bookings-chart'); if( empty($args['show_filters']) ) echo ' hidden-filters'; ?>">
			<div class="em-chart-header">
				<div class="em-chart-title">
					<?php echo esc_html($stats->chartTitle); ?>
				</div>
				<section class="option-triggers">
					<span class="em-chart-filters-trigger em-icon em-icon-filter em-tooltip" aria-label="<?php esc_html_e('Show/Hide Filters', 'events-manager'); ?>" data-tippy-placement="bottom" data-tippy-theme="dark"></span>
					<span class="em-chart-settings-trigger em-icon em-icon-settings em-clickable em-tooltip" rel="#em-chart-settings-<?php echo $id; ?>" aria-label="<?php esc_html_e('Display Settings', 'events-manager'); ?>" data-tippy-placement="bottom" data-tippy-theme="dark"></span>
				</section>
			</div>
			<form action="" method="post" id="em-chart-form-<?php echo $id; ?>">
				<div class="em-chart-filters">
					<section class="main-filters">
						<div class="em-chart-filter-set dataset-1">
							<div class="dataset-1-metric">
								<label>
									<span><?php esc_html_e('Metric', 'events-manager'); ?></span>
									<select name="unit" class="em-chart-filter em-chart-unit">
										<option value="spaces" <?php self::selected('unit', 'spaces', $args); ?>><?php esc_html_e('Spaces', 'events-manager'); ?></option>
										<option value="price" <?php self::selected('unit', 'price', $args); ?>><?php esc_html_e('Sales', 'events-manager'); ?></option>
										<option value="bookings" <?php self::selected('unit', 'bookings', $args); ?>><?php esc_html_e('Bookings', 'events-manager'); ?></option>
									</select>
								</label>
								<label>
									<span><?php esc_html_e('During', 'events-manager'); ?></span>
									<select name="range_type" aria-label="<?php esc_html_e('View Range', 'events-manager'); ?>">
										<option value="custom" <?php self::selected('range_type', 'custom', $args); ?>>
											<?php esc_html_e('Custom Dates', 'events-manager'); ?>
										</option>
										<?php foreach( static::get_range_types() as $name => $label ): ?>
											<?php
											$date_data = is_array($range_dates[$name]) ? implode(',', $range_dates[$name]) : $range_dates[$name];
											?>
											<option value="<?php echo esc_attr($name); ?>" <?php self::selected('range_type', $name, $args); ?> data-date="<?php echo esc_attr($date_data); ?>"><?php echo esc_html($label); ?></option>
										<?php endforeach; ?>
									</select>
								</label>
							</div>
							<div class="em-datepicker em-datepicker-range em-chart-dates-custom" data-until-id="em-chart-dates-compare-<?php echo $id ?>" data-datepicker="<?php echo esc_js(json_encode( (object) array('allowInput', false) )); ?>">
								<label for="em-date-start-end-<?php echo $id ?>" class="screen-reader-text"><?php esc_html_e ( 'Dates', 'events-manager'); ?></label>
								<input id="em-date-start-end-<?php echo $id ?>" type="hidden" class="em-date-input em-date-start-end" aria-hidden="true" placeholder="<?php esc_html_e ( 'Select date range', 'events-manager'); ?>">
								<div class="em-datepicker-data">
									<input type="date" name="range_dates[0][0]" value="<?php if( !empty($args['range_dates'][0][0]) ) echo esc_attr($args['range_dates'][0][0]); ?>" aria-label="<?php esc_html_e ( 'From ', 'events-manager'); ?>">
									<span class="separator"><?php esc_html_e('to','events-manager'); ?></span>
									<input type="date" name="range_dates[0][1]" value="<?php if( !empty($args['range_dates'][0][1]) ) echo esc_attr($args['range_dates'][0][1]); ?>" aria-label="<?php esc_html_e('to','events-manager'); ?>">
								</div>
							</div>
							<label>
								<span><?php esc_html_e('Booking Status', 'events-manager'); ?></span>
								<select name="status" class="em-chart-filter em-booking-status" aria-label="<?php esc_html_e('Booking Statuses', 'events-manager'); ?>">
									<?php
									$status_arg = is_array($args['status']) ? implode(',', $args['status']) : $args['status'];
									?>
									<option value="all" <?php self::selected($status_arg, 'all'); ?>><?php esc_html_e('All', 'events-manager'); ?></option>
									<option value="0,1" <?php self::selected($status_arg, '0,1'); ?>><?php esc_html_e('Pending and Approved', 'events-manager'); ?></option>
									<?php
									$EM_Booking = em_get_booking();
									foreach( $EM_Booking->status_array as $status => $label){
										?>
										<option value="<?php echo esc_attr($status); ?>" <?php self::selected($status_arg, (string) $status); ?>><?php echo esc_html($label); ?></option>
										<?php
									}
									?>
								</select>
							</label>
						</div>
						<div class="em-chart-filter-set dataset-2">
							<label>
								<span><?php esc_html_e('Compare With', 'events-manager'); ?></span>
								<select name="compare" class="em-chart-filter em-chart-compare" aria-label="<?php esc_html_e('Compare With', 'events-manager'); ?>">
									<option value="0"><?php esc_html_e('None', 'events-manager'); ?></option>
									<?php foreach( static::get_compare_options() as $key => $optgroup ): ?>
										<optgroup label="<?php echo esc_attr($optgroup['label']); ?>" data-label-key="<?php echo esc_attr($key); ?>">
											<?php foreach( $optgroup['options'] as $option_name => $option_label ): ?>
											<option value="<?php echo esc_attr($option_name); ?>" <?php self::selected('compare', $option_name, $args); ?>><?php echo esc_html($option_label); ?></option>
											<?php endforeach; ?>
										</optgroup>
									<?php endforeach; ?>
								</select>
							</label>
							<div>
								<div class="em-datepicker em-chart-dates-compare em-tooltip" id="em-chart-dates-compare-<?php echo $id ?>" data-datepicker="<?php echo esc_js(json_encode( (object) array('allowInput', false) )); ?>" aria-label="<?php esc_attr_e('Choose the start date for comparing equivalent date ranges. The latest comparison end date is day before main duration start date.', 'events-manager'); ?>" data-tippy-placement="bottom" data-tippy-theme="dark">
									<label for="em-date-start-end-<?php echo $id ?>" class="screen-reader-text"><?php esc_html_e ( 'Dates', 'events-manager'); ?></label>
									<input id="em-date-start-end-<?php echo $id ?>" type="hidden" class="em-date-input em-date-start-end" aria-hidden="true" placeholder="<?php esc_html_e ( 'Start comparison date', 'events-manager'); ?>">
									<div class="em-datepicker-data">
										<input type="date" name="range_dates[1]" value="<?php if( !empty($args['range_dates'][1]) ) echo esc_attr($args['range_dates'][1]); ?>" aria-label="<?php esc_html_e ( 'From ', 'events-manager'); ?>">
									</div>
								</div>
							</div>
							<label>
								<span><?php esc_html_e('Chart Type', 'events-manager'); ?></span>
								<select name="type" class="em-chart-filter em-chart-mode" aria-label="<?php esc_html_e('View As', 'events-manager'); ?>">
									<option value="line" <?php self::selected('type', 'line', $args); ?>><?php esc_html_e('Line Graph', 'events-manager'); ?></option>
									<option value="bar" <?php self::selected('type', 'bar', $args); ?>><?php esc_html_e('Bar Graph', 'events-manager'); ?></option>
									<option value="pie" <?php self::selected('type', 'pie', $args); ?>><?php esc_html_e('Pie Chart', 'events-manager'); ?></option>
								</select>
							</label>
						</div>
						<div class="mode-filter">
							<label>
								<span><?php esc_html_e('Group By', 'events-manager'); ?></span>
								<select name="mode" class="em-chart-filter em-chart-mode" aria-label="<?php esc_html_e('Group By', 'events-manager'); ?>">
									<option value="day" <?php self::selected('mode', 'day', $args); ?>><?php esc_html_e('Day'); ?></option>
									<option value="week" <?php self::selected('mode', 'week', $args); ?>><?php esc_html_e('Week'); ?></option>
									<option value="month" <?php self::selected('mode', 'month', $args); ?>><?php esc_html_e('Month'); ?></option>
									<option value="year" <?php self::selected('mode', 'year', $args); ?>><?php esc_html_e('Year'); ?></option>
								</select>
							</label>
							<div class="mode-filter em-tooltip" aria-label="<?php esc_attr_e('Choose graph type and stacking view options. Some views and stacking may not be available for all setting combinations.', 'events-manager'); ?>" data-tippy-theme="dark">
								<label>
									<span><?php esc_html_e('Stack By', 'events-manager'); ?></span>
								</label>
								<select name="stacked" class="em-chart-filter em-chart-mode" aria-label="<?php esc_html_e('Group By', 'events-manager'); ?>">
									<option value="0"><?php esc_html_e('Not Stacked'); ?></option>
									<option value="day" <?php self::selected('subgroup', 'day', $args); ?>><?php esc_html_e('Day'); ?></option>
									<option value="week" <?php self::selected('subgroup', 'week', $args); ?>><?php esc_html_e('Week'); ?></option>
									<option value="month" <?php self::selected('subgroup', 'month', $args); ?>><?php esc_html_e('Month'); ?></option>
								</select>
							</div>
						</div>
					</section>
				</div>
				<input type="hidden" name="event_archetype" value="<?php echo esc_attr($args['event_archetype']); ?>">
				<input type="hidden" name="view" value="<?php echo esc_attr($args['view']); ?>">
				<?php if( $args['view'] === 'event' || $args['view'] === 'ticket' ): ?>
					<input type="hidden" name="_nonce" value="<?php echo esc_attr(wp_create_nonce('em-chart-'.$args['view'].'-'. $args[$args['view']])); ?>">
					<input type="hidden" name="<?php echo esc_attr($args['view']); ?>" value="<?php echo esc_attr($args[$args['view']]); ?>">
				<?php else: ?>
					<input type="hidden" name="_nonce" value="<?php echo esc_attr(wp_create_nonce('em-chart-'.$args['view'])); ?>">
				<?php endif; ?>
				
				<div class="em-modal <?php em_template_classes('chart-settings-modal'); ?>" id="em-chart-settings-<?php echo $id; ?>" data-parent="em-chart-form-<?php echo $id; ?>" style="opacity:0;">
					<div class="em-modal-popup">
						<header>
							<a class="em-close-modal" href="#"></a><!-- close modal -->
							<div class="em-modal-title">
								<?php esc_html_e('Chart Options', 'events-manager'); ?>
							</div>
						</header>
						<div class="em-modal-content input">
							<p>
								<label><input type="checkbox" name="show_filters" value="1" <?php if( !empty($args['show_filters'])) echo 'checked'; ?>> <?php esc_html_e('Show search filters on page load', 'events-manager'); ?></label>
							</p>
							<section>
								<header><?php esc_html_e('Statistic Averages/Totals', 'events-manager'); ?></header>
								<div>
									<p><em><?php esc_html_e('Choose what statistic summaries to show below the graph, saved per-view type, such as on the bookings dashboard, single event views, single-ticket views etc.'); ?></em></p>
									<p>
										<label><input type="checkbox" name="summaries[price]" value="1" <?php if( !empty($args['summaries']['price'])) echo 'checked'; ?>> <?php esc_html_e('Total Sales', 'events-manager'); ?></label>
										<label><input type="checkbox" name="summaries[spaces]" value="1" <?php if( !empty($args['summaries']['spaces'])) echo 'checked'; ?>> <?php esc_html_e('Total Tickets', 'events-manager'); ?></label>
										<label><input type="checkbox" name="summaries[bookings]" value="1" <?php if( !empty($args['summaries']['bookings'])) echo 'checked'; ?>> <?php esc_html_e('Total Bookings', 'events-manager'); ?></label>
										<label><input type="checkbox" name="summaries[price_avg]" value="1" <?php if( !empty($args['summaries']['price_avg'])) echo 'checked'; ?>> <?php esc_html_e('Average Sale', 'events-manager'); ?></label>
										<label><input type="checkbox" name="summaries[spaces_avg]" value="1" <?php if( !empty($args['summaries']['spaces_avg'])) echo 'checked'; ?>> <?php esc_html_e('Average Ticket', 'events-manager'); ?></label>
										<label><input type="checkbox" name="summaries[tickets_avg]" value="1" <?php if( !empty($args['summaries']['tickets_avg'])) echo 'checked'; ?>> <?php esc_html_e('Tickets / Booking', 'events-manager'); ?></label>
									</p>
								</div>
							</section>
						</div><!-- content -->
						<footer class="em-submit-section input">
							<div>
								<button type="submit" class="button button-primary"><?php esc_html_e('Save Settings', 'events-manager'); ?></button>
							</div>
						</footer>
					</div><!-- modal -->
				</div>
			</form>
			<?php static::output_chart( $args, $stats ); ?>
		</div>
		<?php
		add_action('wp_footer', array(static::class, 'js_footer'));
		add_action('admin_footer', array(static::class, 'js_footer'));
	}
	
	public static function output_chart( $args, $stats = null ){
		if( $stats === null ) {
			$stats = static::get_stats( $args );
		}
		$s = $stats->stats;
		unset($stats->stats); // not needed in json response
		?>
		<div data-chart="<?php echo esc_attr(json_encode($stats)); ?>" class="em-chart-wrapper">
			<canvas></canvas>
			<div class="em-chart-stats">
				<?php if( !empty($args['summaries']['price']) ): ?>
				<div>
					<div class="title"><?php esc_html_e('Total Sales','events-manager'); ?></div>
					<div class="total">
						<?php echo em_get_currency_formatted($s[0]['price']); ?>
					</div>
					<?php if( !empty($s[1]) ): ?>
						<?php
							$diff = static::get_differences($s[0]['price'], $s[1]['price']);
						?>
						<div class="change <?php echo $diff['class']; ?>">
							<span class="<?php echo $diff['class']; ?>"><?php echo $diff['op'] . number_format($diff['%'], 0) .'%'; ?></span>
							<span class="sub"> (<?php echo em_get_currency_formatted($diff['amt']); ?>)</span>
						</div>
						<div class="comparison"><?php esc_html_e('Compared to', 'events-manager'); ?> <?php echo  em_get_currency_formatted($s[1]['price']); ?></div>
					<?php endif; ?>
				</div>
				<?php endif; ?>
				<?php if( !empty($args['summaries']['bookings']) ): ?>
				<div>
					<div class="title"><?php esc_html_e('Total Bookings','events-manager'); ?></div>
					<div class="total">
						<?php echo $s[0]['bookings']; ?>
					</div>
					<?php if( !empty($s[1]) ): ?>
						<?php
						$diff = static::get_differences($s[0]['bookings'], $s[1]['bookings']);
						?>
						<div class="change">
							<span class="<?php echo $diff['class']; ?>"><?php echo $diff['op'] . number_format($diff['%'], 0) .'%'; ?></span>
							<span class="sub"> (<?php echo $diff['amt']; ?>)</span>
						</div>
						<div class="comparison"><?php esc_html_e('Compared to', 'events-manager'); ?> <?php echo $s[1]['bookings']; ?></div>
					<?php endif; ?>
				</div>
				<?php endif; ?>
				<?php if( !empty($args['summaries']['spaces']) ): ?>
				<div>
					<div class="title"><?php esc_html_e('Total Spaces','events-manager'); ?></div>
					<div class="total">
						<?php echo $s[0]['spaces']; ?>
					</div>
					<?php if( !empty($s[1]) ): ?>
						<?php
						$diff = static::get_differences($s[0]['spaces'], $s[1]['spaces']);
						?>
						<div class="change">
							<span class="<?php echo $diff['class']; ?>"><?php echo $diff['op'] . number_format($diff['%'], 0) .'%'; ?></span>
							<span class="sub"> (<?php echo $diff['amt']; ?>)</span>
						</div>
						<div class="comparison"><?php esc_html_e('Compared to', 'events-manager'); ?> <?php echo $s[1]['spaces']; ?></div>
					<?php endif; ?>
				</div>
				<?php endif; ?>
				<?php if( !empty($args['summaries']['price_avg']) ): ?>
				<div>
					<div class="title"><?php esc_html_e('Sale Averages','events-manager'); ?></div>
					<div class="total">
						<?php echo em_get_currency_formatted($s[0]['price_avg']); ?>
						<span class="sub">/ <?php esc_html_e('booking', 'events-manager'); ?></span>
					</div>
					<?php if( !empty($s[1]) ): ?>
						<?php
						$diff = static::get_differences($s[0]['price_avg'], $s[1]['price_avg']);
						?>
						<div class="change">
							<span class="<?php echo $diff['class']; ?>"><?php echo $diff['op'] . number_format($diff['%'], 0) .'%'; ?></span>
							<span class="sub"> (<?php echo em_get_currency_formatted($diff['amt']); ?>)</span>
						</div>
						<div class="comparison"><?php esc_html_e('Compared to', 'events-manager'); ?> <?php echo  em_get_currency_formatted($s[1]['price_avg']); ?></div>
					<?php endif; ?>
				</div>
				<?php endif; ?>
				<?php if( !empty($args['summaries']['tickets_avg']) ): ?>
				<div>
					<div class="title"><?php esc_html_e('Average Ticket','events-manager'); ?></div>
					<div class="total">
						<?php
						$newer = $s[0]['price'] > 0 && $s[0]['spaces'] > 0 ? $s[0]['price'] / $s[0]['spaces'] : 0;
						echo em_get_currency_formatted($newer);
						?>
						<span class="sub">/ <?php esc_html_e('ticket', 'events-manager'); ?></span>
					</div>
					<?php if( !empty($s[1]) ): ?>
						<?php
						$older = $s[1]['price'] > 0 && $s[1]['spaces'] > 0 ? $s[1]['price'] / $s[1]['spaces'] : 0;
						$diff = static::get_differences($newer, $older);
						?>
						<div class="change">
							<span class="<?php echo $diff['class']; ?>"><?php echo $diff['op'] . number_format($diff['%'], 0) .'%'; ?></span>
							<span class="sub"> (<?php echo em_get_currency_formatted($diff['amt']); ?>)</span>
						</div>
					<div class="comparison"><?php esc_html_e('Compared to', 'events-manager'); ?> <?php echo  em_get_currency_formatted($older); ?></div>
					<?php endif; ?>
				</div>
				<?php endif; ?>
				<?php if( !empty($args['summaries']['spaces_avg']) ): ?>
				<div>
					<div class="title"><?php esc_html_e('Tickets / Booking','events-manager'); ?></div>
					<div class="total">
						<?php echo number_format($s[0]['spaces_avg'], 2); ?>
						<span class="sub">/ <?php esc_html_e('booking', 'events-manager'); ?></span>
					</div>
					<?php if( !empty($s[1]) ): ?>
						<?php
						$diff = static::get_differences($s[0]['spaces_avg'], $s[1]['spaces_avg']);
						?>
						<div class="change">
							<span class="<?php echo $diff['class']; ?>"><?php echo $diff['op'] . number_format($diff['%'], 0) .'%'; ?></span>
							<span class="sub"> (<?php echo number_format($diff['amt'], 2); ?>)</span>
						</div>
						<div class="comparison"><?php esc_html_e('Compared to', 'events-manager'); ?> <?php echo number_format($s[1]['spaces_avg'], 2); ?></div>
					<?php endif; ?>
				</div>
				<?php endif; ?>
			</div>
		</div>
		<?php
	}
	
	public static function get_differences( $newer, $older ) {
		$diff = $newer - $older;
		$class  = $op = '';
		if( $diff == 0 ){
			$change = 0;
		}elseif( $newer == 0 || $older == 0 ){
			$change = 100;
			$op = $newer > $older ? '+':'-';
			$class = $newer > $older ? 'plus':'minus';
		}else {
			$change = $diff / $older * 100;
			if ( $diff > 0 ) {
				$class = 'plus';
				$op    = '+';
			} elseif ( $diff < 0 ) {
				$class = 'minus';
				$op    = '-';
			}
		}
		
		return array(
			'amt'   => abs($diff),
			'%'     => abs($change),
			'class' => $class,
			'op'    => $op
		);
	}
	
	public static function selected( $index, $value, $args = array() ){
		if( empty($args) && $index === $value ){
			echo 'selected';
		}elseif( !empty($args[$index]) && $args[$index] === $value ){
			echo 'selected';
		}
	}
	
	public static function implode_js( $separator, $values, $encloser = null ){
		if( $encloser === null ){
			$encloser = "'";
		}elseif( !$encloser ){
			$encloser = '';
		}
		$outputs = array();
		foreach( $values as $value ){
			$outputs[] = $encloser . esc_js($value) . $encloser;
		}
		return implode( $separator, $outputs );
	}
	
	public static function js_footer(){
		if( static::$footer_js ) return;
		static::$footer_js = true;
		?>
		<script>
			<?php include(EM_DIR.'/includes/js/em-charts.js'); ?>
		</script>
		<?php
	}
}
Dashboard::init();
/*
$colors = array(
	'rgba(54, 162, 235, 0.75)',
	'rgba(255, 99, 132, 0.75)',
	'rgba(255, 159, 64, 0.75)',
	'rgba(255, 205, 86, 0.75)',
	'rgba(75, 192, 192, 0.75)',
	'rgba(153, 102, 255, 0.75)',
	'rgba(146, 203, 207, 0.75)',
	'rgba(201, 231, 127, 0.75)',
	'rgba(203, 67, 53, 0.75)',
	'rgba(31, 97, 141, 0.75)',
	'rgba(241, 196, 15, 0.75)',
	'rgba(39, 174, 96, 0.75)',
	'rgba(136, 78, 160, 0.75)',
	'rgba(211, 84, 0, 0.75)',
	'rgba(213, 90, 200, 0.75)',
	'rgba(200, 90, 100, 0.75)',
	'rgba(34, 207, 207, 0.75)',
	'rgba(5, 155, 255, 0.75)',
	'rgba(201, 203, 207, 0.75)',
	'rgba(129, 129, 129, 0.75)',
	);
$colors = array_unique($colors);
foreach( $colors as $col ){
	echo '<div style="width:40px; height: 40px; padding:10px; background:'.$col.'"></div>';
}
die();
*/