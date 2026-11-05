<?php

use EM\Archetypes;
use EM\Archetypes_Admin;

if(!function_exists('em_paginate')){ //overridable e.g. in you mu-plugins folder.
/**
 * Takes a few params and determines a pagination link structure
 * @param string $link
 * @param int $total
 * @param int $limit
 * @param int $page
 * @param array $data If supplied and EM_USE_DATA_ATTS is true/defined, this set of data will be stripped from the URL and added as a data-em-ajax attribute containing data AJAX can use
 * @return string
 */
function em_paginate($link, $total, $limit, $page=1, $data=array(), $ajax = null){
	if($limit > 0){
		$ajax = $ajax === null ? EM_AJAX : $ajax;
		$pagesToShow = defined('EM_PAGES_TO_SHOW') ? EM_PAGES_TO_SHOW : 11;
		$centered = defined('EM_PAGINATION_CENTERED') ? EM_PAGINATION_CENTERED : true;
		$url_parts = explode('?', $link);
		$base_link = $url_parts[0];
		$base_querystring = '';
		$data_atts = '';
        //Get querystring for first page without page
        if( count($url_parts) > 0 ) {
	        $query_arr = array();
	        parse_str( $url_parts[1], $query_arr );
	        //if $data was passed, strip any of these vars from both the $query_arr and $link for inclusion in the data-em-ajax attribute
	        if ( !empty( $data ) && is_array( $data ) && ( !defined( 'EM_USE_DATA_ATTS' ) || EM_USE_DATA_ATTS ) ) {
		        //remove the data attributes from $query_arr
		        foreach ( $data as $key => $value ) {
			        if ( array_key_exists( $key, $query_arr ) ) {
						if ( $ajax || empty($_REQUEST['action']) || in_array( $key, ['action', 'id'] ) ) {
							unset( $query_arr[ $key ] );
						}
			        }
			        $data[ $key ] = urlencode( $value );
		        }
		        //rebuild the master link, without these data attributes
		        if ( count( $query_arr ) > 0 ) {
			        $link = $base_link . '?' . build_query( $query_arr );
		        } else {
			        $link = $base_link;
		        }
		        $data_atts = 'data-em-ajax="' . esc_attr( build_query( $data ) ) . '"'; //for inclusion later on
	        }
	        //proceed to build the base querystring without pagination arguments
	        unset( $query_arr['page'] );
	        unset( $query_arr['pno'] );
	        $base_querystring = esc_attr( build_query( $query_arr ) );
	        if ( !empty( $base_querystring ) ) {
		        $base_querystring = '?' . $base_querystring;
	        }
        }
    	//calculate pages to show, totals etc.
		$maxPages = ceil($total/$limit); //Total number of pages, i.e. also the last page to show
		if( $centered ){
			$startPage = $page - floor($pagesToShow / 2);
			if( $startPage < 1 ) $startPage = 1;
		}else{
			$startPage = ($page <= $pagesToShow) ? 1 : $pagesToShow * (floor($page / $pagesToShow)); //Which page to start the pagination links from (in case we're on say page 12 and $pagesToShow is 10 pages)
		}
		$placeholder = urlencode('%PAGE%');
		$link = str_replace('%PAGE%', $placeholder, esc_url($link)); //To avoid url encoded/non encoded placeholders
	    //Add the back and first buttons
		    $string = ($page>1 && $startPage != 1) ? '<a class="prev first page-numbers" href="'.str_replace($placeholder,1,$link).'" title="1">&lt;&lt;</a> ' : '';
		    if ( $page == 2 ) {
		    	$string .= ' <a class="prev page-numbers" href="'.esc_url($base_link.$base_querystring).'" title="2">&lt;</a> ';
		    } elseif ( $page > 2 ) {
		    	$string .= ' <a class="prev page-numbers" href="'.str_replace($placeholder,$page-1,$link).'" title="'.($page-1).'">&lt;</a> ';
		    }
		//Loop each page and create a link or just a bold number if its the current page
			// 10 11 12 13 14 15 16 17 18 19 20
			$thisLastPage = $startPage + $pagesToShow < $maxPages ? $startPage + $pagesToShow : $maxPages;
			$responsive = $thisLastPage - $startPage > 5;
			for ($i = $startPage ; $i <= $thisLastPage ; $i++){
			    if( $responsive && $i == $startPage + 1 && $i + 2 <= $page) {
				    // second number onwards should be wrapped with a span and hidden for responsivenes if it's not next to the current number
				    // in other words, if there's only two page numbers before current, always visible, more - hide 2nd till current
				    $nc_open = true;
				    $string .= '<span class="not-current first-half">';
			    }
	            if($i == $page || (empty($page) && $startPage == $i)) {
					if( !empty($nc_open) ){
						// not first page in list, so we should close previous active current
						$string .= '</span>';
						$nc_open = false;
					}
	                $string .= ' <span class="page-numbers current">'.$i.'</span>';
					if( $responsive && $i + 2 < $thisLastPage ) {
						$string .= '<span class="not-current second-half">';
						$nc_open = true;
					}
	            }elseif($i=='1'){
	                $string .= ' <a class="page-numbers" href="'.esc_url($base_link.$base_querystring).'" title="'.$i.'">'.$i.'</a> ';
	            }else{
	                $string .= ' <a class="page-numbers" href="'.str_replace($placeholder,$i,$link).'" title="'.$i.'">'.$i.'</a> ';
	            }
				// leave last number unwrapped
			    if( !empty($nc_open) && $i + 2 == $thisLastPage ){
				    $string .= '</span>';
			    }
		    }
		//Add the forward and last buttons
		    $string .= ($page < $maxPages) ? ' <a class="next page-numbers" href="'.str_replace($placeholder,$page+1,$link).'" title="'.($page+1).'">&gt;</a> ' :' ' ;
		    $string .= ($i-1 < $maxPages) ? ' <a class="next last page-numbers" href="'.str_replace($placeholder,$maxPages,$link).'" title="'.$maxPages.'">&gt;&gt;</a> ' : ' ';
		// add ajax flag
			$ajax_class = $ajax ? 'em-ajax':'';
		//Return the string
		    return apply_filters('em_paginate', '<div class="em-pagination '.$ajax_class.'" '.$data_atts.'>'.$string.'</div>');
	}
}
}

/**
 * Creates a wp-admin style navigation.
 * @param string $link
 * @param int $total
 * @param int $limit
 * @param int $page
 * @param int $pagesToShow
 * @return string
 * @uses paginate_links()
 * @uses add_query_arg()
 */
function em_admin_paginate($total, $limit, $page=1, $vars=false, $base = false, $format = ''){
	$return = '<div class="tablenav-pages em-tablenav-pagination">';
	$base = !empty($base) ? $base:esc_url_raw(add_query_arg( 'pno', '%#%' ));
	$events_nav = paginate_links( array(
		'base' => $base,
		'format' => $format,
		'total' => ceil($total / $limit),
		'current' => $page,
		'add_args' => $vars
	));
	$return .= sprintf( '<span class="displaying-num">' . __( 'Displaying %1$s&#8211;%2$s of %3$s', 'events-manager') . ' </span>%4$s',
		number_format_i18n( ( $page - 1 ) * $limit + 1 ),
		number_format_i18n( min( $page * $limit, $total ) ),
		number_format_i18n( $total ),
		$events_nav
	);
	$return .= '</div>';
	return apply_filters('em_admin_paginate',$return,$total,$limit,$page,$vars);
}

function em_admin_url( $cpt = null ) {
	if ( $cpt ) {
		$cpt = Archetypes::get_post_type( $cpt );
	} else {
		$cpt = Archetypes::get_current();
	}
	return apply_filters( 'em_admin_url', admin_url().'edit.php?post_type='.$cpt );
}

/**
 * Takes a url and appends GET params (supplied as an assoc array), it automatically detects if you already have a querystring there
 * @param string $url
 * @param array $params
 * @param bool $html
 * @param bool $encode
 * @return string
 */
function em_add_get_params($url, $params=array(), $html=true, $encode=true){
	//Splig the url up to get the params and the page location
	$url_parts = explode('?', $url);
	$url = $url_parts[0];
	$url_params_dirty = array();
	if(count($url_parts) > 1){
		$url_params_dirty = $url_parts[1];
		//get the get params as an array
		if( !is_array($url_params_dirty) ){
			if( strstr($url_params_dirty, '&amp;') !== false ){
				$url_params_dirty = explode('&amp;', $url_params_dirty);
			}else{
				$url_params_dirty = explode('&', $url_params_dirty);
			}
		}
		//split further into associative array
		$url_params = array();
		foreach($url_params_dirty as $url_param){
			if( !empty($url_param) ){
				$url_param = explode('=', $url_param);
				if(count($url_param) > 1){
					$url_params[$url_param[0]] = $url_param[1];
				}
			}
		}
		//Merge it together
		$params = array_merge($url_params, $params);
	}
	//Now build the array back up.
	$count = 0;
	foreach($params as $key=>$value){
		if( $value !== null ){
			if( is_array($value) ) $value = implode(',',$value);
			$value = ($encode) ? urlencode($value):$value;
			if( $count == 0 ){
				$url .= "?{$key}=".$value;
			}else{
				$url .= ($html) ? "&amp;{$key}=".$value:"&{$key}=".$value;
			}
			$count++;
		}
	}
	return $html ? esc_url($url):esc_url_raw($url);
}

/**
 * Get a array of countries, translated. Keys are 2 character country iso codes. If you supply a string or array that will be the first value in the array (if array, the array key is the first key in the returned array)
 * @param mixed $add_blank
 * @return array
 */
function em_get_countries($add_blank = false, $sort = true){
	global $em_countries_array;
	if( !is_array($em_countries_array) ){
		$lang = substr(get_locale(), 0, 2);
		$countries = array();
		if( file_exists( EM_DIR . '/includes/i18n/countries-'.$lang.'.php') ){
			include( EM_DIR . '/includes/i18n/countries-'.$lang.'.php' );
			$em_countries_array = $countries[$lang];
		}else{
			include( EM_DIR . '/includes/i18n/countries-en.php' );
			$em_countries_array = $countries['en'];
		}
	}
	$countries = $em_countries_array;
	if($sort){ asort($countries); }
	if( $add_blank !== false ){
		if(is_array($add_blank)){
			$countries = $add_blank + $countries;
		}else{
			$countries = array(0 => $add_blank) + $countries;
		}
	}
	return apply_filters('em_get_countries', $countries);
}

/**
 * Returns an array of scopes available to events manager. Hooking into this function's em_get_scopes filter will allow you to add scope options to the event pages.
 */
function em_get_scopes(){
	global $wp_locale;
	$start_of_week = em_get_option('start_of_week');
	$end_of_week_name = $start_of_week > 0 ? $wp_locale->get_weekday($start_of_week-1) : $wp_locale->get_weekday(6);
	$start_of_week_name = $wp_locale->get_weekday($start_of_week);
	$scopes = array(
		'all' => __('All events','events-manager'),
		'future' => __('Future events','events-manager'),
		'past' => __('Past events','events-manager'),
		'today' => __('Today\'s events','events-manager'),
		'tomorrow' => __('Tomorrow\'s events','events-manager'),
		'week' => sprintf(__('Events this whole week (%s to %s)','events-manager'), $wp_locale->get_weekday_abbrev($start_of_week_name), $wp_locale->get_weekday_abbrev($end_of_week_name)),
		'this-week' => sprintf(__('Events this week (today to %s)','events-manager'), $wp_locale->get_weekday_abbrev($end_of_week_name)),
		'month' => __('Events this month','events-manager'),
		'this-month' => __('Events this month (today onwards)', 'events-manager'),
		'next-month' => __('Events next month','events-manager'),
		'1-months'  => __('Events current and next month','events-manager'),
		'2-months'  => __('Events within 2 months','events-manager'),
		'3-months'  => __('Events within 3 months','events-manager'),
		'6-months'  => __('Events within 6 months','events-manager'),
		'12-months' => __('Events within 12 months','events-manager')
	);
	return apply_filters('em_get_scopes',$scopes);
}

function em_get_currencies(){
	$currencies = new stdClass();
	$currencies->names = array('EUR' => 'EUR - Euros','USD' => 'USD - U.S. Dollars','GBP' => 'GBP - British Pounds','CAD' => 'CAD - Canadian Dollars','AUD' => 'AUD - Australian Dollars','BRL' => 'BRL - Brazilian Reais','CZK' => 'CZK - Czech koruna','DKK' => 'DKK - Danish Kroner','HKD' => 'HKD - Hong Kong Dollars','HUF' => 'HUF - Hungarian Forints','ILS' => 'ILS - Israeli New Shekels','JPY' => 'JPY - Japanese Yen','MYR' => 'MYR - Malaysian Ringgit','MXN' => 'MXN - Mexican Pesos','TWD' => 'TWD - New Taiwan Dollars','NZD' => 'NZD - New Zealand Dollars','NOK' => 'NOK - Norwegian Kroner','PHP' => 'PHP - Philippine Pesos','PLN' => 'PLN - Polish Zlotys','SGD' => 'SGD - Singapore Dollars','SEK' => 'SEK - Swedish Kronor','CHF' => 'CHF - Swiss Francs','THB' => 'THB - Thai Baht','TRY' => 'TRY - Turkish Liras', 'RUB'=>'RUB - Russian Ruble');
	$currencies->symbols = array( 'EUR' => '&euro;','USD' => '$','GBP' => '&pound;','CAD' => '$','AUD' => '$','BRL' => 'R$','CZK' => 'K&#269;','DKK' => 'kr','HKD' => '$','HUF' => 'Ft','JPY' => '&#165;','MYR' => 'RM','MXN' => '$','TWD' => '$','NZD' => '$','NOK' => 'kr','PHP' => 'Php', 'PLN' => '&#122;&#322;','SGD' => '$','SEK' => 'kr','CHF' => 'CHF','TRY' => 'TL','RUB'=>'&#8381;');
	$currencies->true_symbols = array( 'EUR' => '€','USD' => '$','GBP' => '£','CAD' => '$','AUD' => '$','BRL' => 'R$','CZK' => 'Kč','DKK' => 'kr','HKD' => '$','HUF' => 'Ft','JPY' => '¥','MYR' => 'RM','MXN' => '$','TWD' => '$','NZD' => '$','NOK' => 'kr','PHP' => 'Php','PLN' => 'zł','SGD' => '$','SEK' => 'kr','CHF' => 'CHF','TRY' => 'TL', 'RUB'=>'₽');
	return apply_filters('em_get_currencies',$currencies);
}

function em_get_currency_formatted($price, $currency=false, $format=false, $precision = 2){
	$formatted_price = '';
	if(!$format) $format = em_get_option('dbem_bookings_currency_format','@#');
	if(!$currency) $currency = em_get_option('dbem_bookings_currency');
	if( empty($price) ) $price = 0;
	$formatted_price = str_replace('#', number_format( $price, $precision, em_get_option('dbem_bookings_currency_decimal_point','.'), em_get_option('dbem_bookings_currency_thousands_sep',',') ), $format);
	$formatted_price = str_replace('@', em_get_currency_symbol(true,$currency), $formatted_price);
	return apply_filters('em_get_currency_formatted', $formatted_price, $price, $currency, $format);
}

function em_get_currency_symbol($true_symbol = false, $currency = false){
	if( !$currency ) $currency = em_get_option('dbem_bookings_currency');
	if($true_symbol){
		return em_get_currencies()->true_symbols[$currency];
	}
	return apply_filters('em_get_currency_symbol', em_get_currencies()->symbols[$currency]);
}

function em_get_currency_name($currency = false){
	if( !$currency ) $currency = em_get_option('dbem_bookings_currency');
	return apply_filters('em_get_currency_name', em_get_currencies()->names[$currency]);
}

function em_get_hour_format(){
	return em_get_option('dbem_time_24h') ? "H:i":"h:i A";
}

function em_get_days_names(){
	return array (1 => translate( 'Mon' ), 2 => translate( 'Tue' ), 3 => translate( 'Wed' ), 4 => translate( 'Thu' ), 5 => translate( 'Fri' ), 6 => translate( 'Sat' ), 0 => translate( 'Sun' ) );
}

/**
 * Works like check_admin_referrer(), but also in public mode. If in admin mode, it triggers an error like in check_admin_referrer(), if outside admin it just exits with an error.
 * @param string $action
 */
function em_verify_nonce($action, $nonce_name='_wpnonce'){
	if( is_admin() ){
		if( !wp_verify_nonce( $_REQUEST[$nonce_name] ?? '', $action) ) check_admin_referer('trigger_error');
	}else{
		if( !wp_verify_nonce( $_REQUEST[$nonce_name] ?? '', $action) ) exit( __('Trying to perform an illegal action.','events-manager') );
	}
}

/**
 * Verifies a booking form nonce, ending the request in the format it expects if verification fails.
 * @param string $action
 * @param string $nonce_name
 * @return bool
 */
function em_verify_booking_nonce( $action, $nonce_name = '_wpnonce' ){
	if( wp_verify_nonce( $_REQUEST[$nonce_name] ?? '', $action ) ) return true;
	$message = __('This booking form has expired, please reload the page and try again.','events-manager');
	if( !empty($_REQUEST['em_ajax']) ){
		$return = array('result'=>false, 'success'=>false, 'message'=>$message, 'errors'=>array($message));
		if( !headers_sent() ) header( 'Content-Type: application/javascript; charset=UTF-8', true );
		// wp_die() rather than exit() so the body leaves through WP's ajax die handler, as core's own wp_send_json() does
		wp_die( EM_Object::json_encode( apply_filters( 'em_booking_nonce_expired', $return, $action ) ), '', array('response' => null) );
	}
	exit( $message );
}

/**
 * Booking form actions whose nonce is refreshed on cached pages. Add-ons with a booking form action of their own, such as waitlists, add theirs here so the refresh reaches their forms too.
 * @return array
 */
function em_booking_form_nonce_actions(){
	$actions = apply_filters( 'em_booking_form_nonce_actions', array('booking_add') );
	return array_values( array_unique( array_filter( array_map( 'sanitize_key', (array) $actions ) ) ) );
}

/**
 * Whether a booking form action's nonce is served by the cached-page nonce refresh.
 * @param string $action
 * @return bool
 */
function em_booking_form_nonce_refreshable( $action ){
	return in_array( $action, em_booking_form_nonce_actions(), true );
}

/**
 * Fresh nonces for booking forms on cached pages, keyed by the form action they belong to.
 * @return array
 */
function em_booking_form_nonces(){
	$nonces = array(
		'booking_form' => wp_create_nonce( 'booking_form' ),
		'booking_recurrences' => wp_create_nonce( 'booking_recurrences' ),
	);
	foreach( em_booking_form_nonce_actions() as $booking_action ){
		$nonces[$booking_action] = wp_create_nonce( $booking_action );
	}
	return apply_filters( 'em_booking_form_nonces', $nonces );
}

/**
 * Since WP 4.5 em_wp_get_referer() returns false if URL is the same. We use it to get a safe referrer url, so we use the new wp_get_raw_referer() argument instead.
 * @since 5.6.3
 * @return string 
 */
function em_wp_get_referer(){
	if( function_exists('wp_get_raw_referer') ){
		//do essentially what em_wp_get_referer does, but potentially returning the same url as before
		return wp_validate_redirect(wp_get_raw_referer(), false );
	}else{
		return wp_get_referer();
	}
}

/**
 * Gets all WP users
 * @return array
 */
function em_get_wp_users( $args = array(), $extra_users = array() ) {
	global $wpdb;
	if( !empty($args) ){
	    $users = get_users($args);
	}else{
	    //added as a temp fix for http://core.trac.wordpress.org/ticket/23609, we need to make some sort of autocompleter search for users instead
	    $users = $wpdb->get_results("SELECT ID, display_name FROM {$wpdb->users} ORDER BY display_name");
	}
	$indexed_users = array();
	foreach($users as $user){
		$indexed_users[$user->ID] = $user->display_name;
	}
 	return $extra_users + $indexed_users;
}

function em_get_attributes($lattributes = false){
	$attributes = array('names'=>array(), 'values'=>array());
	if( !$lattributes && !em_get_option('dbem_attributes_enabled') ) return $attributes;
	if( $lattributes && !em_get_option('dbem_location_attributes_enabled') ) return $attributes;
	//We also get a list of attribute names and create a ddm list (since placeholders are fixed)
	$formats =
		em_get_option ( 'dbem_placeholders_custom' ).
		em_get_option ( 'dbem_location_placeholders_custom' ).
		em_get_option ( 'dbem_full_calendar_event_format' ).
		em_get_option ( 'dbem_rss_description_format' ).
		em_get_option ( 'dbem_rss_title_format' ).
		em_get_option ( 'dbem_map_text_format' ).
		em_get_option ( 'dbem_location_baloon_format' ).
		em_get_option ( 'dbem_location_event_list_item_format' ).
		em_get_option ( 'dbem_location_page_title_format' ).
		em_get_option ( 'dbem_event_list_item_format' ).
		em_get_option ( 'dbem_event_page_title_format' ).
		em_get_option ( 'dbem_single_event_format' ).
		em_get_option ( 'dbem_calendar_large_pill_format' ).
		em_get_option ( 'dbem_single_location_format' );
	//We now have one long string of formats, get all the attribute placeholders
	if( $lattributes ){
		preg_match_all('/#_LATT\{([^}]+)\}(\{([^}]+)\})?/', $formats, $matches);
	}else{
		preg_match_all('/#_ATT\{([^}]+)\}(\{([^}]+)\})?/', $formats, $matches);
	}
	//Now grab all the unique attributes we can use in our event.
	foreach($matches[1] as $key => $attribute) {
		if( !in_array($attribute, $attributes['names']) ){
			$attributes['names'][] = $attribute ;
			$attributes['values'][$attribute] = array();
		}
		//check if there's ddm values
		if( !empty($matches[3][$key]) ){
		    $new_values = explode('|',$matches[3][$key]);
		    if( count($new_values) > count($attributes['values'][$attribute]) ){
		    	foreach($new_values as $key => $value){
		    	    $new_values[$key] = trim($value);
		    	}
				$attributes['values'][$attribute] = apply_filters('em_get_attributes_'.$attribute, $new_values, $attribute, $matches);
		    }
		}
	}
	return apply_filters('em_get_attributes', $attributes, $matches, $lattributes);
}

/**
 * Decides whether to register a user based on a certain booking that is to be added
 * @param EM_Booking $EM_Booking 
 */
function em_booking_add_registration( $EM_Booking ){
    global $EM_Notices;
    //Does this user need to be registered first?
    $registration = true;
    if( ((!is_user_logged_in() && em_get_option('dbem_bookings_anonymous')) || EM_Bookings::is_registration_forced()) && !em_get_option('dbem_bookings_registration_disable') ){
		// Check if this is a tentative booking, meaning the booking should be made, user checks should be done, but an account isn't created until moved out of this status into an approved or pending status.
    	//find random username - less options for user, less things go wrong
    	$user_email = trim(wp_unslash($_REQUEST['user_email'])); //otherwise may fail validation
    	$username_root = explode('@', wp_kses_data($user_email));
    	$username_root = $username_rand = sanitize_user($username_root[0], true);
    	while( username_exists($username_rand) ) {
    		$username_rand = $username_root.rand(1,1000);
    	}
    	$_REQUEST['dbem_phone'] = (!empty($_REQUEST['dbem_phone'])) ? wp_kses_data($_REQUEST['dbem_phone']):''; //fix to prevent warnings
    	$_REQUEST['user_name'] = (!empty($_REQUEST['user_name'])) ? wp_kses_data($_REQUEST['user_name']):''; //fix to prevent warnings
    	$user_data = array('user_login' => $username_rand, 'user_email'=> $user_email, 'user_name'=> $_REQUEST['user_name'], 'dbem_phone'=> $_REQUEST['dbem_phone']);
    	$id = em_register_new_user($user_data);
    	if( is_numeric($id) ){
    		$EM_Person = new EM_Person($id);
    		$EM_Booking->person_id = $id;
    		$feedback = em_get_option('dbem_booking_feedback_new_user');
    		$EM_Notices->add_confirm( $feedback );
    		add_action('em_bookings_added', 'em_new_user_notification');
    	}else{
    		$registration = false;
    		if( is_object($id) && get_class($id) == 'WP_Error'){
    			/* @var $id WP_Error */
    			if( $id->get_error_code() == 'email_exists' ){
    				$EM_Notices->add_error( em_get_option('dbem_booking_feedback_email_exists') );
    			}else{
    				$EM_Notices->add_error( $id->get_error_messages() );
    			}
    		}else{
    			$EM_Notices->add_error( em_get_option('dbem_booking_feedback_reg_error') );
    		}
    	}
    }elseif( (!is_user_logged_in() || EM_Bookings::is_registration_forced()) && em_get_option('dbem_bookings_registration_disable') ){
    	//Validate name, phone and email
    	if( $EM_Booking->get_person_post() ){
	    	//Save default person to booking
	    	$EM_Booking->person_id = 0;
    	}else{
    	    $registration = false;
    	}
    }elseif( !is_user_logged_in() ){
    	$registration = false;
    	$EM_Notices->add_error( em_get_option('dbem_booking_feedback_log_in') );
    }elseif( empty($EM_Booking->person_id) ){ //user must be logged in, so we make this person the current user id
    	$EM_Booking->person_id = get_current_user_id();
    }
    return apply_filters('em_booking_add_registration_result', $registration, $EM_Booking, $EM_Notices);
}

/**
 * Copied straight from wp-login.php, only change atm is a function renaming.
 * Handles registering a new user.
 *
 * @param array associative array of user values to insert
 * @return int|WP_Error Either user's ID or error on failure.
 */
function em_register_new_user( $user_data, $tentative = false ) {
	$user_data = apply_filters('em_register_new_user_pre',$user_data);
	$errors = new WP_Error();
	if( !empty($user_data['user_name']) ){
		$name = explode(' ', $user_data['user_name']);
		$user_data['first_name'] = array_shift($name);
		$user_data['last_name'] = implode(' ',$name);
	}
	$sanitized_user_login = sanitize_user( $user_data['user_login'] );
	$user_data['user_login'] = $sanitized_user_login;
	$user_email = apply_filters( 'user_registration_email', $user_data['user_email'] );

	// Check the username
	if ( $sanitized_user_login == '' ) {
		$errors->add( 'empty_username', __( '<strong>ERROR</strong>: Please enter a username.', 'events-manager') );
	} elseif ( ! validate_username( $user_data['user_login'] ) ) {
		$errors->add( 'invalid_username', __( '<strong>ERROR</strong>: This username is invalid because it uses illegal characters. Please enter a valid username.', 'events-manager') );
		$sanitized_user_login = '';
	} elseif ( username_exists( $sanitized_user_login ) ) {
		$errors->add( 'username_exists', __( '<strong>ERROR</strong>: This username is already registered, please choose another one.', 'events-manager') );
	}

	// Check the e-mail address
	if ( $user_email == '' ) {
		$errors->add( 'empty_email', __( '<strong>ERROR</strong>: Please type your e-mail address.', 'events-manager') );
	} elseif ( ! is_email( $user_email ) ) {
		$errors->add( 'invalid_email', __( '<strong>ERROR</strong>: The email address isn&#8217;t correct.', 'events-manager') );
		$user_email = '';
	} elseif ( email_exists( $user_email ) ) {
		$errors->add( 'email_exists', __( '<strong>ERROR</strong>: This email is already registered, please choose another one.', 'events-manager') );
	}

	do_action( 'register_post', $sanitized_user_login, $user_email, $errors );

	//custom registration filter to prevent things like SI Captcha and other plugins of this kind interfering with EM
	$errors = apply_filters( 'em_registration_errors', $errors, $sanitized_user_login, $user_email, $user_data );
	
	if ( $errors->get_error_code() ) return $errors;

	
	if(empty($user_data['user_pass'])){
		$user_data['user_pass'] =  wp_generate_password( 12, false);
	}

	if( $tentative ) {
		// return user data which can be used later for registration
		return $user_data;
	}
	
	$user_id = wp_insert_user( $user_data );
	if ( is_numeric( $user_id ) && ! empty( $user_data['dbem_phone'] ) ) {
		update_user_meta( $user_id, 'dbem_phone', $user_data['dbem_phone'] );
	}
	
	if ( ! $user_id ) {
		$errors->add( 'registerfail', sprintf( __( '<strong>ERROR</strong>: Couldn&#8217;t register you... please contact the <a href="mailto:%s">webmaster</a> !', 'events-manager' ), em_get_option( 'admin_email' ) ) );
		
		return $errors;
	}
	
	update_user_option( $user_id, 'default_password_nag', true, true ); //Set up the Password change nag.
	
	global $em_temp_user_data;
	$em_temp_user_data            = $user_data; //for later useage
	$em_temp_user_data['user_id'] = $user_id;
	
	return apply_filters('em_register_new_user',$user_id);
}

/**
 * Notify the blog admin of a new user, normally via email.
 *
 * @since 2.0
 */
function em_new_user_notification() {
	global $em_temp_user_data;
	$user_id = $em_temp_user_data['user_id'];
	$plaintext_pass = $em_temp_user_data['user_pass'];

	//if you want you can disable this email from going out, and will still consider registration as successful.
	if( em_get_option('dbem_email_disable_registration') ){ return true;  }

	//Copied out of /wp-includes/pluggable.php
	$user = new WP_User($user_id);

	$user_login = wp_unslash($user->user_login);
	$user_email = wp_unslash($user->user_email);

	// The blogname option is escaped with esc_html on the way into the database in sanitize_option
	// we want to reverse this for the plain text arena of emails.
	$blogname = wp_specialchars_decode(em_get_option('blogname'), ENT_QUOTES);

	$message  = sprintf(__('New user registration on your blog %s:', 'events-manager'), $blogname) . "\r\n\r\n";
	$message .= sprintf(__('Username: %s', 'events-manager'), $user_login) . "\r\n\r\n";
	$message .= sprintf(__('E-mail: %s', 'events-manager'), $user_email) . "\r\n";
	@wp_mail(em_get_option('admin_email'), sprintf(__('[%s] New User Registration', 'events-manager'), $blogname), $message);

	if ( empty($plaintext_pass) )
		return;

	//send email to user
	$message = em_get_option('dbem_bookings_email_registration_body');
	if( em_locate_template('emails/new-user.php') ){
		ob_start();
		em_locate_template('emails/new-user.php', true);
		$message = ob_get_clean();
	}
	//for WP 4.4, regenerate password link can be used
	$set_password_url = '';
	if( function_exists('get_password_reset_key')){
	    $key = get_password_reset_key( $user );
	    if( is_wp_error($key) ){
	    	$set_password_url = __('Contact a site administrator for your password.', 'events-manager');
	    }else{
		    $set_password_url = network_site_url("wp-login.php?action=rp&key=$key&login=" . rawurlencode($user_login), 'login');
	    }
	}
    $message  = str_replace(array('%password%','%username%','%passwordurl%'), array($plaintext_pass, $user_login, $set_password_url), $message);
	global $EM_Mailer;
	return $EM_Mailer->send(em_get_option('dbem_bookings_email_registration_subject'), $message, $user_email);
}

/**
 * Transitional function to handle WP's eventual move away from the is_super_user() function 
 */
function em_wp_is_super_admin( $user_id = false ){
	$user = ( ! $user_id || $user_id == get_current_user_id() ) ? wp_get_current_user() : get_userdata( $user_id );

	if ( ! $user || ! $user->exists() ) return false;

	if ( is_multisite() ) {
		if( $user->has_cap('manage_network_options') ) return true;
	} else {
		if ( $user->has_cap('delete_users') ) return true;
	}
	return false;
}

/**
 * Returns an array of flags that are used in search forms.
 * @return array
 */
function em_get_search_form_defaults($base_args = array(), $context = 'events') {
	if (!is_array($base_args)) $base_args = array();
	$search_args = array();
	$search_args['ajax'] = EM_AJAX_SEARCH;
	$search_args['id'] = !empty($base_args['id']) ? $base_args['id'] : rand(100, getrandmax());
	$search_args['css'] = em_get_option('dbem_css_search'); // deprecated
	$search_args['search_action'] = 'search_events';
	$search_args['search_url'] = em_get_search_form_url( $context );
	$search_args['search_advanced_text'] = em_get_option('dbem_search_form_advanced_show');
	$search_args['search_text_show'] = em_get_option('dbem_search_form_advanced_show'); // deprecated
	$search_args['search_text_hide'] = em_get_option('dbem_search_form_advanced_hide'); // deprecated
	$search_args['search_button'] = em_get_option('dbem_search_form_submit');
	$search_args['saved_searches'] = em_get_option('dbem_search_form_saved_searches', true);
	$search_args['search_advanced_style'] = em_get_option('dbem_search_form_advanced_style', 'accordion'); // how to show the dropdowns in the advanced section
	$search_args['search_multiselect_style'] = $search_args['search_advanced_style'] === 'accordion' ? 'always-open' : 'multidropdown' ; // how to show the dropdowns in the advanced section
	// sorting options
	$search_args['sorting'] = em_get_option('dbem_search_form_sorting'); // is sorting enabled
	//search text
	$search_args['search'] = ''; //default search term
	$search_args['search_term'] = $search_args['search_term_main'] = em_get_option('dbem_search_form_text');
	$search_args['search_term_label'] = em_get_option('dbem_search_form_text_label'); //field label
	$search_args['search_term_advanced'] = em_get_option('dbem_search_form_text_advanced'); // show in main form?
	$search_args['search_term_label_advanced'] = em_get_option('dbem_search_form_text_label_advanced'); //field label
	//geo and units
	$search_args['geo'] = '';  //default geo search term (requires 'near' as well for it to make sense)
	$search_args['near'] = ''; //default near search params
	$search_args['search_geo'] = em_get_option('dbem_search_form_geo'); // show geo search?
	$search_args['geo_label'] = em_get_option('dbem_search_form_geo_label'); //field label
	$search_args['search_geo_advanced'] = em_get_option('dbem_search_form_geo_advanced'); // show geo search in advanced?
	$search_args['geo_label_advanced'] = em_get_option('dbem_search_form_geo_label_advanced'); // show geo search?
	$search_args['search_geo_units'] = em_get_option('dbem_search_form_geo_units'); //field label
	$search_args['geo_units_label'] = em_get_option('dbem_search_form_geo_units_label'); //field label
	$search_args['near_unit'] = em_get_option('dbem_search_form_geo_unit_default'); //default distance unit
	$search_args['near_distance'] = em_get_option('dbem_search_form_geo_distance_default'); //default distance amount
	$search_args['geo_distance_values'] = explode(',', em_get_option('dbem_search_form_geo_distance_options')); //possible distance values
	//scope
	$search_args['scope'] = array('', '', 'name' => em_get_option('dbem_events_default_scope')); //default scope term
	$search_args['search_scope'] = em_get_option('dbem_search_form_dates'); // show in main form
	$search_args['scope_label'] = em_get_option('dbem_search_form_dates_label'); //field label
	$search_args['scope_seperator'] = em_get_option('dbem_search_form_dates_separator'); //field label
	$search_args['scope_format'] = em_get_option('dbem_search_form_dates_format'); //field label
	$search_args['search_scope_advanced'] = em_get_option('dbem_search_form_dates_advanced'); // show in advanced form?
	$search_args['scope_label_advanced'] = em_get_option('dbem_search_form_dates_label_advanced'); // advanced field label
	$search_args['scope_seperator_advanced'] = em_get_option('dbem_search_form_dates_separator_advanced'); // advanced field label
	$search_args['scope_format_advanced'] = em_get_option('dbem_search_form_dates_format_advanced'); // advanced field label
	//eventful locations
	$search_args['search_eventful_main'] = true;
	$search_args['search_eventful'] = true;
	$search_args['search_eventful_locations_label'] = esc_html__('Eventful Locations?', 'events-manager');
	$search_args['search_eventful_locations_tooltip'] = esc_html__('Display only locations with upcoming events.', 'events-manager');
	//categories
	$search_args['category'] = 0; //default search term
	$search_args['search_categories'] = em_get_option('dbem_search_form_categories');
	$search_args['category_label'] = em_get_option('dbem_search_form_category_label'); //field label
	$search_args['categories_label'] = em_get_option('dbem_search_form_categories_label'); //select default
	$search_args['categories_placeholder'] = em_get_option('dbem_search_form_categories_placeholder'); // advanced search placeholder
	$search_args['categories_clear_text'] = esc_html__('Clear Selected'); // advanced search placeholder
	$search_args['categories_count_text'] = esc_html__('%d Selected'); // advanced search placeholder
	$search_args['categories_include'] = em_get_option('dbem_search_form_categories_include'); // include/exclude filters of categories to show
	$search_args['categories_exclude'] = em_get_option('dbem_search_form_categories_exclude'); // include/exclude filters of categories to hide
	// tags
	$search_args['tag'] = 0; //default search term
	$search_args['search_tags'] = em_get_option('dbem_search_form_tags');
	$search_args['tag_label'] = em_get_option('dbem_search_form_tag_label'); //field label
	$search_args['tags_label'] = em_get_option('dbem_search_form_tags_label'); //select default
	$search_args['tags_placeholder'] = em_get_option('dbem_search_form_tags_placeholder'); // advanced search placeholder
	$search_args['tags_clear_text'] = esc_html__('Clear Selected'); // advanced search placeholder
	$search_args['tags_count_text'] = esc_html__('%d Selected'); // advanced search placeholder
	$search_args['tags_include'] = em_get_option('dbem_search_form_tags_include'); // include/exclude filters of tags to show
	$search_args['tags_exclude'] = em_get_option('dbem_search_form_tags_exclude'); // include/exclude filters of tags to hide
	//countries
	$search_args['search_countries'] = em_get_option('dbem_search_form_countries');
	$search_args['country'] = $search_args['search_countries'] ? em_get_option('dbem_search_form_default_country') : ''; //default country
	$search_args['country_label'] = em_get_option('dbem_search_form_country_label'); //field label
	$search_args['countries_label'] = em_get_option('dbem_search_form_countries_label'); //select default
	//regions
	$search_args['region'] = ''; //default region
	$search_args['search_regions'] = em_get_option('dbem_search_form_regions');
	$search_args['region_label'] = em_get_option('dbem_search_form_region_label'); //field label
	//states
	$search_args['state'] = ''; //default state
	$search_args['search_states'] = em_get_option('dbem_search_form_states');
	$search_args['state_label'] = em_get_option('dbem_search_form_state_label'); //field label
	//towns
	$search_args['town'] = ''; //default state
	$search_args['search_towns'] = em_get_option('dbem_search_form_towns');
	$search_args['town_label'] = em_get_option('dbem_search_form_town_label'); //field label
	//sections to show
	$search_args['show_main'] = em_get_option('dbem_search_form_main');
	$search_args['show_advanced'] = em_get_option('dbem_search_form_advanced') && ( $search_args['search_categories'] || $search_args['search_tags'] || $search_args['search_countries'] || $search_args['search_regions'] || $search_args['search_states'] || $search_args['search_towns']);
	$search_args['advanced_mode'] = em_get_option('dbem_search_form_advanced_mode') === 'inline' ? 'inline':'modal';
	$search_args['advanced_hidden'] = $search_args['show_advanced'] && em_get_option('dbem_search_form_advanced_hidden');
	$search_args['advanced_trigger'] = !( $search_args['advanced_hidden'] && em_get_option('dbem_search_form_advanced_trigger') && $search_args['advanced_mode'] === 'inline' ) && $search_args['show_advanced'];
	
	// disable certain things based on context, can be overriden by $base_args, not necessarily recommended
	if( $context == 'locations' ){
		$location_views = em_get_location_search_views();
		$search_args['views'] = array_intersect(array_keys($location_views), em_get_option('dbem_search_form_views'));
		$search_args['view'] = em_get_option('dbem_search_form_view');
		if( empty($location_views[$search_args['view']]) ){
			$search_args['view'] = key($location_views);
		}
		$search_args['search_categories'] = false;
		$search_args['search_scope_main'] = false;
		$search_args['search_scope'] = false;
		$search_args['search_tags'] = false;
	}else{
		// default is events
		$search_args['views'] = em_get_option('dbem_search_form_views');
		$search_args['view'] = em_get_option('dbem_search_form_view');
		// disable these non-event searches
		$search_args['search_eventful_main'] = false;
		$search_args['search_eventful'] = false;
	}
	
	//merge defaults with supplied arguments
	$args = array_merge($search_args, $base_args);
	
	// forcse some settings if supplied settings require display decisions
	if( $args['show_main'] ) {
		$show_main = ! empty( $args['search_term'] ) || ! empty( $args['search_geo'] ) || ! empty( $args['search_scope'] ); //decides whether or not to show main area and collapseable advanced search options
		$args['show_main'] = $show_main;
	}
	if( !$args['show_main'] && !empty($args['show_search']) ){
		// we're not showing main but are showing the form itself, therefore we must show advanced search
		$args['advanced_mode'] = 'inline';
		$args['advanced_hidden'] = false;
	}elseif( $args['advanced_mode'] === 'modal' ){
		// modal always starts as hidden
		$args['advanced_hidden'] = true;
	}
	
	
	// sanitize views option
	$search_views = em_get_search_views();
	if( !is_array($args['views']) ) $args['views'] = explode(',', str_replace(' ', '', $args['views']));
	$args['views'] = array_intersect( $args['views'], array_keys($search_views) );
	if( empty($search_views[$args['view']]) ) $args['view'] = 'list';
	
	//add specific classes for wrapper dependent on settings
	if (empty($args['css_classes'])){
		$args['css_classes'] = array();
	}elseif( !is_array($args['css_classes']) ){
		$args['css_classes'] = explode(',', $args['css_classes']);
	}
	if (empty($args['main_classes'])){ // deprecated - legacy backcompat
		$args['main_classes'] = array();
	}elseif( !is_array($args['main_classes']) ){
		$args['main_classes'] = explode(',', $args['main_classes']);
	}
	if( !empty($args['css']) ){
		$args['main_classes'][] = 'css-search'; // deprecated
	}
	
	// legacy backwards compatible classes
	$args['main_classes'][] = 'em-search-legacy';
	if( !empty($args['search_term']) ) $args['main_classes'][] = 'has-search-term';
	if( !empty($args['search_geo']) ) $args['main_classes'][] = 'has-search-geo';
	$args['main_classes'][] = $args['show_main'] ? 'has-search-main':'no-search-main';
	$args['main_classes'][] = $args['show_advanced'] ? 'has-advanced':'no-advanced';
	$args['main_classes'][] = $args['advanced_hidden'] ? 'advanced-hidden':'advanced-visible';
	
	// new classes
	$main_search_count = 0; // number of search fields
	$args['css_classes'][] = $args['show_main'] ? 'has-search-main':'no-search-main';
	$args['css_classes'][] = !empty($args['views']) && count($args['views']) > 1 ? 'has-views':'no-views';
	$args['css_classes'][] = $args['sorting'] ? 'has-sorting':'no-sorting';
	$args['css_classes'][] = $args['show_advanced'] ? 'has-advanced':'no-advanced';
	if( $args['show_advanced'] ){
		$args['css_classes'][] = 'advanced-mode-' . $args['advanced_mode'];
		$args['css_classes'][] = $args['advanced_hidden'] ? 'advanced-hidden':'advanced-visible';
		$args['css_classes'][] = $args['advanced_trigger'] ? 'has-advanced-trigger' : 'no-advanced-trigger';
	}
	if( isset($args['show_search']) && !$args['show_search'] ){
		$args['css_classes'][] = 'is-hidden';
	}
	$args['css_classes_advanced'] = array();
	if( empty($args['advanced_hidden']) ){
		$args['css_classes_advanced'][] = ' visible';
	}
	$args['css_classes'][] = em_get_option('dbem_search_form_responsive', 'one-line');
	
	//overwrite with $_REQUEST defaults in event of a submitted search
	if( isset($_REQUEST['view_id']) ) $args['id'] = absint($_REQUEST['view_id']); // id used for element ids
	if( isset($_REQUEST['id']) ) $args['id'] = absint($_REQUEST['id']); // id used for element ids
	if( isset($_REQUEST['geo']) ) $args['geo'] = sanitize_text_field($_REQUEST['geo']);
	if( isset($_REQUEST['near']) ) $args['near'] = sanitize_text_field(wp_unslash($_REQUEST['near']));
	if( isset($_REQUEST['em_search']) ) $args['search'] = sanitize_text_field(wp_unslash($_REQUEST['em_search']));
	if( isset($_REQUEST['category']) ) {
		$args['category'] = is_array($_REQUEST['category']) ? sanitize_text_field( implode(', ', $_REQUEST['category']) ) : sanitize_text_field( $_REQUEST['category'] );
	}
	if( isset($_REQUEST['country']) ) $args['country'] = sanitize_text_field(wp_unslash($_REQUEST['country']));
	if( isset($_REQUEST['region']) ) $args['region'] = sanitize_text_field(wp_unslash($_REQUEST['region']));
	if( isset($_REQUEST['state']) ) $args['state'] = sanitize_text_field(wp_unslash($_REQUEST['state']));
	if( isset($_REQUEST['town']) ) $args['town'] = sanitize_text_field(wp_unslash($_REQUEST['town']));
	if( isset($_REQUEST['near_unit']) ) $args['near_unit'] = sanitize_text_field($_REQUEST['near_unit']);
	if( isset($_REQUEST['near_distance']) ) $args['near_distance'] = sanitize_text_field($_REQUEST['near_distance']);
	// fix scope so it's search-friendly, scopes must have a 0 and 1 key for start/end dates, and optionally an associated name
	if( !empty($args['scope']) ){
		if( !is_array($args['scope']) ){
			// convert currently supported scope into array, future conversions should be done elsewhere in another function
			if( $args['scope'] == 'future' ){
				// future consideration... but currently the commented lines would set a date on search form by default
				//$EM_DateTime = new EM_DateTime;
				//$args['scope'] = array( 0 => $EM_DateTime->format('Y-m-d'), 1 => '', 'name' => 'future', );
				$args['scope'] = array('', '', 'name' => 'future'); //default scope term
			}else{
				$args['scope'] = array('', '', 'name' => 'all'); //default scope term
			}
		}elseif( empty($args['scope']['name']) ){
			$scope_array = array($args['scope'][0]);
			if( !empty($args['scope'][1]) ) $scope_array[1] = $args['scope'][1];
			$args['scope']['name'] = implode(',', $scope_array);
		}
	}else{
		if( !empty($_REQUEST['scope']) && !is_array($_REQUEST['scope'])){
			$args['scope'] = explode(',',sanitize_text_field($_REQUEST['scope'])); //convert scope to an array in event of pagination
		}elseif( !empty($_REQUEST['scope']) ){
			$args['scope'] = array(); // reset and populate sanitized
			foreach( $_REQUEST['scope'] as $k => $v ){
				$args['scope'][absint($k)] = sanitize_text_field($v);
			}
		}
	}
	
	// deal with no-ajax situations such as custom placeholders
	if( empty($args['ajax']) ) {
		$args['css_classes'][] = 'no-ajax';
		// get URL without pno
		$url = add_query_arg( ['pno' => null] );
		$url_parts = explode('?', $url);
		// remove any of these search args from url params
		if ( !empty($url_parts[1]) ) {
			$query_arr = [];
			parse_str( $url_parts[1], $query_arr );
			unset( $query_arr['em_search'] ); // do this manually due to interchanging with 'search' param for compatabaility
			$url = $url_parts[0] . '?' . build_query( array_diff_assoc( $query_arr, $args) );
		}
		// rebuild URL for output
		$args['search_url'] = $url;
	}
	
	return apply_filters('em_get_search_form_defaults', $args, $base_args, $context);
}

/**
 * Adds hidden inputs to the search form in the event certain fields are hidden but also required (e.g. a category but no category search enabled)
 * @param $args
 *
 * @since 6.4
 * @return void
 */
function em_search_form_footer( $args ){
	$show_advanced = !empty($args['show_advanced']);
	$i = array();
	// search terms on main bar and advanced main section
	if( empty($args['search_term']) && $show_advanced && empty($args['search_term_advanced']) && !empty($args['search']) ){
		$i['search'] = $args['search'];
	};
	if( empty($args['search_geo']) && $show_advanced && empty($args['search_geo_advanced']) ){
		$i['geo'] = !empty($args['geo']) ? $args['geo'] : null;
		$i['near'] = !empty($args['near']) ? $args['near'] : null;
		$i['near_distance'] = !empty($args['near_distance']) ? $args['near_distance'] : null;
		$i['near_unit'] = !empty($args['near_unit']) ? $args['near_unit'] : null;
	}
	if( empty($args['search_scope']) && $show_advanced && empty($args['search_scope_advanced']) && !empty($args['scope']) ){
		$scope = array();
		if( is_array($args['scope']) ){
			if( !empty($args['scope'][0]) ){
				$scope[] = $args['scope'][0];
			}
			if( !empty($args['scope'][1]) ){
				if( empty($scope) ) {
					$scope[] = '';
				}
				$scope[] = $args['scope'][1];
			}
			if( empty($scope) && !empty($args['scope']['name']) ){
				$scope = $args['scope']['name'];
			}
		}else{
			$scope = $args['scope'];
		}
		$i['scope'] = $scope;
	}
	// location fields
	$address_fields = array('countries' => 'country', 'regions' => 'region', 'states' => 'state', 'towns' => 'town');
	foreach( $address_fields as $search => $field )
	if( ($show_advanced || empty($args['search_'.$search])) && !empty($args[$field]) ){
		$i[$field] = $args[$field];
	}
	// taxonomies
	if( (!$show_advanced || empty($args['search_categories'])) && !empty($args['category']) ){
		$i['category'] = $args['category'];
	}
	if( (!$show_advanced || empty($args['search_tags'])) && !empty($args['tag']) ){
		$i['tag'] = $args['tag'];
	}
	// put it all together, output hidden inputs, escaped etc.
	foreach( $i as $name => $value ){
		if( $value !== null ) {
			if( is_array($value) ){
				$value = implode(',', $value);
			}
			echo '<input type="hidden" name="' . $name . '" value="' . esc_attr( $value ) . '">';
		}
	}
}
add_action('em_search_form_footer', 'em_search_form_footer', 10, 1);

function em_get_search_views(){
	$search_views = array(
		'list' => array(
			'name' => __('List', 'events-manager'),
		),
		'list-grouped' => array(
			'name' => __('Grouped Lists', 'events-manager'),
		),
		'grid' => array(
			'name' => __('Grid', 'events-manager'),
		),
		'map' => array(
			'name' => __('Map', 'events-manager'),
		),
		'calendar' => array(
			'name' => __('Calendar', 'events-manager'),
		),
	);
	return apply_filters('em_get_search_views', $search_views);
}

function em_output_events_view( $args, $view = null ){
	if( $view === null ){
		$view = empty($args['view']) ? em_get_option('dbem_search_form_view') : $args['view'];
	}
    do_action('em_output_events_view_header', $args, $view);
	if( empty($args['id']) ) $args['id'] = rand(100, getrandmax()); // prevent warnings
	
	if ( !empty($args['has_search']) ) {
		// get the default args for this list of events, so it's defaulted into the search form
		$default_args = EM_Events::get_default_search( $args );
		$search_args = em_get_search_form_defaults($default_args);
		$search_args['has_view'] = true;
		if ( $view ) {
			$search_args['view'] = $view;
		}
		if ( isset($args['views']) ) {
			$search_views = em_get_search_views();
			if( !is_array($args['views']) ) {
				$args['views'] = explode(',', str_replace(' ', '', $args['views']));
			}
			$search_args['views'] = array_intersect( $args['views'], array_keys($search_views) );
			if( empty($search_views[$args['view']]) ) $search_args['views'] = 'list';
		}
		em_locate_template('templates/events-search.php', true, array('args'=>$search_args));
		if ( empty($args['ajax']) ) {
			$args = array_merge( $args, $default_args, $search_args );
		}
	}
	
	switch( $view ){
		case 'list-grouped':
			if( empty($args['date_format']) ){
				$args['date_format'] = em_get_option('dbem_event_list_groupby_format');
			}
			em_locate_template('templates/events-list-grouped.php', true, array('args'=>$args)); //if successful, this template overrides the settings and defaults, including search
			break;
		case 'list':
			em_locate_template('templates/events-list.php', true, array('args'=>$args)); //if successful, this template overrides the settings and defaults, including search
			break;
		case 'grid':
			// add default grid formats
			if( empty($args['format']) ){
				$args['format'] = em_get_option( 'dbem_event_grid_item_format' );
			}
			if( empty($args['format_header']) ){
				$args['format_header'] = em_get_option('dbem_event_grid_item_format_header');
			}
			if( empty($args['format_footer']) ){
				$args['format_footer'] = em_get_option('dbem_event_grid_item_format_footer');
			}
			em_locate_template('templates/events-grid.php', true, array('args'=>$args)); //if successful, this template overrides the settings and defaults, including search
			break;
		case 'map':
			$args['width'] = !empty($args['width']) ? $args['width'] : '100%';
			$args['height'] = !empty($args['height']) ? $args['height'] : 0;
			$args['em_ajax'] = true;
			$args['query'] = 'GlobalEventsMapData';
			$args = em_parse_map_args( $args );
			em_locate_template('templates/map-global.php',true, array('args'=>$args, 'map_json_style' => !empty($args['map_style']) ? $args['map_style'] : ''));
			break;
		case 'calendar':
			$args['has_search'] = false; // prevent view and search getting output again
			echo EM_Calendar::output( $args );
			break;
		default:
			if( has_action('em_events_search_view_'.$view) ){
				do_action('em_events_search_view_'.$view, $args);
			}else{
				// last resort we're showing a list
				em_locate_template('templates/events-list.php', true, array('args'=>$args)); //if successful, this template overrides the settings and defaults, including search
			}
			break;
	}
	do_action('em_output_events_view_footer', $args, $view);
}

function em_parse_map_args( $args ) {
	//get dimensions with px or % added in
	$width = (isset($args['width'])) ? $args['width']:em_get_option('dbem_map_default_width','400px');
	$width = preg_match('/(px)|%/', $width) ? $width:$width.'px';
	if( $width == 0 || $width == '0px' || $width == '0%' ) $width = 0;
	$height = (isset($args['height'])) ? $args['height']:em_get_option('dbem_map_default_height','300px');
	$height = preg_match('/(px)|%/', $height) ? $height:$height.'px';
	if( $height == 0 || $height == '0px' || $height == '0%' ) $height = 0;
	$args['width'] = $width;
	$args['height'] = $height;
	//assign random number for element id reference
	if( empty($args['id']) ) $args['id'] = rand(100, getrandmax());
	//add JSON style to map
	if( !empty($args['map_style']) ){
		$style= wp_kses_data(base64_decode($args['map_style']));
		$style_json= json_decode($style);
		if( is_array($style_json) || is_object($style_json) ){
			$args['map_style'] = preg_replace('/[\r\n\t\s]/', '', $style);
		}else{
			$args['map_style'] = '';
		}
	}
	return $args;
}

function em_get_location_search_views(){
	$search_views = array(
		'list' => array(
			'name' => __('List', 'events-manager'),
		),
		'grid' => array(
			'name' => __('Grid', 'events-manager'),
		),
		'map' => array(
			'name' => __('Map', 'events-manager'),
		),
	);
	return apply_filters('em_get_location_search_views', $search_views);
}

function em_output_locations_view( $args, $view = null ){
	if( $view === null ){
		$view = empty($args['view']) ? em_get_option('dbem_search_form_view') : $args['view'];
		$location_views = em_get_location_search_views();
		if( empty($location_views[$view]) ){
			$args['view'] = key($location_views);
			$view = $args['view'];
		}
	}
	
	// add search form if needed
	if ( !empty($args['has_search']) ) {
		// get the default args for this list of events, so it's defaulted into the search form
		$default_args = EM_Locations::get_default_search( $args );
		$search_args = em_get_search_form_defaults( $default_args, 'locations' );
		$search_args['has_view'] = true;
		$search_args['view'] = $view;
		if ( isset( $args['views'] ) ) {
			$search_args['views'] = $args['views'];
		}
		em_locate_template( 'templates/locations-search.php', true, array( 'args' => $search_args ) );
		if ( empty( $args['ajax'] ) ) {
			$args = array_merge( $args, $default_args, $search_args );
		}
	}
	
	$args['limit'] = !empty($args['limit']) ? $args['limit'] : em_get_option('dbem_locations_default_limit');
	switch( $view ){
		case 'list':
			em_locate_template('templates/locations-list.php', true, array('args'=>$args)); //if successful, this template overrides the settings and defaults, including search
			break;
		case 'grid':
			// add default grid formats
			if( empty($args['format']) ){
				$args['format'] = em_get_option( 'dbem_location_grid_item_format' );
			}
			if( empty($args['format_header']) ){
				$args['format_header'] = em_get_option('dbem_location_grid_format_header');
			}
			if( empty($args['format_footer']) ){
				$args['format_footer'] = em_get_option('dbem_location_grid_format_footer');
			}
			em_locate_template('templates/locations-grid.php', true, array('args'=>$args)); //if successful, this template overrides the settings and defaults, including search
			break;
		case 'map':
			$args['width'] = !empty($args['width']) ? $args['width'] : '100%';
			$args['height'] = !empty($args['height']) ? $args['height'] : 0;
			$args['em_ajax'] = true;
			$args['query'] = 'GlobalMapData';
			$args = em_parse_map_args( $args );
			em_locate_template('templates/map-global.php',true, array('args'=>$args, 'map_json_style' => !empty($args['map_style']) ? $args['map_style'] : ''));
			break;
		default:
			if( has_action('em_locations_search_view_'.$view) ){
				do_action('em_locations_search_view_'.$view, $args);
			}else{
				// last resort we're showing a list
				em_locate_template('templates/locations-list.php', true, array('args'=>$args)); //if successful, this template overrides the settings and defaults, including search
			}
			break;
	}
}

/*
 * UI Helpers
 * previously dbem_UI_helpers.php functions
 */

function em_option_items($array, $saved_value) {
	$output = "";
	foreach($array as $key => $item) {
		$selected ='';
		if ($key == $saved_value)
			$selected = "selected='selected'";
		$output .= "<option value='".esc_attr($key)."' $selected >".esc_html($item)."</option>\n";

	}
	echo $output;
}

function em_checkbox_items($name, $array, $saved_values, $horizontal = true) {
	$output = "";
	foreach($array as $key => $item) {
		$checked = "";
		if (in_array($key, $saved_values)) $checked = "checked";
		$output .= "<label><input type='checkbox' name='".esc_attr($name)."' value='".esc_attr($key)."' $checked > ".esc_html($item)."</label>&nbsp; ";
		if(!$horizontal)
			$output .= "<br/>\n";
	}
	echo $output;

}

function em_options_input_get_value( $name, $default = '' ){
	if( preg_match('/^([^\[]+)\[([^\]]+)?\]$/', $name, $matches) ){
		$value = EM_Options::get($matches[2], $default, $matches[1]);
	}elseif( preg_match('/^([^\[]+)\[([^\]]+)\]\[([^\]]+)?\]$/', $name, $matches) ){
		$value_array = EM_Options::get($matches[2], array(), $matches[1]);
		$value = isset($value_array[$matches[3]]) ? $value_array[$matches[3]]:$default;
	}else{
		$value = get_option($name, $default);
	}
	return $value;
}

function em_booking_timeslots_get_display_options( $EM_Event = null ) {
	$get_option = function( $option, $default ) use ( $EM_Event ) {
		return $EM_Event instanceof EM_Event ? $EM_Event->get_option( $option, $default ) : em_get_option( $option, $default );
	};
	$options = array(
		'show_unavailable' => (bool) $get_option( 'dbem_bookings_timeslots_show_unavailable', 0 ),
		'show_spaces' => (bool) $get_option( 'dbem_bookings_timeslots_show_spaces', 1 ),
		'show_dates' => (bool) $get_option( 'dbem_bookings_timeslots_show_dates', 1 ),
		'show_upcoming' => (bool) $get_option( 'dbem_bookings_timeslots_show_upcoming', 1 ),
		'upcoming_limit' => absint( $get_option( 'dbem_bookings_timeslots_upcoming_limit', 3 ) ),
		'date_format' => trim( (string) $get_option( 'dbem_bookings_timeslots_date_format', '' ) ),
		'time_format' => trim( (string) $get_option( 'dbem_bookings_timeslots_time_format', '' ) ),
	);
	return apply_filters( 'em_booking_timeslots_display_options', $options, $EM_Event );
}

function em_options_input_text($title, $name, $description ='', $default='', $resetable = false) {
    $translate = EM_ML::is_option_translatable($name);
	$value = em_options_input_get_value( $name, $default );
	$archetype_options = em_options_get_archetype_options($name);
	?>
	<tr valign="top" id='<?php echo esc_attr($name);?>_row'>
		<th scope="row">
			<?php echo esc_html($title); ?>
			<?php if( $resetable ): ?>
				<a href="#" class="em-option-resettable em-tooltip" aria-label="<?php esc_attr_e('Reset to default value?', 'events-manager'); ?>" data-name="<?php echo esc_attr($name) ?>" data-nonce="<?php echo wp_create_nonce('option-default-'.$name); ?>">
					<span class="dashicons dashicons-undo"></span>
				</a>
			<?php endif; ?>
		</th>
	    <td>
			<div class="em-default-option">
				<input name="<?php echo esc_attr($name) ?>" type="text" id="<?php echo esc_attr($name) ?>" value="<?php echo esc_attr($value, ENT_QUOTES); ?>" size="45" />
		        <?php if( $translate ): ?><span class="em-translatable dashicons dashicons-admin-site"></span><?php endif; ?>
		        <br />
				<?php
					if( $translate ){
						echo '<div class="em-ml-options"><table class="form-table">';
						foreach( EM_ML::get_langs() as $lang => $lang_name ){
							if( $lang != EM_ML::$wplang ){
								?>
								<tr>
									<td class="lang"><?php echo $lang_name; ?></td>
									<td class="lang-text"><input name="<?php echo esc_attr($name) ?>_ml[<?php echo $lang ?>]" type="text" id="<?php echo esc_attr($name.'_'.$lang) ?>" style="width: 100%" value="<?php echo esc_attr(EM_ML::get_option($name, $lang, false), ENT_QUOTES); ?>" size="45" /></td>
								</tr>
								<?php
							}else{
								$default_lang = '<input name="'.esc_attr($name).'_ml['.EM_ML::$wplang.']" type="hidden" id="'. esc_attr($name.'_'. EM_ML::$wplang) .'" value="'. esc_attr($value, ENT_QUOTES).'" />';
							}
						}
						echo '</table>';
						echo '<em>'.__('If translations are left blank, the default value will be used.','events-manager').'</em>';
						echo $default_lang.'</div>';
					}
				?>
			</div>
			<?php if( !empty($archetype_options['archetypes']) ): ?>
				<div class="em-archetype-options">
					<?php foreach ( $archetype_options['archetypes'] as $type => $atts ): ?>
						<div class="em-archetype-option" data-archetype="<?php echo $type ?>">
							<input name="<?php echo esc_attr($atts['name']) ?>" type="text" id="<?php echo esc_attr($name) ?>_<?php echo $type ?>" value="<?php echo esc_attr($atts['value'], ENT_QUOTES);?>" placeholder="<?php esc_html_e('leave blank for default.','events-manager'); ?>...">
							<?php if( $translate ): ?><span class="em-translatable dashicons dashicons-admin-site"></span><?php endif; ?>
							<span class="em-archetype-option-default em-icon em-icon-enter em-tooltip" aria-label="<?php esc_html_e('Copy default value', 'events-manager'); ?>">
								<template>
									<?php echo esc_html($value, ENT_QUOTES); ?>
								</template>
							</span>
							<br />
							<?php
							if( $translate ){
								$option_name = str_replace($name, $name . '_ml', $atts['name']);
								echo '<div class="em-ml-options"><table class="form-table">';
								foreach( EM_ML::get_langs() as $lang => $lang_name ){
									$value = $atts['ml'][ $lang ] ?? '';
									if( $lang != EM_ML::$wplang ){
										?>
										<tr>
											<td class="lang"><?php echo $lang_name; ?></td>
											<td class="lang-text"><input name="<?php echo esc_attr($option_name) ?>[<?php echo $lang ?>]" type="text" id="<?php echo esc_attr($name.'_ml_'.$lang.'_'. $type) ?>" style="width: 100%" value="<?php echo esc_attr($value, ENT_QUOTES); ?>" size="45" placeholder="<?php esc_html_e('leave blank for default.','events-manager'); ?>..."></td>
										</tr>
										<?php
									}else{
										$default_lang = '<input name="'.esc_attr($name).'_ml['.EM_ML::$wplang.']" type="hidden" id="'. esc_attr($name.'_'. EM_ML::$wplang) .'" value="'. esc_attr($value, ENT_QUOTES).'" />';
									}
								}
								echo '</table>';
								echo '<em>'.__('If left blank, the default value will be used.','events-manager').'</em>';
								echo $default_lang.'</div>';
							}
							?>
						</div>
					<?php endforeach; ?>
				</div>
			<?php endif; ?>
			<em><?php echo $description; ?></em>
		</td>
	</tr>
	<?php
}

function em_options_input_password($title, $name, $description ='') {
	$value = em_options_input_get_value( $name );
	?>
	<tr valign="top" id='<?php echo esc_attr($name);?>_row'>
		<th scope="row"><?php echo esc_html($title); ?></th>
	    <td>
			<input name="<?php echo esc_attr($name) ?>" type="password" id="<?php echo esc_attr($title) ?>" style="width: 95%" value="<?php echo esc_attr($value); ?>" size="45" /><br />
			<em><?php echo $description; ?></em>
		</td>
	</tr>
	<?php
}

function em_options_textarea($title, $name, $description ='', $resetable = false) {
	$translate = EM_ML::is_option_translatable($name);
	$archetype_options = em_options_get_archetype_options($name);
	?>
	<tr valign="top" id='<?php echo esc_attr($name);?>_row'>
		<th scope="row">
			<?php echo esc_html($title); ?>
			<?php if( $resetable ): ?>
			<a href="#" class="em-option-resettable em-tooltip" aria-label="<?php esc_attr_e('Reset to default value?', 'events-manager'); ?>" data-name="<?php echo esc_attr($name) ?>" data-nonce="<?php echo wp_create_nonce('option-default-'.$name); ?>">
				<span class="dashicons dashicons-undo"></span>
			</a>
			<?php endif; ?>
		</th>
		<td>
			<div class="em-default-option">
				<textarea name="<?php echo esc_attr($name) ?>" id="<?php echo esc_attr($name) ?>" rows="6"><?php echo esc_attr(get_option($name), ENT_QUOTES);?></textarea>
		        <?php if( $translate ): ?><span class="em-translatable  dashicons dashicons-admin-site"></span><?php endif; ?>
		        <br>
				<?php
					if( $translate ){
						echo '<div class="em-ml-options"><table class="form-table">';
						foreach( EM_ML::get_langs() as $lang => $lang_name ){
							if( $lang != EM_ML::$wplang ){
								?>
								<tr>
									<td class="lang"><?php echo $lang_name; ?></td>
									<td class="lang-text"><textarea name="<?php echo esc_attr($name) ?>_ml[<?php echo $lang ?>]" id="<?php echo esc_attr($name.'_'.$lang) ?>" style="width: 100%" size="45"><?php echo esc_attr(EM_ML::get_option($name, $lang, false), ENT_QUOTES); ?></textarea></td>
								</tr>
								<?php
							}else{
								$default_lang = '<input name="'.esc_attr($name).'_ml['.EM_ML::$wplang.']" type="hidden" id="'. esc_attr($name.'_'. EM_ML::$wplang) .'" value="'. esc_attr(get_option($name), ENT_QUOTES).'" />';
							}
						}
						echo '</table>';
						echo '<em>'.__('If left blank, the default value will be used.','events-manager').'</em>';
						echo $default_lang.'</div>';
					}
				?>
			</div>
			<?php if( !empty($archetype_options['archetypes']) ): ?>
			<div class="em-archetype-options">
				<?php foreach ( $archetype_options['archetypes'] as $type => $atts ): ?>
					<div class="em-archetype-option" data-archetype="<?php echo $type ?>">
						<textarea  name="<?php echo esc_attr($atts['name']) ?>" id="<?php echo esc_attr($name) ?>_<?php echo $type ?>" rows="6" placeholder="<?php esc_html_e('leave blank for default.','events-manager'); ?>..."><?php echo esc_attr($atts['value'], ENT_QUOTES);?></textarea>
						<?php if( $translate ): ?><span class="em-translatable  dashicons dashicons-admin-site"></span><?php endif; ?>
						<span class="em-archetype-option-default em-icon em-icon-enter em-tooltip" aria-label="<?php esc_html_e('Copy default value', 'events-manager'); ?>">
							<template>
								<?php echo esc_attr( get_option($name), ENT_QUOTES ); ?>
							</template>
						</span>
						<br>
						<?php
						if( $translate ){
							$option_name = str_replace($name, $name . '_ml', $atts['name']);
							echo '<div class="em-ml-options"><table class="form-table">';
							foreach( EM_ML::get_langs() as $lang => $lang_name ){
								$value = $atts['ml'][ $lang ] ?? '';
								if( $lang != EM_ML::$wplang ){
									?>
									<tr>
										<td class="lang"><?php echo $lang_name; ?></td>
										<td class="lang-text"><textarea name="<?php echo esc_attr($option_name) ?>[<?php echo $lang ?>]" id="<?php echo esc_attr($name.'_ml_'.$lang.'_'. $type) ?>" style="width: 100%" size="45" placeholder="<?php esc_html_e('Leave blank for default archetype setting.','events-manager'); ?>"><?php echo esc_attr($value, ENT_QUOTES); ?></textarea></td>
									</tr>
									<?php
								}else{
									$default_lang = '<input name="em_archetype_options_ml['.$type.']['.esc_attr($name).']['.EM_ML::$wplang.']" type="hidden" id="'. esc_attr($name.'_ml_'.$lang.'_'. $type) .'" value="'. esc_attr($value, ENT_QUOTES).'" />';
								}
							}
							echo '</table>';
							echo '<em>'.__('If left blank, the default value will be used.','events-manager').'</em>';
							echo $default_lang.'</div>';
						}
						?>
					</div>
				<?php endforeach; ?>
			</div>
			<?php endif; ?>
			<em><?php echo $description; ?></em>
		</td>
	</tr>
	<?php
}

function em_options_radio($name, $options, $title='') {
		$option = get_option($name);
		$archetype_options = em_options_get_archetype_options($name);
		?>
	   	<tr valign="top" id='<?php echo esc_attr($name);?>_row'>
	   		<?php if( !empty($title) ): ?>
	   		<th scope="row"><?php  echo esc_html($title); ?></th>
	   		<td>
	   		<?php else: ?>
	   		<td colspan="2">
	   		<?php endif; ?>
	   			<div class="em-default-option">
	                <?php foreach($options as $value => $text): ?>
		                <tr>
		                    <td><input id="<?php echo esc_attr($name) ?>_<?php echo esc_attr($value); ?>" name="<?php echo esc_attr($name) ?>" type="radio" value="<?php echo esc_attr($value); ?>" <?php if($option == $value) echo "checked"; ?> /></td>
			                <td><?php echo $text ?></td>
		                </tr>
					<?php endforeach; ?>
			    </div>
			    <?php if( !empty($archetype_options['archetypes']) ): ?>
				    <div class="em-archetype-options">
					    <?php foreach ( $archetype_options['archetypes'] as $type => $atts ): ?>
						    <tbody class="em-archetype-option" data-archetype="<?php echo $type ?>">
							    <tr>
								    <td>
									    <input id="<?php echo esc_attr($name) ?>_default_<?php echo $type ?>" name="em_archetype_options[<?php echo $type ?>][<?php echo esc_attr($name) ?>]" type="radio" value="" <?php if( $undefined ) echo "checked"; ?>>
								    </td>
								    <td><?php esc_html_e('Default', 'events-manager'); ?> (<?php echo esc_html( $options[$option] ?? current($options) ) ?>)</td>
							    </tr>
								<?php foreach($options as $value => $text): ?>
							        <tr>
									    <?php
									    $undefined = $atts['value'] === '' || $atts['value'] === null;
									    ?>
									    <td>
										    <input id="<?php echo esc_attr($name) ?>_<?php echo esc_attr($value); ?>_<?php echo $type ?>" name="em_archetype_options[<?php echo $type ?>][<?php echo esc_attr($name) ?>]" type="radio" value="<?php echo esc_attr($value); ?>" <?php if($atts['value'] == $value) echo "checked"; ?> >
									    </td>
									    <td><?php echo $text ?></td>
							        </tr>
								<?php endforeach; ?>
						    </tbody>
					    <?php endforeach; ?>
				    </div>
			    <?php endif; ?>
			</td>
	   	</tr>
<?php
}

function em_options_get_archetype_options( $option_name ) {
	$return = [ 'classes' => [], 'archetypes' => [] ];
	if ( Archetypes::$types ) {  // skip this if no archetypes exist
		if ( preg_match('/^([^\[]+)(\[([a-z_A-Z0-9\-]+)\])?$/', $option_name, $matches ) && Archetypes_Admin::is_overrideable($option_name) ) {
			$translate = EM_ML::is_option_translatable($option_name);
			$return['classes'] = ['has-archetype-option'];
			$return['archetypes'] = [];
			foreach ( Archetypes::$types as $type => $archetype ) {
				if ( Archetypes_Admin::is_overrideable($option_name, $type) ) {
					$return['classes'][] = 'has-archetype-option-'.$type;
					$options = Archetypes::get_options();
					if ( count($matches) > 2 ) {
						$return['archetypes'][ $type ] = [
							'value' => $options[$type][$matches[1]][$matches[3]] ?? null,
							'name' => "em_archetype_options[$type][{$matches[1]}][{$matches[3]}]",
						];
					} else {
						$return['archetypes'][ $type ] = [
							'value' => $options[$type][$matches[1]] ?? null,
							'name' => "em_archetype_options[$type][{$matches[1]}]",
						];
					}
					if ( $translate ) {
						$translated = Archetypes::get_option( $matches[1] . '_ml', $type);
						$return['archetypes'][ $type ]['ml'] = [
							'values' => $translated[$option_name] ?? [],
						];
					}
				}
			}
		}
	}
	return $return;
}

function em_options_radio_binary($title, $name, $description='', $option_names = '', $trigger='', $untrigger=false) {
	if( empty($option_names) ) $option_names = array(0 => __('No','events-manager'), 1 => __('Yes','events-manager'));
	if( preg_match('/^(.+)\[([a-z_A-Z0-9\-]+)\]$/', $name, $match ) ){
		// deal with an option stored as an array
		$name_data = get_option($match[1]);
		$value = !empty($name_data[$match[2]]);
		$id = $match[1].'-'.$match[2];
		$class = $match[1];
	}else{
		$id = $name;
		$class = $name;
		if( substr($name, 0, 7) == 'dbem_ms' ){
			$value = get_site_option($name);
		}else{
			$value = get_option($name);
		}
	}
	if( $untrigger ){
		$trigger_att = ($trigger) ? ' data-trigger="'.esc_attr($trigger).'" class="em-untrigger"':'';
	}else{
		$trigger_att = ($trigger) ? ' data-trigger="'.esc_attr($trigger).'" class="em-trigger"':'';
	}
	// handle archetype overrides, not applicable for array stored options (yet)
	$archetype_options = em_options_get_archetype_options($name);
	$class = implode(' ', $archetype_options['classes']) . ' ' . $class;
	?>
   	<tr valign="top" class="<?php echo $class ?>_row em-option" id='<?php echo $id;?>_row'>
		<th scope="row"><?php echo esc_html($title); ?></th>
		<td class="<?php echo $class; ?>">
			<div class="em-default-option">
				<?php echo $option_names[1]; ?> <input id="<?php echo esc_attr($id) ?>_yes" name="<?php echo esc_attr($name) ?>" type="radio" value="1" <?php if($value) echo "checked"; echo $trigger_att; ?> >&nbsp;&nbsp;&nbsp;
				<?php echo $option_names[0]; ?> <input id="<?php echo esc_attr($id) ?>_no" name="<?php echo esc_attr($name) ?>" type="radio" value="0" <?php if(!$value) echo "checked"; echo $trigger_att; ?> >
			</div>
			<?php if( !empty($archetype_options['archetypes']) ): ?>
				<div class="em-archetype-options">
					<?php foreach ( $archetype_options['archetypes'] as $type => $opts ): ?>
						<div class="em-archetype-option" id='<?php echo $id;?>_row_<?php echo $type ?>' data-archetype="<?php echo $type ?>">
							<?php
							$undefined = $opts['value'] === '' || $opts['value'] === null;
							$default = $value ? 1 : 0
							?>
							<?php echo $option_names[1]; ?> <input id="<?php echo esc_attr($id) ?>_yes_<?php echo $type ?>" name="<?php echo esc_attr($opts['name']) ?>" type="radio" value="1" <?php if($opts['value']) echo "checked"; echo $trigger_att; ?> >&nbsp;&nbsp;&nbsp;
							<?php echo $option_names[0]; ?> <input id="<?php echo esc_attr($id) ?>_no_<?php echo $type ?>" name="<?php echo esc_attr($opts['name']) ?>" type="radio" value="0" <?php if( !$opts['value'] && !$undefined ) echo "checked"; echo $trigger_att; ?> >&nbsp;&nbsp;&nbsp;
							<?php esc_html_e('Default', 'events-manager'); ?> (<?php echo $option_names[$default]; ?>) <input id="<?php echo esc_attr($id) ?>_default_<?php echo $type ?>" name="<?php echo esc_attr($opts['name']) ?>" type="radio" value="" <?php if( $undefined ) echo "checked"; echo $trigger_att; ?> >
						</div>
					<?php endforeach; ?>
				</div>
			<?php endif; ?>
			<br/><em><?php echo $description; ?></em>
		</td>
	</tr>
	<?php
}

function em_options_select($title, $name, $list, $description='', $default='', $triggers = array(), $options = array() ) {
	$option_value = get_option($name, $default);
	$archetype_options = em_options_get_archetype_options($name);
	if( $name == 'dbem_events_page' && !is_object(get_page($option_value)) ){
		$option_value = 0; //Special value
	}
	$select_classes = array();
	if( !empty($triggers) ) $select_classes[] = 'em-trigger';
	if( !empty($options['selectize']) ) $select_classes[] = 'em-selectize';
	if( !empty($options['multiple']) ){
		$name .= '[]';
		if( !is_array($option_value) ){
			$option_value = array($option_value);
		}
	}
	?>
   	<tr valign="top" id='<?php echo esc_attr($name);?>_row'>
   		<th scope="row"><?php echo esc_html($title); ?></th>
   		<td>
		    <div class="em-default-option">
				<select name="<?php echo esc_attr($name); ?>" class="<?php echo implode(' ', $select_classes); ?>" <?php if( !empty($options['multiple']) ) echo 'multiple'; ?>>
					<?php
					$default = [];
					foreach($list as $key => $value) {
						if( is_array($value) ){
							?><optgroup label="<?php echo $key; ?>"><?php
							foreach( $value as $key_group => $value_group ){
								$trigger = !empty( $triggers[$key_group] ) ? $triggers[$key_group] : '';
								$selected = ("$key_group" == $option_value) ? "selected='selected' " : '';
								if ( $selected ) {
									$default[] = $value_group;
								}
								?>
				                <option value='<?php echo esc_attr($key_group) ?>' <?php echo $selected; ?> data-trigger="<?php echo esc_attr($trigger); ?>"><?php echo esc_html($value_group); ?></option>
								<?php
							}
							?></optgroup><?php
						}else{
							$trigger = !empty( $triggers[$key] ) ? $triggers[$key] : '';
							if( !empty($options['multiple']) ) {
								$selected = in_array($key, $option_value) ? "selected='selected' ":'';
							} else {
								$selected = ("$key" == $option_value) ? "selected='selected' " : '';
							}
							if ( $selected ) {
								$default[] = $value;
							}
							?>
			                <option value='<?php echo esc_attr($key) ?>' <?php echo $selected; ?> data-trigger="<?php echo esc_attr($trigger); ?>"><?php echo esc_html($value); ?></option>
							<?php
						}
					}
					?>
				</select>
		    </div>
		    <?php if( !empty($archetype_options['archetypes']) ): ?>
			    <div class="em-archetype-options">
				    <?php foreach ( $archetype_options['archetypes'] as $type => $opts ): ?>
				    <div class="em-archetype-option" id='<?php echo $name;?>_row_<?php echo $type ?>' data-archetype="<?php echo $type ?>">
					    <select name="<?php echo esc_attr($opts['name']); ?>" class="<?php echo implode(' ', $select_classes); ?>" <?php if( !empty($options['multiple']) ) echo 'multiple'; ?>>
						    <option value="" <?php echo $opts['value'] === '' || $opts['value'] === null ? 'selected':''; ?>><?php esc_html_e('Default', 'events-manager'); ?> (<?php echo esc_html( implode(', ', $default) ); ?>)</option>
						    <?php
						    foreach($list as $key => $value) {
							    if( is_array($value) ){
								    ?><optgroup label="<?php echo $key; ?>"><?php
								    foreach( $value as $key_group => $value_group ){
									    $trigger = !empty( $triggers[$key_group] ) ? $triggers[$key_group] : '';
									    ?>
									    <option value='<?php echo esc_attr($key_group) ?>' <?php echo ("$key_group" == $opts['value']) ? "selected='selected' " : ''; ?> data-trigger="<?php echo esc_attr($trigger); ?>"><?php echo esc_html($value_group); ?></option>
									    <?php
								    }
								    ?></optgroup><?php
							    }else{
								    $trigger = !empty( $triggers[$key] ) ? $triggers[$key] : '';
								    if( !empty($options['multiple']) ) {
									    $selected = in_array($key, $opts['value']) ? "selected='selected' ":'';
								    } else {
									    $selected = ("$key" == $opts['value']) ? "selected='selected' " : '';
								    }
								    ?>
								    <option value='<?php echo esc_attr($key) ?>' <?php echo $selected; ?> data-trigger="<?php echo esc_attr($trigger); ?>"><?php echo esc_html($value); ?></option>
								    <?php
							    }
						    }
						    ?>
					    </select>
				    </div>
				    <?php endforeach; ?>
			    </div>
		    <?php endif; ?>
			<p><em><?php echo $description; ?></em></p>
		</td>
   	</tr>
	<?php
}

/**
 * Generates a dropdown using wp_dropdown_pages for use in settings tables,
 * with archetype override support (for Event Archetypes UI, etc).
 *
 * @param string $title Row label/title.
 * @param string $name Name attribute for the dropdown/select.
 * @param array $dropdown_args Arguments passed to wp_dropdown_pages (except name is forced to $name).
 * @param string $description Optionally show below select.
 * @param mixed $default Default option value.
 */
function em_options_select_page( $title, $name, $dropdown_args = array(), $description = '', $default = '' ) {
	$option_value = get_option($name, $default);
	$archetype_options = function_exists('em_options_get_archetype_options') ? em_options_get_archetype_options($name) : array();
	// Main select, default option value (else fallback)
	if( $name == 'dbem_events_page' && !is_object(get_page($option_value)) ){
		$option_value = 0; //Special value
	}
	// Setup dropdown args
	$args = array_merge( [
			'name' => $name,
			'selected' => $option_value,
			'show_option_none' => !empty($dropdown_args['none']) ? $dropdown_args['none'] === true ? sprintf(esc_html__('[No %s Page]', 'events-manager'), Archetypes::$event['label'] ) : $dropdown_args['none'] : '',
		], $dropdown_args );
	?>
	<tr valign="top" id="<?php echo esc_attr($name); ?>_row">
		<th scope="row"><?php echo esc_html($title); ?></th>
		<td>
			<div class="em-default-option">
				<?php wp_dropdown_pages($args); ?>
			</div>
			<?php if( !empty($archetype_options['archetypes']) ): ?>
				<div class="em-archetype-options">
					<?php foreach ( $archetype_options['archetypes'] as $type => $opts ): ?>
						<div class="em-archetype-option" id="<?php echo esc_attr($name); ?>_row_<?php echo esc_attr($type); ?>" data-archetype="<?php echo esc_attr($type); ?>">
							<?php
							// convert values for default/none:
							if ( $opts['value'] === '0' || $opts['value'] === '' ) {
								$opts['value'] = $opts['value'] === '0' ? '' : '-1';
							}
							$archetype_args = array_merge( $args, array(
								'name' => $opts['name'],
								'selected'=> $opts['value'],
								'show_option_none' => !empty($args['none']) ? sprintf(esc_html__('[No %s Page]', 'events-manager'), Archetypes::$types[$type]['label'] ) : '',
								'show_option_no_change' => ( !isset($args['default']) || $args['default'] !== false ) ?  esc_html__('Default', 'events-manager') : '',
							));
							$archetype_args['echo'] = false;
							$html = wp_dropdown_pages($archetype_args);
							str_replace('value=""', 'value="0"', $html); // no page specifically chosen
							str_replace('value="-1"', 'value=""', $html); // no change = default
							echo $html;
							?>
						</div>
					<?php endforeach; ?>
				</div>
			<?php endif; ?>
			<?php
			if( !empty($description) ){
				echo '<br/><em>' . $description . '</em>';
			}
			?>
		</td>
	</tr>
	<?php
}


// got from http://davidwalsh.name/php-email-encode-prevent-spam
function em_ascii_encode($e){
	$output = '';
    for ($i = 0; $i < strlen($e); $i++) { $output .= '&#'.ord($e[$i]).';'; }
    return $output;
}

/**
 * Handy shortcut similar to constant() which checks if a constant exists and returns the value but does not trigger an error if not defined.
 * @param $constant
 *
 * @return mixed|null
 */
function em_constant( $constant ){
	if( defined($constant) ){
		return constant($constant);
	}
	return null;
}

if( !function_exists( 'is_main_query' ) ){
	/**
	 * Substitutes the original function in 3.3 onwards, for backwards compatability (only created if not previously defined)
	 * @return bool
	 */
	function is_main_query(){ global $wp_query; return $wp_query->in_the_loop == true; }
}

/**
 * deprecated
 * @return string
 */
function em_get_date_format(){
	return em_get_option('dbem_date_format');
}

function em_get_datepicker_format() {
	$format = em_get_option('dbem_datepicker_format');
    $map = ['d'=>'d','D'=>'D','l'=>'l','j'=>'j','J'=>'jS','w'=>'w','W'=>'W',
            'F'=>'F','m'=>'m','n'=>'n','M'=>'M','y'=>'y','Y'=>'Y','H'=>'H',
            'h'=>'h','G'=>'g','i'=>'i','S'=>'s','s'=>'s','K'=>'A','U'=>'U','Z'=>'c'];
    return preg_replace_callback('/./', function($m) use ($map) {
        return isset($map[$m[0]]) ? $map[$m[0]] : '\\'.$m[0];
    }, $format);
}


/**
 * Backwards compatibility fuction to trigger the deprecated em_bookings_form_footer action if the newly introduced action em_booking_form_buttons_header is fired.
 * This will ensure any previous code using this action will still trigger appropriately, because we can assume the template was replaced with a new one containing em_booking_form_buttons_header and not em_booking_form_footer
 * @param $EM_Event
 * @return void
 */
function em_bookings_form_footer_backcompat( $EM_Event ){
	/**
	 * Do not use, this is for backwards compatibility only
	 * @deprecated
	 */
	do_action('em_booking_form_footer', $EM_Event);
}
add_action('em_booking_form_buttons_header', 'em_bookings_form_footer_backcompat', 10, 1);

/**
 * @param EM_Event $EM_Event
 * @return void
 */
function em_bookings_form_footer_polyfill( $EM_Event ) {
	if( !doing_action('em_booking_form_buttons_header') ){
		// we're in backcompat mode for a template, so let's output the intent just in case
		echo $EM_Event->get_bookings()->get_intent_default()->output_intent_html();
	}
}
add_action('em_booking_form_footer', 'em_bookings_form_footer_polyfill');

/**
 * Backwards compatibility for functionality added in EM Pro 3.1 which was moved into EM, ensuring versions of EM Pro removing this code will not duplicate headers.
 * If you still want this header to be handled via EM Pro (in the event you override booking form templates and use an outdated Pro version), remove the action below at the plugins_loaded action like so:
 * add_action('plugins_loaded', function(){ remove_action('em_pro_loaded', 'em_bookings_form_confirm_header_backcompat'); });
 * @return void
 */
function em_bookings_form_confirm_header_backcompat(){
	remove_action('em_checkout_form_footer',  array('EM_Booking_Form', 'booking_form_section_confirm_mb'), 1);
	remove_action('em_booking_form_before_confirm', array('EM_Booking_Form', 'booking_form_section_confirm'), 1);
	remove_action('em_booking_form_footer', array('EM_Booking_Form', 'booking_form_section_confirm'), 1);
	add_action('em_booking_form_before_buttons', function( $EM_Event ){
		do_action('em_booking_form_footer_before_buttons', $EM_Event);
	});
	add_action('em_booking_form_before_confirm', function( $EM_Event ){
		do_action('em_booking_form_before_confirmation', $EM_Event);
	});
	add_action('em_booking_form_after_confirm', function( $EM_Event ){
		do_action('em_booking_form_after_confirmation', $EM_Event);
	});
}
add_action('em_pro_loaded', 'em_bookings_form_confirm_header_backcompat');
?>
