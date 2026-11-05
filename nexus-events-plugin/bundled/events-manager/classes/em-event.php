<?php
use EM\Event\Timeranges;
use EM\Event\Timeslot;
use EM_Event_Locations\Event_Location, EM_Event_Locations\Event_Locations;
use EM\Recurrences\Recurrence_Sets, EM\Recurrences\Recurrence_Set;
use EM\Archetypes;
use EM\Exception;

/**
 * Get an event in a db friendly way, by checking globals, cache and passed variables to avoid extra class instantiations.
 * @param mixed $id can be either a post object, event object, event id or post id
 * @param mixed $search_by default is post_id, otherwise it can be by event_id as well. In multisite global mode, a blog id can be supplied to load events from another blog.
 * @return EM_Event
 */
function em_get_event( $search_id = false, $search_by = 'event_id') {
	global $EM_Event;
	// check for timeslot ID format
	if ( is_string($search_id) && preg_match( '/^(\d+):(\d+)$/', $search_id, $matches ) ) {
		$id = $matches[1];
		$timeslot_id = $matches[2];
	} else {
		$id = $search_id;
		$timeslot_id = false;
	}
	try {
		//check if it's not already global so we don't instantiate again
		if ( is_object( $EM_Event ) && get_class( $EM_Event ) == 'EM_Event' ) {
			if ( is_object( $id ) && $EM_Event->post_id == $id->ID ) {
				$found = true;
			} elseif ( !is_object( $id ) ) {
				if ( $search_by == 'event_id' && $EM_Event->get_event_id() == $id ) {
					$found = true;
				} elseif ( $search_by == 'post_id' && $EM_Event->post_id == $id ) {
					$found = true;
				}
			}
			if ( !empty( $found ) ) {
				if ( !empty( $timeslot_id ) ) {
					// convert to a timeslot if not already
					return apply_filters( 'em_get_event', EM_Event::get_timeslot( $EM_Event, $timeslot_id ), $search_id, $search_by );
				} elseif ( !$EM_Event->timeslot_id ) {
					// load only if current $EM_Event has no timeslot, we may have loaded the same event but in timeslot context
					return apply_filters( 'em_get_event', $EM_Event, $search_id, $search_by );
				}
			}
		}
		if ( is_object( $id ) && get_class( $id ) == 'EM_Event' ) {
			$event = $id;
			if ( $timeslot_id ) {
				$EM_Event = EM_Event::get_timeslot( $EM_Event, $timeslot_id );
			}
			return apply_filters( 'em_get_event', $event );
		} elseif ( !defined( 'EM_CACHE' ) || EM_CACHE ) {
			//check the cache first
			$event_id = false;
			if ( is_numeric( $id ) ) {
				if ( $search_by == 'event_id' ) {
					$event_id = EM_Event::abs_id( $id . ':' . $timeslot_id );
				} elseif ( $search_by == 'post_id' ) {
					$event_id = wp_cache_get( $id, 'em_events_ids' );
				}
			} elseif ( !empty( $id->ID ) && !empty( $id->post_type ) && ( $id->post_type == EM_POST_TYPE_EVENT || $id->post_type == 'event-recurring' ) ) {
				$event_id = wp_cache_get( $id->ID, 'em_events_ids' );
			}
			if ( $event_id ) {
				$event = wp_cache_get( $event_id, 'em_events' ); /* @var EM_Event $event */
				if ( is_object( $event ) && !empty( $event->get_event_id() ) ) {
					if ( $timeslot_id ) {
						$event = EM_Event::get_timeslot( $event, $timeslot_id );
					}
					return apply_filters( 'em_get_event', $event, $search_id, $search_by );
				}
			}
		}
	} catch ( Exception $e ) {
		// something went wrong due to timeslots, bail with just the main event id
		if ( $e->get_error_code() === 'timeslot_not_found' ) {
			return apply_filters( 'em_get_event', new EM_Event( $id, $search_by ), $search_id, $search_by );
		}
	}
	//if we get this far, just create a new event
	return apply_filters( 'em_get_event', new EM_Event($search_id, $search_by), $search_id, $search_by );
}


//TODO Can add more recurring functionality such as "also update all future recurring events" or "edit all events" like google calendar does.
//FIXME If you create a super long recurrence timespan, there could be thousands of events... need an upper limit here.

/**
 * Event Object. This holds all the info pertaining to an event, including location and recurrence info.
 * An event object can be one of three "types" a recurring event, recurrence of a recurring event, or a single event.
 * The single event might be part of a set of recurring events, but if loaded by specific event id then any operations and saves are 
 * specifically done on this event. However, if you edit the recurring group, any changes made to single events are overwritten.
 *
 * @property string $language           Language of the event, shorthand for event_language
 * @property string $translation        Whether or not a event is a translation (i.e. it was translated from an original event), shorthand for event_translation
 * @property int $parent                Event ID of parent event, shorthand for event_parent
 * @property int $event_id              The Event ID, returns formatte id with timeslot if it has one, such as 123:123
 * @property int $id                    The Event ID, case sensitive, shorthand for event_id
 * @property string $slug               Event slug, shorthand for event_slug
 * @property string name                Event name, shorthand for event_name
 * @property int owner                  ID of author/owner, shorthand for event_owner
 * @property int status                 ID of post status, shorthand for event_status
 * @property string $event_start_time   Start time of event
 * @property string $event_end_time     End time of event
 * @property string $event_start_date   Start date of event
 * @property string $event_end_date     End date of event
 * @property string $event_start        The event start date in local time. represented by a mysql DATE format
 * @property string $event_end          The event end date in local time. represented by a mysql DATE format
 * @property string $event_timezone     Timezone representation in PHP string or WP-style UTC offset
 * @property string $event_rsvp_date    Start rsvo date of event
 * @property string $event_rsvp_time    End rsvp time of event
 * @property int $event_active_status   End rsvp time of event
 * @property int $previous_active_status End rsvp time of event
 *
 */
class EM_Event extends EM_Object{
	/* Field Names */
	protected $event_id;
	protected $post_id;
	public $event_archetype;
	public $event_type;
	public $event_parent;
	public $event_slug;
	public $event_owner;
	public $event_name;
	/**
	 * The event start time in local time, represented by a mysql TIME format or 00:00:00 default.
	 * Protected so when set in PHP it will reset the EM_Event->start property (EM_DateTime object) so it will have the correct UTC time according to timezone.
	 * @var string
	 */
	protected $event_start_time = '00:00:00';
	/**
	 * The event end time in local time, represented by a mysql TIME format or 00:00:00 default.
	 * Protected so when set in PHP it will reset the EM_Event->end property (EM_DateTime object) so it will have the correct UTC time according to timezone.
	 * @var string
	 */
	protected $event_end_time = '00:00:00';
	/**
	 * The event start date in local time. represented by a mysql DATE format.
	 * Protected so when set in PHP it will reset the EM_Event->start property (EM_DateTime object) so it will have the correct UTC time according to timezone.
	 * @var string
	 */
	protected $event_start_date;
	/**
	 * The event end date in local time. represented by a mysql DATE format.
	 * Protected so when set in PHP it will reset the EM_Event->start property (EM_DateTime object) so it will have the correct UTC time according to timezone.
	 * @var string
	 */
	protected $event_end_date;
	/**
	 * The event start date/time in UTC timezone, represented as a mysql DATETIME value. Protected non-accessible property. 
	 * Use $EM_Event->start() to obtain the date/time via the returned EM_DateTime object.
	 * @var string
	 */
	protected $event_start;
	/**
	 * The event end date/time in UTC timezone, represented as a mysql DATETIME value. Protected non-accessible property.
	 * Use $EM_Event->end() to obtain the date/time via the returned EM_DateTime object.
	 * @var string
	 */
	protected $event_end;
	/**
	 * Whether an event is all day or at specific start/end times. When set to true, event start/end times are assumed to be 00:00:00 and 11:59:59 respectively.
	 * @var boolean
	 */
	public $event_all_day;
	/**
	 * Timezone representation in PHP string or WP-style UTC offset.
	 * @var string
	 */
	protected $event_timezone;
	public $post_content;
	public $event_rsvp = 0;
	/**
	 * @var string A specific date RSVP is permitted until (YYYY-MM-DD)
	 */
	protected $event_rsvp_date;
	/**
	 * @var string A specific time of day RSVP is required by (HH:MM:SS)
	 */
	protected $event_rsvp_time;
	public $event_rsvp_spaces;
	public $event_spaces;
	public $event_private;
	public $location_id;
	/**
	 * Key name of event location type associated to this event.
	 *
	 * Events can have an event-specific location type, such as a url, webinar or another custom type instead of a regular geographical location. If this value is set, then a registered event location type is loaded and relevant saved event meta is used.
	 *
	 * @var string
	 */
	public $event_location_type;
	public $event_status;
	protected $event_active_status = 1;
	protected $previous_active_status = 1;
	protected $blog_id = 0;
	public $group_id;
	public $event_language;
	public $event_translation = 0;
	/**
	 * Populated with the non-hidden event post custom fields (i.e. not starting with _) 
	 * @var array
	 */
	public $event_attributes = array();
	/* anonymous submission information */
	public $event_owner_anonymous;
	public $event_owner_name;
	public $event_owner_email;

	protected $is_recurrence;
	/* Recurring Specific Values */
	public $recurrence_set_id;
	/**
	 * @var Recurrence_Set
	 */
	public $recurrence_set;
	/**
	 * @var Recurrence_Sets
	 */
	public $recurrence_sets;
	/**
	 * @var int Number of days before/after each recurrence an RSVP is required, can be negative or positive for before/after
	 */
	public $recurrence_rsvp_days;
	/**
	 * Previously used to give this object shorter property names for db values (each key has a name) but this is now deprecated, use the db field names as properties. This propertey provides extra info about the db fields.
	 * @var array
	 */
	public $fields = array(
		'event_id' => array( 'name'=>'id', 'type'=>'%d' ),
		'post_id' => array( 'name'=>'post_id', 'type'=>'%d', 'null' => true ),
		'event_archetype' => array( 'name'=>'archetype', 'type'=>'%s' ),
		'event_type' => array( 'name'=>'type', 'type'=>'%s' ),
		'event_parent' => array( 'type'=>'%d', 'null'=>true ),
		'event_slug' => array( 'name'=>'slug', 'type'=>'%s', 'null'=>true ),
		'event_owner' => array( 'name'=>'owner', 'type'=>'%d', 'null'=>true ),
		'event_name' => array( 'name'=>'name', 'type'=>'%s', 'null'=>true ),
		'event_timezone' => array('type'=>'%s', 'null'=>true ),
		'event_start_time' => array( 'name'=>'start_time', 'type'=>'%s', 'null'=>true ),
		'event_end_time' => array( 'name'=>'end_time', 'type'=>'%s', 'null'=>true ),
		'event_start' => array('type'=>'%s', 'null'=>true ),
		'event_end' => array('type'=>'%s', 'null'=>true ),
		'event_all_day' => array( 'name'=>'all_day', 'type'=>'%d', 'null'=>true ),
		'event_start_date' => array( 'name'=>'start_date', 'type'=>'%s', 'null'=>true ),
		'event_end_date' => array( 'name'=>'end_date', 'type'=>'%s', 'null'=>true ),
		'post_content' => array( 'name'=>'notes', 'type'=>'%s', 'null'=>true ),
		'event_rsvp' => array( 'name'=>'rsvp', 'type'=>'%d' ),
		'event_rsvp_date' => array( 'name'=>'rsvp_date', 'type'=>'%s', 'null'=>true ),
		'event_rsvp_time' => array( 'name'=>'rsvp_time', 'type'=>'%s', 'null'=>true ),
		'event_rsvp_spaces' => array( 'name'=>'rsvp_spaces', 'type'=>'%d', 'null'=>true ),
		'event_spaces' => array( 'name'=>'spaces', 'type'=>'%d', 'null'=>true),
		'location_id' => array( 'name'=>'location_id', 'type'=>'%d', 'null'=>true ),
		'event_location_type' => array( 'type'=>'%s', 'null'=>true ),
		'recurrence_id' => array( 'name'=>'recurrence_id', 'type'=>'%d', 'null'=>true ),
		'recurrence_set_id' => array( 'name'=>'recurrence_set_id', 'type'=>'%d'),
		'recurrence_rsvp_days'  =>  array(  'name'=>'recurrence_rsvp_days',  'type'=>'%d',  'null'=>true  ),  //days  before  or  after  start  date  to  generat  bookings  cut-off  date
		'event_status' => array( 'name'=>'status', 'type'=>'%d', 'null'=>true ),
		'event_active_status' => array( 'name'=>'active_status', 'type'=>'%d', 'null'=>true ),
		'event_private' => array( 'name'=>'private', 'type'=>'%d', 'null'=>true ),
		'blog_id' => array( 'name'=>'blog_id', 'type'=>'%d', 'null'=>true ),
		'group_id' => array( 'name'=>'group_id', 'type'=>'%d', 'null'=>true ),
		'event_language' => array( 'type'=>'%s', 'null'=>true ),
		'event_translation' => array( 'type'=>'%d'),
	);
	public $post_fields = array('event_slug','event_owner','event_name','event_private','event_status','event_attributes','post_id','post_content'); //fields that won't be taken from the em_events table anymore
	
	public static $field_shortcuts = array(
		'language' => 'event_language',
		'translation' => 'event_translation',
		'parent' => 'event_parent',
		'id' => 'event_id',
		'type' => 'event_type',
		'archetype' => 'event_archetype',
		'slug' => 'event_slug',
		'name' => 'event_name',
		'status' => 'event_status',
		'owner' => 'event_owner',
		'start_time' => 'event_start_time',
		'end_time' => 'event_end_time',
		'start_date' => 'event_start_date',
		'end_date' => 'event_end_date',
		'start' => 'event_start',
		'end' => 'event_end',
		'all_day' => 'event_all_day',
		'timezone' => 'event_timezone',
		'rsvp' => 'event_rsvp',
		'rsvp_date' => 'event_rsvp_date',
		'rsvp_time' => 'event_rsvp_time',
		'rsvp_spaces' => 'event_rsvp_spaces',
		'spaces' => 'event_spaces',
		'private' => 'event_private',
		'location_type' => 'event_location_type',
		'owner_anonymous' => 'event_owner_anonymous',
		'owner_name' => 'event_owner_name',
		'owner_email' => 'event_owner_email',
		'active_status' => 'event_active_status',
		'notes' => 'post_content',
	);
	
	public $image_url = '';
	/**
	 * EM_DateTime of start date/time in local timezone.
	 * As of EM 5.8 this property is protected and accessible via __get(). For backwards compatibility accessing this property directly returns the timestamp as before with an offset to timezone.
	 * To access the object use EM_Event::start(), do not try to access it directly for better accuracy use EM_Event::start()->getTimestamp();
	 * @var EM_DateTime
	 */
	protected $start;
	/**
	 * EM_DateTime of end date/time in local timezone.
	 * As of EM 5.8 this property is protected and accessible via __get(). For backwards compatibility accessing this property directly returns the timestamp as before, with an offset to timezone.
	 * To access the object use EM_Event::end(), do not try to access it directly for better accuracy use EM_Event::start()->getTimestamp();
	 * @var EM_DateTime
	 */
	protected $end;
	/**
	 * Timestamp for booking cut-off date/time
	 * @var EM_DateTime
	 */
	protected $rsvp_end;
	
	/**
	 * @var EM_Location
	 */
	public $location;
	/**
	 * @var Event_Location
	 */
	public $event_location;
	/**
	 * If we're switching event location types, previous event location is kept here and deleted upon save()
	 * @var Event_Location
	 */
	public $event_location_deleted = null;
	/**
	 * @var EM_Bookings
	 */
	public $bookings;
	/**
	 * The contact person for this event
	 * @var WP_User
	 */
	public $contact;
	/**
	 * The categories object containing the event categories
	 * @var EM_Categories
	 */
	public $categories;
	/**
	 * The tags object containing the event tags
	 * @var EM_Tags
	 */
	public $tags;
	/**
	 * If there are any errors, they will be added here.
	 * @var array
	 */
	public $errors = array();
	/**
	 * If something was successful, a feedback message might be supplied here.
	 * @var string
	 */
	public $feedback_message;
	/**
	 * Any warnings about an event (e.g. bad data, recurrence, etc.)
	 * @var string
	 */
	public $warnings;
	/**
	 * Array of dbem_event field names required to create an event 
	 * @var array
	 */
	public $required_fields = array('event_name', 'event_start_date');
	public $mime_types = array(1 => 'gif', 2 => 'jpg', 3 => 'png'); 
	/**
	 * previous status of event when instantiated
	 * @access protected
	 * @var mixed
	 */
	public $previous_status = false;
	/**
	 * If the event was just added/created during this execution, value will be true. Useful when running validation or making decisions on taking actions when events are saved/created for the first time.
	 * @var boolean
	 */
	public $just_added_event = false;
	/**
	 * If bookings were previously enabled but then disabled, this flag is set to true during the saving process.
	 * @var boolean
	 */
	public $just_disabled_rsvp = false;
	
	/* Post Variables - copied out of post object for easy IDE reference */
	public $ID;
	public $post_author;
	public $post_date;
	public $post_date_gmt;
	public $post_title;
	public $post_excerpt = '';
	public $post_status;
	public $comment_status;
	public $ping_status;
	public $post_password;
	public $post_name;
	public $to_ping;
	public $pinged;
	public $post_modified;
	public $post_modified_gmt;
	public $post_content_filtered;
	public $post_parent;
	public $guid;
	public $menu_order;
	public $post_type;
	public $post_mime_type;
	public $comment_count;
	public $ancestors;
	public $filter;
	
	/**
	 * @var array   List of status types an event can have, mapped by status number as keys and name of status for value. Consider states 0-9 reserved by core for future features.
	 */
	public static $active_statuses;

	// The following are all deprecated as of EM 7.0, use get_recurrence_set() for the primary rules that these values would have originally referred to. Note that now an event can have multiple recurrence set patterns.
	/**
	 * @deprecated Use EM_Event::get_recurrence_set()::get_event()::event_id
	 */
	public $recurrence_id;
	/**
	 * @deprecated Use EM_Event::is_recurrence()
	 */
	private $recurrence = 0;
	/**
	 * @deprecated Use EM_Event::get_recurrence_set()::interval
	 */
	private $recurrence_interval;
	/**
	 * @deprecated Use EM_Event::get_recurrence_set()::freq
	 */
	private $recurrence_freq;
	/**
	 * @deprecated Use EM_Event::get_recurrence_set()::byday
	 */
	private $recurrence_byday;
	/**
	 * @deprecated Use EM_Event::get_recurrence_set()::duration
	 */
	private $recurrence_days = 0;
	/**
	 * @deprecated Use EM_Event::get_recurrence_set()::byweekno
	 */
	private $recurrence_byweekno;
	/**
	 * If set, the event is contextually restricted to the specific timeslot specificed. This specifically affects things such as checks for capacity, start dates/times, etc.
	 * @var int
	 */
	public $timeslot_id;
	/**
	 * @var Timeslots
	 */
	private $timeslots;
	
	/**
	 * Initialize an event. You can provide event data in an associative array (using database table field names), an id number, or false (default) to create empty event.
	 * @param mixed $id
	 * @param mixed $search_by default is post_id, otherwise it can be by event_id as well. In multisite global mode, a blog id can be supplied to load events from another blog.
	 */
	function __construct($id = false, $search_by = 'event_id') {
		global $wpdb;
		if( is_array($id) ){
			//deal with the old array style, but we can't supply arrays anymore
			$id = (!empty($id['event_id'])) ? absint($id['event_id']) : absint($id['post_id']);
			$search_by = (!empty($id['event_id'])) ? 'event_id':'post_id';
		}
		$is_post = !empty($id->ID) && Archetypes::is_valid_cpt( $id->post_type, ['location'] ); // check all archetypes except location
		if( $is_post ){
			$id->ID = absint($id->ID);
		}else{
			// check for timeslot ID format
			if ( is_string($id) && preg_match( '/^(\d+):(\d+)$/', $id, $matches ) ) {
				$id = $matches[1];
				$timeslot_id = $matches[2];
			} else {
				$id = absint($id);
				$timeslot_id = false;
			}
			if( $id == 0 ) $id = false;
		}
		if( is_numeric($id) || $is_post ){ //only load info if $id is a number
			$event_post = null;
			if($search_by == 'event_id' && !$is_post ){
				//search by event_id, get post_id and blog_id (if in ms mode) and load the post
				$results = $wpdb->get_row($wpdb->prepare("SELECT * FROM ".EM_EVENTS_TABLE." WHERE event_id=%d",$id), ARRAY_A);
				if ( empty( $results['post_id']) ) {
					// this is a recurrence, time-slot or other post-less event, so we just create it here based off the results
					$this->to_object( $results );
					$this->load_event_meta();
				} else {
					if( !empty($results['post_id']) ){ $this->post_id = $results['post_id']; $this->event_id = $id; }
					if( is_multisite() && (is_numeric($results['blog_id']) || $results['blog_id']=='' ) ){
						if( $results['blog_id']=='' )  $results['blog_id'] = get_current_site()->blog_id;
						$event_post = get_blog_post($results['blog_id'], $results['post_id']);
						$search_by = $this->blog_id = $results['blog_id'];
					}elseif( !empty($results['post_id']) ){
						$event_post = get_post($results['post_id']);
					}
				}
			}else{
				//if searching specifically by post_id and in MS Global mode, then assume we're looking in the current blog we're in
				if( $search_by == 'post_id' && EM_MS_GLOBAL ) $search_by = get_current_blog_id();
				//get post data based on ID and search context
				if(!$is_post){
					if( is_multisite() && (is_numeric($search_by) || $search_by == '') ){
					    if( $search_by == '' ) $search_by = get_current_site()->blog_id;
						//we've been given a blog_id, so we're searching for a post id
						$event_post = get_blog_post($search_by, $id);
						$this->blog_id = $search_by;
					}else{
						//search for the post id only
						$event_post = get_post($id);
					}
				}else{
					$event_post = $id;
					//if we're in MS Global mode, then unless a blog id was specified, we assume the current post object belongs to the current blog
					if( EM_MS_GLOBAL && !is_numeric($search_by) ){
						$this->blog_id = get_current_blog_id();
					}
				}
				$this->post_id = !empty($id->ID) ? $id->ID : $id;
			}
			$this->load_postdata($event_post, $search_by);
			// check if active status is enabled, if not set to 1 by default
			if( !$this->get_option('dbem_event_status_enabled') && $this->event_active_status == 0 ){
				$this->event_active_status = 1;
			}
			$this->previous_active_status = $this->event_active_status;
		}
		//set default timezone
		if( empty($this->event_timezone) ){
			if( $this->get_option('dbem_timezone_enabled') ){
				//get default timezone for event, and sanitize UTC variations
				$this->event_timezone = $this->get_option('dbem_timezone_default');
				if( $this->event_timezone == 'UTC+0' || $this->event_timezone == 'UTC +0' ){ $this->event_timezone = 'UTC'; }
			}else{
				$this->event_timezone = EM_DateTimeZone::create()->getName(); //set a default timezone if none exists
			}
		}
		// handle empty post_id case, fill only blank fields from the parent such as post content etc.
		if( empty($this->post_id) && !empty($this->event_parent) ){
			$parent_event = em_get_event($this->event_parent);
			if( $parent_event instanceof EM_Event ){
				if( empty($this->post_content) ) $this->post_content = $parent_event->post_content;
				if( empty($this->event_attributes) ) $this->event_attributes = $parent_event->event_attributes;
				if( empty($this->event_slug) ) $this->event_slug = $parent_event->event_slug;
				if( empty($this->event_owner) ) $this->event_owner = $parent_event->event_owner;
				if( empty($this->event_name) ) $this->event_name = $parent_event->event_name;
				if( empty($this->post_excerpt) ) $this->post_excerpt = $parent_event->post_excerpt;
			}
		}
		// set some type casts
		if ( $this->event_id ) $this->event_id = absint($this->event_id);
		if ( $this->event_parent ) $this->event_parent = absint($this->event_parent);
		if ( $this->timeslot_id ) $this->timeslot_id = absint($this->timeslot_id);
		// do a little cleanup if we notice anything odd from bad installs, plugin conflicts etc.
		if ( $this->event_id && $this->is_recurring(true) ) {
			$this->recurrence_set_id = null; // no recurrence set id for recurring and repeating
			if ( !$this->event_start_date ) {
				$Recurrence_Set = $this->get_recurrence_set();
				if ( empty($this->event_timezone) ) $this->event_timezone = $Recurrence_Set->timezone ?? $this->get_option('dbem_timezone_default');
				if ( empty($this->event_start_date) ) $this->event_start_date = $Recurrence_Set->start_date ?? date('Y-m-d');
				if ( empty($this->event_start_time) || $this->event_start_time == '00:00:00' ) $this->event_start_time = $Recurrence_Set->start_time ?? '00:00:00';
				if ( empty($this->event_end_date) ) $this->event_end_date = $Recurrence_Set->end_date ?? date('Y-m-d');
				if ( empty($this->event_end_time) || $this->event_end_time == '00:00:00' ) $this->event_end_time = $Recurrence_Set->end_time ?? '00:00:00';
				$this->event_all_day ??= $Recurrence_Set->all_day ?? false;
			}
		}
		// if dealing with a timeslot, load up the details
		if ( !empty( $timeslot_id ) ) {
			try {
				$this->convert_to_timeslot( $timeslot_id );
			} catch ( Exception $e ) {
				// do nothing, just don't load the timeslot
			}
		}
		// fire hook to add any extra info to an event
		do_action('em_event', $this, $id, $search_by);
		//add this event to the cache
		if( $this->event_id && $this->post_id ){
			wp_cache_set( $this->get_event_uid(), $this, 'em_events');
			wp_cache_set( $this->post_id, $this->get_event_uid(), 'em_events_ids' );
		}
	}

	/**
	 * Turns this event into one of its own timeslots, in place, taking on that slot's dates, times and status.
	 *
	 * @param int $timeslot_id
	 * @throws Exception If the id names no timeslot of this event.
	 *
	 * @return void
	 */
	public function set_timeslot_id( $timeslot_id ){
		if ( !$this->timeslot_id ) {
			// Delegated rather than queried here: the loader in EM\Event\Timeslot binds the row to this event, which the id on its own does not, and a second copy of that query is how this one came to read columns the table has never had.
			$this->convert_to_timeslot( absint( $timeslot_id ), true );
		}
	}

	public function set_timeslot_data( $timeslot_data ) {
		//reset start and end objects so they are recreated with the new dates/times if and when needed
		$start = explode(' ', $timeslot_data['timeslot_start'] );
		$end = explode(' ', $timeslot_data['timeslot_end'] );
		$this->event_start_date = $start[0];
		$this->event_start_time = $start[1];
		$this->event_end_date = $end[0];
		$this->event_end_time = $end[1];
		$this->start = $this->end = $this->event_start = $this->event_end = null;
		// event status
		$this->event_active_status = $timeslot_data['timeslot_status'];
		// reset objects specific to the timeslot
		$this->bookings = null;
	}

	function __get( $prop ){
		// get the event id with timeslot info
		if( $prop == 'event_id' ){
			return $this->get_event_uid();
		}
		// get post and blog ids
		if ( $prop == 'post_id' ) {
			return $this->get_post_id();
		}
		if ( $prop == 'blog_id' ) {
			return $this->get_blog_id();
		}
	    //get the modified or created date from the DB only if requested, and save to object
	    if( $prop == 'event_date_modified' || $prop == 'event_date_created'){
	        global $wpdb;
	        $row = $wpdb->get_row($wpdb->prepare("SELECT event_date_created, event_date_modified FROM ".EM_EVENTS_TABLE.' WHERE event_id=%d', $this->event_id));
	        if( $row ){
	            $this->event_date_modified = $row->event_date_modified;
	            $this->event_date_created = $row->event_date_created;
	            return $this->$prop;
	        }
	    }elseif( in_array($prop, array('event_start_date', 'event_start_time', 'event_end_date', 'event_end_time', 'event_rsvp_date', 'event_rsvp_time')) ){
	    	return $this->$prop;
	    }elseif( $prop == 'event_timezone' ){
	    	return $this->get_timezone()->getName();
	    } elseif ( in_array( $prop, ['recurrence_interval', 'recurrence_freq', 'recurrence_byday', 'recurrence_days', 'recurrence_byweekno', 'recurrence_byweekno' ])) {
			// legacy support, refer to recurrence sets going forward
			if ( $prop === 'recurrence_days' ) {
				$prop = 'recurrence_duration';
			}
			$prop = str_replace( 'recurrence_', '', $prop );
			return $this->get_recurrence_set()->{$prop};
	    }
	    //deprecated properties for external access, use the start(), end() and rsvp_end() functions to access any of this data.
	    if( $prop == 'start' ) return $this->start()->getTimestampWithOffset();
	    if( $prop == 'end' ) return $this->end()->getTimestampWithOffset();
	    if( $prop == 'rsvp_end' ) return $this->rsvp_end()->getTimestampWithOffset();
		if( $prop == 'event_active_status' || $prop == 'active_status' ) {
			return $this->get_option('dbem_event_status_enabled') ? absint($this->event_active_status) : 1;
		}
	    return parent::__get( $prop );
	}
	
	public function __set( $prop, $val ){
		if ( $prop === 'id' || $prop === 'event_id' ) {
			if ( preg_match( '/^(\d+):(\d+)$/', $val, $matches ) ) {
				$this->event_id = absint( $matches[1] );
				$this->timeslot_id = absint( $matches[2] );
			} elseif ( is_numeric( $val ) ) {
				$this->event_id = absint( $val );
			}
		}
		// set the post and blog ids
		elseif ( $prop === 'post_id' || $prop === 'blog_id' ) {
			$this->{$prop} = $val === null ? null : absint( $val );
		}
		// dates and times
		elseif ( $prop == 'event_start_date' || $prop == 'event_end_date' || $prop == 'event_rsvp_date' ){
			//if date is valid, set it, if not set it to null
			$this->{$prop} = $val && preg_match('/^\d{4}-\d{2}-\d{2}$/', $val) ? $val : null;
			if( $prop == 'event_start_date') $this->start = $this->event_start = null;
			elseif( $prop == 'event_end_date') $this->end = $this->event_end = null;
			elseif( $prop == 'event_rsvp_date') $this->rsvp_end = null;
		} elseif ( $prop == 'event_start_time' || $prop == 'event_end_time' || $prop == 'event_rsvp_time' ){
			//if time is valid, set it, otherwise set it to midnight
			$this->{$prop} = $val && preg_match('/^\d{2}:\d{2}:\d{2}$/', $val) ? $val : '00:00:00';
			if( $prop == 'event_start_time') $this->start = null;
			elseif( $prop == 'event_end_time') $this->end = null;
			elseif( $prop == 'event_rsvp_time') $this->rsvp_end = null;
		}
		//deprecated properties, use start()->setTimestamp() instead
		elseif( $prop == 'start' || $prop == 'end' || $prop == 'rsvp_end' ){
			if( is_numeric($val) ){
				$this->$prop()->setTimestamp( (int) $val);
			}elseif( is_string($val) ){
				$this->{$val} = new EM_DateTime($val, $this->event_timezone);
			}
		}
		// active status
		elseif ( $prop == 'event_active_status' ) {
			$this->event_active_status = absint($val);
		}
		// deprecated recurrence values
		elseif ( in_array( $prop, ['recurrence_interval', 'recurrence_freq', 'recurrence_byday', 'recurrence_days', 'recurrence_byweekno', 'recurrence_byweekno' ])) {
			if ( $prop === 'recurrence_days' ) {
				$prop = 'recurrence_duration';
			}
			$prop = str_replace( 'recurrence_', '', $prop );
			$this->get_recurrence_set()->{$prop} = $val;
		}
		//anything else
		else{
			parent::__set( $prop, $val );
		}
	}
	
	public function __isset( $prop ){
		if( in_array($prop, array('event_id', 'event_start_date', 'event_end_date', 'event_start_time', 'event_end_time', 'event_rsvp_date', 'event_rsvp_time', 'event_start', 'event_end')) ){
			return !empty( $this->{$prop} );
		}elseif( $prop == 'event_timezone' ){
			return true;
		}elseif( $prop == 'event_active_status' ){
			return !empty( $this->event_active_status );
		}elseif( $prop == 'start' || $prop == 'end' || $prop == 'rsvp_end' ){
			return $this->$prop()->valid;
		} elseif ( $prop == 'post_id' ) {
			return !empty( $this->get_post_id() );
		} elseif ( $prop == 'blog_id' ) {
			return !empty( $this->get_blog_id() );
		}
		return parent::__isset( $prop );
	}

	/**
	 * Gets the event ID without timeslot info
	 * @return false|float|int|mixed|string
	 */
	public function get_event_id( $base_only = true ) {
		$event_id = $this->event_id;
		if ( !$base_only && $this->timeslot_id ) {
			$event_id .= ':' . $this->timeslot_id;
		}
		return $event_id;
	}

	/**
	 * Returns the full event ID including the timeslot ID. A shortcut for get_event_id(false).
	 * @return string
	 */
	function get_event_uid() {
		return $this->get_event_id( false );
	}

	/**
	 * Like absint() but accounts for the fact that event IDs may have a timeslot id too. Returns an int if just an event without timeslot, a string like 123:321 if timeslot.
	 * @param $id
	 *
	 * @return int|string
	 */
	public static function abs_id( $id ) {
		if ( preg_match( '/^(\d+):(\d+)$/', $id, $matches ) ) {
			if ( absint( $matches[2] ) === 0 ) {
				$clean_id = absint( $matches[1] );
			} else {
				$clean_id = absint( $matches[1] ) . ':' . absint( $matches[2] );
			}
		} else {
			preg_replace( '/:.+$/', '', $id ); // remove any excess timeslot id attempts
			$clean_id = absint( $id );
		}
		return $clean_id;
	}
	
	/**
	 * When cloning this event, we get rid of the bookings and location objects, since they can be retrieved again from the cache instead. 
	 */
	public function __clone(){
		$this->bookings = null;
		$this->location = null;
		if( is_object($this->event_location) ){
			$this->event_location = clone $this->event_location;
			$this->event_location->event = $this;
		}
	}
	
	/**
	 * Drops object-cached events by id, so anything derived from their bookings is queried again.
	 * @param int|string|array $event_ids One or more event ids, with or without a timeslot id.
	 */
	public static function flush_cache( $event_ids ){
		foreach( array_unique( (array) $event_ids ) as $event_id ){
			if( $event_id ) wp_cache_delete( $event_id, 'em_events' );
		}
	}
	
	function load_postdata($event_post, $search_by = false){
		//load event post object if it's an actual object and also a post type of our event CPT names
		if( is_object($event_post) && Archetypes::is_valid_cpt( $event_post->post_type, ['location'] ) ){
			//load post data - regardless
			$this->post_id = absint($event_post->ID);
			$this->event_name = $event_post->post_title;
			$this->event_owner = $event_post->post_author;
			$this->post_content = $event_post->post_content;
			$this->post_excerpt = $event_post->post_excerpt;
			$this->event_slug = $event_post->post_name;
			foreach( $event_post as $key => $value ){ //merge post object into this object
				$this->$key = $value;
			}
			//load meta data and other related information
			if( $event_post->post_status != 'auto-draft' ){
				$this->load_event_meta($search_by);
				//quick compatability fix in case _event_id isn't loaded or somehow got erased in post meta
				if( empty($this->event_id) && !$this->is_recurring( true ) ){
					global $wpdb;
					if( EM_MS_GLOBAL ){
						$event_array = $wpdb->get_row($wpdb->prepare("SELECT * FROM ".EM_EVENTS_TABLE." WHERE post_id=%d && blog_id=%d",$this->post_id, $this->blog_id), ARRAY_A);
					}else{
						$event_array = $wpdb->get_row('SELECT * FROM '.EM_EVENTS_TABLE. ' WHERE post_id='.$this->post_id, ARRAY_A);	
					}
					if( !empty($event_array['event_id']) ){
						foreach($event_array as $key => $value){
							if( !empty($value) && empty($this->{$key}) ){
								update_post_meta($event_post->ID, '_'.$key, $value);
								$this->{$key} = $value;
							}
						}
					}
				}
			} else {
				$this->event_archetype = Archetypes::get_from_cpt( $this->post_type );
				if ( Archetypes::is_repeating( $this->post_type ) ) {
					$this->event_type = 'repeating';
				}
			}
			$this->get_status();
			$this->compat_keys();
		}elseif( !empty($this->post_id) ){
			//we have an orphan... show it, so that we can at least remove it on the front-end
			global $wpdb;
			if( EM_MS_GLOBAL ){ //if MS Global mode enabled, make sure we search by blog too so there's no cross-post confusion
				if( !empty($this->event_id) ){
					$event_array = $wpdb->get_row($wpdb->prepare("SELECT * FROM ".EM_EVENTS_TABLE." WHERE event_id=%d",$this->event_id), ARRAY_A);
				}else{
					if( $this->blog_id == get_current_blog_id() || empty($this->blog_id) ){
						$event_array = $wpdb->get_row($wpdb->prepare("SELECT * FROM ".EM_EVENTS_TABLE." WHERE post_id=%d AND (blog_id=%d OR blog_id IS NULL)",$this->post_id, $this->blog_id), ARRAY_A);
					}else{
						$event_array = $wpdb->get_row($wpdb->prepare("SELECT * FROM ".EM_EVENTS_TABLE." WHERE post_id=%d AND blog_id=%d",$this->post_id, $this->blog_id), ARRAY_A);
					}
				}
			}else{
				$event_array = $wpdb->get_row($wpdb->prepare("SELECT * FROM ".EM_EVENTS_TABLE." WHERE post_id=%d",$this->post_id), ARRAY_A);
			}
		    if( is_array($event_array) ){
				$this->orphaned_event = true;
				$this->post_id = $this->ID = $event_array['post_id'] = null; //reset post_id because it doesn't really exist
				$this->to_object($event_array);
		    }
		}
		if( empty($this->location_id) && !empty($this->event_id) ) $this->location_id = 0; //just set location_id to 0 and avoid any doubt
		if( EM_MS_GLOBAL && empty($this->blog_id) ) $this->blog_id = get_current_site()->blog_id; //events created before going multisite may have null values, so we set it to main site id
	}

	/**
	 * @param $search_by
	 *
	 * @return void
	 */
	public function load_event_meta( $blog_id = false ) {
		if ( !$this->post_id ) {
			// we need to get the post meta from the parent if possible
			$EM_Event = $this->get_parent();
			if ( $EM_Event ) {
				// if this is a recurrence, load in the post data from the parent
				$this->post_id = $this->ID = $EM_Event->ID;
			}
		}
		$event_meta = $this->get_event_meta( $blog_id );
		if ( !empty($EM_Event) ) {
			$this->post_id = null;
		}
		if( !empty($event_meta['_event_location_type'][0]) ) $this->event_location_type = $event_meta['_event_location_type'][0]; //load this directly so we know further down whether this has an event location type to load
		//Get custom fields and post meta
		$other_event_attributes = apply_filters('em_event_load_postdata_other_attributes', array(), $this);
		foreach($event_meta as $event_meta_key => $event_meta_val){
			$field_name = substr($event_meta_key, 1);
			if($event_meta_key[0] != '_'){
				$this->event_attributes[$event_meta_key] = ( is_array($event_meta_val) ) ? $event_meta_val[0]:$event_meta_val;
			}elseif( is_string($field_name) && !in_array($field_name, $this->post_fields) ){
				if( array_key_exists($field_name, $this->fields) && $this->post_id ){
					$this->$field_name = $event_meta_val[0];
				}elseif( in_array($field_name, array('event_owner_name','event_owner_anonymous','event_owner_email')) ){
					$this->$field_name = $event_meta_val[0];
				}elseif( in_array($field_name, $other_event_attributes) ){
					$this->event_attributes[$field_name] = ( is_array($event_meta_val) ) ? $event_meta_val[0]:$event_meta_val;
				}
			}
		}
		if( $this->has_event_location() ) $this->get_event_location()->load_postdata($event_meta);
	}
	
	function get_event_meta( $blog_id = false ){
		if( !empty($this->blog_id) ) $blog_id = $this->blog_id; //if there's a blog id already, there's no doubt where to look for
		if( empty($this->post_id) ) return array();
		if( is_numeric($blog_id) && $blog_id > 0 && is_multisite() ){
			// if in multisite mode, switch blogs quickly to get the right post meta.
			switch_to_blog($blog_id);
			$event_meta = get_post_meta($this->post_id);
			restore_current_blog();
			$this->blog_id = $blog_id;
		}elseif( EM_MS_GLOBAL ){
			// if a blog ID wasn't defined then we'll check the main blog, in case the event was created in the past
			$this->ms_global_switch();
			$event_meta = get_post_meta($this->post_id);
			$this->ms_global_switch_back();
		}else{
			$event_meta = get_post_meta($this->post_id);
		}
		if( !is_array($event_meta) ) $event_meta = array();
		return apply_filters('em_event_get_event_meta', $event_meta);
	}

	/**
	 * Gets an option from the WordPress options table, by default the option requested is directly retrieved via the WordPress em_get_option function.
	 *
	 * Options that can be customized on a per-archetype basis can override the filters in this function to provide archetype–specific functionality.
	 *
	 * @param $option_name
	 * @param $default
	 *
	 * @return mixed|null
	 */
	public function get_option($option_name, $default = false){
		$option_name = apply_filters('em_event_option', $option_name, $this);
		$option = em_get_option($option_name, $default);
		return apply_filters('em_event_get_option', $option, $option_name, $default, $this);
	}
	
	/**
	 * Retrieve event information via POST (only used in situations where posts aren't submitted via WP)
	 * @return boolean
	 */
	function get_post($validate = true){	
		global $allowedposttags;
		do_action('em_event_get_post_pre', $this);
		//we need to get the post/event name and content.... that's it.
		$this->post_content = isset($_POST['content']) ? wp_kses( wp_unslash($_POST['content']), $allowedposttags):'';
		$this->post_excerpt = !empty($this->post_excerpt) ? $this->post_excerpt:''; //fix null error
		$this->event_name = ( !empty($_POST['event_name']) ) ? sanitize_post_field('post_title', $_POST['event_name'], $this->post_id, 'db'):'';
		// first determine type, in case we have a repeating type of this event
		$this->event_type = in_array( $_POST['event_type'] ?? '', ['recurring','single','repeating'] ) ? $_POST['event_type'] : 'single';
		// now as of 7.1 we detect event_archetype, which will default to a regular event or repeating CPT
		$event_archetype = ( !empty($_POST['event_archetype']) && \EM\Archetypes::is_valid_cpt( $_POST['event_archetype'] ) ) ? $_POST['event_archetype'] : null;
		$this->event_archetype = $event_archetype ?? EM_POST_TYPE_EVENT; // default to base event event_archetype
		$this->post_type = ( $this->is_repeating() ) ? Archetypes::get_repeating_cpt( $this->event_archetype ) : $this->event_archetype;
		//don't forget categories!
		if( $this->get_option('dbem_categories_enabled') ) $this->get_categories()->get_post();
		//get the rest and validate (optional)
		$this->get_post_meta();
		//anonymous submissions and guest basic info
		if ( !is_user_logged_in() && $this->get_option('dbem_events_anonymous_submissions') && empty($this->event_id) ) {
			$this->event_owner_anonymous = 1;
			$this->event_owner_name = !empty($_POST['event_owner_name']) ? wp_kses_data(wp_unslash($_POST['event_owner_name'])):'';
			$this->event_owner_email = !empty($_POST['event_owner_email']) ? wp_kses_data($_POST['event_owner_email']):'';
			if ( empty($this->location_id) && !($this->location_id === 0 && !$this->get_option('dbem_require_location',true)) ) {
				$this->get_location()->owner_anonymous = 1;
				$this->location->owner_email = $this->event_owner_email;
				$this->location->owner_name = $this->event_owner_name;
			}
		}
		//validate and return results
		$result = $validate ? $this->validate():true; //validate both post and meta, otherwise return true
		return apply_filters('em_event_get_post', $result, $this);
	}

	/**
	 * Returns the post ID of this event, and retreives parent post ID if a recurreng event automatically.
	 * @return int|null
	 */
	public function get_post_id() {
		if ( $this->post_id ) {
			return $this->post_id;
		}
		return $this->is_recurrence() ? $this->get_recurring_event()->post_id : $this->post_id;
	}

	public function get_blog_id() {
		return $this->is_recurrence() ? $this->get_recurring_event()->blog_id : $this->blog_id;
	}
	
	/**
	 * Retrieve event post meta information via POST, which should be always be called when saving the event custom post via WP.
	 * @return boolean
	 */
	function get_post_meta(){
		do_action('em_event_get_post_meta_pre', $this);

		//Check if this is recurring or not early on so we can take appropriate action further down
		if ( $this->is_repeating() || ( !empty($_POST['event_type']) && $_POST['event_type'] == 'repeating' ) ) {
			$this->event_type = 'repeating';
		} elseif ( !empty($_POST['recurring']) || (!empty($_POST['event_type']) && $_POST['event_type'] === 'recurring') || $this->is_recurring() ){
			$this->event_type = 'recurring';
		} else {
			$this->event_type = 'single';
		}
		// sort out archetype
		if ( !$this->event_archetype ) {
			$this->event_archetype = $this->is_repeating() ? Archetypes::get_repeating_archetype( $this->post_type ) : $this->post_type;
		}

		// Bookings - part 1 - so that we can know if bookings are enabled for recurrences, the rest is handled after we know the dates/times of an event
		$can_manage_bookings = $this->can_manage('manage_bookings','manage_others_bookings');
		$preview_autosave = is_admin() && !empty($_REQUEST['_emnonce']) && !empty($_REQUEST['wp-preview']) && $_REQUEST['wp-preview'] == 'dopreview'; //we shouldn't save new data during a preview auto-save
		if( !$preview_autosave && $can_manage_bookings && !empty($_POST['event_rsvp']) ){
			if ( !$this->event_rsvp ) {
				$just_enabled_bookings = true;
			}
			$this->event_rsvp = 1;
		} elseif( !$preview_autosave && ($can_manage_bookings || !$this->event_rsvp) ){
			if ( $this->event_rsvp ) {
				// do not turn off RSVP without confirmation
				if ( !empty( $_REQUEST['event_rsvp_delete'] ) && wp_verify_nonce( $_REQUEST['event_rsvp_delete'], 'event_rsvp_delete' ) ) {
					$this->event_rsvp = 0;
					$this->just_disabled_rsvp = true;
				}
			} else {
				$this->event_rsvp = 0; // absint
			}
			$this->event_rsvp_date = $this->event_rsvp_time = $this->rsvp_end = null;
		}
		//Dates and Times
		$this->event_start = $this->event_end = null;
		$times_array = ['event_rsvp_time'];
		if ( $this->is_recurring( true ) ) {
			$this->get_recurrence_sets()->get_post();
			// get the primary recurrence dates/times for now, we will save the definitive range during the save process.
			$Recurrence_Set = $this->get_recurrence_set();
			$this->event_timezone = $Recurrence_Set->timezone;
			$this->event_start_date = $Recurrence_Set->start_date;
			$this->event_start_time = $Recurrence_Set->start_time;
			$this->event_end_date = $Recurrence_Set->end_date;
			$this->event_end_time = $Recurrence_Set->end_time;
			$this->event_all_day = $Recurrence_Set->all_day;
			// set status, if supplied
			$this->previous_active_status = $this->event_active_status;
			$this->event_active_status = absint($Recurrence_Set->status);
		} else {
			//Set Event Timezone to supplied value or alternatively use blog timezone value by default.
			if( !empty($_REQUEST['event_timezone']) ){
				$this->event_timezone = EM_DateTimeZone::create($_REQUEST['event_timezone'])->getName();
			}elseif( empty($this->event_timezone ) ){ //if timezone was already set but not supplied, we don't change it
				$this->event_timezone = EM_DateTimeZone::create()->getName();
			}
			// get post and overall dates/times from post data
			//Event Dates
			$this->event_start_date = ( !empty($_POST['event_start_date']) ) ? wp_kses_data($_POST['event_start_date']) : null;
			$this->event_end_date = ( !empty($_POST['event_end_date']) ) ? wp_kses_data($_POST['event_end_date']) : $this->event_start_date;
			//Sort out time
			if ( $this->get_timeranges()->get_post('event_timeranges') ) {
				if ( $this->get_timeranges()->is_all_day() ) {
					$this->event_all_day = true;
					$this->event_start_time = '00:00:00';
					$this->event_end_time = '23:59:59';
				}else{
					$this->event_all_day = false;
					$this->event_start_time = $this->get_timeranges()->get_time_start();
					$this->event_end_time = $this->get_timeranges()->get_time_end();
				}
			}
			// set status, if supplied
			if ( isset($_POST['event_active_status']) && array_key_exists( $_POST['event_active_status'], static::get_active_statuses() ) ) {
				$this->previous_active_status = $this->event_active_status;
				$this->event_active_status = absint($_POST['event_active_status']);
			}
		}
		// Get times and make sure they are valid
		foreach( $times_array as $timeName ){
			$match = array();
			if( !empty($_POST[$timeName]) && preg_match ( '/^([01]\d|[0-9]|2[0-3])(:([0-5]\d))?(?::[0-5]\d)? ?(AM|PM)?$/', $_POST[$timeName], $match ) ){
				if( empty($match[3]) ) $match[3] = '00';
				if( strlen($match[1]) == 1 ) $match[1] = '0'.$match[1];
				if( !empty($match[4]) && $match[4] == 'PM' && $match[1] != 12 ){
					$match[1] = 12+$match[1];
				}elseif( !empty($match[4]) && $match[4] == 'AM' && $match[1] == 12 ){
					$match[1] = '00';
				}
				$this->$timeName = $match[1].":".$match[3].":00";
			}else{
				$this->$timeName = ($timeName == 'event_start_time') ? "00:00:00":$this->event_start_time;
			}
		}
		//reset start and end objects so they are recreated with the new dates/times if and when needed
		$this->start = $this->end = null;
		
		//Get Location Info
		if( $this->get_option('dbem_locations_enabled') ){
			// determine location type, with backward compatibility considerations for those overriding the location forms
			$location_type = isset($_POST['location_type']) ? sanitize_key($_POST['location_type']) : 'location';
			if( !empty($_POST['no_location']) ) $location_type = 0; //backwards compat
			if( $location_type == 'location' && empty($_POST['location_id']) && $this->get_option('dbem_use_select_for_locations')) $location_type = 0; //backward compat
			// assign location data
			if( $location_type === 0 || $location_type === '0' ){
				// no location
				$this->location_id = 0;
				$this->event_location_type = null;
			}elseif( $location_type == 'location' && EM_Locations::is_enabled() ){
				// a physical location, old school
				$this->event_location_type = null; // if location resides in locations table, location type is null since we have a location_id table value
				if(  !empty($_POST['location_id']) && is_numeric($_POST['location_id']) ){
					// we're using a previously created location
					$this->location_id = absint($_POST['location_id']);
				}else{
					$this->location_id = null;
					//we're adding a new location place, so create an empty location and populate
					$this->get_location()->get_post(false);
					$this->get_location()->post_content = ''; //reset post content, as it'll grab the event description otherwise
				}
			}else{
				// we're dealing with an event location such as a url or webinar
				$this->location_id = null; // no location ID
				if( $this->event_id && $this->has_event_location() && $location_type != $this->event_location_type ){
					// if we're changing location types, then we'll delete all the previous data upon saving
					$this->event_location_deleted = $this->event_location;
				}
				$this->event_location_type = $location_type;
				if( Event_Locations::is_enabled($location_type) ){
					$this->get_event_location()->get_post();
				}
			}
		}else{
			$this->location_id = 0;
			$this->event_location_type = null;
		}
		
		// Bookings - part 2
		if( !$preview_autosave && $can_manage_bookings && $this->event_rsvp ){
			//get tickets only if event is new, non-recurring, or recurring but specifically triggered to reschedule by user
			$recurrence_nonce = $this->is_recurring( true ) && !empty( $_REQUEST['modify_recurring_tickets'] ) && wp_verify_nonce( $_REQUEST['modify_recurring_tickets'], 'modify_recurring_tickets' );
			if( !$this->is_recurring( true ) || empty($this->event_id) || $recurrence_nonce || !empty($just_enabled_bookings) ){
				$this->get_bookings()->get_tickets()->get_post();
			}
			$this->rsvp_end = null;
			//RSVP cuttoff TIME is set up above where start/end times are as well
			if( $this->get_option('dbem_bookings_tickets_single') && count($this->get_tickets()->tickets) == 1 ){
				//single ticket mode will use the ticket end date/time as cut-off date/time, regular event cut-off fields are hidden in this UI mode
		        $EM_Ticket = $this->get_tickets()->get_first();
		        $this->event_rsvp_date = null;
				if ( !empty($EM_Ticket->end) ) {
					$this->event_rsvp_date = $EM_Ticket->end()->getDate();
					$this->event_rsvp_time = $EM_Ticket->end()->getTime();
				} else {
					//no default ticket end time, so make it default to event start date/time
					$this->event_rsvp_date = $this->event_start_date;
					$this->event_rsvp_time = $this->event_start_time;
					if ( $this->event_all_day && empty( $_POST['event_rsvp_date'] ) ) {
						//all-day events start at 0 hour
						$this->event_rsvp_time = '00:00:00';
					}
				}
		    }else{
				// if no rsvp cut-off date supplied, make it the event start date
				$this->event_rsvp_date = ( !empty($_POST['event_rsvp_date']) && preg_match('/^\d{4}-\d{2}-\d{2}$/', $_POST['event_rsvp_date']) ) ? sanitize_text_field($_POST['event_rsvp_date']) : $this->event_start_date;
				// if no specificed time, default to event start time
				if ( empty($_POST['event_rsvp_time']) ) $this->event_rsvp_time = $this->event_start_time;
		    }
		    //reset EM_DateTime object
			$this->rsvp_end = null;
			$this->event_spaces = ( isset($_POST['event_spaces']) ) ? absint($_POST['event_spaces']):0;
			$this->event_rsvp_spaces = ( isset($_POST['event_rsvp_spaces']) ) ? absint($_POST['event_rsvp_spaces']):0;
			// if recurring we save booking data to recurrences too
			if ( $this->is_recurring( true ) ) {
				//recurring events may have a cut-off date x days before or after the recurrence start dates, recurrence cut-off dates are calculated in recurrence sets according to these settings
				$this->recurrence_rsvp_days = null;
				if( get_option('dbem_bookings_tickets_single') && count($this->get_tickets()->tickets) == 1 ){
					//if in single ticket mode then ticket cut-off date determines event cut-off date
					$EM_Ticket = $this->get_tickets()->get_first();
					if( !empty($EM_Ticket->ticket_meta['recurrences']) ){
						$this->recurrence_rsvp_days = $EM_Ticket->ticket_meta['recurrences']['end_days'];
						$this->event_rsvp_time = $EM_Ticket->ticket_meta['recurrences']['end_time'];
					}
				}else{
					if( array_key_exists('recurrence_rsvp_days', $_POST) ){
						if( !empty($_POST['recurrence_rsvp_days_when']) && $_POST['recurrence_rsvp_days_when'] == 'after' ){
							$this->recurrence_rsvp_days = absint($_POST['recurrence_rsvp_days']);
						}else{ //by default the start date is the point of reference
							$this->recurrence_rsvp_days = absint($_POST['recurrence_rsvp_days']) * -1;
						}
					}
				}
				//create timestamps and set rsvp date/time for a normal event
				if( !is_numeric($this->recurrence_rsvp_days) ){
					//falback in case nothing gets set for rsvp cut-off
					$this->event_rsvp_date = $this->event_rsvp_time = $this->rsvp_end = null;
				}else{
					$this->event_rsvp_date = $this->start()->copy()->modify($this->recurrence_rsvp_days.' days')->getDate();
				}
				$this->get_recurrence_sets()->get_post_bookings();
			}
		}
		
		//Sort out event attributes - note that custom post meta now also gets inserted here automatically (and is overwritten by these attributes)
		global $allowedtags;
		if($this->get_option('dbem_attributes_enabled')){
			if( !is_array($this->event_attributes) ){ $this->event_attributes = array(); }
			$event_available_attributes = !empty($event_available_attributes) ? $event_available_attributes : em_get_attributes(); //we use this in locations, no need to repeat if needed
			if( !empty($_POST['em_attributes']) && is_array($_POST['em_attributes']) ){
				foreach($_POST['em_attributes'] as $att_key => $att_value ){
					if( (in_array($att_key, $event_available_attributes['names']) || array_key_exists($att_key, $this->event_attributes) ) ){
						$this->event_attributes[$att_key] = '';
						$att_vals = isset($event_available_attributes['values'][$att_key]) ? count($event_available_attributes['values'][$att_key]) : 0;
						if( $att_value != '' ){
							if( $att_vals <= 1 || ($att_vals > 1 && in_array($att_value, $event_available_attributes['values'][$att_key])) ){
								// Sanitize free-text attribute values based on capability. Users without unfiltered_html (e.g. anonymous submitters, subscribers) must not be allowed to store raw HTML — this is the XSS vector for anonymous event submissions.
								if( $att_vals <= 1 && !current_user_can('unfiltered_html') ){
									$this->event_attributes[$att_key] = wp_unslash(wp_kses($att_value, $allowedtags));
								}else{
									$this->event_attributes[$att_key] = wp_unslash($att_value);
								}
							}
						}
						if( $att_value == '' && $att_vals > 1){
							$this->event_attributes[$att_key] = wp_unslash(wp_kses($event_available_attributes['values'][$att_key][0], $allowedtags));
						}
					}
				}
			}
		}
		// get other event attributes, we may want to
		$other_event_attributes = apply_filters('em_event_get_post_meta_other_attributes', array(), $this);
		foreach( $other_event_attributes as $event_attribute ){
			if( isset($_POST[$event_attribute]) ){
				$this->event_attributes[$event_attribute] = wp_unslash(wp_kses($_POST[$event_attribute], $allowedtags));
			}
		}
		
		//group id
		$this->group_id = (!empty($_POST['group_id']) && is_numeric($_POST['group_id'])) ? absint($_POST['group_id']):0;

		//event language
		if( EM_ML::$is_ml && !empty($_POST['event_language']) && array_key_exists($_POST['event_language'], EM_ML::$langs) ){
			$this->event_language = $_POST['event_language'];
		}
		//categories in MS GLobal
		if(EM_MS_GLOBAL && !is_main_site() && $this->get_option('dbem_categories_enabled') ){
			$this->get_categories()->get_post(); //it'll know what to do
		}
		$this->compat_keys(); //compatability
		return apply_filters('em_event_get_post_meta', count($this->errors) == 0, $this);
	}
	
	function validate(){
		$validate_post = true;
		if( empty($this->event_name) ){
			$validate_post = false; 
			$this->add_error( sprintf(__("%s is required.", 'events-manager'), __('Event name','events-manager')) );
		}
		//anonymous submissions and guest basic info
		if( !empty($this->event_owner_anonymous) ){
			if( !is_email($this->event_owner_email) ){
				$this->add_error( sprintf(__("%s is required.", 'events-manager'), __('A valid email','events-manager')) );
			}
			if( empty($this->event_owner_name) ){
				$this->add_error( sprintf(__("%s is required.", 'events-manager'), __('Your name','events-manager')) );
			}
		}
		$validate_tickets = true; //must pass if we can't validate bookings
		if( $this->can_manage('manage_bookings','manage_others_bookings') ){
		    $validate_tickets = $this->get_bookings()->get_tickets()->validate();
		}
		$validate_image = $this->image_validate();
		$validate_meta = $this->validate_meta();
		return apply_filters('em_event_validate', $validate_post && $validate_image && $validate_meta && $validate_tickets, $this );		
	}
	
	function validate_meta(){
		$missing_fields = Array ();
		foreach ( array('event_start_date') as $field ) {
			if ( $this->$field == "") {
				$missing_fields[$field] = $field;
			}
		}
		if( preg_match('/\d{4}-\d{2}-\d{2}/', $this->event_start_date) && preg_match('/\d{4}-\d{2}-\d{2}/', $this->event_end_date) ){
			if( $this->start()->getTimestamp() > $this->end()->getTimestamp() ){
				$this->add_error(__('Events cannot start after they end.','events-manager'));
			}elseif( $this->is_recurring( true ) && $this->start()->getTimestamp() > $this->end()->getTimestamp() ){
				$this->add_error(__('Events cannot start after they end.','events-manager').' '.__('For recurring events that end the following day, ensure you make your event last 1 or more days.'));
			}
		}else{
			if( !empty($missing_fields['event_start_date']) ) { unset($missing_fields['event_start_date']); }
			if( !empty($missing_fields['event_end_date']) ) { unset($missing_fields['event_end_date']); }
			$this->add_error(__('Dates must have correct formatting. Please use the date picker provided.','events-manager'));
		}
		if ( !$this->get_timeranges()->validate() ) {
			$this->add_error( $this->get_timeranges()->errors );
		}
		if( $this->event_rsvp ){
		    if( !$this->get_bookings()->get_tickets()->validate() ){
		        $this->add_error($this->get_bookings()->get_tickets()->get_errors());
		    }
		    if( !empty($this->event_rsvp_date) && !preg_match('/\d{4}-\d{2}-\d{2}/', $this->event_rsvp_date) ){
				$this->add_error(__('Dates must have correct formatting. Please use the date picker provided.','events-manager'));
		    }
		}
		if( $this->get_option('dbem_locations_enabled') ){
			if( $this->location_id === 0 && $this->get_option('dbem_require_location',true) ){
				// no location chosen, yet we require a location
				$this->add_error(__('No location associated with this event.', 'events-manager'));
			}elseif( $this->has_location() ){
				// physical location
				if( empty($this->location_id) && !$this->get_location()->validate() ){
					// new location doesn't validate
					$this->add_error($this->get_location()->get_errors());
				}elseif( !empty($this->location_id) && !$this->get_location()->location_id ){
					// non-existent location selected
					$this->add_error( __('Please select a valid location.', 'events-manager') );
				}
			}elseif( $this->has_event_location() ){
				// event location, validation applies errors directly to $this
				$this->get_event_location()->validate();
			}
		}
		if ( count($missing_fields) > 0){
			// TODO Create friendly equivelant names for missing fields notice in validation
			$this->add_error( __( 'Missing fields: ', 'events-manager') . implode ( ", ", $missing_fields ) . ". " );
		}
		if ( $this->is_recurring( true ) ){
			// An 'on' recurrence lists its dates explicitly instead of spanning a range, so a set holding one date legitimately has start == end. Recurrence_Set::validate() still rejects a genuinely inverted range.
			$Primary_Set = $this->get_recurrence_set();
		    if( ( !$Primary_Set || $Primary_Set->recurrence_freq !== 'on' ) && ( $this->event_end_date == "" || $this->event_end_date == $this->event_start_date ) ){
		        $this->add_error( __( 'Since the event is recurring, you must specify an event end date greater than the start date.', 'events-manager'));
		    }
			if ( !$this->get_recurrence_sets()->validate() ) {
				$this->add_error( $this->get_recurrence_sets()->get_errors() );
			}
		}
		return apply_filters('em_event_validate_meta', count($this->errors) == 0, $this );
	}
	
	/**
	 * Will save the current instance into the database, along with location information if a new one was created and return true if successful, false if not.
	 * Will automatically detect whether it's a new or existing event. 
	 * @return boolean
	 */
	function save() {
		global $wpdb, $current_user, $blog_id, $EM_SAVING_EVENT;
		$EM_SAVING_EVENT = true; //this flag prevents our dashboard save_post hooks from going further
		if ( $this->is_recurrence() && !$this->duplicating_event ) {
			// not repeated event, but a recurrence of a recurring event - no post saving done here
			$result = true;
		} else {
			if( !$this->can_manage('edit_events', 'edit_others_events') && !( $this->get_option('dbem_events_anonymous_submissions') && empty($this->event_id)) ){
				//unless events can be submitted by an anonymous user (and this is a new event), user must have permissions.
				return apply_filters('em_event_save', false, $this);
			}
			//start saving process
			do_action('em_event_save_pre', $this);
			// programmatic saves (imports, REST, add-ons) never run get_post(), which is where these are otherwise decided, and a NULL of either excludes the event from every listing query
			if( empty($this->event_archetype) ){
				$this->event_archetype = Archetypes::get_from_cpt( $this->post_type ) ?: EM_POST_TYPE_EVENT;
			}
			if( empty($this->event_type) ){
				$this->event_type = $this->is_repeating() ? 'repeating' : 'single';
			}
			$post_array = array();
			//Deal with updates to an event
			if( !empty($this->post_id) ){
				//get the full array of post data so we don't overwrite anything.
				if( !empty($this->blog_id) && is_multisite() ){
					$post_array = (array) get_blog_post($this->blog_id, $this->post_id);
				}else{
					$post_array = (array) get_post($this->post_id);
				}
			}
			//Overwrite new post info
			$post_array['post_type'] = $this->is_repeating() ? 'event-recurring' : EM_POST_TYPE_EVENT;
			$post_array['post_title'] = $this->event_name;
			$post_array['post_content'] = !empty($this->post_content) ? $this->post_content : '';
			$post_array['post_excerpt'] = $this->post_excerpt;
			//decide on post status
			if( empty($this->force_status) ){
				if( count($this->errors) == 0 ){
					$post_array['post_status'] = ( $this->can_manage('publish_events','publish_events') ) ? 'publish':'pending';
				}else{
					$post_array['post_status'] = 'draft';
				}
			}else{
			    $post_array['post_status'] = $this->force_status;
			}
			//anonymous submission only
			if( !is_user_logged_in() && $this->get_option('dbem_events_anonymous_submissions') && empty($this->event_id) ){
				$post_array['post_author'] = $this->get_option('dbem_events_anonymous_user');
				if( !is_numeric($post_array['post_author']) ) $post_array['post_author'] = 0;
			}
			//Save post and continue with meta
			$post_id = wp_insert_post($post_array);
			$post_save = false;
			$meta_save = false;
			if( !is_wp_error($post_id) && !empty($post_id) ){
				$post_save = true;
				//refresh this event with wp post info we'll put into the db
				$post_data = get_post($post_id);
				$this->post_id = $this->ID = $post_id;
				$this->post_type = $post_data->post_type;
				$this->event_slug = $post_data->post_name;
				$this->event_owner = $post_data->post_author;
				$this->post_status = $post_data->post_status;
				$this->get_status();
				//Categories
				if( $this->get_option('dbem_categories_enabled') ){
	                $this->get_categories()->event_id = $this->event_id;
	                $this->categories->post_id = $this->post_id;
	                $this->categories->save();
				}
				//anonymous submissions should save this information
				if( !empty($this->event_owner_anonymous) ){
					update_post_meta($this->post_id, '_event_owner_anonymous', 1);
					update_post_meta($this->post_id, '_event_owner_name', $this->event_owner_name);
					update_post_meta($this->post_id, '_event_owner_email', $this->event_owner_email);
				}
				//save the image, errors here will surface during $this->save_meta()
				$this->image_upload();
				//now save the meta
				$meta_save = $this->save_meta();
			}
			$result = $meta_save && $post_save;
			if($result) $this->load_postdata($post_data, $blog_id); //reload post info
			//do a dirty update for location too if it's not published
			if( $this->is_published() && !empty($this->location_id) ){
				$EM_Location = $this->get_location();
				if( $EM_Location->location_status !== 1 ){
					//let's also publish the location
					$EM_Location->set_status(1, true);
				}
			}
		}
		$return = apply_filters('em_event_save', $result, $this);
		$EM_SAVING_EVENT = false;
		//reload post data and add this event to the cache, after any other hooks have done their thing
		//cache refresh when saving via admin area is handled in EM_Event_Post_Admin::save_post/refresh_cache
		if( $result && $this->is_published() ){
			//we won't depend on hooks, if we saved the event and it's still published in its saved state, refresh the cache regardless
			$this->load_postdata($this);
			//postless events are never object-cached (matches the load path guard) and a NULL post_id must not become a cache key
			if( $this->post_id ){
				// a clone, because saving a new event empties its bookings child and a persistent cache would store that emptied array instead of rebuilding it on load
				wp_cache_set( $this->get_event_uid(), clone $this, 'em_events');
				wp_cache_set( $this->post_id, $this->get_event_uid(), 'em_events_ids');
			}
		}
		return $return;
	}
	
	// only a legacy utf8/utf8mb3 column needs wp_encode_emoji(), a real utf8mb4 column stores emoji natively and encoding it would double-escape on redisplay. MySQL 8 reports the legacy charset as utf8mb3, which wp_insert_post()'s own check misses
	private function encode_emoji_fields( $event_array ) {
		global $wpdb;
		foreach ( array('event_name', 'post_content') as $field ) {
			$charset = $wpdb->get_col_charset(EM_EVENTS_TABLE, $field);
			if ( isset($event_array[$field]) && is_string($event_array[$field]) && ($charset === 'utf8' || $charset === 'utf8mb3') ) {
				$event_array[$field] = wp_encode_emoji($event_array[$field]);
			}
		}
		return $event_array;
	}
	
	function save_meta(){
		global $wpdb, $EM_SAVING_EVENT;
		$EM_SAVING_EVENT = true;
		//sort out multisite blog id if appliable
		if( is_multisite() && empty($this->blog_id) ){
			$this->blog_id = get_current_blog_id();
		}
		//trigger setting of event_end and event_start in case it hasn't been set already
		$this->start();
		$this->end();
		//continue with saving if permissions allow
		if( ( $this->get_option('dbem_events_anonymous_submissions') && empty($this->event_id)) || $this->can_manage('edit_events', 'edit_others_events') ){
			do_action('em_event_save_meta_pre', $this);
			//language default
			if( !$this->event_language ) $this->event_language = EM_ML::$current_language;
			//first save location
			if( empty($this->location_id) && !($this->location_id === 0 && !$this->get_option('dbem_require_location',true)) ){
				//pass language on
				$this->get_location()->location_language = $this->event_language;
			    //proceed with location save
				if( !$this->get_location()->save() ){ //soft fail
					global $EM_Notices;
					if( !empty($this->get_location()->location_id) ){
						$EM_Notices->add_error( __('There were some errors saving your location.','events-manager').' '.sprintf(__('It will not be displayed on the website listings, to correct this you must <a href="%s">edit your location</a> directly.'),$this->get_location()->output('#_LOCATIONEDITURL')), true);
					}
				}
				if( !empty($this->location->location_id) ){ //only case we don't use get_location(), since it will fail as location has an id, whereas location_id isn't set in this object
					$this->location_id = $this->location->location_id;
				}
			}
			//Update Post Meta
			$current_meta_values = $this->get_event_meta();
			foreach( $this->fields as $key => $field_info ){
				//certain keys will not be saved if not needed, including flags with a 0 value. Older databases using custom WP_Query calls will need to use an array of meta_query items using NOT EXISTS - OR - value=0
				if( !in_array($key, $this->post_fields) && $key != 'event_attributes' ){
					//ignore certain fields and delete if not new
					$save_meta_key = true;
					if( !EM_ML::$is_ml && $key == 'event_language' ) $save_meta_key = false;
					$ignore_zero_keys = array('location_id', 'group_id', 'event_all_day', 'event_parent', 'event_translation');
					if( in_array($key, $ignore_zero_keys) && empty($this->$key) ) $save_meta_key = false;
					if( $key == 'blog_id' ) $save_meta_key = false; //not needed, given postmeta is stored on the actual blog table in MultiSite
					//we don't need rsvp info if rsvp is not set, including the RSVP flag too
					if( empty($this->event_rsvp) && in_array($key, array('event_rsvp','event_rsvp_date', 'event_rsvp_time', 'event_rsvp_spaces', 'event_spaces')) ) $save_meta_key = false;
					//save key or ignore/delete key
					if( $save_meta_key ){
						update_post_meta($this->post_id, '_'.$key, $this->$key);
					}elseif( array_key_exists('_'.$key, $current_meta_values) ){
						//delete if this event already existed, in case this event already had the values before
						delete_post_meta($this->post_id, '_'.$key);
					}
				}elseif( array_key_exists('_'.$key, $current_meta_values) && $key != 'event_attributes' ){ //we should delete event_attributes, but maybe something else uses it without us knowing
					delete_post_meta($this->post_id, '_'.$key);
				}
			}
			if( $this->get_option('dbem_attributes_enabled') ){
				//attributes get saved as individual keys
				$atts = em_get_attributes(); //get available attributes that EM manages
				$this->event_attributes = EM_Object::maybe_unserialize($this->event_attributes);
				foreach( $atts['names'] as $event_attribute_key ){
					if( array_key_exists($event_attribute_key, $this->event_attributes) && $this->event_attributes[$event_attribute_key] != '' ){
						update_post_meta($this->post_id, $event_attribute_key, $this->event_attributes[$event_attribute_key]);
					}else{
						delete_post_meta($this->post_id, $event_attribute_key);
					}
				}
			}
			// save other event attributes, we may want to
			$other_event_attributes = apply_filters('em_event_save_post_meta_other_attributes', array(), $this);
			foreach( $other_event_attributes as $key ){
				if( isset($this->event_attributes[$key]) ) {
					update_post_meta( $this->post_id, '_'.$key, $this->event_attributes[$key]);
				}else{
					delete_post_meta( $this->post_id, '_'.$key);
				}
			}
			//update timestamps, dates and times
			update_post_meta($this->post_id, '_event_start_local', $this->start()->getDateTime());
			update_post_meta($this->post_id, '_event_end_local', $this->end()->getDateTime());
			//Deprecated, only for backwards compatibility, these meta fields will eventually be deleted!
			$site_data = get_site_option('dbem_data');
			if( !empty($site_data['updates']['timezone-backcompat']) ){
				update_post_meta($this->post_id, '_start_ts', str_pad($this->start()->getTimestamp(), 10, 0, STR_PAD_LEFT));
				update_post_meta($this->post_id, '_end_ts', str_pad($this->end()->getTimestamp(), 10, 0, STR_PAD_LEFT));
			}
			//sort out event status			
			$result = count($this->errors) == 0;
			$this->get_status();
			$this->event_status = ($result) ? $this->event_status:null; //set status at this point, it's either the current status, or if validation fails, null
			//Save to em_event table
			$event_array = $this->to_array(true);
			unset($event_array['event_id']);
			//decide whether or not event is private at this point
			$event_array['event_private'] = ( $this->post_status == 'private' ) ? 1:0;
			//check if event truly exists, meaning the event_id is actually a valid event id
			if( !empty($this->event_id) ){
				$blog_condition = '';
				if( !empty($this->orphaned_event ) && !empty($this->post_id) ){
				    //we're dealing with an orphaned event in wp_em_events table, so we want to update the post_id and give it a post parent 
				    $event_truly_exists = true;
				}else{
					if( EM_MS_GLOBAL ){
					    if( is_main_site() ){
					        $blog_condition = " AND (blog_id='".get_current_blog_id()."' OR blog_id IS NULL)";
					    }else{
							$blog_condition = " AND blog_id='".get_current_blog_id()."' ";
					    }
					}
					$event_truly_exists = $wpdb->get_var('SELECT post_id FROM '.EM_EVENTS_TABLE." WHERE event_id={$this->event_id}".$blog_condition) == $this->post_id;
				}
			}else{
				$event_truly_exists = false;
			}
			//save all the meta
			if( empty($this->event_id) || !$event_truly_exists ){
				$this->previous_status = 0; //for sure this was previously status 0
				$this->event_date_created = $event_array['event_date_created'] = current_time('mysql');
				$event_array = $this->encode_emoji_fields( $event_array );
				if ( !$wpdb->insert(EM_EVENTS_TABLE, $event_array) ){
					$this->log_db_error( __('event','events-manager'), EM_EVENTS_TABLE );
				}else{
					//success, so link the event with the post via an event id meta value for easy retrieval
					$this->event_id = $wpdb->insert_id;
					update_post_meta($this->post_id, '_event_id', $this->event_id);
					$this->feedback_message = sprintf(__('Successfully saved %s','events-manager'),__('Event','events-manager'));
					$this->just_added_event = true; //make an easy hook
					$this->get_bookings()->bookings = array(); //set bookings array to 0 to avoid an extra DB query
					do_action('em_event_save_new', $this);
				}
			}else{
			    $event_array['post_content'] = $this->post_content; //in case the content was removed, which is acceptable
			    $this->get_previous_status();
				$this->event_date_modified = $event_array['event_date_modified'] = current_time('mysql');
				$event_array = $this->encode_emoji_fields( $event_array );
				if ( $wpdb->update(EM_EVENTS_TABLE, $event_array, array('event_id'=>$this->event_id) ) === false ){
					$this->log_db_error( __('event','events-manager'), EM_EVENTS_TABLE );
				}else{
					//Also set the status here if status != previous status
					if( $this->previous_status != $this->get_status() ) $this->set_status($this->get_status());
					$this->feedback_message = sprintf(__('Successfully saved %s','events-manager'),__('Event','events-manager'));
				}

				//check anonymous submission information
    			if( !empty($this->event_owner_anonymous) && $this->get_option('dbem_events_anonymous_user') != $this->event_owner ){
    			    //anonymous user owner has been replaced with a valid wp user account, so we remove anonymous status flag but leave email and name for future reference
    			    update_post_meta($this->post_id, '_event_owner_anonymous', 0);
    			}elseif( $this->get_option('dbem_events_anonymous_submissions') && $this->get_option('dbem_events_anonymous_user') == $this->event_owner && is_email($this->event_owner_email) && !empty($this->event_owner_name) ){
    			    //anonymous user account has been reinstated as the owner, so we can restore anonymous submission status
    			    update_post_meta($this->post_id, '_event_owner_anonymous', 1);
    			}
			}
			//update event location via post meta
			if( $this->has_event_location() ){
				$this->get_event_location()->save();
			}elseif( !empty($this->event_location) ){
				// we previously had an event location and then switched to no location or a physical location
				$this->event_location->delete();
			}
			if( !empty($this->event_location_deleted) ){
				// we've switched event location types
				$this->event_location_deleted->delete();
			}
			//Add/Delete Tickets
			if( $this->just_disabled_rsvp ){
				$this->get_bookings()->delete();
				$this->get_tickets()->delete();
			}elseif( $this->can_manage('manage_bookings','manage_others_bookings') ){
				if( !$this->get_bookings()->get_tickets()->save() ){
					$this->add_error( $this->get_bookings()->get_tickets()->get_errors() );
				}
			}
			$result = count($this->errors) == 0;
			//deal with categories
			if( $this->get_option('dbem_categories_enabled') ){
				if( EM_MS_GLOBAL ){ //EM_MS_Globals should look up original blog
					//If we're saving event categories in MS Global mode, we'll add them here, saving by term id (cat ids are gone now)
	                if( !is_main_site() ){
	                    $this->get_categories()->save(); //it'll know what to do
	                }else{
	                    $this->get_categories()->save_index(); //just save to index, we assume cats are saved in $this->save();
	                }
				}elseif( $this->get_option('dbem_default_category') > 0 ){
					//double-check for default category in other instances
					if( count($this->get_categories()) == 0 ){
						$this->get_categories()->save(); //let the object deal with this...
					}
				}
			}
		    $this->compat_keys(); //compatability keys, loaded before saving recurrences
			//build recurrences if needed
			if( $this->is_recurring( true ) ) {
				$this->get_recurrence_sets()->event_id = $this->event_id;
				$result = $result && $this->get_recurrence_sets()->save();
				if ( $result && ( $this->is_published() || $this->post_status == 'future' ) ) { //only save events if recurring event validates and is published or set for future
					global $EM_EVENT_SAVE_POST;
					//If we're in WP Admin and this was called by EM_Event_Post_Admin::save_post, don't save here, it'll be done later in {@see EM_Event_Recurring_Post_Admin::save_post()}
					if( empty($EM_EVENT_SAVE_POST) ){
						if( $this->just_added_event ) $this->get_recurrence_sets()->reschedule = true; // force a reschedule since it's first time
					    if( !$this->get_recurrence_sets()->save_recurrences() ){
							$this->add_error(__ ( 'Something went wrong with the recurrence update...', 'events-manager'). __ ( 'There was a problem saving the recurring events.', 'events-manager'));
					    }
					}
				}
			} else if ( !empty($this->timeslots ) && $this->get_option('dbem_timeslots_enabled', true) ) {
				// save the timeslots for this event, it's OK if records are created because they won't show up if master event is not published
				$this->get_timeranges()->save();
			}
			if( !empty($this->just_added_event) ){
				do_action('em_event_added', $this);
			}
			// set active statuses if changed
			if( $this->event_active_status === 0 && $this->previous_active_status !== 0 ){
				$this->cancel();
			}
		}
		$EM_SAVING_EVENT = false;
		return apply_filters('em_event_save_meta', count($this->errors) == 0, $this);
	}
	
	/**
	 * Duplicates this event and returns the duplicated event. Will return false if there is a problem with duplication.
	 * @return EM_Event
	 */
	function duplicate(){
		global $wpdb;
		//First, duplicate.
		if( $this->can_manage('edit_events','edit_others_events') ){
			$EM_Event = clone $this;
			if( $this->get_option('dbem_categories_enabled') ) $EM_Event->get_categories(); //before we remove event/post ids
			$EM_Event->get_bookings()->get_tickets(); //in case this wasn't loaded and before we reset ids
			$EM_Event->event_id = null;
			$EM_Event->timeslot_id = null;
			$EM_Event->post_id = null;
			$EM_Event->ID = null;
			$EM_Event->post_name = '';
			$EM_Event->location_id = (empty($EM_Event->location_id)  && !$this->get_option('dbem_require_location')) ? 0:$EM_Event->location_id;
			$EM_Event->get_bookings()->event_id = null;
			$EM_Event->get_bookings()->get_tickets()->event_id = null;
			//if bookings reset ticket ids and duplicate tickets
			foreach($EM_Event->get_bookings()->get_tickets()->tickets as $EM_Ticket){
				$EM_Ticket->ticket_id = null;
				$EM_Ticket->event_id = null;
			}
			do_action('em_event_duplicate_pre', $EM_Event, $this);
			$EM_Event->duplicated = true;
			$EM_Event->force_status = 'draft';
			// Is this a repeated/recurring event? If so, we need to save recurrence patterns too
			if ( $this->is_recurring( true ) ) {
				$EM_Event->recurrence_sets = clone $this->get_recurrence_sets();
				foreach ( $EM_Event->recurrence_sets->include as $Recurrence_Set ) {
					$Recurrence_Set->recurrence_set_id = null;
				}
				foreach ( $EM_Event->recurrence_sets->exclude as $Recurrence_Set ) {
					$Recurrence_Set->recurrence_set_id = null;
				}
			}
			// go through timeranges, clone data, remove timerange/group ids and enable editing for saving
			$EM_Event->timeslots = clone $this->get_timeranges();
			foreach ( $EM_Event->get_timeranges() as $Timerange ) {
				foreach ( $Timerange->get_timeslots() as $Timeslot ) {
					$Timeslot->timerange_id = null;
					$Timeslot->event = $EM_Event;
				}
				// do this after so we get the timeslot data first
				$EM_Event->timeslots->set_group_id( null );
				$Timerange->timerange_id = null;
			}
			$EM_Event->timeslots->allow_edit = true;
			$EM_Event->timeslots->event = $EM_Event;
			// now save the event and follow through
			$EM_Event->duplicating_event = true; // set special flag so we don't have problems with recurrences not saving as a new event
			if( $EM_Event->save() ){
				$EM_Event->feedback_message = sprintf(__("%s successfully duplicated.", 'events-manager'), __('Event','events-manager'));
				//save tags here - eventually will be moved into part of $this->save();
				if( $this->get_option('dbem_tags_enabled') ){
					$EM_Tags = new EM_Tags($this);
					$EM_Tags->event_id = $EM_Event->event_id;
					$EM_Tags->post_id = $EM_Event->post_id;
					$EM_Tags->save();
				}
			 	//other non-EM post meta inc. featured image
				$event_meta = $this->get_event_meta($this->blog_id);
				$new_event_meta = $EM_Event->get_event_meta($EM_Event->blog_id);
				$event_meta_inserts = array();
				$event_meta_values = array();
			 	//Get custom fields and post meta - adapted from $this->load_post_meta()
			 	foreach($event_meta as $event_meta_key => $event_meta_vals){
			 		if( $event_meta_key == '_wpas_' ) continue; //allow JetPack Publicize to detect this as a new post when published
			 		if( is_array($event_meta_vals) ){
			 		    if( !array_key_exists($event_meta_key, $new_event_meta) &&  !in_array($event_meta_key, array('_event_attributes', '_edit_last', '_edit_lock', '_event_owner_name','_event_owner_anonymous','_event_owner_email')) ){
				 			foreach($event_meta_vals as $event_meta_val){
				 			    $event_meta_inserts[] = '(%d, %s, %s)';
				 			    array_push($event_meta_values, $EM_Event->post_id, $event_meta_key, $event_meta_val);
				 			}
			 			}
			 		}
			 	}
			 	//save in one SQL statement — meta keys/values come from stored post meta and must be parameterised (second-order SQLi otherwise)
			 	if( !empty($event_meta_inserts) ){
			 		$wpdb->query( $wpdb->prepare('INSERT INTO '.$wpdb->postmeta." (post_id, meta_key, meta_value) VALUES ".implode(', ', $event_meta_inserts), $event_meta_values) );
			 	}
				if( array_key_exists('_event_approvals_count', $event_meta) ) update_post_meta($EM_Event->post_id, '_event_approvals_count', 0);
				//copy anything from the em_meta table too
				$wpdb->query('INSERT INTO '.EM_META_TABLE." (object_id, meta_key, meta_value) SELECT '{$EM_Event->event_id}', meta_key, meta_value FROM ".EM_META_TABLE." WHERE object_id='{$this->event_id}'");
			 	//set event to draft status
				return apply_filters('em_event_duplicate', $EM_Event, $this);
			}
		}
		//TODO add error notifications for duplication failures.
		return apply_filters('em_event_duplicate', false, $this);;
	}
	
	function duplicate_url( $raw = false ){
		$url = preg_match('/^https?\:\/\//', $raw ) ? $raw : false;
	    $url = add_query_arg(array('action'=>'event_duplicate', 'event_id'=>$this->get_event_uid(), '_wpnonce'=> wp_create_nonce('event_duplicate_'.$this->get_event_uid())), $url);
	    $url = apply_filters('em_event_duplicate_url', $url, $this);
	    $url = $raw === false ? esc_url_raw($url) : esc_url($url);
	    return $url;
	}

	/**
	 * Delete whole event, including bookings, tickets, etc.
	 * @param boolean $force_delete
	 * @return boolean
	 */
	function delete( $force_delete = false ){
		if( $this->can_manage('delete_events', 'delete_others_events') ){
		    if( !is_admin() ){
				include_once('em-event-post-admin.php');
				if( !defined('EM_EVENT_DELETE_INCLUDE') ){
					EM_Event_Post_Admin::init();
					EM_Event_Recurring_Post_Admin::init();
					define('EM_EVENT_DELETE_INCLUDE',true);
				}
		    }
		    do_action('em_event_delete_pre', $this);
			// delete post or just let event meta delete the rest if not an orphan
			if ( $this->post_id ) {
				if ( $force_delete ) {
					$result = wp_delete_post( $this->post_id, $force_delete );
				} else {
					$result = wp_trash_post( $this->post_id );
					if ( !$result && $this->post_status == 'trash' ) {
						//we're probably dealing with a trashed post already, but the event_status is null from < v5.4.1
						$this->set_status( - 1 );
						$result = true;
					}
				}
				if( !$result && !empty($this->orphaned_event) ){
					//this is an orphaned event, so the wp delete posts would have never worked, so we just delete the row in our events table
					$result = $this->delete_meta();
				}
			} else {
				// no post_id associated (such as a recurrence), delete the record directly
				$result = $this->delete_meta();
			}
		}else{
			$result = false;
		}
		return apply_filters('em_event_delete', $result != false, $this);
	}

	function delete_meta(){
		global $wpdb;
		$result = false;
		if( $this->can_manage('delete_events', 'delete_others_events') ){
			do_action('em_event_delete_meta_event_pre', $this);
			$result = $wpdb->query ( $wpdb->prepare("DELETE FROM ". EM_EVENTS_TABLE ." WHERE event_id=%d", $this->event_id) );
			if( $result !== false ){
				$this->get_bookings()->delete();
				$this->get_tickets()->delete();
				$this->get_timeranges()->delete();
				if( $this->has_event_location() ) {
					$this->get_event_location()->delete();
				}
				//Delete the recurrences then this recurrence event
				if( $this->is_recurring( true ) ){
					$result = $this->get_recurrence_sets()->delete(); //was true at this point, so false if fails
				}
				//Delete categories from meta if in MS global mode
				if( EM_MS_GLOBAL ){
					$wpdb->query('DELETE FROM '.EM_META_TABLE.' WHERE object_id='.$this->event_id." AND meta_key='event-category'");
				}
			}
		}
		return apply_filters('em_event_delete_meta', $result !== false, $this);
	}

	/**
	 * @deprecated
	 * @use EM_Event::get_bookings()::delete()
	 * Shortcut function for {@see EM_Event::get_bookings()::delete()}, because using the EM_Bookings requires loading previous bookings, which isn't neceesary.
	 */
	function delete_bookings(){
		global $wpdb;
		do_action('em_event_delete_bookings_pre', $this);
		$result = false;
		if( $this->can_manage('manage_bookings','manage_others_bookings') ){
			$timeslot = '';
			if ( $this->timeslot_id ) {
				$timeslot = ' AND timeslot_id = '. absint( $this->timeslot_id );
			}
			$result_bt = $wpdb->query( $wpdb->prepare("DELETE FROM ".EM_TICKETS_BOOKINGS_TABLE." WHERE booking_id IN (SELECT booking_id FROM ".EM_BOOKINGS_TABLE." WHERE event_id=%d $timeslot)", $this->event_id) );
			$result = $wpdb->query( $wpdb->prepare("DELETE FROM ".EM_BOOKINGS_TABLE." WHERE event_id=%d $timeslot", $this->event_id) );
		}
		return apply_filters('em_event_delete_bookings', $result !== false && $result_bt !== false, $this);
	}

	/**
	 * @deprecated
	 * @use EM_Event::get_bookings()::delete()
	 * Shortcut function for {@see EM_Event::get_bookings()::delete()}, because using the EM_Bookings requires loading previous bookings, which isn't neceesary.
	 */
	function delete_tickets(){
		global $wpdb;
		do_action('em_event_delete_tickets_pre', $this);
		$result = false;
		if( $this->can_manage('manage_bookings','manage_others_bookings') ){
			$timeslot = '';
			if ( $this->timeslot_id ) {
				$timeslot = ' AND timeslot_id = '. absint( $this->timeslot_id );
			}
			$result_bt = $wpdb->query( $wpdb->prepare("DELETE FROM ".EM_TICKETS_BOOKINGS_TABLE." WHERE ticket_id IN (SELECT ticket_id FROM ".EM_TICKETS_TABLE." WHERE event_id=%d $timeslot)", $this->event_id) );
			$result = $wpdb->query( $wpdb->prepare("DELETE FROM ".EM_TICKETS_TABLE." WHERE event_id=%d $timeslot", $this->event_id) );
		}
		return apply_filters('em_event_delete_tickets', $result, $this);
	}
	
	/**
	 * Change the status of the event. This will save to the Database too. 
	 * @param int $status 				A number to change the status to, which may be -1 for trash, 1 for publish, 0 for pending or null if draft.
	 * @param boolean $set_post_status 	If set to true the wp_posts table status will also be changed to the new corresponding status.
	 * @return string
	 */
	function set_status($status, $set_post_status = false){
		global $wpdb;
		//decide on what status to set and update wp_posts in the process
		if( EM_MS_GLOBAL ) switch_to_blog( $this->blog_id );
		if($status === null){
			$set_status='NULL'; //draft post
			if ( $this->post_id ) {
				if ( $set_post_status ) {
					//if the post is trash, don't untrash it!
					$wpdb->update( $wpdb->posts, array ( 'post_status' => 'draft' ), array ( 'ID' => $this->post_id ) );
				}
				$this->post_status = 'draft'; //set post status in this instance
			}
		}elseif( $status == -1 ){ //trashed post
			$set_status = -1;
			if ( $this->post_id ) {
				if ( $set_post_status ) {
					//set the post status of the location in wp_posts too
					$wpdb->update( $wpdb->posts, array ( 'post_status' => $this->post_status ), array ( 'ID' => $this->post_id ) );
				}
				$this->post_status = 'trash'; //set post status in this instance
			}
		}else{
			$set_status = absint($status); //published or pending post
			if ( $this->post_id ) {
				$post_status = apply_filters( 'em_get_post_status', $set_status ? 'publish':'pending', $set_status, $this );
				if( empty($this->post_name) ){
					//published or pending posts should have a valid post slug
					$slug = sanitize_title($this->post_title);
					$this->post_name = wp_unique_post_slug( $slug, $this->post_id, $post_status, EM_POST_TYPE_EVENT, 0);
					$set_post_name = true;
				}
				if( $set_post_status ){
					$wpdb->update( $wpdb->posts, array( 'post_status' => $post_status, 'post_name' => $this->post_name ), array( 'ID' => $this->post_id ) );
				}elseif( !empty($set_post_name) ){
					//if we've added a post slug then update wp_posts anyway
					$wpdb->update( $wpdb->posts, array( 'post_name' => $this->post_name ), array( 'ID' => $this->post_id ) );
				}
				$this->post_status = $post_status;
			}
		}
		if( EM_MS_GLOBAL ) restore_current_blog();
		if ( $this->is_recurring( true ) ) {
			$this->get_recurrence_sets()->set_status_events( $status );
		}
		//save in the wp_em_events table
		$this->get_previous_status();
		$result = $wpdb->query( $wpdb->prepare("UPDATE ".EM_EVENTS_TABLE." SET event_status=$set_status, event_slug=%s WHERE event_id=%d", array($this->post_name, $this->event_id)) );
		$this->get_status(); //reload status
		return apply_filters('em_event_set_status', $result !== false, $status, $this);
	}
	
	public function cancel(){
		return $this->set_active_status( 0 );
	}
	
	public function set_active_status( $active_status ){
		global $wpdb;
		if( is_int($active_status) && $active_status >= 0 ) {
			if ( $this->event_type === 'timeslot' ) {
				$result = $wpdb->update( EM_EVENT_TIMESLOTS_TABLE, array('timeslot_status' => $active_status ), array( 'timeslot_id' => $this->timeslot_id, 'event_id' => $this->event_id ), array('%d'), array('%d', '%d') );
			} else {
				$em_result = $wpdb->update( EM_EVENTS_TABLE, array('event_active_status' => $active_status ), array( 'event_id' => $this->event_id ), array('%d'), array('%d') );
				if( EM_MS_GLOBAL ) switch_to_blog( $this->blog_id );
				$meta_result = $wpdb->update( $wpdb->postmeta, array( 'meta_key' => '_event_active_status', 'meta_value' => $active_status ), array( 'meta_key' => '_event_active_status', 'post_id' => $this->post_id ), array('%s', '%d'), array('%s', '%d') );
				if( EM_MS_GLOBAL ) restore_current_blog();
				$result = $em_result !== false && $meta_result !== false;
			}
			if( $result ){
				$this->previous_active_status = $this->event_active_status;
				$this->event_active_status = $active_status;
				if( $active_status === 0 ) {
					// cancelled event, let's cancel bookings and send out emails (if set)
					if ( $this->get_option( 'dbem_event_cancelled_bookings' ) ) {
						$bookings_array = array(
							$this->get_bookings()->get_bookings(),
							$this->get_bookings()->get_pending_bookings()
						);
						foreach( $bookings_array as $EM_Bookings ) {
							foreach ( $EM_Bookings as $EM_Booking ) {
								$EM_Booking->manage_override = true;
								$EM_Booking->cancel( $this->get_option( 'dbem_event_cancelled_bookings_email' ), array( 'email_admin' => false ) );
							}
						}
					}
					if ( $this->get_option('dbem_event_cancelled_email') ) {
						if( !isset($bookings_array) ) {
							$bookings_array = array(
								$this->get_bookings()->get_bookings(),
								$this->get_bookings()->get_pending_bookings()
							);
						}
						foreach( $bookings_array as $EM_Bookings ) {
							foreach ( $EM_Bookings as $EM_Booking ) {
								$message = array(
									'user' => array(
										'subject' => $this->get_option('dbem_event_cancelled_email_subject'),
										'body' => $this->get_option('dbem_event_cancelled_email_body'),
									),
								);
								$EM_Booking->email_attendee( $message );
							}
						}
					}
				}
			}
			return apply_filters('em_event_set_active_status', $result, $active_status, $this);
		}
		return false;
	}
	
	public function set_timezone( $timezone = false, $preserve_times = true ){
		//reset UTC times and objects so they're recreated with local time and new timezone
		if ( $preserve_times ) {
			$this->event_start = $this->event_end = $this->start = $this->end = $this->rsvp_end = null;
		} else {
			$this->start()->setTimezone( $timezone );
			$this->end()->setTimezone( $timezone );
			$this->rsvp_end()->setTimezone( $timezone );
		}
		$EM_DateTimeZone = EM_DateTimeZone::create($timezone);
		//modify the timezone string name itself
		$this->event_timezone = $EM_DateTimeZone->getValue();
	}

	/**
	 * Gets the timeslots for this event in the DB, returns array of timeslot data, numbered by event_timeslot_id
	 * @return Timeranges
	 */
	public function get_timeranges() {
		if ( !$this->timeslots ) {
			$group_id = 'event_' . $this->event_id;
			$this->timeslots = new Timeranges( $group_id, $this );
		}
		return apply_filters('get_timeranges', $this->timeslots, $this);
	}

	/**
	 * If the event has an event with this timeslot ID, it provides a clone of the current object, or the object itself if it's already the requested timeslot.
	 *
	 * @param $timeslot_id
	 * @throws Exception
	 *
	 * @return EM_Event
	 */
	public function convert_to_timeslot( $timeslot_id, $convert = true ) {
		if ( $this->timeslot_id === $timeslot_id ) {
			return $this;
		}
		$Timeslot = new Timeslot( $timeslot_id, $this );
		if ( $Timeslot->timeslot_id !== (int) $timeslot_id ) {
			throw new Exception( 'Could not find timeslot for this event based on provided ID', 'timeslot_not_found' );
		}
		return apply_filters('convert_to_timeslot', $Timeslot->get_event( $convert ), $this);
	}

	/**
	 * @param $event_id
	 * @param $timeslot_id
	 *
	 * @return EM_Event|static
	 * @throws Exception
	 */
	public static function get_timeslot( $event_id, $timeslot_id ) {
		$EM_Event = em_get_event( $event_id );
		return $EM_Event->convert_to_timeslot( $timeslot_id, false );
	}

	/**
	 * If the event has more than one time range, or rules within the main time range, then this will return true.
	 * Result based on the settings for timeslots, not the actual timeslots saved in the database.
	 * @return bool
	 */
	public function has_timeslots() {
		$is_enabled = $this->get_option('dbem_event_timeranges_enabled');
		return apply_filters('em_event_has_timeslots', $is_enabled && !$this->is_timeslot() && $this->get_timeranges()->has_timeslots() , $this);
	}
	
	public function get_timezone(){
		return $this->start()->getTimezone();
	}
	
	function is_published(){
		if ( $this->is_recurrence() || $this->is_timeslot() ) {
			$published = $this->event_status == 1;
		} else {
			$published = ($this->post_status == 'publish' || $this->post_status == 'private');
		}
		return apply_filters('em_event_is_published', $published, $this);
	}
	
	/**
	 * Whether this event's post is password-protected and the current visitor hasn't unlocked it. Anyone who can manage the event sees it regardless, matching how location map balloons already behave.
	 * @return boolean
	 */
	public function password_required(){
		$required = false;
		if ( !empty($this->post_id) ) {
			// post_password lives in wp_posts, so in MS Global mode the lookup has to happen on the blog that owns the event.
			if ( EM_MS_GLOBAL && !empty($this->blog_id) && get_current_blog_id() != $this->blog_id ) {
				switch_to_blog($this->blog_id);
				$switch_back = true;
			}
			$required = post_password_required( $this->post_id ) && !$this->can_manage('edit_events','edit_others_events');
			if ( !empty($switch_back) ) restore_current_blog();
		}
		return apply_filters('em_event_password_required', $required, $this);
	}

	/**
	 * Whether the current visitor may read this event when it is rendered outside its own permalink, such as by ID in a shortcode. Judged on the WordPress post the event renders from, so postless recurrences and timeslots inherit their parent's visibility, and password-protected events stay hidden until unlocked.
	 * @return boolean
	 */
	public function is_viewable(){
		$EM_Event = $this;
		if ( empty($EM_Event->post_id) && $this->get_parent() ) {
			$EM_Event = $this->get_parent();
		}
		$viewable = false;
		if ( !empty($EM_Event->post_id) ) {
			if ( EM_MS_GLOBAL && !empty($EM_Event->blog_id) && get_current_blog_id() != $EM_Event->blog_id ) {
				switch_to_blog($EM_Event->blog_id);
				$switch_back = true;
			}
			$viewable = ( is_post_publicly_viewable($EM_Event->post_id) || current_user_can('read_post', $EM_Event->post_id) ) && !$EM_Event->password_required();
			if ( !empty($switch_back) ) restore_current_blog();
		}
		return apply_filters('em_event_is_viewable', $viewable, $this);
	}
	
	/**
	 * Returns an EM_DateTime object of the event start date/time in local timezone of event.
	 * @param bool $utc_timezone Returns EM_DateTime with UTC timezone if set to true, returns local timezone by default.
	 * @return EM_DateTime
	 * @see EM_Event::get_datetime()
	 */
	public function start( $utc_timezone = false ){
		return apply_filters('em_event_start', $this->get_datetime('start', $utc_timezone), $this);
	}
	
	/**
	 * Returns an EM_DateTime object of the event end date/time in local timezone of event
	 * @param bool $utc_timezone Returns EM_DateTime with UTC timezone if set to true, returns local timezone by default.
	 * @return EM_DateTime
	 * @see EM_Event::get_datetime()
	 */
	public function end( $utc_timezone = false ){
		return apply_filters('em_event_end', $this->get_datetime('end', $utc_timezone), $this);
	}
	
	/**
	 * Returns an EM_DateTime representation of when bookings close in local event timezone. If no valid date defined, event start date/time will be used.
	 * @param bool $utc_timezone Returns EM_DateTime with UTC timezone if set to true, returns local timezone by default.
	 * @return EM_DateTime
	 */
	public function rsvp_end( $utc_timezone = false ){
		if( empty($this->rsvp_end) || !$this->rsvp_end->valid ){
			if( !empty($this->event_rsvp_date ) ){
				$rsvp_time = !empty($this->event_rsvp_time) ? $this->event_rsvp_time : $this->event_start_time;
			    $this->rsvp_end = new EM_DateTime($this->event_rsvp_date." ".$rsvp_time, $this->event_timezone);
			    if( !$this->rsvp_end->valid ){
			    	//invalid date will revert to start time
			    	$this->rsvp_end = $this->start()->copy();
			    }
			}else{
				//no date defined means event start date/time is used
		    	$this->rsvp_end = $this->start()->copy();
		    }
		}
		//Set to UTC timezone if requested, local by default
		$tz = $utc_timezone ? 'UTC' : $this->event_timezone;
		$this->rsvp_end->setTimezone($tz);
		return $this->rsvp_end;
	}
	
	/**
	 * Generates an EM_DateTime for the the start/end date/times of the event in local timezone, as well as setting a valid flag if dates and times are valid.
	 * The generated object will be derived from the local date and time values. If no date exists, then 1970-01-01 will be used, and 00:00:00 if no valid time exists. 
	 * If date is invalid but time is, only use local timezones since a UTC conversion will provide inaccurate timezone differences due to unknown DST status.	 * 
	 * @param string $when 'start' or 'end' date/time
	 * @param bool $utc_timezone Returns EM_DateTime with UTC timezone if set to true, returns local timezone by default. Do not use if EM_DateTime->valid is false. 
	 * @return EM_DateTime
	 */
	public function get_datetime( $when = 'start', $utc_timezone = false ){
		if( $when != 'start' && $when != 'end') return new EM_DateTime(); //currently only start/end dates are relevant
		//Initialize EM_DateTime if not already initialized, or if previously initialized object is invalid (e.g. draft event with invalid dates being resubmitted)
		$when_date = 'event_'.$when.'_date';
		$when_time = 'event_'.$when.'_time';
		//we take a pass at creating a new datetime object if it's empty, invalid or a different time to the current start date
		if( empty($this->$when) || !$this->$when->valid ){
			$when_utc = 'event_'.$when;
			$date_regex = '/^\d{4}-\d{2}-\d{2}$/';
			$valid_time = !empty($this->$when_time) && preg_match('/^\d{2}:\d{2}:\d{2}$/', $this->$when_time);
			//If there now is a valid date string for local or UTC timezones, create a new object which will set the valid flag to true by default
			if( !empty($this->$when_date) && preg_match($date_regex, $this->$when_date) && $valid_time ){
				$EM_DateTime = new EM_DateTime(trim($this->$when_date.' '.$this->$when_time), $this->event_timezone);
				if( $EM_DateTime->valid && empty($this->$when_utc) ){
					$EM_DateTime->setTimezone('UTC');
					$this->$when_utc = $EM_DateTime->format();
				}
			}
			//If we didn't attempt to create a date above, or it didn't work out, create an invalid date based on time.
			if( empty($EM_DateTime) || !$EM_DateTime->valid ){
				//create a new datetime just with the time (if set), fake date and set the valid flag to false
				$time = $valid_time ? $this->$when_time : '00:00:00';
				$EM_DateTime = new EM_DateTime('1970-01-01 '.$time, $this->event_timezone);
				$EM_DateTime->valid = false;
			} 
			//set new datetime
			$this->$when = $EM_DateTime;
		}else{
			/* @var EM_DateTime $EM_DateTime */
			$EM_DateTime = $this->$when;
		}
		//Set to UTC timezone if requested, local by default
		$tz = $utc_timezone ? 'UTC' : $this->event_timezone;
		$EM_DateTime->setTimezone($tz);
		return $EM_DateTime;
	}
	
	function get_status($db = false){
		switch( $this->post_status ){
			case 'private':
				$this->event_private = 1;
				$this->event_status = $status = 1;
				break;
			case 'publish':
				$this->event_private = 0;
				$this->event_status = $status = 1;
				break;
			case 'pending':
				$this->event_private = 0;
				$this->event_status = $status = 0;
				break;
			case 'trash':
				$this->event_private = 0;
				$this->event_status = $status = -1;
				break;
			default: //draft or unknown
				$this->event_private = 0;
				$status = $db ? 'NULL':null;
				$this->event_status = null;
				break;
		}
		return apply_filters('em_event_get_status', $status, $this);
	}
	
	function get_previous_status( $force = false ){
		global $wpdb;
		if( $this->event_id > 0 && ($this->previous_status === false || $force) ){
			$this->previous_status = $wpdb->get_var('SELECT event_status FROM '.EM_EVENTS_TABLE.' WHERE event_id='.$this->event_id); //get status from db, not post_status, as posts get saved quickly
		}
		return $this->previous_status;
	}
	
	function get_active_status(){
		if ( !$this->get_option('dbem_event_status_enabled') ) {
			return __('Active', 'events-manager');
		}
		switch( absint($this->event_active_status) ){
			case 0:
				$status = __('Cancelled', 'events-manager');
				break;
			default: // active
				$status = __('Active', 'events-manager');
				break;
		}
		return apply_filters('em_event_get_active_status', $status, $this);
	}
	
	/**
	 * Returns an EM_Categories object of the EM_Event instance.
	 * @return EM_Categories
	 */
	function get_categories() {
		if( empty($this->categories) ){
			$this->categories = new EM_Categories($this);
		}elseif(empty($this->categories->event_id)){
			$this->categories->event_id = $this->event_id;
			$this->categories->post_id = $this->post_id;			
		}
		return apply_filters('em_event_get_categories', $this->categories, $this);
	}
	
	
	/**
	 * Returns an array of colors of this event based on the category assigned. Will return a pre-formatted CSS variables assignment for use in the style attribute of HTML elements.
	 * @param bool $css_vars
	 * @return array|string
	 */
	public function get_colors( $css_vars = false ){
		$orig_color = $this->get_option('dbem_category_default_color');
		$color = $borderColor = $orig_color;
		$textColor = '#fff';
		if ( $this->get_option('dbem_categories_enabled') && !empty ( $this->get_categories()->categories )) {
			foreach($this->get_categories()->categories as $EM_Category){
				/* @public $EM_Category EM_Category */
				if( $EM_Category->get_color() != '' ){
					$color = $borderColor = $EM_Category->get_color();
					if( preg_match("/#fff(fff)?/i",$color) ){
						$textColor = '#777';
						$borderColor = '#ccc';
					}
					break;
				}
			}
		}
		$event_color = array(
			'background-color' => $color,
			'border-color' => $borderColor,
			'color' => $textColor,
		);
		$event_color = apply_filters('em_event_get_colors', $event_color, $this);
		if( $css_vars ){
			// get event colors
			$css_color_vars = array();
			foreach( $event_color as $k => $v ){
				$css_color_vars[] = '--event-'.$k.':'.$v.';';
			}
			return implode(';', $css_color_vars);
		}else{
			return $event_color;
		}
	}
	
	/**
	 * Gets the parent of this event, if none exists, null is returned.
	 * @return EM_Event|null
	 */
	public function get_parent(){
		if( $this->event_parent ){
			return em_get_event( $this->event_parent );
		} elseif ( $this->is_timeslot() ) {
			// return the pure event ID without timeslot ID
			return em_get_event( $this->event_id );
		} elseif ( $this->is_recurrence( true ) ) {
			// this is a recurrence, so it has a 'parent', which is the recurring event itself
			$EM_Event = $this->get_recurring_event();
			if ( $EM_Event->event_id !== $this->event_id ) {
				return $EM_Event;
			}
		}
		return null;
	}

	/**
	 * Gets the recurrence set this recurrence belongs to, or in event of a recurring event, the default recurrence.
	 * @return Recurrence_Set|null
	 */
	public function get_recurrence_set() {
		if ( !empty( $this->recurrence_set ) && is_object( $this->recurrence_set ) ) {
			return $this->recurrence_set;
		}
		if ( !empty( $this->recurrence_set_id ) ) {
			$this->recurrence_set = apply_filters( 'em_get_recurrence_set', Recurrence_Set::get( $this->recurrence_set_id ) );
		} elseif ( $this->is_recurring( true ) ) {
			$this->recurrence_set = $this->get_recurrence_sets()->default;
		} else {
			return new Recurrence_Set();
		}
		return $this->recurrence_set;
	}

	/**
	 * @return Recurrence_Sets
	 */
	public function get_recurrence_sets() {
		if ( empty( $this->recurrence_sets ) || !is_object( $this->recurrence_sets ) ) {
			$this->recurrence_sets = apply_filters( 'em_get_recurrence_set', new Recurrence_Sets( $this ) );
		}
		return $this->recurrence_sets;
	}

	
	/**
	 * Returns the physical location object this event belongs to.
	 * @return EM_Location
	 */
	function get_location() {
		global $EM_Location;
		if( is_object($EM_Location) && $EM_Location->location_id == $this->location_id ){
			$this->location = $EM_Location;
		}else{
			if( !is_object($this->location) || $this->location->location_id != $this->location_id ){
				$this->location = apply_filters('em_event_get_location', em_get_location($this->location_id), $this);
			}
		}
		return $this->location;
	}
	
	/**
	 * Returns whether this event has a phyisical location assigned to it.
	 * @return bool
	 */
	public function has_location(){
		return !empty($this->location_id) || (!empty($this->location) && !empty($this->location->location_name));
	}
	
	/**
	 * Gets the event's event location (note, different from a regular event location, which uses get_location())
	 * Returns implementation of Event_Location or false if no event location assigned.
	 * @return EM_Event_Locations\URL|Event_Location|false
	 */
	public function get_event_location(){
		if( is_object($this->event_location) && $this->event_location->type == $this->event_location_type ) return $this->event_location;
		$Event_Location = false;
		if( $this->has_event_location() ){
			$this->event_location = $Event_Location = Event_Locations::get( $this->event_location_type, $this );
		}
		return apply_filters('em_event_get_event_location', $Event_Location, $this);
	}
	
	/**
	 * Returns whether the event has an event location associated with it (different from a physical location). If supplied, can check against a specific type.
	 * @param string $event_location_type
	 * @return bool
	 */
	public function has_event_location( $event_location_type = null ){
		if( $event_location_type !== null ){
			return !empty($this->event_location_type) && $this->event_location_type === $event_location_type && Event_Locations::is_enabled($event_location_type);
		}
		return !empty($this->event_location_type) && Event_Locations::is_enabled($this->event_location_type);
	}
	
	/**
	 * Returns the location object this event belongs to.
	 * @return EM_Person
	 */	
	function get_contact(){
		if( !is_object($this->contact) ){
			$this->contact = new EM_Person($this->event_owner);
			//if this is anonymous submission, change contact email and name
			if( $this->event_owner_anonymous ){
				$this->contact->user_email = $this->event_owner_email;
				$name = explode(' ',$this->event_owner_name);
				$first_name = array_shift($name);
				$last_name = (count($name) > 0) ? implode(' ',$name):'';
				$this->contact->user_firstname = $this->contact->first_name = $first_name;
				$this->contact->user_lastname = $this->contact->last_name = $last_name;
				$this->contact->display_name = $this->event_owner_name;
			}
		}
		return $this->contact;
	}
	
	/**
	 * Retrieve and save the bookings belonging to instance. If called again will return cached version, set $force_reload to true to create a new EM_Bookings object.
	 * @param boolean $force_reload
	 * @return EM_Bookings
	 */
	function get_bookings( $force_reload = false ){
		if( $this->get_option('dbem_rsvp_enabled') ){
			if ( ( !$this->bookings || $force_reload ) ) {
				$this->bookings = new EM_Bookings( $this );
			}
			$this->bookings->event_id = $this->event_id; //always refresh event_id
			if ( $this->timeslot_id ) {
				$this->bookings->timeslot_id = $this->timeslot_id;
			}
			$this->bookings = apply_filters( 'em_event_get_bookings', $this->bookings, $this );
		}else{
			return new EM_Bookings();
		}
		//TODO for some reason this returned instance doesn't modify the original, e.g. try $this->get_bookings()->add($EM_Booking) and see how $this->bookings->feedback_message doesn't change
		return $this->bookings;
	}
	
	/**
	 * Get the tickets related to this event.
	 * @param boolean $force_reload
	 * @return EM_Tickets
	 */
	function get_tickets( $force_reload = false ){
		return $this->get_bookings($force_reload)->get_tickets();
	}

	/* Provides the tax rate for this event.
	 * @see EM_Object::get_tax_rate()
	 */
	function get_tax_rate( $decimal = false ){
		$tax_rate = apply_filters('em_event_get_tax_rate', parent::get_tax_rate( false ), $this); //we get tax rate but without decimal
		if ( !is_float($tax_rate) ) {
			// clean up tax rate into a float, accounting for user-dirtied data like spaces, % or commas instead of a decimal
			$tax_rate = str_replace(',', '.', (string) $tax_rate);
			$tax_rate = (float) preg_replace('/[^0-9.]/', '', $tax_rate);
		}
		$tax_rate = ( $tax_rate > 0 ) ? $tax_rate : 0;
		if( $decimal && $tax_rate > 0 ) $tax_rate = $tax_rate / 100;
		return (float) $tax_rate;
	}
	
	/**
	 * Deprecated - use $this->get_bookings()->get_spaces() instead.
	 * Gets number of spaces in this event, dependent on ticket spaces or hard limit, whichever is smaller.
	 * @param boolean $force_refresh
	 * @return int 
	 */
	function get_spaces($force_refresh=false){
		return $this->get_bookings()->get_spaces($force_refresh);
	}
	
	/* 
	 * Extends the default EM_Object function by switching blogs as needed if in MS Global mode  
	 * @param string $size
	 * @return string
	 * @see EM_Object::get_image_url()
	 */
	function get_image_url($size = 'full'){
		if ( $this->is_recurrence() ) {
			$this->image_url = $this->get_recurring_event()->get_image_url($size);
			return $this->image_url;
		} else {
			if( EM_MS_GLOBAL && get_current_blog_id() != $this->blog_id ){
				switch_to_blog($this->blog_id);
				$switch_back = true;
			}
			$return = parent::get_image_url($size);
			if( !empty($switch_back) ){ restore_current_blog(); }
		}
		return $return;
	}
	
	function get_edit_reschedule_url(){
		if( $this->is_recurrence( true ) ){
			return $this->get_recurring_event()->get_edit_url();
		}
	}
	
	function get_edit_url( $to_recurring = true ) {
		if ( $this->can_manage( 'edit_events', 'edit_others_events' ) ) {
			$event_id = $this->is_recurrence() && $to_recurring ? $this->get_recurring_event()->event_id : $this->event_id;
			$post_id = $this->is_recurrence() && $to_recurring ? $this->get_recurring_event()->post_id : $this->post_id;
			$blog_id = $this->is_recurrence() && $to_recurring ? $this->get_recurring_event()->blog_id : $this->blog_id;
			if ( EM_MS_GLOBAL && get_site_option( 'dbem_ms_global_events_links' ) && !empty( $blog_id ) && is_main_site() && $blog_id != get_current_blog_id() ) {
				if ( get_blog_option( $blog_id, 'dbem_edit_events_page' ) ) {
					$link = em_add_get_params( get_permalink( get_blog_option( $blog_id, 'dbem_edit_events_page' ) ), [ 'action' => 'edit', 'event_id' => $event_id ], false );
				}
				if ( empty( $link ) ) {
					$link = get_admin_url( $blog_id, "post.php?post={$post_id}&action=edit" );
				}
			} else {
				if ( $this->get_option( 'dbem_edit_events_page' ) && !is_admin() ) {
					$link = em_add_get_params( get_permalink( $this->get_option( 'dbem_edit_events_page' ) ), [ 'action' => 'edit', 'event_id' => $event_id ], false );
				}
				if ( empty( $link ) ) {
					$link = admin_url() . "post.php?post={$post_id}&action=edit";
				}
			}
			return apply_filters( 'em_event_get_edit_url', $link, $this );
		}
	}
	
	function get_bookings_url(){
		if( $this->get_option('dbem_edit_bookings_page') && (!is_admin() || !empty($_REQUEST['is_public'])) ){
			$my_bookings_page = get_permalink($this->get_option('dbem_edit_bookings_page'));
			$bookings_link = em_add_get_params( $my_bookings_page, ['event_id'=>$this->get_event_uid(), 'event_timeslot_id' => $this->event_timeslot_id], false );
		}else{
			if( is_multisite() && $this->blog_id != get_current_blog_id() ){
				$bookings_link = get_admin_url($this->blog_id, 'edit.php?post_type='.$this->event_archetype."&page=events-manager-bookings&event_id=".$this->get_event_uid());
			}else{
				$bookings_link = em_admin_url( $this->event_archetype ) . "&page=events-manager-bookings&event_id=".$this->get_event_uid();
			}
			if ( $this->event_timeslot_id ) {
				$bookings_link .= "&event_timeslot_id=".$this->event_timeslot_id;
			}
		}
		return apply_filters('em_event_get_bookings_url', $bookings_link, $this);
	}
	
	function get_permalink(){
		if ( $this->post_id ) {
			if ( EM_MS_GLOBAL ) {
				//if no blog id defined, assume it's the main blog
				$blog_id = empty( $this->blog_id ) ? get_current_site()->blog_id : $this->blog_id;
				//if we're not on the same blog as this event then decide whether to link to main blog or to source blog
				if ( $blog_id != get_current_blog_id() ) {
					if ( !get_site_option( 'dbem_ms_global_events_links' ) && is_main_site() && $this->get_option( 'dbem_events_page' ) ) {
						//if on main site, and events page exists and direct links are disabled then show link to main site
						$event_link = trailingslashit( get_permalink( $this->get_option( 'dbem_events_page' ) ) . get_site_option( 'dbem_ms_events_slug', EM_EVENT_SLUG ) . '/' . $this->event_slug . '-' . $this->get_event_uid() );
					} else {
						//linking directly to the source blog by default
						$event_link = get_blog_permalink( $blog_id, $this->post_id );
					}
				}
			}
			if ( empty( $event_link ) ) {
				$event_link = get_post_permalink( $this->post_id );
			}
		} else {
			// This is potentially a recurrence, so we need to get the parent event permalink
			$event_link = '';
			$EM_Event = $this->get_parent();
			if ( $EM_Event ) {
				$event_link = $EM_Event->get_permalink();
			}
		}
		return apply_filters('em_event_get_permalink', $event_link, $this);
	}
	
	function get_ical_url(){
		global $wp_rewrite;
		if( !empty($wp_rewrite) && $wp_rewrite->using_permalinks() ){
			$return = trailingslashit($this->get_permalink()).'ical/';
		}else{
			$return = em_add_get_params($this->get_permalink(), array('ical'=>1));
		}
		return apply_filters('em_event_get_ical_url', $return);
	}
	
	function is_free( $now = false ){
		$free = true;
		foreach($this->get_tickets() as $EM_Ticket){
		    /* @public $EM_Ticket EM_Ticket */
			if( $EM_Ticket->get_price() > 0 ){
				if( !$now || $EM_Ticket->is_available() ){	
				    $free = false;
				}
			}
		}
		return apply_filters('em_event_is_free',$free, $this, $now);
	}
	
	/**
	 * Will output a single event format of this event. 
	 * Equivalent of calling EM_Event::output( $this->get_option( 'dbem_single_event_format' ) )
	 * @param string $target
	 * @return string
	 */
	function output_single($target='html'){
		$format = $this->get_option( 'dbem_single_event_format' );
		return apply_filters('em_event_output_single', $this->output($format, $target), $this, $target);
	}

	/**
	 * Whether #_CONTACTMETA may output a user meta key. Protected keys (leading underscore), keys prefixed with the database prefix such as capabilities, and session tokens are refused, since formats can reach visitors.
	 * @param string $meta_key
	 * @return bool
	 */
	public static function is_contact_meta_key_allowed( $meta_key ){
		global $wpdb;
		$allowed = is_string($meta_key) && !is_protected_meta($meta_key, 'user') && strpos($meta_key, $wpdb->base_prefix) !== 0 && !in_array($meta_key, array('session_tokens', 'user_pass', 'user_activation_key', 'default_password_nag'), true);
		return apply_filters('em_event_contact_meta_key_allowed', $allowed, $meta_key);
	}
	
	/**
	 * Will output a event in the format passed in $format by replacing placeholders within the format.
	 * @param string $format
	 * @param string $target
	 * @return string
	 */	
	function output($format, $target="html") {	
		global $wpdb;
		//$format = do_shortcode($format); //parse shortcode first, so that formats within shortcodes are parsed properly, however uncommenting this will break shortcode containing placeholders for arguments
	 	$event_string = $format;
		//Time place holder that doesn't show if empty.
		preg_match_all('/#@?__?\{[^}]+\}/', $format, $results);
		foreach($results[0] as $result) {
			if(substr($result, 0, 3 ) == "#@_"){
				$date = 'end';
				if( substr($result, 0, 4 ) == "#@__" ){
					$offset = 5;
					$show_site_timezone = true;
				}else{
					$offset = 4;
				}
			}else{
				$date = 'start';
				if( substr($result, 0, 3) == "#__" ){
					$offset = 4;
					$show_site_timezone = true;
				}else{
					$offset = 3;
				}
			}
			if( $date == 'end' && $this->event_start_date == $this->event_end_date ){
				$replace = apply_filters('em_event_output_placeholder', '', $this, $result, $target, array($result));
			}else{
				$date_format = substr( $result, $offset, (strlen($result)-($offset+1)) );
				if( !empty($show_site_timezone) ){
					$date_formatted = $this->$date()->copy()->setTimezone()->i18n($date_format);
				}else{
					$date_formatted = $this->$date()->i18n($date_format);
				}
				$replace = apply_filters('em_event_output_placeholder', $date_formatted, $this, $result, $target, array($result));
			}
			$event_string = str_replace($result,$replace,$event_string );
		}
		//This is for the custom attributes
		preg_match_all('/#_ATT\{([^}]+)\}(\{([^}]+\}?)\})?/', $event_string, $results);
		$attributes = em_get_attributes();
		foreach($results[0] as $resultKey => $result) {
			//check that we haven't mistakenly captured a closing bracket in second bracket set
			if( !empty($results[3][$resultKey]) && $results[3][$resultKey][0] == '/' ){
				$result = $results[0][$resultKey] = str_replace($results[2][$resultKey], '', $result);
				$results[3][$resultKey] = $results[2][$resultKey] = '';
			}
			//Strip string of placeholder and just leave the reference
			$attRef = substr( substr($result, 0, strpos($result, '}')), 6 );
			$attString = '';
			$placeholder_atts = array('#_ATT', $results[1][$resultKey]);
			if( is_array($this->event_attributes) && array_key_exists($attRef, $this->event_attributes) ){
				$attString = $this->event_attributes[$attRef];
			}elseif( !empty($results[3][$resultKey]) ){
				//Check to see if we have a second set of braces;
				$placeholder_atts[] = $results[3][$resultKey];
				$attStringArray = explode('|', $results[3][$resultKey]);
				$attString = $attStringArray[0];
			}elseif( !empty($attributes['values'][$attRef][0]) ){
			    $attString = $attributes['values'][$attRef][0];
			}
			$attString = apply_filters('em_event_output_placeholder', $attString, $this, $result, $target, $placeholder_atts);
			$event_string = str_replace($result, $attString ,$event_string );
		}
	 	//First let's do some conditional placeholder removals
	 	for ($i = 0 ; $i < EM_CONDITIONAL_RECURSIONS; $i++){ //you can add nested recursions by modifying this setting in your wp_options table
			preg_match_all('/\{([a-zA-Z0-9_\-,]+)\}(.+?)\{\/\1\}/s', $event_string, $conditionals);
			if( count($conditionals[0]) > 0 ){
				//Check if the language we want exists, if not we take the first language there
				foreach($conditionals[1] as $key => $condition){
					$show_condition = false;
					if ($condition == 'has_bookings') {
						//check if there's a booking, if not, remove this section of code.
						$show_condition = ($this->event_rsvp && $this->get_option('dbem_rsvp_enabled'));
					}elseif ($condition == 'no_bookings') {
						//check if there's a booking, if not, remove this section of code.
						$show_condition = (!$this->event_rsvp && $this->get_option('dbem_rsvp_enabled'));
					}elseif ($condition == 'no_location'){
						//does this event have a valid location?
						$show_condition = !$this->has_event_location() && !$this->has_location();
					}elseif ($condition == 'has_location'){
						//does this event have a valid location?
						$show_condition = ( $this->has_location() && $this->get_location()->is_viewable() ) || $this->has_event_location();
					}elseif ($condition == 'has_location_venue'){
						//does this event have a valid physical location?
						$show_condition = $this->has_location() && ( empty($this->location_id) || $this->get_location()->is_viewable() );
					}elseif ($condition == 'no_location_venue'){
						//does this event NOT have a valid physical location?
						$show_condition = !$this->has_location();
					}elseif ($condition == 'has_event_location'){
						//does this event have a valid event location?
						$show_condition = $this->has_event_location();
					}elseif ( preg_match('/^has_event_location_([a-zA-Z0-9_\-]+)$/', $condition, $type_match)){
						//event has a specific category
						$show_condition = $this->has_event_location($type_match[1]);
					}elseif ($condition == 'no_event_location'){
						//does this event not have a valid event location?
						$show_condition = !$this->has_event_location();
					}elseif ( preg_match('/^no_event_location_([a-zA-Z0-9_\-]+)$/', $condition, $type_match)){
						//does this event NOT have a specific event location?
						$show_condition = !$this->has_event_location($type_match[1]);
					}elseif ($condition == 'has_image'){
						//does this event have an image?
						$show_condition = ( $this->get_image_url() != '' );
					}elseif ($condition == 'no_image'){
						//does this event have an image?
						$show_condition = ( $this->get_image_url() == '' );
					}elseif ($condition == 'has_time'){
						//are the booking times different and not an all-day event
						$show_condition = ( $this->event_start_time != $this->event_end_time && !$this->event_all_day );
					}elseif ($condition == 'no_time'){
						//are the booking times exactly the same and it's not an all-day event.
						$show_condition = ( $this->event_start_time == $this->event_end_time && !$this->event_all_day );
					}elseif ($condition == 'different_timezone'){
						//current event timezone is different to blog timezone
						$show_condition = $this->event_timezone != EM_DateTimeZone::create()->getName();
					}elseif ($condition == 'same_timezone'){
						//current event timezone is different to blog timezone
						$show_condition = $this->event_timezone == EM_DateTimeZone::create()->getName();
					}elseif ($condition == 'all_day'){
						//is it an all day event
						$show_condition = !empty($this->event_all_day);
					}elseif ($condition == 'not_all_day'){
						//is not an all day event
						$show_condition = empty($this->event_all_day);
					}elseif ($condition == 'logged_in'){
						//user is logged in
						$show_condition = is_user_logged_in();
					}elseif ($condition == 'not_logged_in'){
						//not logged in
						$show_condition = !is_user_logged_in();
					}elseif ($condition == 'has_spaces'){
						//there are still empty spaces
						$show_condition = $this->event_rsvp && $this->get_bookings()->get_available_spaces() > 0;
					}elseif ($condition == 'fully_booked'){
						//event is fully booked
						$show_condition = $this->event_rsvp && $this->get_bookings()->get_available_spaces() <= 0;
					}elseif ($condition == 'bookings_open'){
						//bookings are still open
						$show_condition = $this->event_rsvp && $this->get_bookings()->is_open();
					}elseif ($condition == 'bookings_closed'){
						//bookings are still closed
						$show_condition = $this->event_rsvp && !$this->get_bookings()->is_open();
					}elseif ($condition == 'is_free' || $condition == 'is_free_now'){
						//is it a free day event, if _now then free right now
						$show_condition = !$this->event_rsvp || $this->is_free( $condition == 'is_free_now' );
					}elseif ($condition == 'not_free' || $condition == 'not_free_now'){
						//is it a paid event, if _now then paid right now
						$show_condition = $this->event_rsvp && !$this->is_free( $condition == 'not_free_now' );
					}elseif ($condition == 'is_long'){
						//is it an all day event
						$show_condition = $this->event_start_date != $this->event_end_date;
					}elseif ($condition == 'not_long'){
						//is it an all day event
						$show_condition = $this->event_start_date == $this->event_end_date;
					}elseif ($condition == 'is_past'){
						//if event is past
						if( $this->get_option('dbem_events_current_are_past') ){
						    $show_condition = $this->start()->getTimestamp() <= time();
						}else{
							$show_condition = $this->end()->getTimestamp() <= time();
						}
					}elseif ($condition == 'is_future'){
						//if event is upcoming
						$show_condition = $this->start()->getTimestamp() > time();
					}elseif ($condition == 'is_current'){
						//if event is currently happening
						$show_condition = $this->start()->getTimestamp() <= time() && $this->end()->getTimestamp() >= time();
					}elseif ($condition == 'is_recurring'){
						//if event is a recurring event
						$show_condition = $this->is_recurring( true );
					}elseif ($condition == 'not_recurring'){
						//if event is not a recurring event
						$show_condition = !$this->is_recurring( true );
					}elseif ($condition == 'is_recurrence'){
						//if event is a recurrence
						$show_condition = $this->is_recurrence();
					}elseif ($condition == 'not_recurrence'){
						//if event is not a recurrence
						$show_condition = !$this->is_recurrence();
					}elseif ($condition == 'is_private'){
						//if event is a recurrence
						$show_condition = $this->event_private == 1;
					}elseif ($condition == 'not_private'){
						//if event is not a recurrence
						$show_condition = $this->event_private == 0;
					}elseif ($condition == 'is_cancelled'){
						//if event is not a recurrence
						$show_condition = $this->event_active_status == 0;
					}elseif ($condition == 'is_active'){
						//if event is not a recurrence
						$show_condition = $this->event_active_status == 1;
					}elseif ( strpos($condition, 'is_user_attendee') !== false || strpos($condition, 'not_user_attendee') !== false ){
						//if current user has a booking at this event
						$show_condition = false;
						if( is_user_logged_in() ){
							//we only need a user id, booking id and booking status so we do a direct SQL lookup and once for the loop
							if( !isset($user_bookings) || !is_array($user_bookings) ){
								$sql = $wpdb->prepare('SELECT booking_status FROM '.EM_BOOKINGS_TABLE.' WHERE person_id=%d AND event_id=%d', array(get_current_user_id(), $this->event_id));
								if ( $this->timeslot_id ) {
									$sql .= ' AND timeslot_id=' . absint( $this->timeslot_id );
								}
								$user_bookings = $wpdb->get_col($sql);
							}
							if( $condition == 'is_user_attendee' && count($user_bookings) > 0 ){
								//user has a booking for this event, could be any booking status
								$show_condition = true;
							}elseif( $condition == 'not_user_attendee' && count($user_bookings) == 0 ){
								//user has no bookings to this event
								$show_condition = true;
							}elseif( strpos($condition, 'is_user_attendee_') !== false ){
								//user has a booking for this event, and we'll now look for a specific status
								$attendee_booking_status = str_replace('is_user_attendee_', '', $condition);
								$show_condition = in_array($attendee_booking_status, $user_bookings);
							}elseif( strpos($condition, 'not_user_attendee_') !== false ){
								//user has a booking for this event, and we'll now look for a specific status
								$attendee_booking_status = str_replace('not_user_attendee_', '', $condition);
								$show_condition = !in_array($attendee_booking_status, $user_bookings);
							}
						}
					}elseif ( $condition == 'has_category' ||  $condition == 'no_category' ){
						//event is in this category
						if( $this->get_option('dbem_categories_enabled') ) {
							$terms = get_the_terms($this->post_id, EM_TAXONOMY_CATEGORY);
							$show_condition = $condition == 'has_category' ? !empty($terms) : empty($terms);
						}else{
							$show_condition = $condition !== 'has_category'; // no categories
						}
					}elseif ( preg_match('/^has_category_([a-zA-Z0-9_\-,]+)$/', $condition, $category_match)){
						//event is in this category
						$show_condition = $this->get_option('dbem_categories_enabled') && has_term(explode(',', $category_match[1]), EM_TAXONOMY_CATEGORY, $this->post_id);
					}elseif ( preg_match('/^no_category_([a-zA-Z0-9_\-,]+)$/', $condition, $category_match)){
					    //event is NOT in this category
						$show_condition = !$this->get_option('dbem_categories_enabled') || !has_term(explode(',', $category_match[1]), EM_TAXONOMY_CATEGORY, $this->post_id);
					}elseif ( $condition == 'has_tag' ||  $condition == 'no_tag' ){
						//event is in this category
						if( $this->get_option('dbem_tags_enabled') ) {
							$terms = get_the_terms( $this->post_id, EM_TAXONOMY_TAG);
							$show_condition = $condition == 'has_tag' ? !empty($terms) : empty($terms);
						} else {
							$show_condition = $condition !== 'has_tag'; // no tags
						}
					}elseif ( $condition == 'has_taxonomy' ||  $condition == 'no_taxonomy' ){
						//event is in this category
						$cats = $this->get_option('dbem_categories_enabled') ? get_the_terms( $this->post_id, EM_TAXONOMY_CATEGORY) : array();
						$tax = $this->get_option('dbem_tags_enabled') ? get_the_terms( $this->post_id, EM_TAXONOMY_TAG) : array();
						$show_condition = $condition == 'has_taxonomy' ? !empty($tax) || !empty($cats) : empty($tax) && empty($cats);
					}elseif ( preg_match('/^has_tag_([a-zA-Z0-9_\-,]+)$/', $condition, $tag_match)){
						//event has this tag
						$show_condition = $this->get_option('dbem_tags_enabled') && has_term(explode(',', $tag_match[1]), EM_TAXONOMY_TAG, $this->post_id);
					}elseif ( preg_match('/^no_tag_([a-zA-Z0-9_\-,]+)$/', $condition, $tag_match)){
					   //event doesn't have this tag
						$show_condition = !$this->get_option('dbem_tags_enabled') || !has_term(explode(',', $tag_match[1]), EM_TAXONOMY_TAG, $this->post_id);
					}elseif ( preg_match('/^has_att_([a-zA-Z0-9_\-,]+)$/', $condition, $att_match)){
						//event has a specific custom field
						$show_condition = !empty($this->event_attributes[$att_match[1]]) || !empty($this->event_attributes[str_replace('_', ' ', $att_match[1])]);
					}elseif ( preg_match('/^no_att_([a-zA-Z0-9_\-,]+)$/', $condition, $att_match)){
						//event has a specific custom field
						$show_condition = empty($this->event_attributes[$att_match[1]]) && empty($this->event_attributes[str_replace('_', ' ', $att_match[1])]);
					}
					//other potential ones - has_attribute_... no_attribute_... has_categories_...
					$show_condition = apply_filters('em_event_output_show_condition', $show_condition, $condition, $conditionals[0][$key], $this);
					if($show_condition){
						//calculate lengths to delete placeholders
						$placeholder_length = strlen($condition)+2;
						$replacement = substr($conditionals[0][$key], $placeholder_length, strlen($conditionals[0][$key])-($placeholder_length *2 +1));
					}else{
						$replacement = '';
					}
					$event_string = str_replace($conditionals[0][$key], apply_filters('em_event_output_condition', $replacement, $condition, $conditionals[0][$key], $this), $event_string);
				}
			}
	 	}
		//Now let's check out the placeholders.
	 	preg_match_all("/(#@?_?[A-Za-z0-9_]+)({([^}]+)})?/", $event_string, $placeholders);
	 	$replaces = array();
		foreach($placeholders[1] as $key => $result) {
			$match = true;
			$replace = '';
			$full_result = $placeholders[0][$key];
			$placeholder_atts = array($result);
			if( !empty($placeholders[3][$key]) ) $placeholder_atts[] = $placeholders[3][$key];
			switch( $result ){
				//Event Details
				case '#_EVENTID':
					$replace = $this->get_event_uid();
					break;
				case '#_EVENTPOSTID':
					$replace = $this->post_id;
					break;
				case '#_NAME': //deprecated
				case '#_EVENTNAME':
					$replace = $this->event_name;
					break;
				case '#_EVENTSTATUS':
					$statuses = static::get_active_statuses();
					if( array_key_exists($this->event_active_status, $statuses) ){
						$replace = $statuses[$this->event_active_status];
					}else{
						$replace = $statuses[1];
					}
					break;
				case '#_NOTES': //deprecated
				case '#_EVENTNOTES':
					$replace = $this->post_content;
					break;
				case '#_EXCERPT': //deprecated
				case '#_EVENTEXCERPT':
				case '#_EVENTEXCERPTCUT':
					if( !empty($this->post_excerpt) && $result != "#_EVENTEXCERPTCUT" ){
						$replace = $this->post_excerpt;
					}else{
						$excerpt_length = ( $result == "#_EVENTEXCERPTCUT" ) ? 55:false;
						$excerpt_more = apply_filters('em_excerpt_more', ' ' . '[...]');
						if( !empty($placeholders[3][$key]) ){
							$ph_args = explode(',', $placeholders[3][$key]);
							if( is_numeric($ph_args[0]) || empty($ph_args[0]) ) $excerpt_length = $ph_args[0];
							if( !empty($ph_args[1]) ) $excerpt_more = $ph_args[1];
						}
						$replace = $this->output_excerpt($excerpt_length, $excerpt_more, $result == "#_EVENTEXCERPTCUT");
					}
					break;
				case '#_EVENTIMAGEURL':
				case '#_EVENTIMAGE':
	        		if($this->get_image_url() != ''){
						if($result == '#_EVENTIMAGEURL'){
		        			$replace =  esc_url($this->image_url);
						}else{
							if( empty($placeholders[3][$key]) ){
								$replace = "<img src='".esc_url($this->image_url)."' alt='".esc_attr($this->event_name)."'/>";
							}else{
								$image_size = explode(',', $placeholders[3][$key]);
								$image_url = $this->image_url;
								if( self::array_is_numeric($image_size) && count($image_size) > 1 ){
								    //get a thumbnail
								    if( $this->get_option('dbem_disable_thumbnails') ){
    								    $image_attr = '';
    								    $image_args = array();
    								    if( empty($image_size[1]) && !empty($image_size[0]) ){    
    								        $image_attr = 'width="'.$image_size[0].'"';
    								        $image_args['w'] = $image_size[0];
    								    }elseif( empty($image_size[0]) && !empty($image_size[1]) ){
    								        $image_attr = 'height="'.$image_size[1].'"';
    								        $image_args['h'] = $image_size[1];
    								    }elseif( !empty($image_size[0]) && !empty($image_size[1]) ){
    								        $image_attr = 'width="'.$image_size[0].'" height="'.$image_size[1].'"';
    								        $image_args = array('w'=>$image_size[0], 'h'=>$image_size[1]);
    								    }
								        $replace = "<img src='".esc_url(em_add_get_params($image_url, $image_args))."' alt='".esc_attr($this->event_name)."' $image_attr />";
								    }else{
    								    if( EM_MS_GLOBAL && get_current_blog_id() != $this->blog_id ){
    								        switch_to_blog($this->blog_id);
    								        $switch_back = true;
    								    }
										$post_id = $this->is_recurrence() ? $this->get_recurring_event()->post_id : $this->post_id;
								        $replace = get_the_post_thumbnail($post_id, $image_size, array('alt' => esc_attr($this->event_name)) );
								        if( !empty($switch_back) ){ restore_current_blog(); }
								    }
								}else{
									$replace = "<img src='".esc_url($image_url)."' alt='".esc_attr($this->event_name)."'/>";
								}
							}
						}
	        		}
					break;
				//Times & Dates
				case '#_24HSTARTTIME':
				case '#_24HENDTIME':
					$replace = ($result == '#_24HSTARTTIME') ? $this->start()->format('H:i'):$this->end()->format('H:i');
					break;
				case '#_24HSTARTTIME_SITE':
				case '#_24HENDTIME_SITE':
					$replace = ($result == '#_24HSTARTTIME_SITE') ? $this->start()->copy()->setTimezone(false)->format('H:i'):$this->end()->copy()->setTimezone(false)->format('H:i');
					break;
				case '#_24HSTARTTIME_LOCAL':
				case '#_24HENDTIME_LOCAL':
				case '#_24HTIMES_LOCAL':
					$ts = ($result == '#_24HENDTIME_LOCAL') ? $this->end()->getTimestamp():$this->start()->getTimestamp();
					$date_end = ($result == '#_24HTIMES_LOCAL' && $this->event_start_time !== $this->event_end_time) ? 'data-time-end="'. esc_attr($this->end()->getTimestamp()) .'" data-separator="'. esc_attr($this->get_option('dbem_times_separator')) . '"' : '';
					$replace = '<span class="em-time-localjs" data-time-format="24"  data-time="'. esc_attr($ts) .'" '. $date_end .'>JavaScript Disabled</span>';
					break;
				case '#_12HSTARTTIME':
				case '#_12HENDTIME':
					$replace = ($result == '#_12HSTARTTIME') ? $this->start()->format('g:i A'):$this->end()->format('g:i A');
					break;
				case '#_12HSTARTTIME_SITE':
				case '#_12HENDTIME_SITE':
					$replace = ($result == '#_12HSTARTTIME_SITE') ? $this->start()->copy()->setTimezone(false)->format('g:i A'):$this->end()->copy()->setTimezone(false)->format('g:i A');
					break;
				case '#_12HSTARTTIME_LOCAL':
				case '#_12HENDTIME_LOCAL':
				case '#_12HTIMES_LOCAL':
					$ts = ($result == '#_12HENDTIME_LOCAL') ? $this->end()->getTimestamp():$this->start()->getTimestamp();
					$date_end = ($result == '#_24HTIMES_LOCAL' && $this->end()->getTimestamp() !== $ts) ? 'data-time-end="'. esc_attr($this->end()->getTimestamp()) .'" data-separator="'. esc_attr($this->get_option('dbem_times_separator')) . '"' : '';
					$replace = '<span class="em-time-localjs" data-time-format="12"  data-time="'. esc_attr($ts) .'" '. $date_end .'>JavaScript Disabled</span>';
					break;
				case '#_EVENTTIMES':
					//get format of time to show
					$replace = $this->output_times();
					break;
				case '#_EVENTTIMES_SITE':
					//get format of time to show but show timezone of site rather than local time
					$replace = $this->output_times(false, false, false, true);
					break;
				case '#_EVENTTIMES_LOCAL':
				case '#_EVENTDATES_LOCAL':
					if( !defined('EM_JS_MOMENTJS_PH') || EM_JS_MOMENTJS_PH ){
						// check for passed parameters, in which case we skip replacements entirely and use pure moment formats
						$time_format = $separator = null;
						if( !empty($placeholder_atts[1]) ){
							$params = explode(',', $placeholder_atts[1]);
							if( !empty($params[0]) ) $time_format = $params[0];
							if( !empty($params[1]) ) $separator = $params[1];
						}
						// if no moment format provided, we convert the one stored for times in php
						$start_time = $this->start()->getTimestamp();
						if( empty($time_format) ){
							// convert EM format setting to moment formatting, adapted from https://stackoverflow.com/questions/30186611/php-dateformat-to-moment-js-format
							$replacements = array(
								/* Day */ 'jS' => 'Do', /*o doesn't exist on its own, so we find/replase jS only*/ 'd' => 'DD', 'D' => 'ddd', 'j' => 'D', 'l' => 'dddd', 'N' => 'E', /*'S' => 'o' - see jS*/ 'w' => 'e', 'z' => 'DDD',
								/* Week */ 'W' => 'W',
								/* Month */ 'F' => 'MMMM', 'm' => 'MM', 'M' => 'MMM', 'n' => 'M', 't' => '#t', /* days in the month => moment().daysInMonth(); */
								/* Year */ 'L' => '#L', /* Leap year? => moment().isLeapYear(); */ 'o' => 'YYYY', 'Y' => 'YYYY', 'y' => 'YY',
								/* Time */ 'a' => 'a', 'A' => 'A', 'B' => '', /* Swatch internet time (.beats), no equivalent */ 'g' => 'h', 'G' => 'H', 'h' => 'hh', 'H' => 'HH', 'i' => 'mm', 's' => 'ss', 'u' => 'SSSSSS', /* microseconds */ 'v' => 'SSS',    /* milliseconds (from PHP 7.0.0) */
								/* Timezone */ 'e' => '##T', /* Timezone - deprecated since version 1.6.0 of moment.js, we'll use Intl.DateTimeFromat().resolvedOptions().timeZone instead. */ 'I' => '##t',       /* Daylight Saving Time? => moment().isDST(); */ 'O' => 'ZZ', 'P' => 'Z', 'T' => '#T', /* deprecated since version 1.6.0 of moment.js, using GMT difference with colon to keep it shorter than full timezone */ 'Z' => '###t',    /* time zone offset in seconds => moment().zone() * -60 : the negative is because moment flips that around; */
								/* Full Date/Time */ 'c' => 'YYYY-MM-DD[T]HH:mm:ssZ', /* ISO 8601 */ 'r' => 'ddd, DD MMM YYYY HH:mm:ss ZZ', /* RFC 2822 */ 'U' => 'X',
							);
							// Converts escaped characters.
							foreach ($replacements as $from => $to) {
								$replacements['\\' . $from] = '[' . $from . ']';
							}
							if( $result === '#_EVENTDATES_LOCAL' ){
								$time_format = ( $this->get_option('dbem_date_format') ) ? $this->get_option('dbem_date_format'):$this->get_option('date_format');
								$end_time = $this->event_start_date == $this->event_end_date ? $start_time : $this->end()->getTimestamp();
								if( empty($separator) ) $separator = $this->get_option('dbem_dates_separator');
							}else{
								$time_format = ( $this->get_option('dbem_time_format') ) ? $this->get_option('dbem_time_format'):$this->get_option('time_format');
								$end_time = $this->event_start_time == $this->event_end_time ? $start_time : $this->end()->getTimestamp();
								if( empty($separator) ) $separator = $this->get_option('dbem_times_separator');
							}
							$time_format = strtr($time_format, $replacements);
						} else {
							$end_time = $this->end()->getTimestamp();
							// decide whether to use dates separator or time separator, if there's a day format, use date, if not use time
							if( empty($separator) ) $separator = $result === '#_EVENTDATES_LOCAL' ? $this->get_option('dbem_dates_separator') : $this->get_option('dbem_times_separator');
						}
						wp_enqueue_script('moment', '', array(), false, true); //add to footer if not already
						// start output
						ob_start();
						?>
						<span class="em-date-momentjs" data-date-format="<?php echo esc_attr($time_format); ?>" data-date-start="<?php echo $start_time ?>" data-date-end="<?php echo $end_time ?>" data-date-separator="<?php echo esc_attr($separator); ?>">JavaScript Disabled</span>
						<?php
						$replace = ob_get_clean();
					}
					break;
				case '#_EVENTDATES':
					//get format of time to show
					$replace = $this->output_dates();
					break;
				case '#_EVENTSTARTDATE':
					//get format of time to show
					if( empty($date_format) ) $date_format = ( $this->get_option('dbem_date_format') ) ? $this->get_option('dbem_date_format'):$this->get_option('date_format');
					$replace = $replace = $this->start()->i18n($date_format);
					break;
				case '#_EVENTDATES_SITE':
					//get format of time to show but use timezone of site rather than event
					$replace = $this->output_dates(false, false, true);
					break;
				case '#_EVENTTIMEZONE':
					$replace = str_replace('_', ' ', $this->event_timezone);
					break;
				case '#_EVENTTIMEZONERAW':
					$replace = $this->event_timezone;
					break;
				case '#_EVENTTIMEZONE_LOCAL':
					$rand = rand();
					ob_start();
					?>
					<span id="em-start-local-timezone-<?php echo $rand ?>">JavaScript Disabled</span>
					<script>
						document.getElementById("em-start-local-timezone-<?php echo $rand ?>").innerHTML = Intl.DateTimeFormat().resolvedOptions().timeZone;
					</script>
					<?php
					$replace = ob_get_clean();
					break;
				//Recurring Placeholders
				case '#_RECURRINGDATERANGE': //Outputs the #_EVENTDATES equivalent of the recurring event template pattern.
					$replace = $this->get_event_recurrence()->output_dates(); //if not a recurrence, we're running output_dates on $this
					break;
				case '#_RECURRINGPATTERN':
					$replace = '';
					if( $this->is_recurrence( true ) || $this->is_recurring( true ) ){
						$replace = $this->get_event_recurrence()->get_recurrence_set()->get_recurrence_description();
					}
					break;
				case '#_RECURRINGID':
					$replace = $this->get_recurrence_sets()->event_id;
					break;
				//Links
				case '#_EVENTPAGEURL': //deprecated	
				case '#_LINKEDNAME': //deprecated
				case '#_EVENTURL': //Just the URL
				case '#_EVENTLINK': //HTML Link
					$event_link = esc_url($this->get_permalink());
					if($result == '#_LINKEDNAME' || $result == '#_EVENTLINK'){
						$replace = '<a href="'.$event_link.'">'.esc_attr($this->event_name).'</a>';
					}else{
						$replace = $event_link;	
					}
					break;
				case '#_EDITEVENTURL':
				case '#_EDITEVENTLINK':
					if( $this->can_manage('edit_events','edit_others_events') ){
						$link = esc_url($this->get_edit_url());
						if( $result == '#_EDITEVENTLINK'){
							$replace = '<a href="'.$link.'">'.esc_html(sprintf(__('Edit Event','events-manager'))).'</a>';
						}else{
							$replace = $link;
						}
					}	 
					break;
				//Bookings
				case '#_ADDBOOKINGFORM': //deprecated
				case '#_REMOVEBOOKINGFORM': //deprecated
				case '#_BOOKINGFORM':
					if( $this->get_option('dbem_rsvp_enabled')) {
						$replace = $this->output_booking_form();
					}
					break;
				case '#_BOOKINGBUTTON':
					if( $this->get_option('dbem_rsvp_enabled') && $this->event_rsvp && !$this->is_recurring( true ) ){
						ob_start();
						em_locate_template('placeholders/bookingbutton.php', true, array('EM_Event'=>$this));
						$replace = ob_get_clean();
					}
					break;
				case '#_EVENTPRICERANGEALL':				    
				    $show_all_ticket_prices = true; //continues below
				case '#_EVENTPRICERANGE':
					//get the range of prices
					$min = false;
					$max = 0;
					if( $this->get_bookings()->is_open() || !empty($show_all_ticket_prices) ){
						foreach( $this->get_tickets()->tickets as $EM_Ticket ){
							/* @public $EM_Ticket EM_Ticket */
							if( $EM_Ticket->is_available() || $this->get_option('dbem_bookings_tickets_show_unavailable') || !empty($show_all_ticket_prices) ){
								if($EM_Ticket->get_price() > $max ){
									$max = $EM_Ticket->get_price();
								}
								if($EM_Ticket->get_price() < $min || $min === false){
									$min = $EM_Ticket->get_price();
								}						
							}
						}
					}
					if( empty($min) ) $min = 0;
					if( $min != $max ){
						$replace = em_get_currency_formatted($min).' - '.em_get_currency_formatted($max);
					}else{
						$replace = em_get_currency_formatted($min);
					}
					break;
				case '#_EVENTPRICEMIN':
				case '#_EVENTPRICEMINALL':
					//get the range of prices
					$min = false;
					foreach( $this->get_tickets()->tickets as $EM_Ticket ){
						/* @public $EM_Ticket EM_Ticket */
						if( $EM_Ticket->is_available() || $result == '#_EVENTPRICEMINALL'){
							if( $EM_Ticket->get_price() < $min || $min === false){
								$min = $EM_Ticket->get_price();
							}
						}
					}
					if( $min === false ) $min = 0;
					$replace = em_get_currency_formatted($min);
					break;
				case '#_EVENTPRICEMAX':
				case '#_EVENTPRICEMAXALL':
					//get the range of prices
					$max = 0;
					foreach( $this->get_tickets()->tickets as $EM_Ticket ){
						/* @public $EM_Ticket EM_Ticket */
						if( $EM_Ticket->is_available() || $result == '#_EVENTPRICEMAXALL'){
							if( $EM_Ticket->get_price() > $max ){
								$max = $EM_Ticket->get_price();
							}
						}			
					}
					$replace = em_get_currency_formatted($max);
					break;
				case '#_AVAILABLESEATS': //deprecated
				case '#_AVAILABLESPACES':
					if ($this->event_rsvp && $this->get_option('dbem_rsvp_enabled')) {
					   $replace = $this->get_bookings()->get_available_spaces();
					} else {
						$replace = "0";
					}
					break;
				case '#_BOOKEDSEATS': //deprecated
				case '#_BOOKEDSPACES':
					// Previously, this placeholder also counted pending bookings if they are to be reserved, now only confirmed bookings are included here
					if ($this->event_rsvp && $this->get_option('dbem_rsvp_enabled')) {
						$replace = $this->get_bookings()->get_booked_spaces();
					} else {
						$replace = "0";
					}
					break;
				case '#_RESERVEDSPACES':
					// This does not include confirmed spaces, only pending bookings that are witholding availability
					if ($this->event_rsvp && $this->get_option('dbem_rsvp_enabled')) {
						$replace = $this->get_bookings()->get_reserved_spaces();
					} else {
						$replace = "0";
					}
					break;
				case '#_UNAVAILABLESPACES':
					// This includes both confirmed and reserved spaces, in other words the number of spaces booked that affect capacity, somewhat the opposite of available spaces
					if ($this->event_rsvp && $this->get_option('dbem_rsvp_enabled')) {
						$replace = $this->get_bookings()->get_booked_spaces();
						$replace += $this->get_bookings()->get_reserved_spaces();
					} else {
						$replace = "0";
					}
					break;
				case '#_PENDINGSPACES':
					if ($this->event_rsvp && $this->get_option('dbem_rsvp_enabled')) {
					   $replace = $this->get_bookings()->get_pending_spaces();
					} else {
						$replace = "0";
					}
					break;
				case '#_SEATS': //deprecated
				case '#_SPACES':
					$replace = $this->get_spaces();
					break;
				case '#_BOOKINGSURL':
				case '#_BOOKINGSLINK':
					if( $this->can_manage('manage_bookings','manage_others_bookings') ){
						$bookings_link = esc_url($this->get_bookings_url());
						if($result == '#_BOOKINGSLINK'){
							$replace = '<a href="'.$bookings_link.'" title="'.esc_attr($this->event_name).'">'.esc_html($this->event_name).'</a>';
						}else{
							$replace = $bookings_link;	
						}
					}
					break;
				case '#_BOOKINGSCUTOFF':
				case '#_BOOKINGSCUTOFFDATE':
				case '#_BOOKINGSCUTOFFTIME':
					$replace = '';
					if ($this->event_rsvp && $this->get_option('dbem_rsvp_enabled') ) {
						$replace_format = em_get_date_format() .' '. em_get_hour_format();
						if( $result == '#_BOOKINGSCUTOFFDATE' ) $replace_format = em_get_date_format();
						if( $result == '#_BOOKINGSCUTOFFTIME' ) $replace_format = em_get_hour_format();
						$replace = $this->rsvp_end()->i18n($replace_format);
					}
					break;
				//Contact Person
				case '#_CONTACTNAME':
				case '#_CONTACTPERSON': //deprecated (your call, I think name is better)
					$replace = $this->get_contact()->display_name;
					break;
				case '#_CONTACTUSERNAME':
					$replace = $this->get_contact()->user_login;
					break;
				case '#_CONTACTEMAIL':
				case '#_CONTACTMAIL': //deprecated
					$replace = $this->get_contact()->user_email;
					break;
				case '#_CONTACTURL':
					$replace = $this->get_contact()->user_url;
					break;
				case '#_CONTACTID':
					$replace = $this->get_contact()->ID;
					break;
				case '#_CONTACTPHONE':
		      		$replace = ( $this->get_contact()->phone != '') ? $this->get_contact()->phone : __('N/A', 'events-manager');
					break;
				case '#_CONTACTAVATAR': 
					$replace = get_avatar( $this->get_contact()->ID, $size = '50' ); 
					break;
				case '#_CONTACTPROFILELINK':
				case '#_CONTACTPROFILEURL':
					if( function_exists('bp_core_get_user_domain') ){
						$replace = bp_core_get_user_domain($this->get_contact()->ID);
						if( $result == '#_CONTACTPROFILELINK' ){
							$replace = '<a href="'.esc_url($replace).'">'.__('Profile', 'events-manager').'</a>';
						}
					}
					break;
				case '#_CONTACTMETA':
					if( !empty($placeholders[3][$key]) && static::is_contact_meta_key_allowed($placeholders[3][$key]) ){
						$replace = get_user_meta($this->event_owner, $placeholders[3][$key], true);
						if( !is_scalar($replace) ) $replace = '';
					}
					break;
				case '#_ATTENDEES':
					ob_start();
					em_locate_template('placeholders/attendees.php', true, array('EM_Event'=>$this));
					$replace = ob_get_clean();
					break;
				case '#_ATTENDEESLIST':
					ob_start();
					em_locate_template('placeholders/attendeeslist.php', true, array('EM_Event'=>$this));
					$replace = ob_get_clean();
					break;
				case '#_ATTENDEESPENDINGLIST':
					ob_start();
					em_locate_template('placeholders/attendeespendinglist.php', true, array('EM_Event'=>$this));
					$replace = ob_get_clean();
					break;
				//Categories and Tags
				case '#_EVENTCATEGORIESIMAGES':
				    $replace = '';
				    if( $this->get_option('dbem_categories_enabled') ){
    					ob_start();
    					em_locate_template('placeholders/eventcategoriesimages.php', true, array('EM_Event'=>$this));
    					$replace = ob_get_clean();
				    }
					break;
				case '#_EVENTTAGS':
				    $replace = '';
                    if( $this->get_option('dbem_tags_enabled') ){
    					ob_start();
    					em_locate_template('placeholders/eventtags.php', true, array('EM_Event'=>$this));
    					$replace = ob_get_clean();
                    }
					break;
				case '#_EVENTTAGSLINE':
					$tags = get_the_terms($this->post_id, EM_TAXONOMY_TAG);
					if( is_array($tags) && count($tags) > 0 ){
						$tags_list = array();
						foreach($tags as $tag) {
							$link = get_term_link($tag->slug, EM_TAXONOMY_TAG);
							if( is_wp_error($link) ) $link = '';
							$tags_list[] = '<a href="' . $link . '">' . $tag->name . '</a>';
						}
					}
					if( !empty($tags_list) ) {
						$replace = implode(', ', $tags_list);
					}else{
						$replace = $this->get_option( 'dbem_no_tags_message' );
					}
					break;
				case '#_CATEGORIES': //deprecated
				case '#_EVENTCATEGORIES':
				    $replace = '';
				    if( $this->get_option('dbem_categories_enabled') ){
    					ob_start();
    					em_locate_template('placeholders/categories.php', true, array('EM_Event'=>$this));
    					$replace = ob_get_clean();
				    }
					break;
				case '#_EVENTCATEGORIESLINE':
					$categories = array();
					foreach( $this->get_categories() as $EM_Category ){
						$categories[] = $EM_Category->output("#_CATEGORYLINK");
					}
					if( !empty($categories) ) {
						$replace = implode(', ', $categories);
					}else{
						$replace = $this->get_option( 'dbem_no_categories_message' );
					}
					break;
				//Ical Stuff
				case '#_EVENTICALURL':
				case '#_EVENTICALLINK':
					$replace = $this->get_ical_url();
					if( $result == '#_EVENTICALLINK' ){
						$replace = '<a href="'.esc_url($replace).'">iCal</a>';
					}
					break;
				case '#_EVENTWEBCALURL':
				case '#_EVENTWEBCALLINK':
					$replace = $this->get_ical_url();
					$replace = str_replace(array('http://','https://'), 'webcal://', $replace);
					if( $result == '#_EVENTWEBCALLINK' ){
						$replace = '<a href="'.esc_url($replace).'">webcal</a>';
					}
					break;
				case '#_EVENTGCALURL':
				case '#_EVENTGCALLINK':
					//get dates in UTC/GMT time
					if($this->event_all_day && $this->event_start_date == $this->event_end_date){
						$dateStart	= $this->start()->format('Ymd');
						$dateEnd	= $this->end()->copy()->add('P1D')->format('Ymd');
					}else{
						$dateStart	= $this->start()->format('Ymd\THis');
						$dateEnd = $this->end()->format('Ymd\THis');
					}
					//build url
					$gcal_url = 'https://www.google.com/calendar/event?action=TEMPLATE&text=event_name&dates=start_date/end_date&details=post_content&location=location_name&trp=false&sprop=event_url&sprop=name:blog_name&ctz=event_timezone';
					$replace = $this->generate_ical_url($gcal_url, $dateStart, $dateEnd);
					if( $result == '#_EVENTGCALLINK' ){
						$img_url = 'https://www.google.com/calendar/images/ext/gc_button2.gif';
						$replace = '<a href="'.esc_url($replace).'" target="_blank"><img src="'.esc_url($img_url).'" alt="0" border="0"></a>';
					}
					break;
				case '#_EVENTOUTLOOKLIVELINK':
				case '#_EVENTOUTLOOKLIVEURL':
				case '#_EVENTOFFICE365LINK':
				case '#_EVENTOFFICE365URL':
					$base_url = $result == '#_EVENTOUTLOOKLIVELINK' || $result == '#_EVENTOUTLOOKLIVEURL' ? 'https://outlook.live.com':'https://outlook.office.com';
					if($this->event_all_day && $this->event_start_date == $this->event_end_date){
						$dateStart	= $this->start()->copy()->format('c');
						$dateEnd	= $this->end()->copy()->sub('P1D')->format('c');
						$url = $base_url.'/calendar/0/deeplink/compose?allday=true&body=post_content&location=location_name&path=/calendar/action/compose&rru=addevent&startdt=start_date&enddt=end_date&subject=event_name';
					}else{
						$dateStart	= $this->start()->copy()->format('c');
						$dateEnd = $this->end()->copy()->format('c');
						$url = $base_url.'/calendar/0/deeplink/compose?allday=false&body=post_content&location=location_name&path=/calendar/action/compose&rru=addevent&startdt=start_date&enddt=end_date&subject=event_name';
					}
					$replace = $this->generate_ical_url( $url, $dateStart, $dateEnd );
					if( $result == '#_EVENTOUTLOOKLIVELINK' ){
						$replace = '<a href="'.esc_url($replace).'" target="_blank">Outlook Live</a>';
					} elseif ( $result == '#_EVENTOFFICE365LINK' ){
						$replace = '<a href="'.esc_url($replace).'" target="_blank">Office 365</a>';
					}
					break;
				//Event location (not physical location)
				case '#_EVENTADDTOCALENDAR':
					ob_start();
					$rand_id = rand();
					?>
					<button type="button" class="em-event-add-to-calendar em-tooltip-ddm em-clickable input" data-button-width="match" data-tooltip-class="em-add-to-calendar-tooltip" data-content="em-event-add-to-colendar-content-<?php echo $rand_id; ?>"><span class="em-icon em-icon-calendar"></span> <?php esc_html_e('Add To Calendar', 'events-manager'); ?></button>
					<div class="em-tooltip-ddm-content em-event-add-to-calendar-content" id="em-event-add-to-colendar-content-<?php echo $rand_id; ?>">
						<a class="em-a2c-download" href="<?php echo esc_url($this->get_ical_url()); ?>" target="_blank"><?php echo sprintf(esc_html__('Download %s', 'events-manager'), 'ICS'); ?></a>
						<a class="em-a2c-google" href="<?php echo esc_url($this->output('#_EVENTGCALURL')); ?>" target="_blank"><?php esc_html_e('Google Calendar', 'events-manager'); ?></a>
						<a class="em-a2c-apple" href="<?php echo esc_url(str_replace(array('http://','https://'), 'webcal://', $this->get_ical_url())); ?>" target="_blank">iCalendar</a>
						<a class="em-a2c-office" href="<?php echo esc_url($this->output('#_EVENTOFFICE365URL')); ?>" target="_blank">Office 365</a>
						<a class="em-a2c-outlook" href="<?php echo esc_url($this->output('#_EVENTOUTLOOKLIVEURL')); ?>" target="_blank">Outlook Live</a>
					</div>
					<?php
					$replace = ob_get_clean();
					break;
				case '#_EVENTLOCATION':
					if( $this->has_event_location() ) {
						if (!empty($placeholders[3][$key])) {
							$replace = $this->get_event_location()->output( $placeholders[3][$key], $target );
						} else {
							$replace = $this->get_event_location()->output( null, $target );
						}
					}
					break;
				default:
					$replace = $full_result;
					break;
			}
			$replaces[$full_result] = apply_filters('em_event_output_placeholder', $replace, $this, $full_result, $target, $placeholder_atts);
		}
		//sort out replacements so that during replacements shorter placeholders don't overwrite longer varieties.
		krsort($replaces);
		foreach($replaces as $full_result => $replacement){
			if( !in_array($full_result, array('#_NOTES','#_EVENTNOTES')) ){
				$event_string = str_replace($full_result, $replacement , $event_string );
			}else{
			    $new_placeholder = str_replace('#_', '__#', $full_result); //this will avoid repeated filters when locations/categories are parsed
			    $event_string = str_replace($full_result, $new_placeholder , $event_string );
				$desc_replace[$new_placeholder] = $replacement;
			}
		}
		//Time placeholders
		foreach($placeholders[1] as $result) {
			// matches all PHP START date and time placeholders
			if (preg_match('/^#[dDjlNSwzWFmMntLoYyaABgGhHisueIOPTZcrU]$/', $result)) {
				$replace = $this->start()->i18n(ltrim($result, "#"));
				$replace = apply_filters('em_event_output_placeholder', $replace, $this, $result, $target, array($result));
				$event_string = str_replace($result, $replace, $event_string );
			}
			// matches all PHP END time placeholders for endtime
			if (preg_match('/^#@[dDjlNSwzWFmMntLoYyaABgGhHisueIOPTZcrU]$/', $result)) {
				$replace = $this->end()->i18n(ltrim($result, "#@"));
				$replace = apply_filters('em_event_output_placeholder', $replace, $this, $result, $target, array($result));
				$event_string = str_replace($result, $replace, $event_string ); 
		 	}
		}
		//Now do dependent objects
		if( $this->get_option('dbem_locations_enabled') ){
			if( !empty($this->location_id) && $this->get_location()->is_viewable() ){
				$event_string = $this->get_location()->output($event_string, $target);
			}else{
				$EM_Location = new EM_Location();
				$event_string = $EM_Location->output($event_string, $target);
			}
		}
		
		if( $this->get_option('dbem_categories_enabled') ){
    		//for backwards compat and easy use, take over the individual category placeholders with the frirst cat in th elist.
    		if( count($this->get_categories()) > 0 ){
    			$EM_Category = $this->get_categories()->get_first();
    		}
    		if( empty($EM_Category) ) $EM_Category = new EM_Category();
    		$event_string = $EM_Category->output($event_string, $target);
		}
		
		if( $this->get_option('dbem_tags_enabled') ){
			$EM_Tags = new EM_Tags($this);
			if( count($EM_Tags) > 0 ){
				$EM_Tag = $EM_Tags->get_first();
			}
			if( empty($EM_Tag) ) $EM_Tag = new EM_Tag();
			$event_string = $EM_Tag->output($event_string, $target);
		}
		
		//Finally, do the event notes, so that previous placeholders don't get replaced within the content, which may use shortcodes
		if( !empty($desc_replace) ){
			foreach($desc_replace as $full_result => $replacement){
				$event_string = str_replace($full_result, $replacement , $event_string );
			}
		}
		
		//do some specific formatting
		//TODO apply this sort of formatting to any output() function
		if( $target == 'ical' ){
		    //strip html and escape characters
		    $event_string = str_replace('\\','\\\\',strip_tags($event_string));
		    $event_string = str_replace(';','\;',$event_string);
		    $event_string = str_replace(',','\,',$event_string);
		    //remove and define line breaks in ical format
		    $event_string = str_replace('\\\\n','\n',$event_string);
		    $event_string = str_replace("\r\n",'\n',$event_string);
		    $event_string = str_replace("\n",'\n',$event_string);
		}
		return apply_filters('em_event_output', $event_string, $this, $format, $target);
	}
	
	public function generate_ical_url($url, $dateStart, $dateEnd, $description_max_length = 1350 ){
		//replace url template placeholders
		$url = str_replace('event_name', urlencode($this->event_name), $url);
		$url = str_replace('start_date', urlencode($dateStart), $url);
		$url = str_replace('end_date', urlencode($dateEnd), $url);
		$location_name = ( !empty($this->location_id) && $this->get_location()->is_viewable() ) ? $this->get_location()->get_full_address(', ', true) : '';
		$url = str_replace('location_name', urlencode($location_name), $url);
		$url = str_replace('blog_name', urlencode(get_bloginfo()), $url);
		$url = str_replace('event_url', urlencode($this->get_permalink()), $url);
		$url = str_replace('event_timezone', urlencode($this->event_timezone), $url); // Google specific
		//calculate URL length so we know how much we can work with to make a description.
		if( !empty($this->post_excerpt) ){
			$description = $this->post_excerpt;
		}else{
			$matches = explode('<!--more', $this->post_content);
			$description = wp_kses_data($matches[0]);
		}
		$url_length = strlen($url) - 9;
		// truncate
		if( $description_max_length && strlen($description) + $url_length > $description_max_length ){
			$description = substr($description, 0, $description_max_length - $url_length - 3 ).'...';
		}
		$url = str_replace('post_content', urlencode($description), $url);
		return $url;
	}

	function output_booking_form() {
		if( !defined('EM_XSS_BOOKINGFORM_FILTER') && locate_template('plugins/events-manager/placeholders/bookingform.php') ){
			//xss fix for old overridden booking forms
			add_filter('em_booking_form_action_url','esc_url');
			define('EM_XSS_BOOKINGFORM_FILTER',true);
		}
		ob_start();
		// We are firstly checking if the user has already booked a ticket at this event, if so offer a link to view their bookings.
		//count tickets and available tickets
		$template_vars = $this->get_bookings()->get_booking_vars();
		//if user is logged out, check for member tickets that might be available, since we should ask them to log in instead of saying 'bookings closed'
		if( !$template_vars['is_open'] && !is_user_logged_in() && $this->get_bookings()->is_open(true) ){
			$template_vars['is_open'] = true;
			$template_vars['can_book'] = false;
			$template_vars['show_tickets'] = $this->get_option('dbem_bookings_tickets_show_unavailable') && $this->get_option('dbem_bookings_tickets_show_member_tickets');
		}
		if ( $this->is_recurring() ) {
			em_locate_template( 'forms/bookingform/booking-recurring.php', true, $template_vars );
		} elseif ( $this->has_timeslots() ) {
			em_locate_template( 'forms/bookingform/booking-timeslots.php', true, $template_vars );
		} else {
			em_locate_template('placeholders/bookingform.php', true, $template_vars);
		}
		EM_Bookings::enqueue_js();
		return ob_get_clean();
	}
	
	function output_times( $time_format = false, $time_separator = false , $all_day_message = false, $use_site_timezone = false ){
		if( !$this->event_all_day ){
			if( empty($time_format) ) $time_format = ( $this->get_option('dbem_time_format') ) ? $this->get_option('dbem_time_format'):$this->get_option('time_format');
			if( empty($time_separator) ) $time_separator = $this->get_option('dbem_times_separator');
			if( $this->event_start_time != $this->event_end_time ){
				if( $use_site_timezone ){
					$replace = $this->start()->copy()->setTimezone()->i18n($time_format). $time_separator . $this->end()->copy()->setTimezone()->i18n($time_format);
				}else{
					$replace = $this->start()->i18n($time_format). $time_separator . $this->end()->i18n($time_format);
				}
			}else{
				if( $use_site_timezone ){
					$replace = $this->start()->copy()->setTimezone()->i18n($time_format);
				}else{
					$replace = $this->start()->i18n($time_format);
				}
			}
		}else{
			$replace = $all_day_message ? $all_day_message : $this->get_option('dbem_event_all_day_message');
		}
		return $replace;
	}
	
	function output_dates( $date_format = false, $date_separator = false, $use_site_timezone = false ){
		if( empty($date_format) ) $date_format = ( $this->get_option('dbem_date_format') ) ? $this->get_option('dbem_date_format'):$this->get_option('date_format');
		if( empty($date_separator) ) $date_separator = $this->get_option('dbem_dates_separator');
		if( $this->event_start_date != $this->event_end_date){
			if( $use_site_timezone ){
				$replace = $this->start()->copy()->setTimezone()->i18n($date_format). $date_separator . $this->end()->copy()->setTimezone()->i18n($date_format);
			}else{
				$replace = $this->start()->i18n($date_format). $date_separator . $this->end()->i18n($date_format);
			}
		}else{
			if( $use_site_timezone ){
				$replace = $this->start()->copy()->setTimezone()->i18n($date_format);
			}else{
				$replace = $this->start()->i18n($date_format);
			}
		}
		return $replace;
	}
	
	/**********************************************************
	 * RECURRENCE METHODS
	 ***********************************************************/

	/**
	 * Returns true if this is a recurring event. Set $include_repeating to true to also evaluate repeating events as a recurring event (mainly for backwards compatibility)
	 *
	 * @param boolean $include_repeating
	 * @return boolean
	 */
	function is_recurring( $include_repeating = false ) {
		return $this->event_type == 'recurring' || ( $include_repeating && $this->is_repeating() );
	}

	/**
	 * Will return true if this individual event is part of a set of events that recur. If this event is a specific timeslot of a set of recurring events, it will still return true as well.
	 *
	 * Unlike is_recurring() this pre-loads the Recurrence_Set into this object by default. If you don't intend to call get_recurrence_sets() right after and use the object returned, you can set $prepare_set to false.
	 *
	 * @param boolean $include_repeating	 *
	 * @return boolean
	 */
	function is_recurrence( $include_repeating = false ) {
		$is_recurrence = ( !$this->post_id || $include_repeating ) && $this->event_type === 'recurrence' && $this->recurrence_set_id;
		if ( !$is_recurrence && $this->is_timeslot() && $this->recurrence_set_id ) {
			$is_recurrence = $this->get_parent()->is_recurrence( $include_repeating );
		}
		return $is_recurrence;
	}

	/**
	 * Returns true if this is a recurring event.
	 *
	 * @return boolean
	 */
	function is_repeating() {
		return $this->event_type == 'repeating' || Archetypes::is_repeating( $this->post_type );
	}

	/**
	 * Will return true if this individual event is part of a repeating event set. Recurrences of repeating events are individual events with their own post id.
	 *
	 * @return boolean
	 */
	function is_repeated() {
		return !$this->is_recurrence && $this->post_id && $this->event_type === 'recurrence' && $this->recurrence_set_id;
	}

	/**
	 * Returns if this is an individual event and is not a recurrence
	 * @return boolean
	 */
	function is_individual() {
		return ( $this->event_type === 'single' );
	}

	/**
	 * Returns true if this is a timeslot event.
	 * @return bool
	 */
	function is_timeslot() {
		return $this->event_type == 'timeslot' && $this->timeslot_id;
	}
	
	/**
	 * Gets the recurring event set that this event belongs to, use get_recurring_event() instead.
	 * @depreacted
	 * @use $this->get_recurring_event()
	 * @return EM_Event
	 */
	function get_event_recurrence() {
		return $this->get_recurring_event();
	}
	/**
	 * Gets the event recurrence template, which is an EM_Event object (based off an event-recurring post)
	 * @return EM_Event
	 */
	function get_recurring_event() {
		if( !$this->is_recurring( true ) ){
			return $this->get_recurrence_set()->get_event();
		}else{
			return $this;
		}
	}
	
	function get_detach_url(){
		return admin_url().'admin.php?event_id='.$this->event_id.'&amp;action=event_detach&amp;_wpnonce='.wp_create_nonce('event_detach_'.get_current_user_id().'_'.$this->event_id);
	}

	/**
	 * @param $recurrence_set_id
	 * @param $recurring_event_id
	 *
	 * @return string
	 */
	function get_attach_url( $recurrence_set_id = null, $recurring_event_id = null ) {
		$recurrence_set_id = $recurrence_set_id ? absint($recurrence_set_id) : $this->recurrence_set_id;
		if ( !$recurrence_set_id && !$recurring_event_id ) {
			// attach to recurring event if no set id defined
			if ( $this->get_recurrence_set() ) {
				$recurring_event_id = $this->get_recurrence_set()->event_id;
			}
		}
		$recurring_event_id = $recurring_event_id ? absint($recurring_event_id) : null;
		$admin_url = admin_url('admin.php');
		$admin_args = [
			'undo_id' => $recurrence_set_id,
			'recurring_id' => $recurring_event_id,
			'event_id' => $this->event_id,
			'action' => 'event_attach',
			'_wpnonce' => wp_create_nonce( 'event_attach_' . get_current_user_id() . '_' . $this->event_id),
		];
		return add_query_arg( $admin_args, $admin_url );
	}
	
	/**
	 * Returns if this is an individual event and is not recurring or a recurrence
	 * @return boolean
	 */
	function detach(){
		global $wpdb;
		if( $this->is_repeated() && $this->can_manage('edit_recurring_events','edit_others_recurring_events') ){
			//remove recurrence id from post meta and index table
			$url = $this->get_attach_url();
			$updated = $wpdb->update(EM_EVENTS_TABLE, array('recurrence_id' => null, 'recurrence_set_id' => null, 'event_type' => 'single' ), array('event_id' => $this->event_id));
			if( $updated === false ){
				//a failed UPDATE must not leave the events table and postmeta diverged
				$this->add_error(__('Event could not be detached.','events-manager'));
				return apply_filters('em_event_detach', false, $this);
			}
			delete_post_meta($this->post_id, '_recurrence_id'); // legacy
			delete_post_meta($this->post_id, '_recurrence_set_id');
			update_post_meta($this->post_id, '_event_type', 'single' );
			$this->feedback_message = __('Event detached.','events-manager') . ' <a href="'.$url.'">'.__('Undo','events-manager').'</a>';
			$this->recurrence_id = null;
			$this->recurrence_set_id = null;
			$this->recurrence_set = null;
			$this->event_type = 'single';
			$this->get_tickets()->detach();
			return apply_filters('em_event_detach', true, $this);
		}
		$this->add_error(__('Event could not be detached.','events-manager'));
		return apply_filters('em_event_detach', false, $this);
	}

	/**
	 * Attaches an event to a recurrence set or creates a new one-off recurrence set if necessary.
	 * Returns true if successful, false if not.
	 *
	 * If $recurrence_set_id is null, a $recurring_event_id must be supplied, and a new one-off recurrence set will be created.
	 *
	 * @param int|null $recurrence_set_id
	 * @param int|null $recurring_event_id
	 * @return boolean
	 */
	function attach( $recurrence_set_id = null, $recurring_event_id = null ) {
		global $wpdb;

		if ( $this->is_individual() && $this->can_manage( 'edit_recurring_events', 'edit_others_recurring_events' ) ) {
			if ( !$recurrence_set_id && $recurring_event_id ) {
				$recurrence_duration = $this->start()->diff( $this->end() )->days;
				$inserted = $wpdb->insert( EM_EVENT_RECURRENCES_TABLE, [
					'event_id' => absint($recurring_event_id),
					'recurrence_type' => 'include',
					'recurrence_freq' => 'once',
					'recurrence_start_date' => $this->event_start_date,
					'recurrence_duration' => $recurrence_duration,
					'recurrence_start_time' => $this->event_start_time,
					'recurrence_end_time' => $this->event_end_time
				]);
				if ( $inserted ) {
					$recurrence_set_id = $wpdb->insert_id;
				}
			}
			if ( !empty( $recurrence_set_id ) ) {
				$recurrence_set = !empty($inserted) ? true : Recurrence_Set::get( $recurrence_set_id );
				if ( !empty( $recurrence_set ) ) {
					$wpdb->update( EM_EVENTS_TABLE, ['recurrence_set_id' => $recurrence_set_id, 'event_type' => 'recurrence'], ['event_id' => $this->event_id] );
					update_post_meta( $this->post_id, '_recurrence_set_id', $recurrence_set_id );
					update_post_meta( $this->post_id, '_event_type', 'recurrence' );
					$this->event_type = 'recurrence';
					$this->recurrence_set_id = $recurrence_set_id;
					$event_type = $recurrence_set->get_event()->event_type === 'repeating' ? esc_html__('repeating event', 'events-manager') : esc_html__('recurring event', 'events-manager');
					if ( !empty($inserted) ) {
						$this->feedback_message = sprintf(__('Event attached to %s.','events-manager'), $event_type);
					} else {
						$this->feedback_message = sprintf(__('Event re-attached to %s.','events-manager'), $event_type);
						$this->get_tickets()->attach();
					}
					return apply_filters( 'em_event_attach', true, $recurrence_set_id, $this );
				}
			}
		}
		$this->add_error( __( 'Event could not be attached.', 'events-manager' ) );
		return apply_filters( 'em_event_attach', false, $recurring_event_id, $this );
	}

	
	/**
	 * Saves events and replaces old ones. Returns true if sucecssful or false if not.
	 *
	 * @return boolean
	 * @deprecated This is now handled in Recurrence_Sets::save() and subsequently in Recurrence_Set::save_recurrences()
	 */
	function save_events() {
		return $this->get_recurrence_sets()->save_recurrences();
	}
	
	/**
	 * @param string $post_name
	 * @param string $post_slug_postfix
	 * @return string
	 * @deprecated use Recurrence_Set::sanitize_recurrence_slug
	 */
	public function sanitize_recurrence_slug( $post_name, $post_slug_postfix ){
		if ( $this->get_recurrence_sets()->length ) {
			$this->get_recurrence_sets()->get_first()->sanitize_recurrence_slug( $post_name, $post_slug_postfix );
		}
	}

	/**
	 * Removes all recurrences of a recurring event.
	 *
	 * @return null
	 * @deprecated use Recurrence_Sets::delete_events() or Recurrence_Set::delete_events()
	 */
	function delete_events(){
		$this->get_recurrence_sets()->delete_events();
	}

	/**
	 * Returns the days that match the recurrance array passed (unix timestamps)
	 *
	 * @param array $recurrence
	 * @return array
	 * @deprecated use Recurrence_Sets::get_recurrence_days() or Recurrence_Set::get_recurrence_days()
	 */
	function get_recurrence_days(){
		if ( $this->get_recurrence_sets()->length ) {
			return $this->get_recurrence_sets()->get_recurrence_days();
		}
		return [];
	}

	/**
	 * If event is recurring, set recurrences to same status as template
	 *
	 * @param $status
	 * @deprecated use Recurrence_Sets::get_recurrence_days() or Recurrence_Set::get_recurrence_days()
	 */
	function set_status_events($status){
		$this->get_recurrence_sets()->set_status_events( $status );
	}

	/**
	 * Returns a string representation of this recurrence. Will return false if not a recurrence
	 * @return string
	 * @deprecated use Recurrence_Sets::get_recurrence_description() or Recurrence_Set::get_recurrence_description()
	 */
	function get_recurrence_description() {
		if ( $this->is_recurrence( true ) ) {
			return $this->get_recurring_event()->get_recurrence_description();
		} else {
			return $this->get_recurrence_sets()->get_recurrence_description();
		}
	}
	
	/**********************************************************
	 * UTILITIES
	 ***********************************************************/
	function to_array( $db = false ){
		$event_array = parent::to_array($db);
		//we reset start/end datetimes here, based on the EM_DateTime objects if they are valid
		$event_array['event_start'] = $this->start()->valid ? $this->start(true)->format('Y-m-d H:i:s') : null;
		$event_array['event_end'] = $this->end()->valid ? $this->end(true)->format('Y-m-d H:i:s') : null;
		return apply_filters('em_event_to_array', $event_array, $this);
	}
	
	/**
	 * Can the user manage this? 
	 */
	function can_manage( $owner_capability = false, $admin_capability = false, $user_to_check = false ){
		if( ($this->just_added_event || $this->event_id == '') && !is_user_logged_in() && $this->get_option('dbem_events_anonymous_submissions') ){
			$user_to_check = $this->get_option('dbem_events_anonymous_user');
		}
		return apply_filters('em_event_can_manage', parent::can_manage($owner_capability, $admin_capability, $user_to_check), $this, $owner_capability, $admin_capability, $user_to_check);
	}
	
	/**
	 * Returns the $_POST-shape array that EM_Event::get_post() expects.
	 * Used by API consumers to pre-load $_REQUEST before applying partial updates,
	 * so that get_post() (which is destructive on missing keys) doesn't wipe fields
	 * the caller didn't intend to touch.
	 * @return array
	 */
	function to_request_data() {
		$data = array(
			'event_name'         => $this->event_name,
			'content'            => $this->post_content,
			'event_type'         => $this->event_type,
			'event_archetype'    => $this->event_archetype,
			'event_start_date'   => $this->event_start_date,
			'event_end_date'     => $this->event_end_date,
			'event_rsvp_date'    => $this->event_rsvp_date,
			'event_rsvp_time'    => $this->event_rsvp_time,
			'event_timezone'     => $this->event_timezone,
			'event_rsvp'         => $this->event_rsvp,
			'event_rsvp_spaces'  => $this->event_rsvp_spaces,
			'event_spaces'       => $this->event_spaces,
			'event_active_status'=> $this->event_active_status,
			'event_private'      => $this->event_private,
			'location_id'        => $this->location_id,
		);
		// Times go through the timeranges subsystem, not flat $_POST['event_start_time'].
		// Format start/end as HH:MM to satisfy Timerange::get_post()'s regex.
		if ( $this->event_all_day ) {
			$data['event_timeranges'] = array( 0 => array( 'all_day' => '1' ) );
		} else {
			$data['event_timeranges'] = array( 0 => array(
				'start' => $this->event_start_time ? substr( $this->event_start_time, 0, 5 ) : '00:00',
				'end'   => $this->event_end_time   ? substr( $this->event_end_time, 0, 5 )   : '00:00',
			) );
		}
		// Current taxonomy state, as term IDs. EM_Taxonomy_Terms::get_post() unconditionally resets the terms collection and rebuilds it from $_POST['event_categories'] / $_POST['event_tags'], so an event re-submitted (e.g. a partial API update that omits taxonomies) would have its categories/tags wiped on save. Emitting the existing terms here means re-posting this data preserves them; a caller that genuinely wants to change them overrides these keys, and passing an empty array still clears them.
		if ( !empty( $this->post_id ) ) {
			if ( $this->get_option( 'dbem_categories_enabled' ) && defined( 'EM_TAXONOMY_CATEGORY' ) ) {
				$cat_ids = wp_get_object_terms( $this->post_id, EM_TAXONOMY_CATEGORY, array( 'fields' => 'ids' ) );
				if ( !is_wp_error( $cat_ids ) && !empty( $cat_ids ) ) {
					$data['event_categories'] = array_map( 'absint', $cat_ids );
				}
			}
			if ( defined( 'EM_TAXONOMY_TAG' ) && taxonomy_exists( EM_TAXONOMY_TAG ) ) {
				$tag_ids = wp_get_object_terms( $this->post_id, EM_TAXONOMY_TAG, array( 'fields' => 'ids' ) );
				if ( !is_wp_error( $tag_ids ) && !empty( $tag_ids ) ) {
					$data['event_tags'] = array_map( 'absint', $tag_ids );
				}
			}
		}
		return $data;
	}

	/**
	 * Returns this event's terms in a taxonomy as a compact [{ id, name, slug }] list for API output. Empty array when the taxonomy is unavailable or the event has no terms. Used by to_api() so a get-event response shows the event's categories and tags — both so agents can read them and so they know which term IDs to re-send (via event_categories / event_tags) on a partial update.
	 *
	 * @param string $taxonomy
	 * @return array
	 */
	protected function to_api_terms( $taxonomy ) {
		if ( empty( $this->post_id ) || !$taxonomy || !taxonomy_exists( $taxonomy ) ) {
			return array();
		}
		$terms = wp_get_object_terms( $this->post_id, $taxonomy );
		if ( is_wp_error( $terms ) || empty( $terms ) ) {
			return array();
		}
		$out = array();
		foreach ( $terms as $term ) {
			$out[] = array(
				'id'   => absint( $term->term_id ),
				'name' => $term->name,
				'slug' => $term->slug,
			);
		}
		return $out;
	}

	/**
	 * Outputs a JSON-encodable associative array of data to output to REST or other remote operations
	 * @return array
	 */
	function to_api(){
		$event = array (
			'name' => $this->event_name,
			'id' => $this->get_event_uid(),
			'type' => $this->event_type,
			'post_id' => $this->post_id,
			'parent' => $this->event_parent,
			'owner' => $this->event_owner, // overwritten further down
			'blog_id' => $this->blog_id,
			'group_id' => $this->group_id,
			'slug' => $this->event_slug,
			'status' => $this->post_status ?: ( $this->post_id ? get_post_status( $this->post_id ) : null ),
			'private' => !empty( $this->event_private ),
			'active' => (bool) $this->event_active_status,
			'active_status' => absint( $this->event_active_status ),
			'content' => $this->post_content,
			'image' => ( $em_api_image = $this->get_image_url( 'thumbnail' ) ) ? array( 'thumbnail' => $em_api_image, 'full' => $this->get_image_url( 'full' ) ) : null,
			'bookings' => array (
				'enabled' => !empty( $this->event_rsvp ),
				'end_date' => $this->event_rsvp_date,
				'end_time' => $this->event_rsvp_time,
				'rsvp_spaces' => $this->event_rsvp_spaces,
				'spaces' => $this->event_spaces,
				// Booked / available counts, computed only for booking-enabled events to avoid extra queries elsewhere.
				'booked_spaces' => !empty( $this->event_rsvp ) ? absint( $this->get_bookings()->get_booked_spaces() ) : 0,
				'available_spaces' => !empty( $this->event_rsvp ) ? absint( $this->get_bookings()->get_available_spaces() ) : null,
			),
			'when' => array(
				'all_day' => $this->event_all_day,
				'start' => $this->event_start,
				'start_date' => $this->event_start_date,
				'start_time' => $this->event_start_time,
				'end' => $this->event_end,
				'end_date' => $this->event_end_date,
				'end_time' => $this->event_end_time,
				'timezone' => $this->event_timezone,
				// Timeslot sub-shape: index 0 is the primary range, extra entries are additional timeslots / slot generators. Always present (a plain event has one). Mirrors the front-end timeranges editor and is what the REST write contract inverts.
				'timeranges' => $this->get_timeranges()->to_api()['timeranges'],
			),
			'location' => false,
			'categories' => $this->to_api_terms( EM_TAXONOMY_CATEGORY ),
			'tags' => $this->to_api_terms( EM_TAXONOMY_TAG ),
			'recurrence' => $this->get_recurrence_set()->id ? $this->get_recurrence_set()->to_api() : false,
			'recurring' => $this->is_recurring( true ),
			'language' => $this->event_language,
			'translation' => $this->event_translation,
		);
		if ( $this->is_recurring( true ) ) {
			$event['recurrences'] = $this->get_recurrence_sets()->to_api();
		}
		if( !empty( $this->event_owner_anonymous ) || empty( $this->event_owner ) ){
			// anonymous or guest-submitted event
			$event['owner'] = array(
				'guest' => true,
				'email' => $this->get_contact()->user_email,
				'name' => $this->get_contact()->get_name(),
			);
		}else{
			// registered user
			$event['owner'] = array(
				'guest' => false,
				'email' => $this->get_contact()->user_email,
				'name' => $this->get_contact()->get_name(),
			);
		}
		if( $this->get_recurrence_set()->length ){
			$event['recurrences'] = $this->get_recurrence_set()->to_api();
		}
		if( $this->has_location() ) {
			$EM_Location = $this->get_location();
			if ( empty($this->location_id) || $EM_Location->is_viewable() ) $event['location'] = $EM_Location->to_api();
		}elseif( $this->has_event_location() ){
			$event['location_type'] = $this->event_location_type;
			$event['location'] = $this->get_event_location()->to_api();
		}
		if ( $this->timeslot_id ) {
			$event['timeslot_id'] = $this->timeslot_id;
		}
		return apply_filters('em_event_to_api', $event, $this);
	}
	
	public static function get_active_statuses(){
		if( !empty(static::$active_statuses) ) {
			return static::$active_statuses;
		}
		$statuses = array(
			0 => __('Cancelled', 'events-manager'),
			1 => __('Active', 'events-manager')
		);
		static::$active_statuses = apply_filters('event_get_active_statuses', $statuses);
		return static::$active_statuses;
	}

	public static function is_id( $id ) {
		if ( is_numeric( $id ) ) {
			return [ 'id' => absint( $id ), 'timeslot_id' => null ];
		} elseif ( is_string( $id ) && preg_match( '/^(\d+)(:(\d+))?$/', $id , $matches) ) {
			return [ 'id' => absint( $id[1] ), 'timeslot_id' => absint( $matches[3] ) ];
		}
		return false;
	}

	/**
	 * Converts a repeating event into a recurring event.
	 *
	 * *WARNING* - This cannot be easily undone, post data/meta is completely deleted in the process.
	 *
	 * @return bool
	 */
	public function convert_to_recurring() {
		global $wpdb;
		if ( $this->is_repeating() ) {
			// go through all the repeated events, remove the post, unset post_id and done!
			$recurrence_set_ids = $wpdb->get_col('SELECT recurrence_set_id FROM ' . EM_EVENT_RECURRENCES_TABLE . ' WHERE event_id = ' . absint($this->event_id) );
			$recurrence_set_ids = implode(',', $recurrence_set_ids);
			$post_ids_subquery = 'SELECT post_id FROM '. EM_EVENTS_TABLE ." WHERE recurrence_set_id IN ( $recurrence_set_ids )";
			$post_deletion = $wpdb->query( 'DELETE FROM '. $wpdb->posts . ' WHERE ID IN (' . $post_ids_subquery . ')');
			if ( $post_deletion !== false ) {
				$meta_deletion = $wpdb->query( 'DELETE FROM ' . $wpdb->postmeta . ' WHERE post_id IN (' . $post_ids_subquery . ')' );
				if ( $meta_deletion !== false ) {
					$update_events = $wpdb->query( 'UPDATE ' . EM_EVENTS_TABLE . " SET post_id = NULL, event_type='recurrence'  WHERE recurrence_set_id IN ( $recurrence_set_ids )" );
					if ( $update_events !== false ) {
						$wpdb->update( EM_EVENTS_TABLE, ['event_type' => 'recurring'], ['event_id' => $this->event_id] );
						$wpdb->update( $wpdb->postmeta, ['meta_value' => 'recurring'], ['meta_key'=> '_event_type', 'post_id' => $this->post_id] );
						$wpdb->update( $wpdb->posts, ['post_type' => $this->event_archetype], ['ID' => $this->post_id] );
						$this->event_type = 'recurring';
						$this->post_type = $this->event_archetype;
						return true;
					} else {
						$this->add_error( 'Deleted post data and meta, but could not update event.' );
					}
				} else {
					$this->add_error( 'Could not delete post meta.' );
				}
			} else {
				$this->add_error( 'Could not delete post data.' );
			}
		} else {
			$this->add_error( sprintf( __('You can only convert a repeating %s', 'events-manager'), __('event', 'events-manager') ) );
		}
		return false;
	}
}

//TODO placeholder targets filtering could be streamlined better
/**
 * This is a temporary filter function which mimicks the old filters in the old 2.x placeholders function
 * @param string $result
 * @param EM_Event $event
 * @param string $placeholder
 * @param string $target
 * @return mixed
 */
function em_event_output_placeholder($result,$event,$placeholder,$target='html'){
	if( $target == 'raw' ) return $result;
	if( in_array($placeholder, array("#_EXCERPT",'#_EVENTEXCERPT','#_EVENTEXCERPTCUT', "#_LOCATIONEXCERPT")) && $target == 'html' ){
		$result = apply_filters('dbem_notes_excerpt', $result);
	}elseif( $placeholder == '#_CONTACTEMAIL' && $target == 'html' ){
		$result = em_ascii_encode($event->get_contact()->user_email);
	}elseif( in_array($placeholder, array('#_EVENTNOTES','#_NOTES','#_DESCRIPTION','#_LOCATIONNOTES','#_CATEGORYNOTES','#_CATEGORYDESCRIPTION')) ){
		if($target == 'rss'){
			$result = apply_filters('dbem_notes_rss', $result);
			$result = apply_filters('the_content_rss', $result);
		}elseif($target == 'map'){
			$result = apply_filters('dbem_notes_map', $result);
		}elseif($target == 'ical'){
			$result = apply_filters('dbem_notes_ical', $result);
		}elseif ($target == "email"){    
			$result = apply_filters('dbem_notes_email', $result); 
	  	}else{ //html
			$result = apply_filters('dbem_notes', $result);
		}
	}elseif( in_array($placeholder, array("#_NAME",'#_LOCATION','#_TOWN','#_ADDRESS','#_LOCATIONNAME',"#_EVENTNAME","#_LOCATIONNAME",'#_CATEGORY')) ){
		if ($target == "rss"){
			$result = apply_filters('dbem_general_rss', $result);
	  	}elseif ($target == "ical"){    
			$result = apply_filters('dbem_general_ical', $result); 
	  	}elseif ($target == "email"){    
			$result = apply_filters('dbem_general_email', $result); 
	  	}else{ //html
			$result = apply_filters('dbem_general', $result); 
	  	}				
	}
	return $result;
}
add_filter('em_category_output_placeholder','em_event_output_placeholder',1,4);
add_filter('em_event_output_placeholder','em_event_output_placeholder',1,4);
add_filter('em_location_output_placeholder','em_event_output_placeholder',1,4);
// FILTERS
// filters for general events field (corresponding to those of  "the _title")
add_filter('dbem_general', 'wptexturize');
add_filter('dbem_general', 'convert_chars');
add_filter('dbem_general', 'trim');
// filters for the notes field in html (corresponding to those of  "the _content")
add_filter('dbem_notes', 'wptexturize');
add_filter('dbem_notes', 'convert_smilies');
add_filter('dbem_notes', 'convert_chars');
add_filter('dbem_notes', 'wpautop');
add_filter('dbem_notes', 'prepend_attachment');
add_filter('dbem_notes', 'do_shortcode');
// filters for the notes field in html (corresponding to those of  "the _content")
add_filter('dbem_notes_excerpt', 'wptexturize');
add_filter('dbem_notes_excerpt', 'convert_smilies');
add_filter('dbem_notes_excerpt', 'convert_chars');
add_filter('dbem_notes_excerpt', 'wpautop');
add_filter('dbem_notes_excerpt', 'prepend_attachment');
add_filter('dbem_notes_excerpt', 'do_shortcode');
// RSS content filter
add_filter('dbem_notes_rss', 'convert_chars', 8);
add_filter('dbem_general_rss', 'esc_html', 8);
// Notes map filters
add_filter('dbem_notes_map', 'convert_chars', 8);
add_filter('dbem_notes_map', 'js_escape');
//embeds support if using placeholders
if ( is_object($GLOBALS['wp_embed']) ){
	add_filter( 'dbem_notes', array( $GLOBALS['wp_embed'], 'run_shortcode' ), 8 );
	add_filter( 'dbem_notes', array( $GLOBALS['wp_embed'], 'autoembed' ), 8 );
}

// booking form notices, overridable to inject other content (e.g. waiting list)
function em_booking_form_status_disabled(){
	echo '<p>'. em_get_option('dbem_bookings_form_msg_disabled') .'</p>';
}
add_action('em_booking_form_status_disabled', 'em_booking_form_status_disabled');

function em_booking_form_status_full(){
	echo '<p>'. em_get_option('dbem_bookings_form_msg_full') .'</p>';
}
add_action('em_booking_form_status_full', 'em_booking_form_status_full');

function em_booking_form_status_closed(){
	echo '<p>'. em_get_option('dbem_bookings_form_msg_closed') .'</p>';
}
add_action('em_booking_form_status_closed', 'em_booking_form_status_closed');

function em_booking_form_status_cancelled(){
	echo '<p>'. em_get_option('dbem_bookings_form_msg_cancelled') .'</p>';
}
add_action('em_booking_form_status_cancelled', 'em_booking_form_status_cancelled');

function em_booking_form_status_already_booked(){
	echo em_get_option('dbem_bookings_form_msg_attending');
	echo '<a href="'. em_get_my_bookings_url() .'">'. em_get_option('dbem_bookings_form_msg_bookings_link') .'</a>';
}
add_action('em_booking_form_status_already_booked', 'em_booking_form_status_already_booked');

/**
 * This function replaces the default gallery shortcode, so it can check if this is a recurring event recurrence and pass on the parent post id as the default post. 
 * @param array $attr
 */
function em_event_gallery_override( $attr = array() ){
	global $post;
	if( !empty($post->post_type) && Archetypes::is_valid_cpt($post->post_type, ['location']) && empty($attr['id']) && empty($attr['ids']) ){
		//no id specified, so check if it's recurring and override id with recurrence template post id
		$EM_Event = em_get_event($post->ID, 'post_id');
		if( $EM_Event->is_recurrence( true) ){
			$attr['id'] = $EM_Event->get_event_recurrence()->post_id;
		}
	}
	return gallery_shortcode($attr);
}
function em_event_gallery_override_init(){
	remove_shortcode('gallery');
	add_shortcode('gallery', 'em_event_gallery_override');
}
add_action('init','em_event_gallery_override_init', 1000); //so that plugins like JetPack don't think we're overriding gallery, we're not i swear!
?>
