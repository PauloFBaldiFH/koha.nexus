<?php
use EM\List_Table;

/**
 * A lot less todo here... suggestions welcome!
 * TODO: Add tax-excempt columns for ticket/attendee/booking prices
 * TODO: Add tax-excempt checkbox in settings (maybe one or another for tickets/attendees/booking prices above)
 * TODO: When changing views, the context like [Attendee] prefix should be removed for attendees view, and conflicting higher-level columns should have an asterisk with tooltip, to reduce col widths with prefixes
 */

//Builds a table of bookings, still work in progress...
class EM_Bookings_Table extends EM\List_Table {
	public static $cols_allowed_html = array('user_login' => 1, 'user_name' => 1, 'event_name' => 1, 'actions' => 1, 'ticket_name' => 0, 'ticket_description' => 0, 'ticket_price' => 0, 'ticket_total' => 0, 'ticket_spaces' => 0, 'ticket_booking_spaces' => 0, 'ticket_id' => 0);
	public static $has_filters = true;
	public static $filter_vars = [
		'search' => [
			'param' => 'em_search',
			'default' => '',
		],
		'scope' => [ 'default' => 'all' ],
		'status' => [
			'default' => 'confirmed',
			'array_key' => 'statuses'
		],
		'archetype' => [ 'default' => '' ],
	];
	
	public $cols = array('user_name','event_name', 'event_date', 'booking_spaces','booking_status','booking_price');
	public $cols_users_template = array();
	public $cols_events_template = array();
	public $cols_bookings_template = array();
	public $cols_tickets_template = array();
	public $cols_attendees_template = array();
	public $cols_payments_template = array();
	public $checkbox_id = 'booking_id';
	/**
	 * Used in areas where hook names or options are dynamically obtained from parent functions.
	 * @var string
	 */
	public static $basename = 'em_bookings_table';
	/**
	 * Supplied to em_template_classes() in HTML wrappers.
	 * @var string
	 */
	public static $template_component_name = 'bookings-table';
	public static $form_class = 'bookings-filter';
	/**
	 * Overriden to export action name to be compatible with potential extensions circumventing the export feature.
	 * @var string
	 */
	public static $export_action = 'export_bookings_csv';
	/**
	 * Used for creating class names in HTML and a unique ID base prefix.
	 * @var string
	 */
	public $id = 'em-bookings-table';
	public $orderby = 'booking_date';
	/**
	 * Index key used for looking up status information we're filtering in the booking table
	 * @var string
	 */
	public $string = 'needs-attention';
	/**
	 * Associative array of status information.
	 *
	 * * key - status index value
	 * * value - associative array containing keys
	 * ** label - the label for use in filter forms
	 * ** search - array or integer status numbers to search
	 *
	 * @var array
	 */
	public $statuses = array();
	public $show_tickets = false;
	public $show_attendees = false;
	/**
	 * @var EM_Ticket
	 */
	public $ticket;
	public $person;
	public $event;
	public $item_type;
	
	public $view;
	public $views = array();
	public $view_default = 'bookings';
	/**
	 * Placeholder used in sprintf to prefix attendee field names, you can change this by defining EM_BOOKINGS_TABLE_ATTENDEE_PREFIX which must either be false to disable entirely, or a string with %s in it.
	 * @var mixed|string
	 */
	public $attendee_header_placeholder = 'Attendee %s'; //translated in __construct
	
	function __construct( $args = [] ) {
		
		$this->statuses = array(
			'all' => ['label'=>__('All','events-manager'), 'search'=> false ],
			'pending' => [ 'label'=>__('Pending','events-manager'), 'search' => [0] ],
			'confirmed' => [ 'label'=>__('Confirmed','events-manager'), 'search'=> [1]  ],
			'cancelled' => [ 'label'=>__('Cancelled','events-manager'), 'search'=> [3]  ],
			'rejected' => [ 'label'=>__('Rejected','events-manager'), 'search'=> [2]  ],
			'needs-attention' => [ 'label'=>__('Needs Attention','events-manager'), 'search'=> [0]  ],
			'incomplete' => [ 'label'=>__('Incomplete Bookings','events-manager'), 'search'=> [0]  ],
		);
		if( !em_get_option('dbem_bookings_approval') ){
			unset($this->statuses['pending']);
			unset($this->statuses['incomplete']);
			$this->statuses['confirmed']['search'] = [0,1];
		}
		// set default status to search for
		static::$filter_vars['status']['default'] = em_get_option('dbem_bookings_approval') ? 'needs-attention':'confirmed';
		
		// set/translate Attendee column header previd accordingly
		if ( !defined('EM_BOOKINGS_TABLE_ATTENDEE_PREFIX') || constant('EM_BOOKINGS_TABLE_ATTENDEE_PREFIX') === true ) {
			$this->attendee_header_placeholder = esc_html__('Attendee %s', 'events-manager');
		} elseif ( constant('EM_BOOKINGS_TABLE_ATTENDEE_PREFIX') !== false ) {
			// we assume here you have a string that has %s in it, otherwise it'll cause PHP warnings and unexpected UI behaviour
			$this->attendee_header_placeholder = constant('EM_BOOKINGS_TABLE_ATTENDEE_PREFIX');
		} else {
			$this->attendee_header_placeholder = '%s';
		}
		
		// determine the view
		$this->views = apply_filters('em_bookings_table_views', [
			'bookings' => [
				'label' => __('Bookings','events-manager'),
				'label_singular' => __('Booking', 'events_manager'),
				'limit' => 20,
				'cols' => [ 'user_name','event_name', 'event_date', 'event_time', 'booking_spaces','booking_status','booking_price' ],
				'contexts' => [
					'event' => [
						'cols' => [ 'user_name','booking_spaces','booking_status','booking_price' ],
					],
				]
			],
			'tickets' => [
				'label' => __('Tickets','events-manager'),
				'label_singular' => __('Ticket', 'events_manager'),
				'limit' => 20,
				'cols' => [ 'user_name','event_name', 'event_date', 'event_time','ticket_name', 'ticket_price', 'ticket_total','ticket_booking_spaces','booking_status' ],
				'contexts' => [
					'event' => [
						'cols' => [ 'user_name', 'ticket_name', 'booking_status', 'ticket_price', 'ticket_booking_spaces', 'ticket_total' ],
					],
				]
			],
			'attendees' => [
				'label' => __('Attendees','events-manager'),
				'label_singular' => __('Attendee', 'events_manager'),
				'limit' => 20,
				'cols' => [ 'user_name','event_name', 'event_date', 'event_time', 'ticket_name','ticket_price', 'booking_status' ],
				'contexts' => [
					'event' => [
						'cols' => [ 'user_name', 'ticket_name', 'booking_status', 'ticket_price' ],
					],
				]
			],
		], $this);
		
		// determine current view
		if( !empty($args['view']) || !empty($_REQUEST['view']) ) {
			$proposed_view = !empty($args['view']) ? $args['view'] : $_REQUEST['view'];
			if( !empty($this->views[$proposed_view] ) ) {
				$this->view = $proposed_view;
			}
		}
		
		// LIST TABLE stuff
		if( empty($GLOBALS['hook_suffix']) ){
			$GLOBALS['hook_suffix'] = 'events-manager-bookings';
		}
		if( !empty($_GET['page']) ) {
			$this->item_type = str_replace('events-manager-', '', $_GET['page']);
		}else{
			$this->item_type = 'bookings';
		}
		
		parent::__construct();
		
		// backcompat with EM Pro 3.2.10 and earlier
		remove_action('em_bookings_table_export_options', array('EM_Attendees_Form', 'em_bookings_table_export_options')); //show booking form and ticket summary
	}
	
	public function load_columns() {
		//build template of possible collumns
		$this->cols_users_template = apply_filters('em_bookings_table_cols_users_template',  array(
			'user_login' => __('Username', 'events-manager'),
			'user_name'=>__('Name','events-manager'),
			'first_name'=>__('First Name','events-manager'),
			'last_name'=>__('Last Name','events-manager'),
			'user_email'=>__('E-mail','events-manager'),
			'dbem_phone'=>__('Phone Number','events-manager'),
		), $this);
		$this->cols_events_template = apply_filters('em_bookings_table_cols_events_template', array(
			'event_name'=>__('Event','events-manager'),
			'event_date'=>__('Event Date(s)','events-manager'),
			'event_time'=>__('Event Time(s)','events-manager'),
		), $this);
		$this->cols_bookings_template = apply_filters('em_bookings_table_cols_bookings_template', array(
			'booking_spaces'=>__('Spaces','events-manager'),
			'booking_status'=>__('Status','events-manager'),
			'booking_rsvp_status'=>__('RSVP Status','events-manager'),
			'booking_date'=>__('Booking Date','events-manager'),
			'booking_price'=>__('Total','events-manager'),
			'booking_id'=>__('Booking ID','events-manager'),
			'booking_comment'=>__('Booking Comment','events-manager')
		), $this);
		$this->cols_attendees_template = apply_filters('em_bookings_table_cols_attendees_template', array(
			'ticket_booking_id' => array(
				'label' => __('Ticket ID','events-manager'),
				'column_header' => sprintf( $this->attendee_header_placeholder, __('Ticket ID','events-manager')),
			),
			'ticket_uuid' => array(
				'label' => __('Ticket UUID','events-manager'),
				'column_header' => sprintf( $this->attendee_header_placeholder, __('Ticket UUID','events-manager')),
			),
		), $this);
		$this->cols_tickets_template = apply_filters('em_bookings_table_cols_tickets_template', array(
			'ticket_spaces'=>__('Ticket Capacity','events-manager'),
			'ticket_booking_spaces'=>__('Ticket Spaces','events-manager'),
			'ticket_name'=>__('Ticket Name','events-manager'),
			'ticket_description'=>__('Ticket Description','events-manager'),
			'ticket_price'=>__('Ticket Price','events-manager'),
			'ticket_total'=>__('Ticket Total','events-manager'),
			'ticket_id'=>__('Ticket ID','events-manager')
		), $this);
		$this->cols_payments_template = apply_filters('em_bookings_table_cols_payments_template', array(), $this);
		$cols_template = array_merge( $this->cols_template, $this->cols_users_template, $this->cols_events_template, $this->cols_bookings_template, $this->cols_tickets_template, $this->cols_attendees_template, $this->cols_payments_template); // we're adding this every time now
		$this->cols_template = apply_filters('em_bookings_table_cols_template', $cols_template, $this);
		$this->cols_template['actions'] = __('Actions','events-manager');
		$this->cols_template_groups = apply_filters('em_bookings_table_cols_template_groups', array(
			'user'=> array(
				'label' => __('User Fields','events-manager'),
				'fields' => array_keys( $this->cols_users_template ),
			),
			'event'=> array(
				'label' => __('Event','events-manager'),
				'fields' => array_keys( $this->cols_events_template ),
			),
			'payment' => array(
				'label' => __('Payment Information','events-manager'),
				'fields' => array_keys( $this->cols_payments_template ),
			),
			'booking' => array(
				'label' => __('Booking','events-manager'),
				'fields' => array_keys( $this->cols_bookings_template ),
			),
			'ticket'=> array(
				'label' => __('Ticket','events-manager'),
				'fields' => array_keys( $this->cols_tickets_template ),
			),
			'booking_meta'=> array(
				'label' => __('Booking Meta','events-manager'),
				'fields' => [],
			),
			'attendee' => array(
				'label' => __('Attendee (Per Space Booked)','events-manager'),
				'fields' => array_keys( $this->cols_attendees_template ),
			),
		), $this);
	}
	
	public function load_current_context() {
		// determine current context first, so any filters etc. can be applied
		if( !empty($args['context']) ) {
			$this->context = $args['context'];
		} else {
			$this->context = false; // means it's 'loaded'
			// load collumn context settings
			if ( $this->get_person() !== false ) {
				$this->context = 'person';
			} elseif ( $this->get_ticket() !== false ) {
				$this->context = 'ticket';
				$this->view_default = 'tickets';
			} elseif ( $this->get_event() !== false ) {
				$this->context = 'event';
			}
		}
		$this->load_current_context_view();
		return parent::load_current_context();
	}
	
	/**
	 * Loads or reloads the provided view, triggering reloading contexts etc. if not already loaded
	 * @param $view
	 *
	 * @return array
	 */
	public function load_view ( $view ) {
		if( !empty($this->views[$view]) ) {
			$this->view = $view;
			return $this->load_current_context();
		}
		_doing_it_wrong('You must ensure the view exists in the views array before loading it.', 'EM_Bookings_Table::load_view', '6.4.11');
		return array();
	}
	
	public function load_current_context_view() {
		// load current view context default cols, or add bookings view context just in case
		if ( $this->view && $this->context && !empty($this->views[$this->view]['contexts'][$this->context]) ) {
			$context_view = $this->views[$this->view]['contexts'][$this->context];
			$context_view = array_merge( $this->views[$this->view], $context_view );
			unset( $context_view['contexts'], $context_view['label'] );
			$this->context_views[$this->context] = $context_view;
		}
	}
	
	public function get_current_context() {
		$settings = parent::get_current_context();
		// set default view if there is one
		if( !empty($settings['view']) ) {
			$this->view_default = $settings['view'];
		}
		// load the view settings or default view
		if( !empty($this->view) && !empty($settings['views'][$this->view]) ) {
			// load the saved view settings based on current view
			$context_settings = $settings['views'][$this->view];
			unset( $context_settings['views'] ); // in case it's bookings or other
		} elseif( empty($this->view) ) {
			// set and load the saved view, or default to bookings
			$view = $settings['view'] ?? $this->view_default;
			return $this->load_view( $view );
		} else {
			// no saved setting for view/context so at this point we load defaults
			$context_settings = $settings;
			// also remove the default cols and views if we're not bookings
			if( $this->view !== 'bookings' ) { // we just loaded bookings cols if so, so we should allow default context or base to take over
				$context_settings['cols'] = array();
			}
		}
		// re-add to raw saved arrays in event they're missing
		if ( !empty($settings['context']) ) $context_settings['context'] = $settings['context'];
		$context_settings['view'] = $this->view;
		// load default columns or cols based on view, which would have been loaded on construct
		if( empty($context_settings['cols']) ) {
			$context_default = $this->get_current_context_default();
			$view_default = $this->views[$this->view]; unset($view_default['contexts']);
			$default_settings = $context_default ?: $view_default;
			$context_settings = array_merge_recursive( $context_settings, $default_settings );
		}
		return apply_filters( 'em_bookings_table_get_current_context', $context_settings, $this);
	}
	
	public function set_default_settings( $settings = array() ) {
		$settings = parent::set_default_settings( $settings );
		// one saved-settings record covers every archetype, so remembering this filter would show one archetype's bookings under another
		if( isset($settings['filters']['archetype']) ) {
			unset( $settings['filters']['archetype'] );
		}
		// if not bookings view we need to save this into the views array and clean it up from redundant data
		if( $settings['view'] !== 'bookings' ) {
			// get the context setting
			$context_settings = parent::get_current_context();
			if( empty($context_settings['views']) ) {
				$context_settings['views'] = array();
			}
			// clean up unwanted keys
			$view_settings = $settings;
			unset( $view_settings['contexts'], $view_settings['view'], $view_settings['views'] );
			// remove duplicate data
			foreach( $view_settings as $k => $v ) {
				if( !empty($context_settings[$k]) && $context_settings[$k] === $v && $k !== 'cols' ) {
					unset( $view_settings[ $k ] );
				}
			}
			// add to context settings and return that instead.
			$context_settings['views'][$settings['view']] = $view_settings;
			if ( !empty($_REQUEST['save_default_view']) ) {
				$context_settings['view'] = $settings['view'];
				$this->view_default = $settings['view'];
			}
			// save filter settings to
			
			return $context_settings;
		}
		return $settings;
	}
	
	public static function init(){
		parent::init();
		//add export options action
		add_action('em_bookings_table_export_options', array(static::class, 'em_bookings_table_options'));
		add_action('em_bookings_table_settings_options', array(static::class, 'em_bookings_table_options'));
	}
	
	public static function em_ajax_table_row_action( $requested_action ) {
		do_action( static::$basename . '_ajax_table_row_action_' . $requested_action );
		do_action( static::$basename . '_ajax_table_row_action', $requested_action );
		$allowed_actions = array('bookings_approve'=>'approve','bookings_reject'=>'reject','bookings_unapprove'=>'unapprove', 'bookings_delete'=>'delete');
		$EM_Booking = em_get_booking_request( $_REQUEST['booking_id'] ?? false );
		if( ( array_key_exists($requested_action, $allowed_actions) || in_array( $requested_action, $allowed_actions )) && $EM_Booking->can_manage('manage_bookings','manage_others_bookings') ){
			//Event Admin only actions
			$action = $allowed_actions[$requested_action] ?? $requested_action;
			$result = $EM_Booking->$action();
			if( $action === 'delete' && $result ) {
				// just output an icon with feedback message, no updated row to show
				echo '<span class="em-icon em-icon-trash em-tooltip" aria-label="'. $EM_Booking->feedback_message .'"></span>';
			} else {
				$EM_Bookings_Table = new EM_Bookings_Table();
			}
		} elseif ( $requested_action == 'refresh' ) {
			$feedback = !empty($_REQUEST['feedback']) ? wp_kses_data($_REQUEST['feedback']) : esc_html__('Updated', 'events-manager');
			$EM_Booking->feedback_message = $feedback;
			$EM_Bookings_Table = new EM_Bookings_Table();
		}
		if( !empty($EM_Bookings_Table) ) {
			// Re-check management rights against the object actually being rendered: row_id/booking_id are request-supplied and the 'refresh' action reaches here without the capability gate applied to the mutating verbs above.
			if ( isset( $_REQUEST['view'] ) && $_REQUEST['view'] === 'attendees' ) {
				$EM_Ticket_Booking = new EM_Ticket_Booking( $_REQUEST['row_id'] );
				if ( ! $EM_Ticket_Booking->can_manage( 'manage_bookings', 'manage_others_bookings' ) ) return;
				$EM_Ticket_Booking->feedback_message = $EM_Booking->feedback_message;
				$EM_Bookings_Table->single_row( $EM_Ticket_Booking );
			} elseif ( isset( $_REQUEST['view'] ) && $_REQUEST['view'] === 'tickets' ) {
				$row_id = explode( '-', $_REQUEST['row_id'] );
				$data = array( 'booking_id' => $row_id[0], 'ticket_id' => $row_id[1] );
				if ( ! em_get_booking( $row_id[0] )->can_manage( 'manage_bookings', 'manage_others_bookings' ) ) return;
				$EM_Ticket_Bookings = new EM_Ticket_Bookings( $data );
				$EM_Ticket_Bookings->feedback_message = $EM_Booking->feedback_message;
				$EM_Bookings_Table->single_row( $EM_Ticket_Bookings );
			} else {
				if ( ! $EM_Booking->can_manage( 'manage_bookings', 'manage_others_bookings' ) ) return;
				$EM_Bookings_Table->single_row( $EM_Booking );
			}
		}
	}
	
	/**
	 * @return EM_Person|false
	 */
	function get_person(){
		global $EM_Person;
		if( !empty($this->person) && is_object($this->person) ){
			return $this->person;
		}elseif( !empty($_REQUEST['person_id']) && !empty($EM_Person) && is_object($EM_Person) ){
			return $EM_Person;
		}elseif( !empty($_REQUEST['person_id']) ){
			return new EM_Person( $_REQUEST['person_id'] );
		}
		return false;
	}
	/**
	 * @return EM_Ticket|false
	 */
	function get_ticket(){
		global $EM_Ticket;
		if( !empty($this->ticket) && is_object($this->ticket) ){
			return $this->ticket;
		}elseif( !empty($EM_Ticket) && is_object($EM_Ticket) ){
			return $EM_Ticket;
		} elseif( !empty($_REQUEST['ticket_id']) ) {
			$this->ticket = EM_Ticket::get( $_REQUEST['ticket_id'] );
			return $this->ticket;
		}
		return false;
	}
	/**
	 * @return $EM_Event|false
	 */
	function get_event(){
		global $EM_Event;
		if( !empty($this->event) && is_object($this->event) ){
			return $this->event;
		}elseif( !empty($EM_Event) && is_object($EM_Event) ){
			return $EM_Event;
		} elseif( !empty($_REQUEST['event_id']) ) {
			return em_get_event( $_REQUEST['event_id'] );
		}
		if( $this->get_ticket() !== false ) {
			return $this->get_ticket()->get_event();
		}
		return false;
	}
	
	/**
	 * Returns a compatible search arg value for searching bookings by status, which may contain one or more statuses based on name of status, e.g. needs-attention could contain custom statuses.
	 * @return string|int
	 */
	function get_status_search() {
		$status = $this->filters['status'] ?? 'all';
		if ( !empty($this->statuses[ $status ]) && isset($this->statuses[ $status ]['search']) ) {
			$search = $this->statuses[ $status ]['search'];
			if ( is_array( $search ) ) {
				return implode( ',', $search );
			}
			// tolerate a single scalar status id (e.g. an add-on registering one status) rather than silently falling back to every booking
			if ( is_scalar( $search ) && !is_bool( $search ) && $search !== '' ) {
				return (string) $search;
			}
		}
		return $this->statuses['all']['search'];
	}
	
	/**
	 * Returns the event archetype bookings should be restricted to, or false to search every archetype.
	 *
	 * @param string|null $archetype An archetype CPT name, 'all' for every archetype, or null/invalid to use the archetype currently being viewed.
	 *
	 * @return string|false
	 */
	public static function get_archetype_search( $archetype = null ) {
		// without custom archetypes there is nothing to separate, and a condition here would hide bookings whose event row has no archetype value yet
		if ( empty(\EM\Archetypes::$types) || $archetype === 'all' ) {
			return false;
		}
		if ( !\EM\Archetypes::is_event( $archetype, false ) ) {
			$archetype = \EM\Archetypes::get_current();
		}
		return $archetype;
	}
	
	/**
	 * Associative array of archetype CPT names and their plural labels, used to build the archetype filter.
	 *
	 * @return array
	 */
	public function get_archetype_options() {
		$options = array();
		foreach ( \EM\Archetypes::get_cpts( ['location', 'repeating'] ) as $cpt ) {
			$post_type = get_post_type_object( $cpt );
			$options[$cpt] = $post_type ? $post_type->labels->name : $cpt;
		}
		return apply_filters( 'em_bookings_table_archetype_options', $options, $this );
	}
	
	/**
	 * Gets the bookings for this object instance according to its settings
	 *
	 * @return EM_Bookings[]|EM_Ticket_Bookings[]|EM_Ticket_Booking[]
	 */
	function get_items(){
		$EM_Ticket = $this->get_ticket();
		$EM_Event = $this->get_event();
		$EM_Person = $this->get_person();
		$base_args = array( 'limit'=>$this->limit, 'offset'=>$this->offset );
		$default_args = array(
			'status'=> $this->get_status_search(),
			'search' => $this->filters['search'],
			'order' => $this->order,
			'orderby'=>$this->orderby,
			'scope' => false,
		);
		// add booking date to ordering in case we have multiple same-value items in order
		if ( $default_args['orderby'] !== 'booking_date' && $this->view === 'bookings' ) {
			$default_args['orderby'] .= ', booking_date ASC';
		}
		// add bookings scope args e.g. if a person's bookings
		if( $EM_Person !== false ){
			$args = $EM_Person->get_manageable_bookings_args( array( 'scope' => $this->filters['scope'] ) );
		}elseif( $EM_Ticket !== false ){
			//searching bookings with a specific ticket
			$args = array( 'ticket_id' => $EM_Ticket->ticket_id );
		}elseif( $EM_Event !== false ){
			//bookings for an event
			if ( $EM_Event->is_recurring() ) {
				$args = array( 'recurring_event' => $EM_Event->event_id );
			} else {
				$args = array( 'event' => $EM_Event->event_id );
			}
			$args['owner'] = !current_user_can('manage_others_bookings') ? get_current_user_id() : false;
		}else{
			//all bookings for a status
			$args = array( 'scope' => $this->filters['scope'] );
			$args['owner'] = !current_user_can('manage_others_bookings') ? get_current_user_id() : false;
			$archetype = static::get_archetype_search( $this->filters['archetype'] ?? null );
			if( $archetype ){
				$args['event_archetype'] = $archetype;
			}
		}
		$count_args = apply_filters('em_bookings_table_get_bookings_args', array_merge( $default_args, $args ), $this);
		$search_args = array_merge($count_args, $base_args);
		// decide how to split up results, via bookings, or some other way
		$items = array();
		if( $this->view === 'attendees' ) {
			$this->total_items = EM_Ticket_Bookings::get( $count_args, true );
			$items = EM_Ticket_Bookings::get( $search_args );
		} elseif ( $this->view === 'tickets' ) {
			$this->total_items = EM_Tickets_Bookings::get( $count_args, true );
			$items = EM_Tickets_Bookings::get( $search_args );
		} elseif( $this->view === 'bookings' ) {
			$this->total_items = EM_Bookings::count( $count_args );
			$items = EM_Bookings::get( $search_args )->load(); // get the bookings only as an array of EM_Bookings via load()
		}
		// return items, or allow overriding (for example a different view)
		return apply_filters( static::$basename . '_get_items', $items, $this, [ 'count_args' => $count_args, 'search_args' => $search_args, 'base_args' => $base_args, 'default_args' => $default_args ] );
	}
	
	function get_cols_template(){
		return array_merge( $this->cols_attendees_template, $this->cols_tickets_template, $this->cols_events_template, $this->cols_template );
	}
	
	/**
	 * Gets a single row in HTML format for output to table HTML format.
	 * @param EM_Booking|EM_Ticket_Bookings|EM_Ticket_Booking $item
	 *
	 * @return void
	 */
	public function single_row( $item ) {
		echo '<tr data-id="'. esc_attr($item->id) .'" data-id="'. $item->booking_id .'">';
		$this->single_row_columns( $item );
		echo '</tr>';
	}
	
	/**
	 * Accepts an EM_Ticket_Bookings or EM_Ticket_Booking object as well as EM_Booking, which then displays ticket data in cotext of booking
	 * @param EM_Booking|EM_Ticket_Bookings|EM_Ticket_Booking $EM_Object
	 *
	 * @return array[]
	 */
	function get_row ( $EM_Object ){
		if( !$EM_Object instanceof EM_Booking && !$EM_Object instanceof EM_Ticket_Booking && !$EM_Object instanceof EM_Ticket_Bookings ){
			// unrecognized $object, return empty padded array
			return apply_filters( static::$basename . '_get_row', array(array_pad( array(), count($this->cols), '' )), $EM_Object, $this);
		}
		return parent::get_row( $EM_Object );
	}
	
	/**
	 * @param EM_Booking|EM_Ticket_Bookings|EM_Ticket_Booking $EM_Booking
	 * @return mixed
	 */
	public function get_booking_allowed_actions( $EM_Object ){
		$booking_actions = array();
		extract( $this->get_item_objects($EM_Object) );
		$actions = $this->get_action_data_extra( [ 'booking_id' => $EM_Booking->booking_id ] );
		// determine which keys to show
		switch( $EM_Booking->booking_status ){
			case 0: //pending
				if( em_get_option('dbem_bookings_approval') ){
					$allowed_actions = ['approve', 'reject', 'delete'];
					break;
				}//if approvals are off, treat as a 1
			case 1: //approved
				$allowed_actions = ['unapprove', 'reject', 'delete'];
				break;
			case 2: //rejected
				$allowed_actions = ['approve', 'delete'];
				break;
			case 3: //cancelled
			case 4: //awaiting online payment - similar to pending but always needs approval in EM Free
			case 5: //awaiting payment - similar to pending but always needs approval in EM Free
				$allowed_actions = ['approve', 'reject', 'delete'];
				break;
			default:
				$allowed_actions = [];
				break;
		}
		$allowed_actions = apply_filters('em_bookings_table_booking_allowed_actions', $allowed_actions, $EM_Booking, ['table' => $this, 'item' => $EM_Object, 'actions' => $actions]);
		// create actions array where key in $booking_actions exists in $data
		foreach( $allowed_actions as $action ){
			if( !empty($actions[$action]) ) {
				$booking_actions[ $action ] = $actions[ $action ];
			}
		}
		// return the data
		return apply_filters('em_bookings_table_get_booking_allowed_actions', $booking_actions, $this, ['booking' => $EM_Booking, 'item' => $EM_Object, 'actions' => $actions, 'allowed_actions' => $allowed_actions]);
	}
	
	/**
	 * Gets action data for this list table, will reuse saved param data if $extra_data is empty
	 *
	 * @return array
	 */
	public function get_action_data_items() {
		$data_template = array('action' => static::$basename . '_row', 'context' => 'bookings');
		$actions = array(
			'approve' => [ 'label' => __('Approve','events-manager'), 'data' => array_merge($data_template, ['row_action' => 'approve']) ],
			'reject' => [ 'label' => __('Reject','events-manager'), 'data' => array_merge($data_template, ['row_action' => 'reject']) ],
			'delete' => [ 'label' => __('Delete','events-manager'), 'data' => array_merge($data_template, ['row_action' => 'delete']) ],
			'unapprove' => [ 'label' => __('Unapprove','events-manager'), 'data' => array_merge($data_template, ['row_action' => 'unapprove']) ],
		);
		$actions = apply_filters( static::$basename . '_get_action_data_items', $actions, $this, ['data_template' => $data_template]);
		// add upstream context
		foreach( $actions as $action => $action_data ) {
			if( isset($action_data['actions']) ) {
				foreach( $action_data['actions'] as $the_action => $the_action_data ) {
					if ( in_array( $this->view, [ 'attendees', 'tickets' ] ) && $the_action_data['data']['context'] === 'bookings' ) {
						$actions[$action]['actions'][ $the_action ]['data']['upstream'] = 1;
					}
				}
			} else {
				if ( in_array( $this->view, [ 'attendees', 'tickets' ] ) && $action_data['data']['context'] === 'bookings' ) {
					$actions[ $action ]['data']['upstream'] = 1;
				}
			}
		}
		return $actions;
	}
	
	public function get_bulk_actions() {
		$booking_action_data = $this->get_action_data();
		/**
		 * @deprecated do not use anymore, use em_bookings_table_get_bulk_actions instead
		 */
		$booking_actions = apply_filters('em_bookings_table_get_booking_bulk_actions', $booking_action_data, $this);
		// clean up $booking_actions bulk actions array for legacy additions
		foreach( $booking_actions as $action => $action_data ) {
			// if $action_data isn't an array, copy one from $booking_action_data and merge in default info
			if( !is_array($action_data) ) {
				$template = current($booking_action_data);
				$template['label'] = $action_data;
				$template['data']['row_action'] = $action;
				$booking_actions[$action] = $template;
			}
		}
		return apply_filters('em_bookings_table_get_bulk_actions', $booking_actions, $this);
	}
	
	public function get_bulk_action_message( $action, $context ) {
		/*
		ACTION MB - This action will be applied to all the [%s] belonging to each selected set of bookings.
		 */
		// MB Mode (Pro) aside, all actions are either upwards from bottom (e.g. select 1 ticket/attendee, all in the booking are affected), or downawards from top (e.g. select 1 booking, all tickets/attendees are affected)
		if ( $context === $this->view ) return false;
		if( $context == 'bookings' ) { // top context, so anything going down is applied to
			$message = esc_html__('This action will be applied to the entire booking the selected %s belong to. Do you want to continue?', 'events-manager');
		} elseif ( $context === 'attendees' ) { // bottom context, anything else is upwards
			$message = esc_html__('This action aill be applied to every attendee belonging to the selected %s. Do you want to continue?', 'events-manager');
		}
		$message = sprintf ( $message, $this->views[ $this->view ]['label'] );
		// prepened deletion message, we know there's no more to it than that
		$parent_message = parent::get_bulk_action_message( $action, $context );
		if( $parent_message && $action === 'delete' ) $message = $parent_message . '&#10;&#10;' . $message;
		// return message via custom filtersd
		return apply_filters( static::$basename . '_get_bulk_action_message', $message, $action, $context, $this, ['parent_message' => $parent_message] );
	}
	
	public function get_action_message( $action, $context ) {
		$message = $parent_message = parent::get_action_message( $action, $context );
		if ( $context === $this->view ) return $message;
		if ( $context == 'bookings' ) { // top context, so anything going down is applied to
			$context_msg = esc_html__( 'This action will be applied to the entire booking the %s belongs to. Do you want to continue?', 'events-manager' );
			if( $message ) $message .= "\n\n";
			$message .= sprintf( $context_msg, $this->views[ $this->view ]['label_singular'] );
		} elseif ( $context === 'attendees' ) { // bottom context, anything else is upwards
			$context_msg = esc_html__( 'This action aill be applied to every attendee belonging to the selected %s. Do you want to continue?', 'events-manager' );
			if( $message ) $message .= "\n\n";
			$message .= sprintf( $context_msg, $this->views[ $this->view ]['label_singular'] );
		}
		return apply_filters( static::$basename . '_get_action_message', $message, $action, $context, $this, ['parent_message' => $parent_message] );
	}
	
	/**
	 * Generate a list of booking action links
	 * @param $EM_Booking
	 *
	 * @return array
	 */
	public function get_action_links( $EM_Object ) {
		extract( $this->get_item_objects($EM_Object) ); /* @var EM_Ticket $EM_Ticket *//* @var EM_Ticket_Booking $EM_Ticket_Booking *//* @var EM_Ticket_Bookings $EM_Ticket_Bookings *//* @var EM_Booking $EM_Booking */
		$booking_actions_data = $this->get_booking_allowed_actions( $EM_Object );
		$url = $EM_Booking->get_event()->get_bookings_url();
		// add current view and row_id
		$row_id = $EM_Object->id;
		foreach( $booking_actions_data as $k => $action_data ) {
			if( is_array($action_data) && empty($action_data['label']) ) {
				foreach( array_keys($action_data) as $kk ) {
					$booking_actions_data[ $k ][ $kk ]['data']['row_id'] = $row_id;
					$booking_actions_data[ $k ][ $kk ]['data']['view'] = $this->view;
				}
			} else {
				$booking_actions_data[ $k ]['data']['row_id'] = $row_id;
				$booking_actions_data[ $k ]['data']['view'] = $this->view;
			}
		}
		$booking_actions_data = apply_filters('em_bookings_table_booking_actions_data_'.$EM_Booking->booking_status, $booking_actions_data, $EM_Booking);
		$booking_actions = $this->build_action_link( $booking_actions_data, $url );
		$booking_actions = apply_filters('em_bookings_table_booking_actions_'.$EM_Booking->booking_status, $booking_actions, $EM_Booking);
		return apply_filters('em_bookings_table_cols_col_action', $booking_actions, $EM_Booking, $booking_actions_data);
	}
	
	/**
	 * Generate an array of HTML links consisting of booking actions, this can be a multi-level array, which will split into sections if supplied to output_action_links())
	 * @param $EM_Booking
	 *
	 * @return mixed|null
	 */
	public function get_booking_actions ( $EM_Booking ) {
		$booking_actions = $this->get_action_links( $EM_Booking );
		$booking_actions['edit'] = [
			'actions' => [
				'edit' => '<a class="em-list-table-row-edit" href="'. $EM_Booking->get_admin_url().'">'.__('Edit/View','events-manager').'</a>',
			],
		];
		$booking_actions = apply_filters('em_bookings_table_booking_actions_'.$EM_Booking->booking_status , $booking_actions, $EM_Booking);
		return apply_filters('em_bookings_table_cols_col_action', $booking_actions, $EM_Booking);
	}
	
	
	/**
	 * Define the sortable columns
	 *
	 * @return array
	 */
	public function get_sortable_columns(){
		$fields = EM_Bookings::get_sql_accepted_fields();
		$sortable_cols = array();
		foreach( $fields['orderby'] as $field => $col ){
			$sortable_cols[$field] = array( $field, false );
		}
		foreach( $fields['orderby_user_meta'] as $field => $col ){
			$sortable_cols[$field] = array( $field, false );
		}
		// also add ticket fields if in tickets or attendee views
		if ( $this->view == 'tickets' || $this->view == 'attendees' ) {
			$fields = EM_Tickets_Bookings::$sortable_columns;
			foreach( $fields as $field ) {
				$sortable_cols[$field] = array( $field, false );
			}
		}
		// some specific fields that still map
		$sortable_cols['event_date'] = array('event_start', false);
		return apply_filters('em_bookings_table_get_sortable_columns', $sortable_cols, $this);
	}
	
	/**
	 * Override the parent columns method. Defines the columns to use in your listing table
	 *
	 * @return array
	 */
	public function get_columns(){
		return apply_filters('em_bookings_table_get_columns', parent::get_columns(), $this);
	}
	
	/**
	 * Returns an associative array of variables, depending on the $item context, for example if EM_Ticket_Booking, it'll also provide EM_Booking
	 *
	 * This is a useful shortcut function to provide to extract() and still have the different ticket booking contexts.
	 *
	 * @param $item
	 *
	 * @return array{EM_Booking: EM_Booking, EM_Ticket_Bookings: EM_Ticket_Bookings, EM_Ticket_Booking: EM_Ticket_Booking}
	 */
	public function get_item_objects ( $item ) {
		$r = array();
		if ( $item instanceof EM_Ticket_Booking ) {
			$EM_Ticket_Booking = $r['EM_Ticket_Booking'] = $item;
			$r['EM_Booking'] = $EM_Ticket_Booking->get_booking();
		} elseif ( $item instanceof EM_Ticket_Bookings ) {
			$EM_Ticket_Bookings = $r['EM_Ticket_Bookings'] = $item;
			$r['EM_Booking'] = $EM_Ticket_Bookings->get_booking();
			if( $EM_Ticket_Bookings->get_spaces() == 1 ) {
				$r['EM_Ticket_Booking'] = $EM_Ticket_Bookings->get_first();
			}
		} elseif ( $item instanceof EM_Booking ) {
			$EM_Booking = $r['EM_Booking'] = $item;
			if( $this->context === 'ticket' && $this->ticket ) {
				$EM_Ticket = $r['EM_Ticket'] = $this->ticket;
				$EM_Tickets_Bookings = $r['EM_Tickets_Bookings'] = $EM_Booking->get_tickets_bookings();
				if( !empty($EM_Tickets_Bookings->tickets_bookings[$EM_Ticket->ticket_id]) ) {
					$r['EM_Ticket_Bookings'] = $EM_Tickets_Bookings->tickets_bookings[$EM_Ticket->ticket_id];
				}
			} elseif ( $EM_Booking->get_tickets()->count() <= 1 ) { // account for wierd 0 booking instances like waitlists
				$r['EM_Ticket_Bookings'] = $EM_Booking->get_tickets_bookings()->get_first();
			}
		}
		return $r;
	}
	
	/**
	 * @param EM_Booking|EM_Ticket_Bookings|EM_Ticket_Booking $item
	 * @param string $col
	 *
	 * @return mixed
	 * @throws Exception
	 */
	public function get_default_column_data( $item, $col ){
		extract( $this->get_item_objects($item) ); /* @var EM_Ticket $EM_Ticket *//* @var EM_Ticket_Booking $EM_Ticket_Booking *//* @var EM_Ticket_Bookings $EM_Ticket_Bookings *//* @var EM_Booking $EM_Booking */
		$tickets_array = array(); // for ticket columns that have multiple tickets
		$format = $this->format;
		$val = ''; //reset value
		//is col a user col or else?
		//TODO fix urls so this works in all pages in front as well
		if( $col == 'user_email' ){
			$val = $EM_Booking->get_person()->user_email;
		}elseif($col == 'user_login'){
			if( $EM_Booking->is_no_user() ){
				$val = esc_html__('Guest User', 'events-manager');
			}else{
				if( in_array( $format, ['csv', 'xls', 'xlsx'] ) ){
					$val = $EM_Booking->get_person()->user_login;
				}else{
					$val = '<a href="'.esc_url(add_query_arg(array('person_id'=>$EM_Booking->person_id, 'event_id'=>null), $EM_Booking->get_event()->get_bookings_url())).'">'. esc_html($EM_Booking->person->user_login) .'</a>';
				}
			}
		}elseif($col == 'dbem_phone'){
			if( !in_array( $format, ['csv', 'xls', 'xlsx'] ) && !$EM_Booking->get_person()->phone_validity ) {
				static::$cols_allowed_html[ $col ] = true;
				$val = '<span class="em-icon em-icon-warning em-tooltip" aria-label="' . esc_attr__( 'Invalid Number', 'events-manager' ) . '"></span> '. $EM_Booking->get_person()->phone;
			} else {
				$val = $EM_Booking->get_person()->phone;
			}
		}elseif($col == 'user_name'){
			if( in_array( $format, ['csv', 'xls', 'xlsx'] ) ){
				$val = $EM_Booking->get_person()->get_name();
			}elseif( $EM_Booking->is_no_user() ){
				$val = esc_html($EM_Booking->get_person()->get_name());
			}else{
				$val = '<a href="'.esc_url(add_query_arg(array('person_id'=>$EM_Booking->person_id, 'event_id'=>null), $EM_Booking->get_event()->get_bookings_url())).'">'. esc_html($EM_Booking->person->get_name()) .'</a>';
			}
		}elseif($col == 'first_name'){
			$val = $EM_Booking->get_person()->first_name;
		}elseif($col == 'last_name'){
			$val = $EM_Booking->get_person()->last_name;
		}elseif($col == 'event_name'){
			if( in_array( $format, ['csv', 'xls', 'xlsx'] ) ){
				$val = $EM_Booking->get_event()->event_name;
			}else{
				$val = '<a href="'.$EM_Booking->get_event()->get_bookings_url().'">'. esc_html($EM_Booking->get_event()->event_name) .'</a>';
			}
		}elseif($col == 'event_date'){
			if( in_array( $format, ['csv', 'xls', 'xlsx'] ) ){
				$val = $EM_Booking->get_event()->output('#_EVENTDATES');
			}else{
				if ( $EM_Booking->get_event()->is_recurrence() || $EM_Booking->get_event()->is_timeslot() ) {
					$val = $EM_Booking->get_event()->output('#_EVENTDATES');
					$val = '<a href="'. add_query_arg( [ 'event_id' => $EM_Booking->get_event()->get_event_id() ], $EM_Booking->get_event()->get_bookings_url() ).'">'. esc_html($val) .'</a>';
					static::$cols_allowed_html[$col] = true;
				} else {
					$val = $EM_Booking->get_event()->output('#_EVENTDATES');
				}
			}
		}elseif($col == 'event_time'){
			if( in_array( $format, ['csv', 'xls', 'xlsx'] ) ){
				$val = $EM_Booking->get_event()->output('#_EVENTTIMES');
			}else{
				if ( $EM_Booking->get_event()->is_timeslot() ) {
					$val = $EM_Booking->get_event()->output('#_EVENTTIMES');
					$val = '<a href="'.$EM_Booking->get_event()->get_bookings_url().'">'. esc_html($val) .'</a>';
					static::$cols_allowed_html[$col] = true;
				} else {
					$val = $EM_Booking->get_event()->output('#_EVENTTIMES');
				}
			}
		}elseif($col == 'booking_price'){
			$val = $EM_Booking->get_price(true);
		}elseif($col == 'booking_status'){
			$val = $EM_Booking->get_status(true);
		} elseif ( $col == 'booking_rsvp_status' ) {
			$val = $EM_Booking->get_rsvp_status( true );
		}elseif($col == 'booking_date'){
			$val = $EM_Booking->date()->i18n( $EM_Booking->get_option('dbem_date_format').' '. $EM_Booking->get_option('dbem_time_format') );
		}elseif($col == 'actions' && !in_array( $format, ['csv', 'xls', 'xlsx'] ) ) {
			// html only
			$booking_actions = $this->get_booking_actions($EM_Booking, true);
			array_walk( $booking_actions, function( &$item ) {
				if( isset($item['actions']) ) {
					$item = implode(' ', $item['actions']);
				}
			});
			$val = implode(' ', $booking_actions );
		}elseif( $col == 'booking_spaces' ){
			$val = $EM_Booking->get_spaces();
		}elseif( $col == 'booking_id' ){
			$val = $EM_Booking->booking_id;
		}elseif( $col == 'ticket_booking_spaces' ){
			static::$cols_allowed_html[$col] = false; // guilty until proven innocent each time
			if( !empty($EM_Ticket_Bookings) || !empty($EM_Ticket_Booking) ) {
				$EM_Ticket_Bookings = !empty($EM_Ticket_Bookings) ? $EM_Ticket_Bookings : $EM_Ticket_Booking;
				$val = $EM_Ticket_Bookings->get_spaces();
			} else {
				// single ticket
				foreach ( $EM_Booking->get_tickets_bookings() as $EM_Ticket_Bookings ) {
					$tickets_array[$EM_Ticket_Bookings->ticket_id] = array(
						'label' => $EM_Ticket_Bookings->get_ticket()->ticket_name,
						'value' => $EM_Ticket_Bookings->get_spaces(),
					);
				}
				$val = $this->get_tickets_multiple_col( $tickets_array, $col, $EM_Booking );
				static::$cols_allowed_html[$col] = true;
			}
		}elseif( $col == 'ticket_description' || $col == 'ticket_name' || $col == 'ticket_spaces' ){
			static::$cols_allowed_html[$col] = false; // guilty until proven innocent each time
			if( !empty($EM_Ticket_Bookings) || !empty($EM_Ticket_Booking) ) {
				$EM_Ticket_Bookings = !empty($EM_Ticket_Bookings) ? $EM_Ticket_Bookings : $EM_Ticket_Booking;
				$val = $EM_Ticket_Bookings->get_ticket()->$col;
				iF ( $format == 'html' && $col == 'ticket_name' ) {
					static::$cols_allowed_html[$col] = true;
					$val = '<a class="em-bookings-table-col-tooltip-ticket" href="'. esc_url(add_query_arg('ticket_id', $EM_Ticket_Bookings->ticket_id, $EM_Booking->get_event()->get_bookings_url())) . '" target="_blank">' . esc_html($val) . '</a>';
				}
			} else {
				// single ticket
				foreach ( $EM_Booking->get_tickets_bookings() as $EM_Ticket_Bookings ) {
					$tickets_array[$EM_Ticket_Bookings->ticket_id] = array(
						'label' => $EM_Ticket_Bookings->get_ticket()->ticket_name,
						'value' => $EM_Ticket_Bookings->get_ticket()->$col,
					);
				}
				$val = $this->get_tickets_multiple_col( $tickets_array, $col, $EM_Booking );
				static::$cols_allowed_html[$col] = true;
			}
		}elseif( $col == 'ticket_price' ){
			static::$cols_allowed_html[$col] = false; // guilty until proven innocent each time
			if( !empty($EM_Ticket_Bookings) || !empty($EM_Ticket_Booking) ) {
				$EM_Ticket_Bookings = !empty($EM_Ticket_Bookings) ? $EM_Ticket_Bookings : $EM_Ticket_Booking;
				$val = $EM_Ticket_Bookings->get_ticket()->get_price( true );
			} else {
				// single ticket
				foreach ( $EM_Booking->get_tickets_bookings() as $EM_Ticket_Bookings ) {
					$tickets_array[$EM_Ticket_Bookings->ticket_id] = array(
						'label' => $EM_Ticket_Bookings->get_ticket()->ticket_name,
						'value' => $EM_Ticket_Bookings->get_ticket()->get_price( true ),
					);
				}
				$val = $this->get_tickets_multiple_col( $tickets_array, $col, $EM_Booking );
				static::$cols_allowed_html[$col] = true;
			}
		}elseif( $col == 'ticket_total' ){
			// all spaces in a booking for that ticket
			static::$cols_allowed_html[$col] = false; // guilty until proven innocent each time
			$tax = 1 + $EM_Booking->get_tax_rate(true); // get tax for all calculations
			if( !empty($EM_Ticket_Bookings) || !empty($EM_Ticket_Booking) ) {
				$EM_Ticket_Bookings = !empty($EM_Ticket_Bookings) ? $EM_Ticket_Bookings : $EM_Ticket_Booking;
				// single ticket booking or individual ticket rows being shown
				$val = apply_filters('em_bookings_table_row_booking_price_ticket', $EM_Ticket_Bookings->get_price() * $tax, $EM_Booking, $EM_Ticket_Bookings);
				$val = $EM_Booking->format_price($val);
			} else {
				// multiple tickets row
				foreach ( $EM_Booking->get_tickets_bookings() as $EM_Ticket_Bookings ) {
					$price = apply_filters('em_bookings_table_row_booking_price_ticket', $EM_Ticket_Bookings->get_price() * $tax, $EM_Booking, $EM_Ticket_Bookings);
					$tickets_array[$EM_Ticket_Bookings->ticket_id] = array(
						'label' => $EM_Ticket_Bookings->get_ticket()->ticket_name,
						'value' => $EM_Booking->format_price($price),
					);
				}
				$val = $this->get_tickets_multiple_col( $tickets_array, $col, $EM_Booking );
				static::$cols_allowed_html[$col] = true;
			}
		}elseif( $col == 'ticket_id' ){
			static::$cols_allowed_html[$col] = false; // guilty until proven innocent each time
			if( !empty($EM_Ticket_Bookings) || !empty($EM_Ticket_Booking) ) {
				$EM_Ticket_Bookings = !empty($EM_Ticket_Bookings) ? $EM_Ticket_Bookings : $EM_Ticket_Booking;
				$val = $EM_Ticket_Bookings->ticket_id;
			} else {
				// single ticket
				foreach ( $EM_Booking->get_tickets_bookings() as $EM_Ticket_Bookings ) {
					$tickets_array[$EM_Ticket_Bookings->ticket_id] = array(
						'label' => $EM_Ticket_Bookings->get_ticket()->ticket_name,
						'value' => $EM_Ticket_Bookings->get_ticket()->ticket_id,
					);
				}
				$val = $this->get_tickets_multiple_col( $tickets_array, $col, $EM_Booking );
				static::$cols_allowed_html[$col] = true;
			}
		} elseif( $col == 'ticket_booking_id' || $col == 'ticket_uuid' ){
			static::$cols_allowed_html[$col] = false; // guilty until proven innocent each time
			if ( !empty($EM_Ticket_Booking) ) {
				$val = $EM_Ticket_Booking->$col;
			} else {
				if( !empty($EM_Ticket_Bookings) ) {
					$attendees_array = $this->get_attendees_ticket_bookings_col_data( $col, $EM_Ticket_Bookings );
					$val = $this->get_attendees_multiple_col( $attendees_array, $col, $EM_Ticket_Bookings );
				} else {
					$attendees_array = $this->get_attendees_booking_col_data( $col, $EM_Booking );
					$val = $this->get_attendees_multiple_col( $attendees_array, $col, $EM_Booking );
				}
				static::$cols_allowed_html[$col] = true;
			}
		} elseif( $col == 'ticket_booking_price' ){ // do we need this? it's the same as ticket_price in theory... leaving for now in case but not adding to cols_templates
			static::$cols_allowed_html[$col] = false; // guilty until proven innocent each time
			if ( !empty($EM_Ticket_Booking) ) {
				$val = $EM_Ticket_Booking->get_price( true );
			} elseif( !empty($EM_Ticket_Bookings) || $EM_Booking->get_spaces() > 1 ) {
				if ( $EM_Booking->get_spaces() > 1 ) {
					$attendees_array = $attendees_array_data = array();
					foreach ( $EM_Booking->get_tickets_bookings() as $EM_Ticket_Bookings ) {
						foreach( $EM_Ticket_Bookings as $EM_Ticket_Booking ) {
							$attendees_array_data[] = $EM_Ticket_Booking->get_price( true );
						}
						$attendees_array[$EM_Ticket_Bookings->ticket_id] = array(
							'label' => $EM_Ticket_Bookings->get_ticket()->name,
							'attendees' => $attendees_array_data,
						);
					}
					$val = $this->get_attendees_multiple_col( $attendees_array, $col, $EM_Ticket_Bookings );
					static::$cols_allowed_html[$col] = true;
				} else {
					$val = $EM_Ticket_Bookings->get_first()->$col;
				}
			} else {
				$val = $EM_Booking->get_tickets_bookings()->get_first()->get_first()->$col;
			}
		} elseif( $col == 'booking_comment' ){
			$val = $EM_Booking->booking_comment;
		}
		// escape and return
		return $this->default_column_sanitize_data( $val, $col, $item, !empty($allow_html) );
	}
	
	public function primary_column_responsive_meta ( $item, $column_name ) {
		extract( $this->get_item_objects($item) ); /* @var EM_Ticket $EM_Ticket *//* @var EM_Ticket_Booking $EM_Ticket_Booking *//* @var EM_Ticket_Bookings $EM_Ticket_Bookings *//* @var EM_Booking $EM_Booking */
		$meta = '';
		if( $this->get_event() === false ) {
			$meta = $EM_Booking->get_event()->output( '<em>#_EVENTNAME</em> - #_EVENTSTARTDATE @ #_EVENTTIMES' ) . '<br>';
		}
		$meta .= '<strong>[ ' . esc_html($EM_Booking->get_status()) . ' ]</strong> ';
		if( $this->view === 'attendees' ) {
			if( $this->get_ticket() === false ) {
				$meta .= ' ' . $EM_Ticket_Booking->get_ticket()->ticket_name;
			}
			$meta .= ' @ ' . $EM_Ticket_Booking->get_price(true);
		} elseif( $this->view === 'tickets' ) {
			if( $this->get_ticket() === false ) {
				$meta .= ' ' . $EM_Ticket_Bookings->get_ticket()->ticket_name;
			}
			$meta .= ' x ' . $EM_Ticket_Bookings->get_spaces() . ' @ ' . $EM_Ticket_Bookings->get_price(true);
		} else {
			$meta .= sprintf(__('%d Spaces','events-manager'), $EM_Booking->get_spaces()) . ' @ ' . $EM_Booking->get_price(true);
		}
		return apply_filters('em_bookings_table_primary_column_responsive_meta', $meta, $item, $column_name, $this);
	}
	
	/**
	 * Handles how to show multiple tickets when viewing a single row.
	 * @param EM_Booking $EM_Booking
	 * @param string|false $show_meta
	 *
	 * @return false|string
	 */
	public function get_tickets_multiple_col( $tickets_array, $col, $EM_Booking ){
		ob_start();
		$value = $col === 'ticket_booking_spaces' ? $EM_Booking->get_spaces() : __( 'View', 'events-manager' );
		if( !in_array( $this->format, ['csv', 'xls', 'xlsx'] ) ){
			$id = $this->uid . '-col-tickets-tooltip-content-' . $EM_Booking->booking_id . '-' . $col;
			?>
			<section class="em-list-table-col-tooltip em-bookings-table-tickets-tooltip">
				<a class="em-tooltip" data-content="#<?php echo esc_attr($id); ?>" data-tippy-interactive="true">
					<?php echo sprintf(esc_html__( '%d Tickets', 'events-manager' ), count($tickets_array)); ?>
				</a>
				<aside class="em-tooltip-content hidden" id="<?php echo esc_attr($id); ?>" data-type="ticket">
					<section>
						<dl class="tabular-data">
							<?php foreach( $tickets_array as $ticket_id => $ticket_data ): ?>
							<dt>
								<a class="em-bookings-table-col-tooltip-ticket" href="<?php echo esc_url(add_query_arg('ticket_id', $ticket_id, $EM_Booking->get_event()->get_bookings_url())); ?>" target="_blank">
									<?php echo esc_html($ticket_data['label']); ?>
								</a>
							</dt>
							<dd>
								<?php echo esc_html($ticket_data['value']); ?>
							</dd>
							<?php endforeach; ?>
						</dl>
					</section>
				</aside>
			</section>
			<?php
			return ob_get_clean();
		}
		return $value;
	}
	
	/**
	 * @param $EM_Booking
	 * @param $col
	 *
	 * @return false|string
	 * @deprecated use $this->get_tickets_multiple_col() instead
	 * @see $this->get_tickets_multiple_col()
	 */
	public function multiple_tickets_col( $EM_Booking, $col = false ){
		$tickets_array = $this->get_ticket_booking_col_data( $col, $EM_Booking );
		return $this->get_tickets_multiple_col( $tickets_array, $col, $EM_Booking );
	}
	
	/**
	 * @param string $col
	 * @param EM_Ticket_Bookings $EM_Ticket_Bookings
	 *
	 * @return array
	 */
	public function get_attendees_ticket_bookings_col_data( $col, $EM_Ticket_Bookings ) {
		$attendees_array_data = $attendees_array = array();
		foreach( $EM_Ticket_Bookings as $EM_Ticket_Booking ) {
			$attendees_array_data[] = $EM_Ticket_Booking->$col;
		}
		$attendees_array[$EM_Ticket_Bookings->ticket_id] = array(
			'label' => $EM_Ticket_Bookings->get_ticket()->name,
			'attendees' => $attendees_array_data,
		);
		return $attendees_array;
	}
	
	/**
	 * @param string $col
	 * @param EM_Booking $EM_Booking
	 *
	 * @return array
	 */
	public function get_attendees_booking_col_data( $col, $EM_Booking ) {
		$attendees_array = array();
		foreach ( $EM_Booking->get_tickets_bookings() as $EM_Ticket_Bookings ) {
			$attendees_array_data = $this->get_attendees_ticket_bookings_col_data( $col, $EM_Ticket_Bookings );
			if( !empty($attendees_array_data[$EM_Ticket_Bookings->ticket_id]) ) {
				$attendees_array = $attendees_array + $attendees_array_data;
			}
		}
		return $attendees_array;
	}
	
	/**
	 * Handles how to show multiple tickets when viewing a single row.
	 * @param EM_Booking|EM_Ticket_Bookings $EM_Object
	 * @param string|false $show_meta
	 *
	 * @return false|string
	 */
	public function get_attendees_multiple_col( $attendees_array, $col, $EM_Object, $html = false ){
		$value = '';
		if( !in_array( $this->format, ['csv', 'xls', 'xlsx'] ) ){
			if ( $EM_Object instanceof EM_Ticket_Bookings ) {
				$EM_Ticket_Bookings = $EM_Object;
				$uid = $EM_Ticket_Bookings->booking_id .'-'. $EM_Ticket_Bookings->ticket_id;
			} else {
				$EM_Booking = $EM_Object;
				$uid = $EM_Booking->booking_id;
			}
			$content_id = $this->uid .'-col-attendees-tooltip-content-'. $uid;
			// count the attendees
			$attendees_count = 0;
			foreach( $attendees_array as $ticket_attendees ) $attendees_count += count($ticket_attendees['attendees']);
			if( !empty($attendees_array) ) {
				ob_start();
				?>
				<section class="em-list-table-col-tooltip em-bookings-table-attendees-tooltip">
					<a class="em-tooltip" data-content="#<?php echo esc_attr($content_id); ?>" data-tippy-interactive="true">
						<?php echo sprintf(esc_html__( '%d Attendees', 'events-manager' ), $attendees_count); ?>
					</a>
					<div class="em-tooltip-content hidden" id="<?php echo esc_attr($content_id); ?>">
						<?php foreach( $attendees_array as $ticket_id => $attendee_data ): ?>
						<section>
							<?php if( !($EM_Object instanceof EM_Ticket_Bookings) ) : ?>
							<header class="title">
								<a class="em-bookings-table-col-tooltip-ticket" href="<?php echo esc_url( add_query_arg('ticket_id', $ticket_id, $EM_Booking->get_event()->get_bookings_url())); ?>" target="_blank"><?php echo esc_html($attendee_data['label']); ?></a>
							</header>
							<?php endif; ?>
							<dl class="attendee-data">
								<?php
									foreach ( $attendee_data['attendees'] as $attendee_num => $attendee_value ) {
										echo '<dt>' . esc_html( sprintf( __('Attendee #%d', 'events-manager-pro'), $attendee_num + 1) ) . '</dt>';
										if ( $html ) {
											echo '<dd>' . $attendee_value . '</dd>';
										} else {
											echo '<dd>' . esc_html($attendee_value) . '</dd>';
										}
									}
								?>
							</dl>
						</section>
						<?php endforeach; ?>
					</div>
				</section>
				<?php
				$value = ob_get_clean();
			} else {
				$value = '';
			}
		}
		return $value;
	}
	
	public function display_attributes() {
		$atts = parent::display_attributes();
		$atts['data-view'] = $this->view;
		return apply_filters('em_bookings_table_display_attributes', $atts, $this);
	}
	
	public function extra_tablenav( $which ) {
		if ( $which != 'top' ) {
			parent::extra_tablenav( $which );
			return null;
		}
		$EM_Event = $this->get_event();
		$id = esc_attr($this->id);
		?>
		<div class="alignleft actions filters em-list-table-filters <?php echo $id; ?>-filters <?php if ( !static::$show_filters ) echo 'hidden'; ?>">
			<input name="em_search" type="text" class="inline <?php echo $id; ?>-filter" placeholder="<?php esc_attr_e('Search bookings', 'events-manager'); ?> ..." value="<?php echo esc_attr($this->filters['search']);?>">
			<?php if( $EM_Event === false ): ?>
				<select name="scope" class="<?php echo $id; ?>-filter">
					<?php
						foreach ( em_get_scopes() as $key => $value ) {
							$selected = "";
							if ($key == $this->filters['scope'])
								$selected = "selected='selected'";
							echo "<option value='".esc_attr($key)."' $selected>".esc_html($value)."</option>  ";
						}
					?>
				</select>
			<?php endif; ?>
			<select name="status" class="<?php echo $id; ?>-filter">
				<?php
					foreach ( $this->statuses as $key => $value ) {
						$selected = "";
						if ($key == $this->filters['status'])
							$selected = "selected='selected'";
						echo "<option value='".esc_attr($key)."' $selected>".esc_html($value['label'])."</option>  ";
					}
				?>
			</select>
			<?php if( $this->context === false && !empty(\EM\Archetypes::$types) ): $archetype_search = static::get_archetype_search( $this->filters['archetype'] ?? null ); ?>
				<select name="archetype" class="<?php echo $id; ?>-filter">
					<option value="all" <?php selected( $archetype_search, false ); ?>><?php esc_html_e('All Event Types', 'events-manager'); ?></option>
					<?php foreach( $this->get_archetype_options() as $archetype_cpt => $archetype_label ): ?>
						<option value="<?php echo esc_attr($archetype_cpt); ?>" <?php selected( $archetype_search, $archetype_cpt ); ?>><?php echo esc_html($archetype_label); ?></option>
					<?php endforeach; ?>
				</select>
			<?php endif; ?>
			<?php do_action('em_bookings_table_output_table_filters', $this); ?>
			<input name="pno" type="hidden" value="1">
			<input id="post-query-submit" class="button button-secondary" type="submit" value="<?php esc_attr_e( 'Filter' ); ?>">
			<?php /* if( $EM_Event !== false ): ?>
				<?php esc_html_e('Displaying Event','events-manager'); ?> : <?php echo esc_html($EM_Event->event_name); ?>
			<?php elseif( $EM_Person !== false ): ?>
				<?php esc_html_e('Displaying User','events-manager'); echo ' : '.esc_html($EM_Person->get_name()); ?>
			<?php endif; */ ?>
		</div>
		<?php parent::extra_tablenav( $which ); ?>
		<?php
	}
	
	public function column_cb( $item ){
		extract( $this->get_item_objects($item) ); /* @var EM_Ticket $EM_Ticket *//* @var EM_Ticket_Booking $EM_Ticket_Booking *//* @var EM_Ticket_Bookings $EM_Ticket_Bookings *//* @var EM_Booking $EM_Booking */
		$column_id = $item instanceof EM_Ticket_Bookings ?  $item->booking_id . '-' . $item->ticket_id : $this->id;
		$html = sprintf('<input type="checkbox" name="column_id[]" value="%s" data-id="%d" />', $column_id, $EM_Booking->booking_id);
		if( $EM_Booking->booking_status === false && DOING_AJAX && !empty($_REQUEST['row_action']) && $_REQUEST['row_action'] == 'delete' ){
			// booking deleted, no editing/actions possible
			return $html;
		}
		ob_start();
		?>
		<button type="button" class="em-list-table-actions em-tooltip-ddm em-clickable" data-tooltip-class="em-list-table-actions-tooltip" title="<?php esc_attr_e('Booking Actions', 'events-manager'); ?>">...</button>
		<div class="em-tooltip-ddm-content em-bookings-admin-get-invoice-content">
			<?php echo $this->output_action_links( $this->get_booking_actions($EM_Booking) ); ?>
		</div>
		<a class="em-icon em-icon-edit em-tooltip" href="<?php echo esc_url($EM_Booking->get_admin_url()); ?>" aria-label="<?php esc_attr_e('Edit/View', 'events-manager'); ?>"></a>
		<div class="em-loader"></div>
		<?php
		$html .= ob_get_clean();
		return $html;
	}
	
	public function display_hidden_input(){
		$EM_Ticket = $this->get_ticket();
		$EM_Event = $this->get_event();
		$EM_Person = $this->get_person();
		?>
		<?php if( $EM_Event !== false ): ?>
			<input type="hidden" name="event_id" value='<?php echo esc_attr($EM_Event->event_id); ?>' data-persist>
		<?php endif; ?>
		<?php if( $EM_Ticket !== false ): ?>
			<input type="hidden" name="ticket_id" value='<?php echo esc_attr($EM_Ticket->ticket_id); ?>' data-persist>
		<?php endif; ?>
		<?php if( $EM_Person !== false ): ?>
			<input type="hidden" name="person_id" value='<?php echo esc_attr($EM_Person->ID); ?>' data-persist>
		<?php endif; ?>
		<input type="hidden" name="event_archetype" value='<?php echo esc_attr(\EM\Archetypes::get_current()); ?>' data-persist>
		<input type="hidden" name="save_default_view" value='0'>
		<input type="hidden" name="view" value='<?php echo esc_attr($this->view); ?>' data-setting>
		<?php
		do_action('em_bookings_table_display_hidden_input', $this);
	}
	
	public function extra_tablenav_trigger ( $which = '' ) {
		// add a selection trigger of ticket view types
		$id = 0;
		?>
		<div class="alignleft actions em-bookings-table-views-selection">
			<div class="em-bookings-table-views" aria-label="<?php esc_attr_e('View Types', 'events-manager'); ?>">
				<?php $search_views = em_get_search_views(); ?>
				<div class="em-bookings-table-views-trigger" data-template="em-bookings-table-views-options-<?php echo $id; ?>">
					<button type="button" class="em-bookings-table-view-option em-clickable em-bookings-table-view-type-<?php echo $this->view; ?>" data-view="<?php echo esc_attr($this->view); ?>"><?php echo esc_html($this->views[$this->view]['label']); ?></button>
				</div>
				<div class="em-bookings-table-views-options" id="em-bookings-table-views-options-<?php echo $id; ?>">
					<fieldset class="em-bookings-table-views-options-list" id="em-bookings-table-views-options-select-<?php echo $id; ?>">
						<legend class="screen-reader-text"><?php esc_html_e('Search Results View Type','events-manager'); ?></legend>
						<?php foreach( $this->views as $view_id => $view ): ?>
							<label class="em-bookings-table-view-option em-bookings-table-view-type-<?php echo esc_attr($view_id); ?> <?php if( $view_id === $this->view ) echo 'checked'; ?>"  data-view="<?php echo esc_attr($view_id); ?>">
								<input type="radio" name="view" class="em-bookings-table-view-option em-bookings-table-view-type-<?php echo esc_attr($view_id); ?>" value="<?php echo esc_attr($view_id); ?>"  <?php if( $view_id === $this->view ) echo 'checked'; ?>>
								<?php echo esc_html($view['label']); ?>
							</label>
						<?php endforeach; ?>
					</fieldset>
				</div>
			</div>
		</div>
		<?php
		parent::extra_tablenav_trigger( $which );
	}
	
	/* --------------------------------------
		TICKET/ATTENDEE SPLITTING Settings
	-------------------------------------- */
	
	public static function em_bookings_table_options( $EM_Bookings_Table ){
		$uid = esc_attr( $EM_Bookings_Table->uid );
		$id = esc_attr( $EM_Bookings_Table->id );
		?>
		<div class="<?php echo $uid; ?>-rows-setting em-list-table-setting">
			<label for="<?php echo $uid; ?>-rows-setting"><strong><?php esc_html_e('Bookings View', 'events-manager'); ?></strong></label>
			<select name="view" class="<?php echo $id; ?>-filter" id="<?php echo $uid; ?>-rows-setting">
				<?php foreach ( $EM_Bookings_Table->views as $view_id => $view ): ?>
					<option value="<?php echo esc_attr($view_id); ?>" <?php selected( $view_id, $EM_Bookings_Table->view ); ?>><?php echo esc_html($view['label']); ?></option>
				<?php endforeach; ?>
			</select>
		</div>
		<?php if( !doing_action('em_bookings_table_export_options') ): ?>
		<p>
			<label>
				<input type="checkbox" name="save_default_view" value="1" data-setting <?php checked( $EM_Bookings_Table->view === $EM_Bookings_Table->view_default ); ?>>
				<strong><?php esc_html_e('Make this the default view.', 'events-manager'); ?></strong>
			</label>
		</p>
		<?php endif;
	}
	
	public function output_overlay_settings_remember_tooltip() {
		?>
		<span class="em-icon em-icon-info s-15 em-tooltip" aria-label="<?php esc_html_e('Your current settings will be saved for this selected view.', 'events-manager'); ?>" data-tippy-maxWidth="250px"></span>
		<?php
	}
	
	
	/* --------------------------------------
		EXPORT FUNCTIONS
	-------------------------------------- */
	
	/**
	 * Extends exporting a single row depending if tickets are to be split or not
	 * @param EM_Booking $item
	 * @param EM_Bookings_Table $EM_List_Table
	 * @param resource $handle
	 *
	 * @return void
	 */
	public static function export_csv_table_row_x ( $item, $EM_List_Table, $handle ) {
		//Display all values
		$EM_Booking = $item;
		if( $EM_List_Table->show_tickets  ){
			if ( $EM_List_Table->show_attendees ) {
				/* @var EM_Ticket_Booking $EM_Ticket_Booking */
				foreach($EM_Booking->get_tickets_bookings() as $EM_Ticket_Bookings){
					foreach( $EM_Ticket_Bookings as $EM_Ticket_Booking ){
						$rows = $EM_List_Table->get_row($EM_Ticket_Booking);
						foreach( $rows as $row ) {
							fputcsv( $handle, $row, static::$export_delimiter );
						}
					}
				}
			} else {
				foreach( $EM_Booking->get_tickets_bookings() as $EM_Ticket_Bookings ){ /* @var \EM_Ticket_Bookings $EM_Ticket_Bookings */
					// since we're splitting by ticket type, we don't need individual EM_Ticket_Booking objects, but the wrapper object
					$rows = $EM_List_Table->get_row($EM_Ticket_Bookings);
					foreach( $rows as $row ) {
						fputcsv( $handle, $row, static::$export_delimiter );
					}
				}
			}
		}else{
			parent::export_csv_table_row( $EM_Booking, $EM_List_Table, $handle );
		}
	}
	
	/**
	 * Do not use this method, use get_row instead. This is kept here for backcompat with EM Pro
	 * @param $EM_Booking
	 *
	 * @return array
	 * @depreacted
	 */
	public function get_row_csv( $EM_Booking ) {
		$this->format = 'csv';
		return $this->get_row( $EM_Booking );
	}
	
	/* END EXPORT FUNCTIONS */
}
EM_Bookings_Table::init();
?>