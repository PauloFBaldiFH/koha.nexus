<?php
/**
 * Deals with the ticket info for an event
 *
 * @property EM_Event $event
 */
class EM_Tickets extends EM_Object implements Iterator, Countable {
	
	/**
	 * Array of EM_Ticket objects for a specific event
	 * @var EM_Ticket[]
	 */
	var $tickets = [];
	/**
	 * @var int
	 */
	var $event_id;
	/**
	 * @var EM_Booking
	 */
	var $booking;
	var $spaces;
	
	/**
	 * @var EM_Event
	 */
	protected $event;
	public $deleted_tickets = [];
	
	/**
	 * Creates an EM_Tickets instance
	 * @param mixed $object
	 * @param bool $force_load  Loads tickets from database, skipping any caching or local loading
	 */
	function __construct( $object = false, $force_load = false ){
		global $wpdb;
		if( is_numeric($object) || $object instanceof EM_Event || $object instanceof EM_Booking ){
			$this->event_id = (is_object($object)) ? $object->get_event_id():$object;
			if( $object instanceof EM_Event ) $this->event = $object;
			$orderby_option = em_get_option('dbem_bookings_tickets_orderby');
			$order_by = em_get_option('dbem_bookings_tickets_ordering') ? array('ticket_order ASC') : array();
			$ticket_orderby_options = apply_filters('em_tickets_orderby_options', array(
				'ticket_price DESC, ticket_name ASC'=>__('Ticket Price (Descending)','events-manager'),
				'ticket_price ASC, ticket_name ASC'=>__('Ticket Price (Ascending)','events-manager'),
				'ticket_name ASC, ticket_price DESC'=>__('Ticket Name (Ascending)','events-manager'),
				'ticket_name DESC, ticket_price DESC'=>__('Ticket Name (Descending)','events-manager')
			));
			if( array_key_exists($orderby_option, $ticket_orderby_options) ){
				$order_by[] = $orderby_option;
			}else{
				$order_by[] = 'ticket_price DESC, ticket_name ASC';
			}
		    if( $object instanceof  EM_Booking ){
				$sql = "SELECT * FROM ". EM_TICKETS_TABLE ." WHERE ticket_id IN (SELECT ticket_id FROM ".EM_TICKETS_BOOKINGS_TABLE." WHERE booking_id='{$object->booking_id}') ORDER BY ".implode(',', $order_by);
		    }else{
		        $sql = "SELECT * FROM ". EM_TICKETS_TABLE ." WHERE event_id ='{$this->event_id}' ORDER BY ".implode(',', $order_by);
		    }
			$tickets = $wpdb->get_results($sql, ARRAY_A);
			foreach ($tickets as $ticket){
				$EM_Ticket = $force_load ? new EM_Ticket($ticket) : EM_Ticket::get($ticket);
				$EM_Ticket->event_id = $this->event_id;
				$EM_Ticket->event = $this->event;
				$this->tickets[$EM_Ticket->ticket_id] = $EM_Ticket;
			}
		}elseif( is_array($object) ){ //expecting an array of EM_Ticket objects or ticket db array
			if( current($object) instanceof EM_Ticket ){
			    foreach($object as $EM_Ticket){
					$this->tickets[$EM_Ticket->ticket_id] = $EM_Ticket;
			    }
			}else{
				foreach($object as $ticket){
					$EM_Ticket = $force_load ? new EM_Ticket($ticket) : EM_Ticket::get($ticket);
					$EM_Ticket->event_id = $this->event_id;
					$EM_Ticket->event = $this->event;
					$this->tickets[$EM_Ticket->ticket_id] = $EM_Ticket;				
				}
			}
		}
		do_action('em_tickets', $this, $object);
	}
	
	public function __get( $prop ){
		if( $prop == 'event' ){
			return $this->get_event();
		}
	}
	
	public function __set( $prop, $val ){
		if( $prop == 'event' && $val instanceof EM_Event ){
			$this->event = $val;
			$this->event_id = $this->event->get_event_id();
		}
	}
	
	public function __isset( $prop ) {
		//start_timestamp and end_timestamp are deprecated, don't use them anymore
		if ($prop == 'event') {
			return !empty($this->event);
		}
	}
	
	/**
	 * Returnds the event associated with this set of tickets, if there is one.
	 * @return EM_Event
	 */
	function get_event(){
		if( $this->event && $this->event->get_event_id() == $this->event_id ){
			return $this->event;
		}
		global $EM_Event;
		if( is_object($EM_Event) && $EM_Event->get_event_id() == $this->event_id ){
			$this->event = $EM_Event;
			return $EM_Event;
		}else{
			$this->event = em_get_event($this->event_id);
		}
	}

	/**
	 * does this ticket exist?
	 * @return bool 
	 */
	function has_ticket($ticket_id){
		foreach( $this->tickets as $EM_Ticket){
			if($EM_Ticket->ticket_id == $ticket_id){
				return apply_filters('em_tickets_has_ticket',true, $EM_Ticket, $this);
			}
		}
		return apply_filters('em_tickets_has_ticket',false, false,$this);
	}
	
	/**
	 * Get the first EM_Ticket object in this instance. Returns false if no tickets available.
	 * @return EM_Ticket
	 */
	function get_first(){
		if( count($this->tickets) > 0 ){
			foreach($this->tickets as $EM_Ticket){
				return $EM_Ticket;
			}
		}else{
			return false;
		}
	}
	
	/**
	 * Delete tickets in this object
	 * @return boolean
	 */
	function delete(){
		global $wpdb;
		//get all the ticket ids
		$result = false;
		$ticket_ids = array();
		if( !empty($this->tickets) ){
			//get ticket ids if tickets are already preloaded into the object
			foreach( $this->tickets as $EM_Ticket ){
				$ticket_ids[] = $EM_Ticket->ticket_id;
			}
			//check that tickets don't have bookings
			if(count($ticket_ids) > 0){
				$bookings = $wpdb->get_var("SELECT COUNT(*) FROM ". EM_TICKETS_BOOKINGS_TABLE." WHERE ticket_id IN (".implode(',',$ticket_ids).")");
				if( $bookings > 0 ){
					$result = false;
					$this->add_error(__('You cannot delete tickets if there are any bookings associated with them. Please delete these bookings first.','events-manager'));
				}else{
					$result = $wpdb->query("DELETE FROM ".EM_TICKETS_TABLE." WHERE ticket_id IN (".implode(',',$ticket_ids).")");
				}
			}
		}elseif( !empty($this->event_id) ){
			//if tickets aren't preloaded into object and this belongs to an event, delete via the event ID without loading any tickets
			$event_id = absint($this->event_id);
			$bookings = $wpdb->get_var("SELECT COUNT(*) FROM ". EM_TICKETS_BOOKINGS_TABLE." WHERE ticket_id IN (SELECT ticket_id FROM ".EM_TICKETS_TABLE." WHERE event_id='$event_id')");
			$ticket_ids = $wpdb->get_col("SELECT ticket_id FROM ". EM_TICKETS_TABLE." WHERE event_id='$event_id'");
			if( $bookings > 0 ){
				$result = false;
				$this->add_error(__('You cannot delete tickets if there are any bookings associated with them. Please delete these bookings first.','events-manager'));
			}else{
				$result = $wpdb->query("DELETE FROM ".EM_TICKETS_TABLE." WHERE event_id='$event_id'");
			}
		}
		return apply_filters('em_tickets_delete', ($result !== false), $ticket_ids, $this);
	}

	function detach() {
		$results = [];
		foreach ( $this->tickets as $EM_Ticket ) {
			$results[] = $EM_Ticket->detach();
		}
		return !in_array(false, $results);
	}

	/**
	 * If the associated event with these tickets is a recurrence, try and re-link tickets with parent tickets, based on name.
	 * @return bool
	 */
	function attach() {
		if ( $this->get_event()->is_repeated() ) {
			$results = [];
			$EM_Tickets = $this->get_event()->get_recurring_event()->get_tickets();
			foreach ( $this->tickets as $EM_Ticket ) {
				foreach ( $EM_Tickets as $ticket ) {
					if ( $ticket->name === $EM_Ticket->name ) {
						// link the ticket to the ticket parent and remove redundant inherited data
						$results[] = $EM_Ticket->attach( $ticket->ticket_id );
					}
				}
			}
		}
		return isset($results) && !in_array(false, $results);
	}
	
	/**
	 * Retrieve multiple ticket info via POST
	 * @return boolean
	 */
	function get_post(){
		//Build Event Array
		do_action('em_tickets_get_post_pre', $this);
		$current_tickets = $this->tickets; //save previous tickets so things like ticket_meta doesn't get overwritten
		$this->tickets = []; //clean current tickets out
		if( !empty($_POST['em_tickets']) && is_array($_POST['em_tickets']) ){
			//get all ticket data and create objects
			global $allowedposttags;
			$order = 1;
			foreach($_POST['em_tickets'] as $row => $ticket_data){
			    if( $row > 0 ){
			    	if( !empty($ticket_data['ticket_id']) && !empty($current_tickets[$ticket_data['ticket_id']]) ){
			    		$EM_Ticket = $current_tickets[$ticket_data['ticket_id']];
			    	}else{
			    		$EM_Ticket = new EM_Ticket();
			    		unset($ticket_data['ticket_id']);
			    	}
					$ticket_data['event_id'] = $this->event_id;
					// check if a ticket is to be deleted
				    if ( $EM_Ticket->ticket_id && !empty($ticket_data['delete']) && wp_verify_nonce( $ticket_data['delete'], 'delete_ticket_'.$EM_Ticket->ticket_id ) ) {
					    $this->deleted_tickets[ $EM_Ticket->ticket_id ] = $EM_Ticket;
				    } else {
					    $EM_Ticket->get_post($ticket_data);
					    $EM_Ticket->ticket_order = $order;
					    if( $EM_Ticket->ticket_id ){
						    $this->tickets[ $EM_Ticket->ticket_id ] = $EM_Ticket;
					    }else{
						    $this->tickets[ $EM_Ticket->ticket_uuid ] = $EM_Ticket;
					    }
					    $order++;
				    }
			    }
			}
		}else{
			//we create a blank standard ticket
			$EM_Ticket = new EM_Ticket(array(
				'event_id' => $this->event_id,
				'ticket_name' => __('Standard','events-manager')
			));
			$this->tickets[] = $EM_Ticket;
		}
		return apply_filters('em_tickets_get_post', count($this->errors) == 0, $this);
	}
	
	/**
	 * Go through the tickets in this object and validate them 
	 */
	function validate(){
		$this->errors = array();
		foreach($this->tickets as $EM_Ticket){
			if( !$EM_Ticket->validate() ){
				$this->add_error($EM_Ticket->get_errors());
			} 
		}
		return apply_filters('em_tickets_validate', count($this->errors) == 0, $this);
	}
	
	/**
	 * Save tickets into DB, deletes any tickets set to be deleted
	 */
	function save() {
		$result = true;
		// save tickets
		foreach ( $this->tickets as $EM_Ticket ) {
			$EM_Ticket->event_id = $this->event_id; //pass on saved event_data
			if ( !$EM_Ticket->save() ) {
				$result = false;
				$this->add_error( $EM_Ticket->get_errors() );
			}
		}
		// delete tickets
		foreach ( $this->deleted_tickets as $EM_Ticket ) {
			if ( !$EM_Ticket->delete() ) {
				$result = false;
				$this->add_error( $EM_Ticket->get_errors() );
			}
		}

		return apply_filters( 'em_tickets_save', $result, $this );
	}
	
	/**
	 * Goes through each ticket and populates it with the bookings made
	 */
	function get_ticket_bookings(){
		foreach( $this->tickets as $EM_Ticket ){
			$EM_Ticket->get_bookings();
		}
	}
	
	/**
	 * Get the total number of spaces this event has. This will show the lower value of event global spaces limit or total ticket spaces. Setting $force_refresh to true will recheck spaces, even if previously done so.
	 * @param boolean $force_refresh
	 * @return int
	 */
	function get_spaces( $force_refresh=false ){
		$spaces = 0;
		if($force_refresh || $this->spaces == 0){
			foreach( $this->tickets as $EM_Ticket ){
				/* @var $EM_Ticket EM_Ticket */
				$spaces += $EM_Ticket->get_spaces();
			}
			$this->spaces = $spaces;
		}
		return apply_filters('em_booking_get_spaces',$this->spaces,$this);
	}
	
	/**
	 * Returns the collumns used in ticket public pricing tables/forms
	 * @param unknown_type $EM_Event
	 */
	function get_ticket_collumns($EM_Event = false){
		if( !$EM_Event ) $EM_Event = $this->get_event();
		$collumns = array( 'type' => __('Ticket Type','events-manager'), 'price' => __('Price','events-manager'), 'spaces' => __('Spaces','events-manager'));
		if( $EM_Event->is_free() ) unset($collumns['price']); //add event price
		return apply_filters('em_booking_form_tickets_cols', $collumns, $EM_Event );
	}
	
	//Iterator Implementation
	#[\ReturnTypeWillChange]
    public function rewind(){
        reset($this->tickets);
    }
	#[\ReturnTypeWillChange]
	/**
	 * @return EM_Ticket
	 */
    public function current(){
        $var = current($this->tickets);
        return $var;
    }
	#[\ReturnTypeWillChange]
    public function key(){
        $var = key($this->tickets);
        return $var;
    }
	#[\ReturnTypeWillChange]
	/**
	 * @return EM_Ticket
	 */
    public function next(){
        $var = next($this->tickets);
        return $var;
    }
	#[\ReturnTypeWillChange]
    public function valid(){
        $key = key($this->tickets);
        $var = ($key !== NULL && $key !== FALSE);
        return $var;
    }
    //Countable Implementation
	#[\ReturnTypeWillChange]
    public function count(){
    	return count($this->tickets);
    }
}
?>