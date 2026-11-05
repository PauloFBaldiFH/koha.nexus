<?php
// TODO make person details more secure and integrate with WP user data 
class EM_Person extends WP_User{

    public $custom_user_fields = array();

	function __construct( $person_id = false, $username = '', $blog_id='' ){
		if( is_array($person_id) ){
			if( array_key_exists('person_id',$person_id) ){
				$person_id = $person_id['person_id'];
			}elseif ( array_key_exists('user_id',$person_id) ){
				$person_id = $person_id['user_id'];
			}else{
				$person_id = $person_id['ID'];
			}
		}elseif( is_object($person_id) && get_class($person_id) == 'WP_User'){
			$person_id = $person_id->ID; //create new object if passed a wp_user
		}
		if($username){
			parent::__construct($person_id, $username);
		}elseif( is_numeric($person_id) && $person_id == 0 ){
			$this->data = new stdClass();
			$this->ID = 0;
			$this->display_name = 'Anonymous User';
			$this->user_email = 'anonymous@'.preg_replace('/https?:\/\//', '', get_site_url());
		}else{
			parent::__construct($person_id);
		}
		$this->phone = get_metadata('user', $this->ID, 'dbem_phone', true); //extra field for EM
		$this->phone_validity = true; // by default no validation, until EM\Phone
		if( $this->phone && EM\Phone::is_enabled() ) {
			// parse number ot make sure it's valid
			$number = EM\Phone::parse( $this->phone );
			if( $number ) {
				$this->phone = $number;
				$this->phone_validity = true;
			} else {
				$this->phone_validity = false;
			}
		}
		do_action('em_person',$this, $person_id, $username);
	}
	
	/**
	 * //TODO : refactor this to handle no-user bookings too
	 * @param $ids_only
	 * @param $status
	 *
	 * @return mixed|null
	 */
	function get_bookings($ids_only = false, $status= false){
		global $wpdb;
		$status_condition = $blog_condition = '';
		if( is_multisite() ){
			if( !is_main_site() ){
				//not the main blog, force single blog search
				$blog_condition = "AND e.blog_id=".get_current_blog_id();
			}elseif(is_main_site() && !em_get_option('dbem_ms_global_events')){
				$blog_condition = "AND (e.blog_id=".get_current_blog_id().' OR e.blog_id IS NULL)';
			}
		}
		if( is_numeric($status) ){
			$status_condition = " AND booking_status=$status";
		}elseif( EM_Object::array_is_numeric($status) ){
			$status_condition = " AND booking_status IN (".implode(',', $status).")";
		}
		$EM_Booking = em_get_booking(); //empty booking for fields
		// Whitelist the ORDER BY column and direction
		$orderby_options = apply_filters('em_settings_bookings_default_orderby_ddm', array( 'event_name' => '', 'event_start_date' => '', 'booking_date' => '' ));
		$orderby = em_get_option('dbem_bookings_default_orderby', 'event_start_date');
		if( !array_key_exists($orderby, $orderby_options) ) $orderby = 'event_start_date';
		$order = strtoupper( em_get_option('dbem_bookings_default_order', 'ASC') ) === 'DESC' ? 'DESC' : 'ASC';
		$results = $wpdb->get_results("SELECT b.".implode(', b.', array_keys($EM_Booking->fields))." FROM ".EM_BOOKINGS_TABLE." b, ".EM_EVENTS_TABLE." e WHERE e.event_id=b.event_id AND person_id={$this->ID} {$blog_condition} {$status_condition} ORDER BY ".$orderby." ".$order, ARRAY_A);
		$bookings = array();
		if($ids_only){
			foreach($results as $booking_data){
				$bookings[] = $booking_data['booking_id'];
			}
			return apply_filters('em_person_get_bookings', $bookings, $this);
		}else{
			foreach($results as $booking_data){
				$bookings[] = em_get_booking($booking_data);
			}
			return apply_filters('em_person_get_bookings', new EM_Bookings($bookings), $this);
		}
	}

	/**
	 * Scopes a set of EM_Bookings search arguments to this person's bookings that the current user is allowed to manage.
	 *
	 * The page gate and the bookings table AJAX re-query both scope through this, so what the page shows cannot drift from what its pagination shows.
	 *
	 * @param array $args EM_Bookings::get() search arguments to scope.
	 * @return array
	 */
	public function get_manageable_bookings_args( $args = array() ){
		$args['person'] = $this->ID;
		$args['owner'] = current_user_can('manage_others_bookings') ? false : 'me';
		return $args;
	}

	/**
	 * Whether the current user is allowed to manage any of this person's bookings.
	 *
	 * @return bool
	 */
	public function can_manage_bookings(){
		if( current_user_can('manage_others_bookings') ) return true;
		if( !current_user_can('manage_bookings') ) return false;
		if( EM_Bookings::count( $this->get_manageable_bookings_args( array('scope' => 'all') ) ) > 0 ) return true;
		// an event managed through em_event_can_manage rather than owned, a BuddyPress group admin for one, is invisible to the owner-scoped query; a booking whose event row has been deleted is excluded because EM_Object reads a missing id as ownership
		foreach( $this->get_bookings() as $EM_Booking ){
			if( $EM_Booking->get_event()->event_id && $EM_Booking->can_manage('manage_bookings','manage_others_bookings') ) return true;
		}
		return false;
	}

	/**
	 * @return EM_Events
	 */
	function get_events(){
		global $wpdb;
		$events = array();
		foreach( $this->get_bookings()->get_bookings() as $EM_Booking ){
			$events[$EM_Booking->event_id] = $EM_Booking->get_event();
		}
		return apply_filters('em_person_get_events', $events);
	}
	
	function get_bookings_url(){
		if( em_get_option('dbem_edit_bookings_page') && (!is_admin() || !empty($_REQUEST['is_public'])) ){
			$my_bookings_page = get_permalink(em_get_option('dbem_edit_bookings_page'));
			$bookings_link = em_add_get_params($my_bookings_page, array('person_id'=>$this->ID, 'event_id'=>null, 'ticket_id'=>null, 'booking_id'=>null), false);
		}else{
			$bookings_link = EM_ADMIN_URL. "&page=events-manager-bookings&person_id=".$this->ID;
		}
		return apply_filters('em_person_get_bookings_url', $bookings_link, $this);
	}
	
	function display_summary(){
		ob_start();
		?>
		<table class="em-form-fields">
			<tr>
				<td><?php echo get_avatar($this->ID); ?></td>
				<td style="padding-left:10px; vertical-align: top;">
					<table>
						<?php if( $this->ID === 0 ): ?>
						<tr><th><?php _e('Name','events-manager'); ?> : </th><th><?php echo $this->get_name(); ?></th></tr>
						<?php else: ?>
						<tr><th><?php _e('Name','events-manager'); ?> : </th><th><a href="<?php echo $this->get_bookings_url(); ?>"><?php echo $this->get_name(); ?></a></th></tr>
						<?php endif; ?>
						<tr><th><?php _e('Email','events-manager'); ?> : </th><td><?php echo $this->user_email; ?></td></tr>
						<tr>
							<th><?php _e('Phone','events-manager'); ?> : </th>
							<td>
								<?php
									if( !$this->phone_validity ) {
										echo '<span class="em-icon em-icon-warning em-tooltip" aria-label="'. esc_attr__('Invalid Number', 'events-manager') .'"></span>';
									}
									echo esc_html($this->phone);
								?>
							</td>
						</tr>
						<?php do_action('em_person_display_summary_bottom', $this); ?>
					</table>
				</td>
			</tr>
		</table>
		<?php
		return apply_filters('em_person_display_summary', ob_get_clean(), $this);
	}

	function get_summary(){
	    $summary = array(
		    'user_name' => array('name' => __('Name','events-manager'), 'value' => $this->get_name()),
		    'user_email' => array('name' => __('Email','events-manager'), 'value' => $this->user_email),
		    'dbem_phone' => array('name' => __('Phone','events-manager'), 'value' => $this->phone),
        );
	    $summary = array_merge( $summary, $this->custom_user_fields );
	    return apply_filters('em_person_get_summary', $summary, $this);
    }

	function get_name(){
		$full_name = $this->first_name  . " " . $this->last_name ;
		$full_name = wp_kses_data(trim($full_name));
		$name = !empty($full_name) ? $full_name : $this->display_name;
		return apply_filters('em_person_get_name', $name, $this);
	}
	
	function to_api(){
		$person = array(
			'id' => $this->ID, // maybe hide this depending on permissions
			'name' => $this->get_name(),
			'name_first' => $this->first_name,
			'name_last' => $this->last_name,
			'email' => $this->user_email,
			'phone' => $this->phone,
			'guest' => $this->ID <= 0, // whether person is registered or not
		);
		$person = array_merge( $person, $this->custom_user_fields );
		return apply_filters('em_person_to_api', $person);
	}
}
?>
