<?php

use EM\Archetypes;

/**
 * @author marcus
 * Standard events calendar widget
 */
class EM_Widget_Calendar extends WP_Widget {
	
	var $defaults = array();
	
	public static function init(){
		return register_widget("EM_Widget_Calendar");
	}
	
    /** constructor */
    function __construct() {
    	$this->defaults = array(
    		'title' => 'Calendar',
    		'long_events' => 0,
    		'category' => 0,
		    'scope' => 'all',
		    'calendar_size' => em_get_option('dbem_calendar_default', 'auto'),
		    'calendar_event_style' => em_get_option('dbem_calendar_event_style', 'pill'),
		    'limit' => em_get_option('dbem_display_calendar_events_limit', 3),
			'event_archetype' => '',
    	);
	    $widget_ops = array('description' => "Display your events in a calendar widget.");
	    parent::__construct(false, 'Events Calendar', $widget_ops);
	    add_action('wp_loaded', array($this, 'wp_loaded'));
    }

    /** Loads translated strings and updates defaults */
    function wp_loaded() {
		$this->name = __('Events Calendar','events-manager');
        $this->defaults['title'] = __('Calendar','events-manager');
        $this->widem_get_options['description'] = __("Display your events in a calendar widget.", 'events-manager');
    }

    /** @see WP_Widget::widget */
    function widget($args, $instance) {
    	$instance = array_merge($this->defaults, $instance);
	    $instance['event_archetype'] = $instance['event_archetype'] === '' ? EM_POST_TYPE_EVENT : $instance['event_archetype'];

    	echo $args['before_widget'];
    	if( !empty($instance['title']) ){
		    echo $args['before_title'];
		    echo apply_filters('widget_title',$instance['title'], $instance, $this->id_base);
		    echo $args['after_title'];
    	}
    	//Shall we show a specific month?
		if ( !empty($_REQUEST['calendar_day']) ) {
			$date = explode('-', $_REQUEST['calendar_day']);
			$instance['month'] = $date[1];
			$instance['year'] = $date[0];
		}else{
			$instance['month'] = date("m");
			$instance['year'] = date('Y');
		}
	    
	    //Our Widget Content  
	    echo EM_Calendar::output(apply_filters('em_widget_calendar_get_args',$instance));
	    
	    echo $args['after_widget'];
    }

    /** @see WP_Widget::update */
    function update($new_instance, $old_instance) {
    	//filter the new instance and replace blanks with defaults
    	$new_instance['title'] = (!isset($new_instance['title'])) ? $this->defaults['title']:$new_instance['title'];
    	$new_instance['long_events'] = isset($new_instance['long_events']) ? empty($new_instance['long_events']) : $this->defaults['long_events'];
	    $new_instance['category'] = ($new_instance['category'] == '') ? $this->defaults['category']:$new_instance['category'];
	    $new_instance['scope'] = ($new_instance['scope'] == 'future') ? 'future':$this->defaults['scope'];
	    $allowed_sizes = apply_filters('em_calendar_output_sizes', array('large', 'medium', 'small'));
	    $new_instance['calendar_size'] = in_array( $new_instance['calendar_size'], $allowed_sizes) ? $new_instance['calendar_size'] : $this->defaults['calendar_size'];
	    $allowed_styles = apply_filters('em_calendar_output_event_styles', array('pill', 'dot', 'dots', 'ring'));
	    $new_instance['calendar_event_style'] = in_array( $new_instance['calendar_event_style'] ?? '', $allowed_styles, true ) ? $new_instance['calendar_event_style'] : $this->defaults['calendar_event_style'];
	    $new_instance['limit'] = ( isset($new_instance['limit']) && is_numeric($new_instance['limit']) ) ? absint($new_instance['limit']) : $this->defaults['limit'];
	    $new_instance['event_archetype'] = (!$new_instance['event_archetype']) ? EM_POST_TYPE_EVENT:$new_instance['event_archetype'];
    	return $new_instance;
    }

    /** @see WP_Widget::form */
    function form($instance) {
    	$instance = array_merge($this->defaults, $instance);
        ?>
		<p>
			<label for="<?php echo $this->get_field_id('title'); ?>"><?php _e('Title', 'events-manager'); ?>: </label>
			<input type="text" id="<?php echo $this->get_field_id('title'); ?>" name="<?php echo $this->get_field_name('title'); ?>" value="<?php echo esc_attr($instance['title']); ?>" />
		</p>
		<p>
			<label for="<?php echo $this->get_field_id('long_events'); ?>"><?php _e('Show Long Events?', 'events-manager'); ?>: </label>
			<input type="checkbox" id="<?php echo $this->get_field_id('long_events'); ?>" name="<?php echo $this->get_field_name('long_events'); ?>" value="1" <?php echo ($instance['long_events'] == '1') ? 'checked="checked"':''; ?>/>
		</p>
	    <p>
		    <label for="<?php echo $this->get_field_id('scope'); ?>"><?php _e('Future Events Only?','events-manager'); ?>: </label>
		    <input type="checkbox" id="<?php echo $this->get_field_id('scope'); ?>" name="<?php echo $this->get_field_name('scope'); ?>" value="future" <?php echo ($instance['scope'] == 'future') ? 'checked="checked"':''; ?>/>
	    </p>
		<p>
            <label for="<?php echo $this->get_field_id('category'); ?>"><?php _e('Category IDs','events-manager'); ?>: </label>
            <input type="text" id="<?php echo $this->get_field_id('category'); ?>" name="<?php echo $this->get_field_name('category'); ?>" size="3" value="<?php echo esc_attr($instance['category']); ?>" /><br />
            <em><?php _e('1,2,3 or 2 (0 = all)','events-manager'); ?> </em>
        </p>
	    <?php if ( Archetypes::$types ) : ?>
	    <p>
		    <label for="<?php echo $this->get_field_id('event_archetype'); ?>"><?php _e('Archetype','events-manager'); ?>: </label>
		    <select id="<?php echo $this->get_field_id('event_archetype'); ?>" name="<?php echo $this->get_field_name('event_archetype'); ?>">
			    <option value="auto" <?php selected($instance['event_archetype'], ''); ?>><?php esc_html_e('Default', 'events-manager'); ?></option>
			    <?php foreach(Archetypes::$types as $type => $archetype) : ?>
			    <option value="<?php echo $type; ?>" <?php selected($instance['event_archetype'], $type); ?>><?php echo $archetype['label']; ?></option>
			    <?php endforeach; ?>
		    </select>
	    </p>
	    <?php endif; ?>
	    <p>
		    <label for="<?php echo $this->get_field_id('calendar_size'); ?>"><?php _e('Calendar Size','events-manager'); ?>: </label>
		    <select id="<?php echo $this->get_field_id('calendar_size'); ?>" name="<?php echo $this->get_field_name('calendar_size'); ?>">
			    <option value="auto" <?php selected($instance['calendar_size'], 'auto'); ?>><?php esc_html_e('Responsive', 'events-manager'); ?></option>
			    <option value="large" <?php selected($instance['calendar_size'], 'large'); ?>><?php esc_html_e('Large', 'events-manager'); ?></option>
			    <option value="medium" <?php selected($instance['calendar_size'], 'medium'); ?>><?php esc_html_e('Medium', 'events-manager'); ?></option>
			    <option value="small" <?php selected($instance['calendar_size'], 'small'); ?>><?php esc_html_e('Small', 'events-manager'); ?></option>
		    </select>
	    </p>
	    <p>
		    <label for="<?php echo $this->get_field_id('calendar_event_style'); ?>"><?php _e('Event Style','events-manager'); ?>: </label>
		    <select id="<?php echo $this->get_field_id('calendar_event_style'); ?>" name="<?php echo $this->get_field_name('calendar_event_style'); ?>">
			    <option value="pill" <?php selected($instance['calendar_event_style'], 'pill'); ?>><?php esc_html_e('Pills', 'events-manager'); ?></option>
			    <option value="dot" <?php selected($instance['calendar_event_style'], 'dot'); ?>><?php esc_html_e('Single dot', 'events-manager'); ?></option>
				    <option value="dots" <?php selected($instance['calendar_event_style'], 'dots'); ?>><?php esc_html_e('Multiple dots', 'events-manager'); ?></option>
			    <option value="ring" <?php selected($instance['calendar_event_style'], 'ring'); ?>><?php esc_html_e('Rings', 'events-manager'); ?></option>
		    </select>
	    </p>
	    <p>
		    <label for="<?php echo $this->get_field_id('limit'); ?>"><?php _e('Events per day','events-manager'); ?>: </label>
		    <input type="number" min="0" id="<?php echo $this->get_field_id('limit'); ?>" name="<?php echo $this->get_field_name('limit'); ?>" size="3" value="<?php echo esc_attr($instance['limit']); ?>" /><br />
		    <em><?php _e('Max events shown per calendar day (0 = no limit).','events-manager'); ?></em>
	    </p>
        <?php
    }

}
add_action('widgets_init', 'EM_Widget_Calendar::init');