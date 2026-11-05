<?php
namespace EM_Event_Locations;
/**
 * Class EM_Event_Location
 * This class is to be extended by any event location type. The only time this class is not used when not extended is if
 * @property-read string $type
 * @property array $data
 * @property string $event
 */
class Event_Location {
	/**
	 * @var \EM_Event
	 */
	protected $event;
	/**
	 * The type name of this location type, used to store in the database. Use alphanmeric characters (a-z, A-Z, 0-9), dashes and underscores only.
	 * @var string
	 */
	public static $type;
	/**
	 * Represents shortcut property names for an event location child object that can be accessed safely which then refers to the EM_Event object.
	 * This is a map of property names as keys to custom field names in the event_attributes array property of EM_Event.
	 * Naming conventions should follow the lines of lowercase event_location_{static::$type}(_$property_name), for example a url would have event_location_url as a url, and event_location_url_text for link text
	 * @var array
	 */
	public $properties = array();
	/**
	 * Contains associative array of data of this event location. Data is accessed via getters and setters and keys must correspond to values in the $properties property.
	 * @var array
	 */
	protected $data = array();
	/**
	 * The admin template path, if there is one.
	 * @var string
	 * @see EM_Event_Location::load_admin_template()
	 */
	public static $admin_template;
	
	public static function init(){
		Event_Locations::register( static::$type, get_called_class() );
	}
	
	/**
	 * EM_Event_Location constructor.
	 * @param \EM_Event $EM_Event
	 */
	public function __construct( $EM_Event ) {
		if( is_object($EM_Event) && property_exists($EM_Event, 'event_id') ){ // we check for the event_id property in case we're dealing with an extended class
			$this->event = $EM_Event;
		}
	}
	
	/**
	 * @param $name
	 * @return string|null|array
	 */
	public function __get( $name ) {
		if( $name == 'type' ){
			return static::$type;
		}elseif( $name == 'event' ){
			return $this->event;
		}elseif( $name == 'data' ){
			return $this->data;
		}elseif( in_array($name, $this->properties) && array_key_exists($name, $this->data) ){
			return $this->data[$name];
		}
		return null;
	}
	
	public function __set($name, $value) {
		if( $name === 'event' && is_object($value) && property_exists($value, 'event_id') ){ // we check for the event_id property in case we're dealing with an extended class
			$this->event = $value;
		}elseif( $name == 'data' && is_array($value) ){
			$this->data = $value;
		}elseif( in_array($name, $this->properties) ){
			$this->data[$name] = $value;
		}
	}
	
	public function __isset($name) {
		if( in_array($name, $this->properties) ){
			return isset($this->data[$name]);
		}
		return false;
	}
	
	/**
	 * @param array $event_meta     Array of event meta, if not supplied meta is obtained from linked event object.
	 * @param bool $reload          Reloads post meta again into object, by default previously loaded data will be re-used.
	 */
	public function load_postdata( $event_meta = array(), $reload = false ){
		if( empty($event_meta) ) $event_meta = $this->event->get_event_meta();
		$base_key = '_event_location_'.static::$type;
		foreach( $event_meta as $event_meta_key => $event_meta_val ){
			if( $event_meta_key == $base_key ){
				// in case we have something like _event_location_url which is the actual URL of a Event_Location_URL object/type.
				$this->data[static::$type] = ( is_array($event_meta_val) ) ? $event_meta_val[0]:$event_meta_val;
				$this->data[static::$type] = \EM_Object::maybe_unserialize($this->data[static::$type]);
			}elseif( substr($event_meta_key, 0, strlen($base_key) ) == $base_key ){
				// event location data is placed directly into the event_location_data array and referenced via get_event_location()
				$key = str_replace('_event_location_'.static::$type.'_', '', $event_meta_key);
				$this->data[$key] = ( is_array($event_meta_val) ) ? $event_meta_val[0]:$event_meta_val;
				$this->data[$key] = \EM_Object::maybe_unserialize($this->data[$key]);
			}
		}
		do_action('em_event_location_load_postdata', $this);
	}
	
	/**
	 * @param array $post
	 * @return boolean
	 */
	public function get_post(){
		$this->data = array();
		return apply_filters('em_event_location_get_post', true, $this);
	}
	
	/**
	 * @return boolean
	 */
	public function validate(){
		return apply_filters('em_event_location_validate', false, $this);
	}
	
	public function save(){
		if( is_numeric($this->event->post_id) && $this->event->post_id > 0 && static::$type !== null ){
			$this->reset_data();
			foreach( $this->properties as $prop ){
				$meta_key = $prop == static::$type ? '_event_location_'.$prop : '_event_location_'.static::$type.'_'.$prop;
				if( $this->$prop !== null ){
					update_post_meta( $this->event->post_id, $meta_key, $this->$prop );
				}else{
					delete_post_meta( $this->event->post_id, $meta_key );
				}
			}
		}
		return apply_filters('em_event_location_save', true, $this);
	}
	
	public function delete(){
		$this->reset_data();
		$this->data = array();
		do_action('em_event_location_deleted', $this);
		return apply_filters('em_event_location_delete', true, $this);
	}
	
	/**
	 * Deletes stored information about this location type in the database
	 * @return int|false
	 */
	final function reset_data(){
		if( is_numeric($this->event->post_id) && $this->event->post_id > 0 ){
			global $wpdb;
			$result = $wpdb->query( $wpdb->prepare('DELETE FROM '.$wpdb->postmeta." WHERE post_id=%d AND meta_key LIKE %s AND meta_key != '_event_location_type'", $this->event->post_id, "_event_location_{$this->type}_%") );
			wp_cache_delete( $this->event->post_id, 'post_meta' ); //refresh cache to prevent looking at old data
			return $result;
		}
		return false;
	}
	
	public function get_admin_column(){
		return $this->get_label('singular');
	}
	
	/**
	 * Returns whether or not this event location is enabled for use.
	 * @return bool
	 */
	public static function is_enabled(){
		$location_types = em_get_option('dbem_location_types', array());
		return !empty($location_types[static::$type]);
	}
	
	/**
	 * Loads admin template automatically if static $admin_template is set to a valid path in templates folder.
	 * Classes with custom forms outside of template folders can override this function and provide their own HTML that will go in the loop of event location type forms.
	 */
	public static function load_admin_template(){
		if( static::$admin_template ){
			em_locate_template( static::$admin_template, true );
		}
	}
	
	/**
	 * Outputs additional warning info to user if they're switching event location types, this may include additional information about what may happen to event location data.
	 * For example, webinars on third party platforms may get deleted too, which deserves a mention and should be marked up with surrounding p tags if necessary.
	 */
	public function admin_delete_warning(){
		echo '';
	}
	
	public static function get_label( $label_type = 'siingular' ){
		//override and return plural name.
		return static::$type;
	}
	
	public function output( $what = null, $target = null ){
		if( $what !== null && $what !== 'type' ){
			return esc_html($this->$what);
		}else{
			return static::get_label();
		}
	}
	
	public function get_ical_location(){
		return false;
	}
	
	public function to_api(){
		return array_merge( $this->data, array(
			'type' => static::$type,
		));
	}
}

//include default Event Locations
include('em-event-location-url.php');