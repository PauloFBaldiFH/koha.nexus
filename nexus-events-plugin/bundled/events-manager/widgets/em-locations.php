<?php
/**
 * @author marcus
 * Standard events list widget
 */
class EM_Locations_Widget extends WP_Widget {
	
	var $defaults = array();
	
	public static function init(){
		return register_widget("EM_Locations_Widget");
	}
	
    /** constructor */
    function __construct() {
    	$this->defaults = array(
    		'title' => 'Event Locations',
    		'scope' => 'future',
    		'order' => 'ASC',
    		'limit' => 5,
		    'format_header' => '',
		    'format' => EM_Formats::dbem_block_location_list_item_format(''),
		    'format_footer' => '',
    	    'no_locations_text' => '<div class="em-list-no-items">No locations</div>',
    		'orderby' => 'event_start_date,event_start_time,location_name',
		    'v6' => false,
    	);
        parent::__construct(false, 'Event Locations', ['description' => 'Display a list of event locations on Events Manager.']);
        add_action('wp_loaded', array($this, 'wp_loaded'));
    }

    /** Loads translated strings and updates defaults */
    function wp_loaded() {
		$this->name = __('Event Locations', 'events-manager');
        $this->defaults['title'] = __('Event Locations','events-manager');
        $this->defaults['no_locations_text'] = '<div class="em-list-no-items">'.__('No locations', 'events-manager').'</div>';
        
        $this->em_orderby_options = array(
    		'event_start_date, event_start_time, location_name' => __('Event start date/time, location name','events-manager'),
    		'location_name' => __('Location name','events-manager')
    	);
        
        $this->widem_get_options['description'] = __("Display a list of event locations on Events Manager.", 'events-manager');
    }

    /** @see WP_Widget::widget */
    function widget($args, $instance) {	
    	$instance = array_merge($this->defaults, $instance);

    	echo $args['before_widget'];
    	if( !empty($instance['title']) ){
		    echo $args['before_title'];
		    echo apply_filters('widget_title',$instance['title'], $instance, $this->id_base);
		    echo $args['after_title'];
    	}
    	
	    //make sure no owner searches are being run
		$instance['owner'] = false;
	
	    //legacy stuff - deal with unsaved pre-v6 items, v6 saved and preview modes
	    $v6 = EM_Options::get('v6', null);
	    //add li tags to old widgets that have no forced li wrappers
	    if( ($v6 && empty($instance['v6'])) || $v6 === 'p' || $v6 === 'p' ){
		    $instance = $this->get_v6_instance_options($instance);
	    }
		//get locations
		$locations = EM_Locations::get(apply_filters('em_widget_locations_get_args',$instance));
		//output locations
	    echo '<div class="'. implode(' ', em_get_template_classes('locations-widget')) .'">';
		echo $instance['format_header'];
		if ( count($locations) > 0 ){
			foreach($locations as $location){
				echo $location->output($instance['format']);
			}
		}else{
		    echo $instance['no_locations_text'];
		}
		echo $instance['format_footer'];
		echo '</div>';
		
	    echo $args['after_widget'];
    }
	
	function get_v6_instance_options( $instance ){
		$instance['format_header'] = '';
		$instance['format'] = EM_Formats::dbem_block_location_list_item_format('');
		$instance['format_footer'] = '';
		return $instance;
	}

    /** @see WP_Widget::update */
    function update($new_instance, $old_instance) {
    	//filter the new instance and replace blanks with defaults
    	foreach($this->defaults as $key => $value){
    		if( !isset($new_instance[$key]) ){
    			$new_instance[$key] = $value;
    		}
		    //balance tags and sanitize output formats
		    if( in_array($key, array('format', 'no_locations_text')) ){
		        if( is_multisite() && !em_wp_is_super_admin() ) $new_instance[$key] = wp_kses_post($new_instance[$key]); //for multisite
		        $new_instance[$key] = force_balance_tags($new_instance[$key]);
		    }
    	}
    	return $new_instance;
    }

    /** @see WP_Widget::form */
    function form($instance) {
    	$instance = array_merge($this->defaults, $instance);
	    $v6 = EM_Options::get('v6', null);
	    if( ($v6 === true || $v6 === 'undo') && empty($instance['v6']) ){
		    $instance = $this->get_v6_instance_options($instance);
	    }elseif( empty($instance['v6']) && $instance['format'] !== $this->defaults['format'] ) {
		    // still unmigrated, not saved either during v6
		    $instance['format_header'] = '<ul>';
		    $instance['format_footer'] = '</ul>';
	    }
        ?>
		<p>
			<label for="<?php echo $this->get_field_id('title'); ?>"><?php esc_html_e('Title', 'events-manager'); ?>: </label>
			<input class="widefat" type="text" id="<?php echo $this->get_field_id('title'); ?>" name="<?php echo $this->get_field_name('title'); ?>" value="<?php echo esc_attr($instance['title']); ?>" />
		</p>
		<p>
			<label for="<?php echo $this->get_field_id('limit'); ?>"><?php esc_html_e('Show number of locations','events-manager'); ?>: </label>
			<input type="text" id="<?php echo $this->get_field_id('limit'); ?>" name="<?php echo $this->get_field_name('limit'); ?>" value="<?php echo esc_attr($instance['limit']); ?>" />
		</p>
		<p>
			<label for="<?php echo $this->get_field_id('scope'); ?>"><?php esc_html_e('Scope of the locations','events-manager'); ?>:</label><br/>
			<select class="widefat" id="<?php echo $this->get_field_id('scope'); ?>" name="<?php echo $this->get_field_name('scope'); ?>" >
				<?php foreach( em_get_scopes() as $key => $value) : ?>   
				<option value='<?php echo esc_attr($key) ?>' <?php echo ($key == $instance['scope']) ? "selected='selected'" : ''; ?>>
					<?php echo esc_html($value); ?>
				</option>
				<?php endforeach; ?>
			</select>
		</p>
		<p>
			<label for="<?php echo $this->get_field_id('order'); ?>"><?php esc_html_e('Order By','events-manager'); ?>: </label>
			<select class="widefat" id="<?php echo $this->get_field_id('orderby'); ?>" name="<?php echo $this->get_field_name('orderby'); ?>">
				<?php foreach($this->em_orderby_options as $key => $value) : ?>   
	 			<option value='<?php echo esc_attr($key); ?>' <?php echo ( !empty($instance['orderby']) && $key == $instance['orderby']) ? "selected='selected'" : ''; ?>>
	 				<?php echo esc_html($value); ?>
	 			</option>
				<?php endforeach; ?>
			</select> 
		</p>
		<p>
			<label for="<?php echo $this->get_field_id('order'); ?>"><?php esc_html_e('Order of the locations','events-manager'); ?>:</label><br/>
			<select class="widefat" id="<?php echo $this->get_field_id('order'); ?>" name="<?php echo $this->get_field_name('order'); ?>" >
				<option value="ASC" <?php echo ($instance['order'] == 'ASC') ? 'selected="selected"':''; ?>><?php esc_html_e('Ascending','events-manager'); ?></option>
				<option value="DESC" <?php echo ($instance['order'] == 'DESC') ? 'selected="selected"':''; ?>><?php esc_html_e('Descending','events-manager'); ?></option>
			</select>
		</p>
	    <p>
		    <label for="<?php echo $this->get_field_id('format_header'); ?>"><?php esc_html_e('List item header format','events-manager'); ?>: </label>
		    <textarea rows="5" cols="24" id="<?php echo $this->get_field_id('format_header'); ?>" name="<?php echo $this->get_field_name('format_header'); ?>" class="widefat"><?php echo esc_textarea($instance['format_header'] ); ?></textarea>
	    </p>
	    <p>
		    <label for="<?php echo $this->get_field_id('format'); ?>"><?php esc_html_e('List item format','events-manager'); ?>: </label>
		    <textarea rows="10" cols="24" id="<?php echo $this->get_field_id('format'); ?>" name="<?php echo $this->get_field_name('format'); ?>" class="widefat"><?php echo esc_textarea($instance['format']); ?></textarea>
	    </p>
	    <p>
		    <label for="<?php echo $this->get_field_id('format_footer'); ?>"><?php esc_html_e('List item footer format','events-manager'); ?>: </label>
		    <textarea rows="5" cols="24" id="<?php echo $this->get_field_id('format_footer'); ?>" name="<?php echo $this->get_field_name('format_footer'); ?>" class="widefat"><?php echo esc_textarea($instance['format_footer']); ?></textarea>
	    </p>
		<p>
			<label for="<?php echo $this->get_field_id('no_locations_text'); ?>"><?php esc_html_e('No Locations message','events-manager'); ?>: </label>
			<input type="text" id="<?php echo $this->get_field_id('no_locations_text'); ?>" name="<?php echo $this->get_field_name('no_locations_text'); ?>" value="<?php echo esc_attr( $instance['no_locations_text'] ); ?>" >
		</p>
        <?php 
    }
}
add_action('widgets_init', 'EM_Locations_Widget::init');
?>