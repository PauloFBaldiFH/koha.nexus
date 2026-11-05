<?php
//TODO add a shortcode to link for a specific event, e.g. [event id=x]text[/event]
/**
 * Cleans shortcode arguments, ensuring that the format is safe for use in shortcodes.
 * @param $args
 * @param $format
 *
 * @return array
 * @since 6.4.7.4
 */
function em_clean_shortcode_args( $args, $format = '' ) {
	$supplied_args = $args;
	$args['ajax'] = isset($args['ajax']) ? $args['ajax']:(!defined('EM_AJAX') || EM_AJAX );
	if( !get_option('dbem_shortcodes_allow_format_params') ) {
		unset($args['format'], $args['header_format'], $args['format_header'], $args['format_footer']);
	}
	if( empty($format) && !empty($args['format']) ) {
		// If supplied via $args in shortcode context, we cannot guarantee the format HTML is safe as it can be invoked by any user. Therefore, we must wp_kses it.
		// We strongly suggest users to add formats within the shortcode such as [event]format[/event] to avoid this, and header/footer HTML surrounds the shortcode.
		global $allowedposttags;
		if( get_option('dbem_shortcodes_decode_params') ) {
			$args['format'] = html_entity_decode($args['format']); //shorcode doesn't accept html
		}
		$args['format'] = wp_kses($args['format'], $allowedposttags); //shorcode doesn't accept html
	} else {
		// format is empty (default) or defined within shortcode
		$args['format'] = $format;
		if( get_option('dbem_shortcodes_decode_content') ) {
			// If supplied via $args in shortcode context, we cannot guarantee the entity-encoded format HTML is safe as it can be invoked by any user. Therefore, we must wp_kses it after decoding it.
			// We strongly suggest users to add formats within the shortcode such as [event]format[/event] to avoid this, and header/footer HTML surrounds the shortcode.
			global $allowedposttags;
			$args['format'] = html_entity_decode($args['format']); //shorcode doesn't accept html
			if( get_option('dbem_shortcodes_kses_decoded_content') ) {
				$args['format'] = wp_kses( $args['format'], $allowedposttags ); //shorcode doesn't accept html
			}
		}
	}
	foreach ( ['format_header', 'format_footer', 'header_format'] as $arg ) {
		if ( !empty( $args[$arg] ) ) {
			global $allowedposttags;
			if( get_option('dbem_shortcodes_decode_params') ) {
				$args[$arg] = html_entity_decode($args[$arg]); //shorcode doesn't accept html
			}
			$args[$arg] = wp_kses($args[$arg], $allowedposttags); //shorcode doesn't accept html
		}
	}
	return apply_filters('em_clean_shortcode_args', $args, $format, $supplied_args);
}

/**
 * Returns the html of an events calendar with events that match given query attributes. Accepts any event query attribute.
 * @param array $args
 * @return string
 */
function em_get_calendar_shortcode( $args, $format='' ) {
	$args = em_clean_shortcode_args( (array) $args, $format );
	return EM_Calendar::output( $args );
}
add_shortcode('events_calendar', 'em_get_calendar_shortcode');

function em_get_gcal_shortcode($args){
	$img_url = is_ssl() ? 'https://www.google.com/calendar/images/ext/gc_button6.gif':'http://www.google.com/calendar/images/ext/gc_button6.gif';
	$args = shortcode_atts(array('img'=>$img_url, 'button'=>6), $args);
	if( $img_url == $args['img'] && $args['button'] != 6 ){
		$img_url = str_replace('gc_button6.gif', 'gc_button'.$args['button'].'.gif', $img_url);
	}
	$url = '<a href="http://www.google.com/calendar/render?cid='.urlencode(trailingslashit(get_home_url()).'events.ics').'" target="_blank"><img src="'.esc_url($img_url).'" alt="0" border="0"></a>';
	return $url;
}
add_shortcode('events_gcal', 'em_get_gcal_shortcode');

/**
 * Generates a map of locations that match given query attributes. Accepts any location query attributes. 
 * @param array $args
 * @return string
 */
function em_get_locations_map_shortcode($args){
	$args = em_clean_shortcode_args( (array) $args );
	$args = em_parse_map_args($args);
	$args['view'] = !empty($args['view']) ? $args['view'] : 'map';
	ob_start();
	em_output_locations_view( $args, 'map' );
	return ob_get_clean();
}
add_shortcode('locations_map', 'em_get_locations_map_shortcode');
add_shortcode('locations-map', 'em_get_locations_map_shortcode'); //deprecate this... confusing for WordPress 


/**
 * Generates a map of locations that match given query attributes. Accepts any location query attributes.
 * @param array $args
 * @return string
 */
function em_get_events_map_shortcode($args){
	$args = em_clean_shortcode_args( (array) $args );
	$args = em_parse_map_args($args);
	$args['view'] = !empty($args['view']) ? $args['view'] : 'map';
	ob_start();
	em_output_events_view( $args, 'map' );
	return ob_get_clean();
}
add_shortcode('events_map', 'em_get_events_map_shortcode');

/**
 * Shows a list of events according to given specifications. Accepts any event query attribute.
 * @param array $args
 * @param string $format
 * @return string
 */
function em_get_events_list_shortcode($args, $format='') {
	$args = em_clean_shortcode_args( (array) $args, $format );
	$args['limit'] = isset($args['limit']) ? $args['limit'] : em_get_option('dbem_events_default_limit', $args['event_archetype'] ?? null);
	$args['view'] = !empty($args['view']) ? $args['view'] : 'list';
	// if AJAX is being used with formats, we can't accept arbitrary HTML via AJAX calls for security reasons, they must be generated server-side
	if( !empty($args['format']) || !empty($args['format_header']) || !empty($args['format_footer']) ){
		// manually add page number and remove ajax
		$args['ajax'] = false;
		$pno = ( !empty($args['pagination']) && !empty($_GET['pno']) && is_numeric($_GET['pno']) )? $_GET['pno'] : 1;
		$args['page'] = ( !empty($args['pagination']) && !empty($args['page']) && is_numeric($args['page']) )? $args['page'] : $pno;
	}
	ob_start();
	em_output_events_view( $args );
	return ob_get_clean();
}
add_shortcode ( 'events_list', 'em_get_events_list_shortcode' );

/**
 * Creates a grouped list of events by year, month, week or day
 * @since 4.213
 * @param array $args
 * @param string $format
 * @return string
 */
function em_get_events_list_grouped_shortcode($args = array(), $format = ''){
	$args['view'] = 'list-grouped';
	return em_get_events_list_shortcode( $args, $format );
}
add_shortcode ( 'events_list_grouped', 'em_get_events_list_grouped_shortcode' );

/**
 * Shows a list of events according to given specifications. Accepts any event query attribute.
 * @param array $args
 * @return string
 */
function em_get_event_shortcode($args, $format='') {
    global $post;
	$return = '';
	$args = em_clean_shortcode_args( (array) $args, $format );
	if( !empty($args['event']) && is_numeric($args['event']) ){
		$EM_Event = em_get_event($args['event']);
	}elseif( !empty($args['post_id']) && is_numeric($args['post_id']) ){
		$EM_Event = em_get_event($args['post_id'], 'post_id');
	}
	// an explicit ID lets any author embed another user's event, so it must be one this visitor could read on its own permalink
	if( !empty($EM_Event) && !$EM_Event->is_viewable() ){
		return '';
	}
	//no specific event or post id supplied, check globals
	if( !empty($EM_Event) ){
	    $return = ( !empty($args['format']) ) ? $EM_Event->output($args['format']) : $EM_Event->output_single();
	}elseif( $post->post_type == EM_POST_TYPE_EVENT ){
	    $EM_Event = em_get_event($post->ID, 'post_id');
	    $return = ( !empty($args['format']) ) ? $EM_Event->output($args['format']) : $EM_Event->output_single();
	}
    return $return;
}
add_shortcode ( 'event', 'em_get_event_shortcode' );

/**
 * Returns list of locations according to given specifications. Accepts any location query attribute.
 */
function em_get_locations_list_shortcode( $args, $format='' ) {
	$args = em_clean_shortcode_args( (array) $args, $format );
	$args['view'] = !empty($args['view']) ? $args['view'] : 'list';
	$args['limit'] = isset($args['limit']) ? $args['limit'] : em_get_option('dbem_locations_default_limit', $args['event_archetype'] ?? null);
	if( !empty($args['format']) || !empty($args['format_header']) || !empty($args['format_footer']) ){
		// manually add page number and remove ajax
		$args['ajax'] = false;
		$pno = ( !empty($args['pagination']) && !empty($_GET['pno']) && is_numeric($_GET['pno']) )? $_GET['pno'] : 1;
		$args['page'] = ( !empty($args['pagination']) && !empty($args['page']) && is_numeric($args['page']) )? $args['page'] : $pno;
	}
	ob_start();
	em_output_locations_view( $args );
	return ob_get_clean();
}
add_shortcode('locations_list', 'em_get_locations_list_shortcode');

/**
 * Shows a single location according to given specifications. Accepts any event query attribute.
 * @param array $args
 * @return string
 */
function em_get_location_shortcode($args, $format='') {
	$args = em_clean_shortcode_args( (array) $args, $format );
	if( !empty($args['location']) && is_numeric($args['location']) ){
		$EM_Location = em_get_location($args['location']);
	}elseif( !empty($args['post_id']) && is_numeric($args['post_id']) ){
		$EM_Location = em_get_location($args['post_id'],'post_id');
	}
	if( !empty($EM_Location) ){
		// as with [event], an explicit ID must point at a location this visitor could read on its own page
		if( !$EM_Location->is_viewable() || $EM_Location->password_required() ) return '';
		return ( !empty($args['format']) ) ? $EM_Location->output($args['format']) : $EM_Location->output_single();
	}
	//no specific location or post id supplied, check globals
	global $EM_Location, $post;
	if( !empty($EM_Location) ){
		return ( !empty($args['format']) ) ? $EM_Location->output($args['format']) : $EM_Location->output_single();
	}elseif( $post->post_type == EM_POST_TYPE_LOCATION ){
		$EM_Location = em_get_location($post->ID,'post_id');
		return ( !empty($args['format']) ) ? $EM_Location->output($args['format']) : $EM_Location->output_single();
	}
}
add_shortcode ( 'location', 'em_get_location_shortcode' );

function em_get_categories_shortcode($args, $format=''){
	$args = em_clean_shortcode_args( (array) $args, $format );
	$args['orderby'] = !empty($args['orderby']) ? $args['orderby'] : em_get_option('dbem_categories_default_orderby', $args['event_archetype'] ?? null);
	$args['order'] = !empty($args['order']) ? $args['order'] : em_get_option('dbem_categories_default_order', $args['event_archetype'] ?? null);
	$args['pagination'] = isset($args['pagination']) ? $args['pagination'] : !isset($args['limit']);
	$args['limit'] = isset($args['limit']) ? $args['limit'] : em_get_option('dbem_categories_default_limit', $args['event_archetype'] ?? null);
	if( empty($args['id']) ) $args['id'] = rand(100, getrandmax());
	if( empty($args['format']) && empty($args['format_header']) && empty($args['format_footer']) ){
		ob_start();
		if( !empty($args['ajax']) ){ echo '<div class="em-search-ajax">'; } //open AJAX wrapper
		em_locate_template('templates/categories-list.php', true, array('args'=>$args));
		if( !empty($args['ajax']) ) echo "</div>"; //close AJAX wrapper
		$return = ob_get_clean();
	}else{
		$args['ajax'] = false;
		$args['page'] = ( !empty($args['pagination']) && !empty($args['page']) && is_numeric($args['page']) )? $args['page'] : 1;
		$args['page'] = ( !empty($args['pagination']) && !empty($_GET['pno']) && is_numeric($_GET['pno']) )? $_GET['pno'] : $args['page'];
		$return = EM_Categories::output($args);
	}
	return $return;
}
add_shortcode ( 'categories_list', 'em_get_categories_shortcode' );

/**
 * Shows a single location according to given specifications. Accepts any event query attribute.
 * @param array $args
 * @return string
 */
function em_get_event_category_shortcode($args, $format='') {
	$args = em_clean_shortcode_args( (array) $args, $format );
	if( !empty($args['category']) && is_numeric($args['category']) ){
		$EM_Category = em_get_category($args['category']);
		return ( !empty($args['format']) ) ? $EM_Category->output($args['format']) : $EM_Category->output_single();
	}elseif( !empty($args['post_id']) && is_numeric($args['post_id']) ){
		// deprecated, backwards compatibility
		$EM_Category = em_get_category($args['post_id']);
		return ( !empty($args['format']) ) ? $EM_Category->output($args['format']) : $EM_Category->output_single();
	}
}
add_shortcode ( 'event_category', 'em_get_event_category_shortcode' );


function em_get_tags_shortcode($args, $format=''){
	$args = em_clean_shortcode_args( (array) $args, $format );
	$args['orderby'] = !empty($args['orderby']) ? $args['orderby'] : em_get_option('dbem_tags_default_orderby', $args['event_archetype'] ?? null);
	$args['order'] = !empty($args['order']) ? $args['order'] : em_get_option('dbem_tags_default_order', $args['event_archetype'] ?? null);
	$args['pagination'] = isset($args['pagination']) ? $args['pagination'] : !isset($args['limit']);
	$args['limit'] = isset($args['limit']) ? $args['limit'] : em_get_option('dbem_tags_default_limit', $args['event_archetype'] ?? null);
	if( empty($args['id']) ) $args['id'] = rand(100, getrandmax());
	if( empty($args['format']) && empty($args['format_header']) && empty($args['format_footer']) ){
		ob_start();
		if( !empty($args['ajax']) ){ echo '<div class="em-search-ajax">'; } //open AJAX wrapper
		em_locate_template('templates/tags-list.php', true, array('args'=>$args));
		if( !empty($args['ajax']) ) echo "</div>"; //close AJAX wrapper
		$return = ob_get_clean();
	}else{
		$args['ajax'] = false;
		$args['page'] = ( !empty($args['pagination']) && !empty($args['page']) && is_numeric($args['page']) )? $args['page'] : 1;
		$args['page'] = ( !empty($args['pagination']) && !empty($_GET['pno']) && is_numeric($_GET['pno']) )? $_GET['pno'] : $args['page'];
		$return = EM_Tags::output($args);
	}
	return $return;
}
add_shortcode ( 'tags_list', 'em_get_tags_shortcode' );

/**
 * Shows a single location according to given specifications. Accepts any event query attribute.
 * @param array $args
 * @return string
 */
function em_get_event_tag_shortcode($args, $format='') {
	$args = em_clean_shortcode_args( (array) $args, $format );
	if( !empty($args['tag']) && is_numeric($args['tag']) ){
		$EM_Tag = em_get_tag($args['tag']);
		return ( !empty($args['format']) ) ? $EM_Tag->output($args['format']) : $EM_Tag->output_single();
	}elseif( !empty($args['post_id']) && is_numeric($args['post_id']) ){
		// deprecated, backwards compatibility only
		$EM_Tag = em_get_tag($args['post_id']);
		return ( !empty($args['format']) ) ? $EM_Tag->output($args['format']) : $EM_Tag->output_single();
	}
}
add_shortcode ( 'event_tag', 'em_get_event_tag_shortcode' );

/**
 * DO NOT DOCUMENT! This should be replaced with shortcodes events-link and events_uri
 * @param array $args
 * @return string
 */
function em_get_events_page_shortcode($args) {
	$args = shortcode_atts ( array ('justurl' => 0, 'text' => '' ), $args );
	if($args['justurl']){
		return EM_URI;
	}else{
		return em_get_link($args['text']);
	}
}
add_shortcode ( 'events_page', 'em_get_events_page_shortcode' );

/**
 * Shortcode for a link to events page. Default will show events page title in link text, if you use [events_link]text[/events_link] 'text' will be the link text
 * @param array $args
 * @param string $text
 * @return string
 */
function em_get_link_shortcode($args, $text='') {
	return em_get_link($text);
}
add_shortcode ( 'events_link', 'em_get_link_shortcode');

/**
 * Returns the uri of the events page only
 * @return string
 */
function em_get_url_shortcode(){
	return EM_URI;
}
add_shortcode ( 'events_url', 'em_get_url_shortcode');

/**
 * CHANGE DOCUMENTATION! if you just want the url you should use shortcode events_rss_uri
 * @param array $args
 * @return string
 */
function em_get_rss_link_shortcode($args) {
	$args = shortcode_atts ( array ('justurl' => 0, 'text' => 'RSS' ), $args );
	if($args['justurl']){
		return EM_RSS_URI;
	}else{
		return em_get_rss_link($args['text']);
	}
}
add_shortcode ( 'events_rss_link', 'em_get_rss_link_shortcode' );

/**
 * Returns the uri of the events rss page only, takes no attributes.
 * @return string
 */
function em_get_rss_url_shortcode(){
	return EM_RSS_URI;
}
add_shortcode ( 'events_rss_url', 'em_get_rss_url_shortcode');

/**
 * Creates a form to submit events with
 * @param array $args
 * @return string
 */
function em_get_event_form_shortcode( $args = array() ){
	return em_get_event_form( (array) $args );
}
add_shortcode ( 'event_form', 'em_get_event_form_shortcode');

/**
 * Creates a form to search events with
 * @param array $args
 * @return string
 */
function em_get_event_search_form_shortcode( $args = array() ){
	return em_get_event_search_form( (array) $args );
}
add_shortcode ( 'event_search_form', 'em_get_event_search_form_shortcode');
add_shortcode ( 'events_search', 'em_get_event_search_form_shortcode');

/**
 * Creates a form to search locations with
 * @param array $args
 * @return string
 */
function em_get_location_search_form_shortcode( $args = array() ){
	return em_get_location_search_form( (array) $args );
}
add_shortcode ( 'location_search_form', 'em_get_location_search_form_shortcode');
add_shortcode ( 'locations_search', 'em_get_location_search_form_shortcode');

/**
 * Shows the list of bookings the user has made. Whilst maybe useful to some, the preferred way is to create a page and assign it as a my bookings page in your settings > pages > other pages section
 * @param array $args
 * @return string
 */
function em_get_my_bookings_shortcode(){
	return em_get_my_bookings();
}
add_shortcode ( 'my_bookings', 'em_get_my_bookings_shortcode');