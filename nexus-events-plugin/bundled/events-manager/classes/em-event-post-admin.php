<?php
/*
 * Events Edit Page
 */

use EM\Archetypes;

class EM_Event_Post_Admin{
	public static function init(){
		global $pagenow;
		if($pagenow == 'post.php' || $pagenow == 'post-new.php' ){ //only needed if editing post
			add_action('admin_head', array('EM_Event_Post_Admin','admin_head')); //I don't think we need this anymore?
			//Meta Boxes
			foreach ( Archetypes::get_cpts(['location', 'repeating']) as $archetype ) {
				add_action('add_meta_boxes_'.$archetype, array('EM_Event_Post_Admin','meta_boxes'), 10, 1);
			}
			add_filter( 'hidden_meta_boxes', [ static::class, 'unhide_recurrences_metabox' ], 10, 2 );
			//Notices
			add_action('admin_notices',array('EM_Event_Post_Admin','admin_notices'));
			// Add body class for event editor styling
			add_filter('admin_body_class', array('EM_Event_Post_Admin','admin_body_class'));
		}
		//Save/Edit actions
		add_filter('wp_insert_post_data',array('EM_Event_Post_Admin','wp_insert_post_data'),100,2); //validate post meta before saving is done
		add_action('save_post',array('EM_Event_Post_Admin','save_post'),1,1); //set to 1 so metadata gets saved ASAP
		add_action('before_delete_post',array('EM_Event_Post_Admin','before_delete_post'),10,1);
		add_action('trashed_post',array('EM_Event_Post_Admin','trashed_post'),10,1);
		add_action('untrash_post',array('EM_Event_Post_Admin','untrash_post'),10,1);
		add_action('untrashed_post',array('EM_Event_Post_Admin','untrashed_post'),10,1);
		//Notices
		add_action('post_updated_messages',array('EM_Event_Post_Admin','admin_notices_filter'),1,1);
	}

	public static function admin_head(){
		global $post, $EM_Event;
		if( empty($EM_Event) && !empty($post) && Archetypes::is_event($post) ){
			$EM_Event = em_get_event($post->ID, 'post_id');
		}
		// Canvas-mode hiding of the mirrored classic postboxes is handled centrally and registry-driven by \EM\Editor\Editor::print_canvas_hide_css() (covers events + locations).
	}

	public static function admin_body_class($classes){
		global $post;
		if( !empty($post) && Archetypes::is_event($post) ){
			$classes .= ' em-event-editor';
		}
		return $classes;
	}

	public static function admin_notices(){
		//When editing
		global $post, $EM_Event, $pagenow;
		if( $pagenow == 'post.php' && Archetypes::is_event($post) ){
			if ( $EM_Event->is_recurring() ) {
				$recurring_events = strtolower( sprintf( __('Recurring %s', 'events-manager'), __('Events', 'events-manager') ) );
				$event_txt = __('Event', 'events-manager');
				$recurring_event = strtolower( sprintf( __('Recurring %s', 'events-manager'), $event_txt ) );
				$warning = "<p><strong>". sprintf( esc_html__( 'WARNING: This is a %s.', 'events-manager'), $recurring_event )."</strong></p>";
				$warning .= "<p>". esc_html( sprintf( __( 'Modifications to %s can be applied to all recurrences and will overwrite any changes made to those individual %s recurrences.', 'events-manager'), $recurring_events, strtolower($event_txt) ) ) . '</p>';
				$warning .= "<p>". sprintf( esc_html__( 'Bookings to individual %s recurrences will be preserved unless you delete tickets or choose to reschedule and delete rescheduled recurrences.', 'events-manager'), $event_txt ) . '</p>';
				?><div class="notice notice-warning is-dismissible"><?php echo $warning; ?></div><?php
			} elseif ( $EM_Event->is_repeating() ) {
				$recurring_events = strtolower( sprintf( __('Repeating %s', 'events-manager'), __('Events', 'events-manager') ) );
				$event_txt = __('Event', 'events-manager');
				$recurring_event = strtolower( sprintf( __('Repeating %s', 'events-manager'), $event_txt ) );
				$warning = "<p><strong>". sprintf( esc_html__( 'WARNING: This is a %s.', 'events-manager'), $recurring_event )."</strong></p>";
				$warning .= "<p>". esc_html( sprintf( __( 'Modifications to %s can be applied to all recurrences and will overwrite any changes made to those individual %s recurrences.', 'events-manager'), $recurring_events, strtolower($event_txt) ) ) . '</p>';
				$warning .= "<p>". sprintf( esc_html__( 'Bookings to individual %s recurrences will be preserved unless you delete tickets or choose to reschedule and delete rescheduled recurrences.', 'events-manager'), $event_txt ) . '</p>';
				$warning .= '<p><a href="'. esc_url( add_query_arg(array('scope'=>'all', 'recurring_event'=>$EM_Event->event_id), em_get_events_admin_url()) ).'">'. esc_html__('You can edit individual recurrences and disassociate them with this repeating event.','events-manager') . '</a></p>';
				?><div class="notice notice-warning is-dismissible"><?php echo $warning; ?></div><?php
			} elseif ( $EM_Event->is_repeated() ) {
				$warning = "<p><strong>".__('WARNING: This is a recurrence in a set of repeating events.', 'events-manager')."</strong></p>";
				$warning .= "<p>". sprintf(__('If you update this event data and save, it could get overwritten if you edit the repeating event template. To make it an independent, <a href="%s">detach it</a>.', 'events-manager'), $EM_Event->get_detach_url())."</p>";
				$warning .= "<p>".sprintf(__('To manage the whole set, <a href="%s">edit the repeating event template</a>.', 'events-manager'),admin_url('post.php?action=edit&amp;post='.$EM_Event->get_recurring_event()->post_id))."</p>";
				?><div class="notice notice-warning is-dismissible"><?php echo $warning; ?></div><?php
			}
			if( !empty($EM_Event->group_id) && function_exists('groups_get_group') ){
				$group = groups_get_group(array('group_id'=>$EM_Event->group_id));
				$warning = sprintf(__('WARNING: This is a event belonging to the group "%s". Other group admins can also modify this event.', 'events-manager'), $group->name);
				?><div class="notice notice-info is-dismissible"><p><?php echo $warning; ?></p></div><?php
			}
		}
	}

	public static function admin_notices_filter($messages){
		//When editing
		global $post, $EM_Notices; /* @var EM_Notices $EM_Notices */
		if( $post->post_type == EM_POST_TYPE_EVENT || $post->post_type == 'event-recurring' ){
			if ( $EM_Notices->count_errors() > 0 ) {
				unset($_GET['message']);
			}
		}
		return $messages;
	}

	/**
	 * Validate event once BEFORE it goes into the database, because otherwise it could get 'published' between now and save_post,
	 * allowing other plugins hooking here to perform incorrect actions e.g. tweet a new event.
	 *
	 * @param array $data
	 * @param array $postarr
	 * @return array
	 */
	public static function wp_insert_post_data( $data, $postarr ){
		global $wpdb, $EM_SAVING_EVENT;
		if( !empty($EM_SAVING_EVENT) ) return $data; //never proceed with this if using EM_Event::save();
		$post_type = $data['post_type'];
		$post_ID = !empty($postarr['ID']) ? $postarr['ID'] : false;
		$is_post_type =  Archetypes::is_event($post_type);
		$doing_add_meta_ajax = defined('DOING_AJAX') && DOING_AJAX && !empty($_REQUEST['action']) && $_REQUEST['action'] == 'add-meta' && check_ajax_referer( 'add-meta', '_ajax_nonce-add-meta', false );  //we don't need to save anything here, we don't use this action
		$saving_status = !in_array($data['post_status'], array('trash','auto-draft')) && !defined('DOING_AUTOSAVE') && !$doing_add_meta_ajax;
		$untrashing = $post_ID && defined('UNTRASHING_'.$post_ID);
		if( !$untrashing && $is_post_type && $saving_status ){
			if( !empty($_REQUEST['_emnonce']) && wp_verify_nonce($_REQUEST['_emnonce'], 'edit_event') ){
				//this is only run if we know form data was submitted, hence the nonce
				$EM_Event = em_get_event($post_ID, 'post_id');
				$EM_Event->post_type = $post_type;
				//Handle Errors by making post draft
				$get_meta = $EM_Event->get_post_meta();
				$validate_meta = $EM_Event->validate_meta();
				if( !$get_meta || !$validate_meta ) $data['post_status'] = 'draft';
			}
		}
		return $data;
	}

	public static function save_post($post_id, $post = false){
		global $wpdb, $EM_Event, $EM_Notices, $EM_SAVING_EVENT, $EM_EVENT_SAVE_POST; /* @var EM_Notices $EM_Notices */
		if( !empty($EM_SAVING_EVENT) ) return; //never proceed with this if using EM_Event::save();
		if ( isset($_GET['preview_id']) && isset($_GET['preview_nonce']) && wp_verify_nonce( $_GET['preview_nonce'], 'post_preview_' . $post_id ) ) return; //don't proceed with saving when previewing, may cause issues
		$post_type = get_post_type($post_id);
		$is_post_type = Archetypes::is_event($post_type);
		$doing_add_meta_ajax = defined('DOING_AJAX') && DOING_AJAX && !empty($_REQUEST['action']) && $_REQUEST['action'] == 'add-meta' && check_ajax_referer( 'add-meta', '_ajax_nonce-add-meta', false ); //we don't need to save anything here, we don't use this action
		$saving_status = !in_array(get_post_status($post_id), array('trash','auto-draft')) && !defined('DOING_AUTOSAVE') && !$doing_add_meta_ajax;
		$EM_EVENT_SAVE_POST = true; //first filter for save_post in EM for events
		if(!defined('UNTRASHING_'.$post_id) && $is_post_type && $saving_status ){
			Archetypes::set_current( $post_type );
			//Reset server timezone to UTC in case other plugins are doing something naughty
			$server_timezone = date_default_timezone_get();
			date_default_timezone_set('UTC');
			//grab event, via post info, reset the $EM_Event variable
			$EM_Event = new EM_Event($post_id, 'post_id');
			$EM_Event->post_type = $post_type;
			//check whether this is a quick save or not, then save accordingly
			if( !empty($_REQUEST['_emnonce']) && wp_verify_nonce($_REQUEST['_emnonce'], 'edit_event') ){
				//this is only run if we know form data was submitted, hence the nonce
				$get_meta = $EM_Event->get_post_meta();
				do_action('em_event_save_pre', $EM_Event); //technically, the event is saved... but the meta isn't. wp doesn't give an pre-intervention action for this (or does it?)
				//if we execute a location save here, we will screw up the current save_post $wp_filter pointer executed in do_action()
        	    //therefore, we save the current pointer position (priority) and set it back after saving the location further down
        	    global $wp_filter, $wp_current_filter;
				$wp_filter_priority = key($wp_filter['save_post']->callbacks);
				$tag = end($wp_current_filter);
				//save the event meta, whether validated or not and which includes saving a location
				$save_meta = $EM_Event->save_meta();
				$validate_meta = $EM_Event->validate_meta(); // Handle Errors by making post draft, but only after we save the event. It should be a saved event but with a 'draft' status
        		//reset save_post pointer in $wp_filter to its original position
        		reset( $wp_filter[$tag]->callbacks );
        		do{
        		   if( key($wp_filter[$tag]->callbacks) == $wp_filter_priority ) break;
        		}while ( next($wp_filter[$tag]->callbacks) !== false );
        		//save categories in case of default category
        		if( em_get_option('dbem_categories_enabled') ) $EM_Event->get_categories()->save();
				//continue whether all went well or not
				if( !$get_meta || !$validate_meta || !$save_meta ){
					//failed somewhere, set to draft, don't publish
					$EM_Event->set_status(null, true);
					if( $EM_Event->is_recurring( true ) ){
						$EM_Notices->add_error( '<strong>'.__('Your event details are incorrect and recurrences cannot be created, please correct these errors first:','events-manager').'</strong>', true); //Always seems to redirect, so we make it static
					}else{
						$EM_Notices->add_error( '<strong>'.sprintf(__('Your %s details are incorrect and cannot be published, please correct these errors first:','events-manager'),__('event','events-manager')).'</strong>', true); //Always seems to redirect, so we make it static
					}
					$EM_Notices->add_error($EM_Event->get_errors(), true); //Always seems to redirect, so we make it static
					apply_filters('em_event_save', false, $EM_Event);
				}else{
					//if this is just published, we need to email the user about the publication, or send to pending mode again for review
					if( (!$EM_Event->is_recurring( true ) && !current_user_can('publish_events')) || ($EM_Event->is_recurring( true ) && !current_user_can('publish_recurring_events')) ){
						if( $EM_Event->is_published() ){ $EM_Event->set_status(0, true); } //no publishing and editing... security threat
					}
					apply_filters('em_event_save', true, $EM_Event);
					//flag a cache refresh if we get here
					$EM_Event->refresh_cache = true;
					add_filter('save_post', 'EM_Event_Post_Admin::refresh_cache', 100000000);
				}
			}else{
				//we're updating only the quick-edit style information, which is only post info saved into the index
				if( $EM_Event->validate() ){
					do_action('em_event_save_pre', $EM_Event); //technically, the event is saved... but the meta isn't. wp doesn't give an pre-intervention action for this (or does it?)
					//first things first, we must make sure we have an index, if not, reset it to a new one:
					$event_truly_exists = $wpdb->get_var('SELECT event_id FROM '.EM_EVENTS_TABLE." WHERE event_id={$EM_Event->event_id}") == $EM_Event->event_id;
					if(empty($EM_Event->event_id) || !$event_truly_exists){ $EM_Event->save_meta(); }
					//we can save the status now
					$EM_Event->get_previous_status(); //before we save anything
					$event_status = $EM_Event->get_status(true);
					//if this is just published, we need to email the user about the publication, or send to pending mode again for review
					if( (!$EM_Event->is_recurring( true ) && !current_user_can('publish_events')) || ($EM_Event->is_recurring( true ) && !current_user_can('publish_recurring_events')) ){
						if( $EM_Event->is_published() ){ $EM_Event->set_status(0, true); } //no publishing and editing... security threat
					}
					//now update the db
					$where_array = array($EM_Event->event_name, $EM_Event->event_owner, $EM_Event->event_slug, $EM_Event->event_private, $EM_Event->event_id);
					$sql = $wpdb->prepare("UPDATE ".EM_EVENTS_TABLE." SET event_name=%s, event_owner=%d, event_slug=%s, event_status={$event_status}, event_private=%d WHERE event_id=%d", $where_array);
					$wpdb->query($sql);
					//If we're saving via quick-edit in MS Global mode, then the categories need to be pushed to the ms global index
					if( EM_MS_GLOBAL && em_get_option('dbem_categories_enabled') && is_main_site() ){
		    			$EM_Event->get_categories()->save_index(); //just save to index, WP should have saved the taxonomy data
					}
					//deal with recurrences
					if( $EM_Event->is_recurring( true ) && $EM_Event->is_published() ){
						//recurrences are (re)saved only if event is published
						$EM_Event->get_recurrence_sets()->save_recurrences();
					}
					apply_filters('em_event_save', true, $EM_Event);
					//flag a cache refresh if we get here
					$EM_Event->refresh_cache = true;
					add_filter('save_post', 'EM_Event_Post_Admin::refresh_cache', 100000000);
				}else{
					do_action('em_event_save_pre', $EM_Event); //technically, the event is saved... but the meta isn't. wp doesn't give an pre-intervention action for this (or does it?)
					//Event doesn't validate, so set status to null
					$EM_Event->set_status(null, true);
					apply_filters('em_event_save', false, $EM_Event);
				}
			}
			self::maybe_publish_location($EM_Event);
			//Set server timezone back, even though it should be UTC anyway
			date_default_timezone_set($server_timezone);

			// handle recurrences (previously handled via EM_Event_Recurring_Post_Admin::save_post but now handled here since regular events can be recurring)
			if ( $EM_Event->is_recurring( true ) ) {
				if ( !$EM_Event->get_recurrence_sets()->save_recurrences() && ( $EM_Event->is_published() || 'future' == $EM_Event->post_status ) ) {
					$EM_Event->set_status( null, true );
					$EM_Notices->add_error( __( 'Something went wrong with the recurrence update...', 'events-manager' ) . __( 'There was a problem saving the recurring events.', 'events-manager' ) );
				}
			}
			$EM_EVENT_SAVE_POST = false; //last filter of save_post in EM for events
			Archetypes::revert_current();
		}
	}

	/**
	 * Refreshes the cache of the current global $EM_Event, provided the refresh_cache flag is set to true within the object and the object has a published state
	 */
	public static function refresh_cache(){
		global $EM_Event;
		//if this is a published event, and the refresh_cache flag was added to this event during save_post, refresh the meta and update the cache
		if( !empty($EM_Event->refresh_cache) && !empty($EM_Event->post_id) && $EM_Event->is_published() ){
			$post = get_post($EM_Event->post_id);
			$EM_Event->load_postdata($post);
			unset($EM_Event->refresh_cache);
			// a clone, so a persistent cache cannot store an emptied bookings child
			wp_cache_set($EM_Event->event_id, clone $EM_Event, 'em_events');
			wp_cache_set($EM_Event->post_id, $EM_Event->event_id, 'em_events_ids');
		}
	}

	/**
	 * Publish the location if the event has just been approved and the location is pending. We assume an editor published the event and approves the location too.
	 * @param EM_Event $EM_Event
	 */
	public static function maybe_publish_location($EM_Event){
		//do a dirty update for location too if it's not published
		if( $EM_Event->is_published() && !empty($EM_Event->location_id) ){
			$EM_Location = $EM_Event->get_location();
			if( $EM_Location->location_status !== 1 ){
				//let's also publish the location
				$EM_Location->set_status(1, true);
			}
		}
	}

	public static function before_delete_post($post_id){
		if( Archetypes::is_event( $post_id ) ){
			$EM_Event = em_get_event($post_id,'post_id');
			do_action('em_event_delete_pre',$EM_Event);
			$EM_Event->delete_meta();
		}
	}

	public static function trashed_post($post_id){
		if( Archetypes::is_event( $post_id ) ){
			global $EM_Notices;
			$EM_Event = em_get_event($post_id,'post_id');
			$EM_Event->set_status(-1);
			$EM_Notices->remove_all(); //no validation/notices needed
		}
	}

	public static function untrash_post($post_id){
		if( Archetypes::is_event( $post_id ) ){
			//set a constant so we know this event doesn't need 'saving'
			if(!defined('UNTRASHING_'.$post_id)) define('UNTRASHING_'.$post_id, true);
		}
	}

	public static function untrashed_post($post_id){
		if( Archetypes::is_event( $post_id ) ){
			global $EM_Notices, $EM_Event;
			$EM_Event = new EM_Event($post_id, 'post_id'); //get a refreshed $EM_Event because otherwise statuses don't get updated by WP
			$EM_Event->set_status( $EM_Event->get_status() );
			$EM_Notices->remove_all(); //no validation/notices needed
		}
	}

	public static function unhide_recurrences_metabox( $hidden, $screen ) {
		// Replace 'your_metabox_id' with the actual ID you used in add_meta_box()
		if ( Archetypes::is_event( $screen->post_type ) ) {
			$key = array_search( 'em-event-recurring', $hidden );
			if ( false !== $key ) {
				unset( $hidden[ $key ] );
			}
		}
		return $hidden;
	}

	public static function meta_boxes( $post ){
		global $EM_Event;
		//since this is the first point when the admin area loads event stuff, we load our EM_Event here
		if( empty($EM_Event) && !empty($post) ){
			$EM_Event = em_get_event($post->ID, 'post_id');
		}
		$screens = array_merge( [Archetypes::$event['cpt']], array_keys(Archetypes::$types ) );
		if( !empty($EM_Event->event_owner_anonymous) ){
			add_meta_box('em-event-anonymous', __('Anonymous Submitter Info','events-manager'), array('EM_Event_Post_Admin','meta_box_anonymous'), $screens, 'side','high');
		}
		add_meta_box('em-event-when', __('When','events-manager'), array('EM_Event_Post_Admin','meta_box_date'), $screens, 'side','high');
		if ( em_get_option('dbem_recurrence_enabled') || ( !$EM_Event->event_id || $EM_Event->is_recurring() ) ) {
			add_meta_box('em-event-recurring', __('Recurrences','events-manager'), array('EM_Event_Recurring_Post_Admin','meta_box_recurrence'), $screens, 'normal','high');
		}
		if(em_get_option('dbem_locations_enabled', true)){
			add_meta_box('em-event-where', __('Where','events-manager'), array('EM_Event_Post_Admin','meta_box_location'), $screens, 'normal','high');
		}
		if( defined('WP_DEBUG') && WP_DEBUG && defined('WP_DEBUG_DISPLAY') && WP_DEBUG_DISPLAY  && (!defined('EM_DEBUG_DISPLAY') || EM_DEBUG_DISPLAY) ){
			add_meta_box('em-event-meta', 'Event Meta (debugging only)', array('EM_Event_Post_Admin','meta_box_metadump'), $screens, 'normal','high');
		}
		if( em_get_option('dbem_rsvp_enabled', true) && $EM_Event->can_manage('manage_bookings','manage_others_bookings') ){
			add_meta_box('em-event-bookings', __('Bookings/Registration','events-manager'), array('EM_Event_Post_Admin','meta_box_bookings'), $screens, 'normal','high');
			if( !empty($EM_Event->event_id) && $EM_Event->event_rsvp ){
				add_meta_box('em-event-bookings-stats', __('Bookings Stats','events-manager'), array('EM_Event_Post_Admin','meta_box_bookings_stats'), $screens, 'side','core');
			}
		}
		if( em_get_option('dbem_attributes_enabled', true) ){
			add_meta_box('em-event-attributes', __('Attributes','events-manager'), array('EM_Event_Post_Admin','meta_box_attributes'), $screens, 'normal','default');
		}
		if( EM_MS_GLOBAL && !is_main_site() && em_get_option('dbem_categories_enabled') ){
			add_meta_box('em-event-categories', __('Site Categories','events-manager'), array('EM_Event_Post_Admin','meta_box_ms_categories'), $screens, 'side','low');
		}
		add_action('post_submitbox_misc_actions', 'EM_Event_Post_Admin::meta_box_action_post_submitbox_start');
	}

	public static function meta_box_action_post_submitbox_start(){
		global $EM_Event;
		?>
		<div class="misc-pub-section misc-pub-post-status misc-event-duplicate-link">
			<a href="<?php echo esc_url($EM_Event->duplicate_url()); ?>"><?php echo esc_html(sprintf(__('Duplicate %s','events-manager'), __('Event','events-manager'))); ?></a>
		</div>
		<?php
	}

	public static function meta_box_metadump(){
		global $post,$EM_Event;
		echo "<pre>"; print_r($EM_Event); echo "</pre>";
	}

	public static function meta_box_anonymous(){
		global $EM_Event;
		?>
		<div class='updated'><p><?php echo sprintf(__('This %s was submitted by a guest. You will find their details in the <em>Anonymous Submitter Info</em> box','events-manager'), __('event', 'events-manager')); ?></p></div>
		<p><strong><?php _e('Name','events-manager'); ?> :</strong> <?php echo $EM_Event->event_owner_name; ?></p>
		<p><strong><?php _e('Email','events-manager'); ?> :</strong> <?php echo $EM_Event->event_owner_email; ?></p>
		<?php
	}

	public static function meta_box_date(){
		//create meta box check of date nonce
		?><input type="hidden" name="_emnonce" value="<?php echo wp_create_nonce('edit_event'); ?>" /><?php
		em_locate_template('forms/event/when.php', true);
		EM_Events::add_editor_js_vars();
	}

	public static function meta_box_bookings_stats(){
		em_locate_template('forms/event/booking-stats.php',true);
	}

	public static function meta_box_bookings(){
		EM_Events::add_editor_js_vars();
		em_locate_template('forms/event/bookings.php', true);
		add_action('admin_footer',array('EM_Event_Post_Admin','meta_box_bookings_overlay'));
	}

	public static function meta_box_bookings_overlay(){
		em_locate_template('forms/tickets-form.php', true); //put here as it can't be in the add event form
	}

	public static function meta_box_attributes(){
		em_locate_template('forms/event/attributes.php',true);
	}

	public static function meta_box_location(){
		em_locate_template('forms/event/location.php',true);
	}

	public static function meta_box_ms_categories(){
		global $EM_Event;
		EM_Object::ms_global_switch();
		$categories = EM_Categories::get(array('hide_empty'=>false));
		?>
		<?php if( count($categories) > 0 ): ?>
			<p class="ms-global-categories">
			 <?php $selected = $EM_Event->get_categories()->get_ids(); ?>
			 <?php $walker = new EM_Walker_Category(); ?>
			 <?php $args_em = array( 'hide_empty' => 0, 'name' => 'event_categories[]', 'hierarchical' => true, 'id' => EM_TAXONOMY_CATEGORY, 'taxonomy' => EM_TAXONOMY_CATEGORY, 'selected' => $selected, 'walker'=> $walker); ?>
			 <?php echo walk_category_dropdown_tree($categories, 0, $args_em); ?>
			</p>
		<?php else: ?>
			<p><?php sprintf(__('No categories available, <a href="%s">create one here first</a>','events-manager'), get_bloginfo('wpurl').'/wp-admin/admin.php?page=events-manager-categories'); ?></p>
		<?php endif; ?>
		<!-- END Categories -->
		<?php
		EM_Object::ms_global_switch_back();
	}
}
add_action('admin_init',array('EM_Event_Post_Admin','init'));
add_action('rest_api_init',array('EM_Event_Post_Admin','init')); //also register save/edit hooks for REST-driven saves (e.g. Gutenberg)

/*
 * Recurring Events
 */
class EM_Event_Recurring_Post_Admin{
	public static function init(){
		global $pagenow;
		if($pagenow == 'post.php' || $pagenow == 'post-new.php' ){ //only needed if editing post
			add_action('admin_head', array('EM_Event_Recurring_Post_Admin','admin_head'));
			//Meta Boxes
			foreach ( Archetypes::get_cpts([], ['repeating']) as $post_type ) {
				add_action('add_meta_boxes_' . $post_type, array('EM_Event_Recurring_Post_Admin','meta_boxes'), 10, 1);
			}
			//Notices
			add_action('admin_notices',array('EM_Event_Post_Admin','admin_notices')); //shared with posts
		}
		//Save/Edit actions
		add_action('save_post',array('EM_Event_Recurring_Post_Admin','save_post'),10000,1); //late priority for checking non-EM meta data added later
		add_action('before_delete_post',array('EM_Event_Recurring_Post_Admin','before_delete_post'),10,1);
		add_action('trashed_post',array('EM_Event_Recurring_Post_Admin','trashed_post'),10,1);
		add_action('untrash_post',array('EM_Event_Recurring_Post_Admin','untrash_post'),10,1);
		add_action('untrashed_post',array('EM_Event_Recurring_Post_Admin','untrashed_post'),10,1);
		//Notices
		add_action('post_updated_messages',array('EM_Event_Post_Admin','admin_notices_filter'),1,1); //shared with posts
	}

	public static function admin_head(){
		global $post, $EM_Event;
		if( !empty($post) && Archetypes::is_repeating( $post ) ){
			$EM_Event = em_get_event($post->ID, 'post_id');
		}
	}

	/**
	 * Beacuse in wp admin repeated events get saved early on during save_post, meta added by  other plugins to the repeating event template don't get copied over to recurrences
	 * This re-saves meta late in save_post to correct this issue, in the future when recurrences refer to one post, this shouldn't be an issue
	 * @param int $post_id
	 */
	public static function save_post($post_id){
		global $wpdb, $EM_Notices, $EM_SAVING_EVENT, $EM_EVENT_SAVE_POST;
		if( !empty($EM_SAVING_EVENT) ) return; //never proceed with this if using EM_Event::save(); which only gets executed outside wp admin
	}

	public static function before_delete_post($post_id){
		$post_type = get_post_type($post_id);
		if( Archetypes::is_repeating( $post_type ) ){
			$EM_Event = em_get_event($post_id,'post_id');
			do_action('em_event_delete_pre',$EM_Event);
			//now delete recurrences
			//only delete other events if this isn't a draft-never-published event
			if( !empty($EM_Event->event_id) ){
    			$events_array = EM_Events::get( array('recurring_event'=>$EM_Event->event_id, 'scope'=>'all', 'status'=>'everything' ) );
    			foreach($events_array as $event){
    				/* @var $event EM_Event */
    				if($EM_Event->event_id == $event->get_recurrence_set()->event_id ){
    					wp_delete_post($event->post_id, true);
    				}
    			}
			}
			// get the regular post type of this archetype, or default to main type
			$post_type = str_replace('-repeating', '', $post_type);
			$EM_Event->post_type = Archetypes::is_valid_cpt($post_type) ? $post_type : EM_POST_TYPE_EVENT; //trick it into thinking it's one event.
			$EM_Event->delete_meta();
		}
	}

	public static function trashed_post($post_id){
		if ( Archetypes::is_repeating( get_post_type($post_id) ) ) {
			global $EM_Notices, $wpdb;
			$EM_Event = em_get_event($post_id,'post_id');
			$EM_Event->set_status(-1);
			//only trash other events if this isn't a draft-never-published event
			if( !empty($EM_Event->event_id) ){
    			//now trash recurrences
    			$events_array = EM_Events::get( array('recurring_event'=>$EM_Event->event_id, 'scope'=>'all', 'status'=>'everything' ) );
    			foreach($events_array as $event){
    				/* @var $event EM_Event */
    				if( $EM_Event->event_id == $event->get_recurrence_set()->event_id ){ //double check the event is a recurrence of this event
    					wp_trash_post($event->post_id);
    				}
    			}
			}
			$EM_Notices->remove_all(); //no validation/notices needed
		}
	}

	public static function untrash_post($post_id){
		if ( Archetypes::is_repeating( get_post_type($post_id) ) ) {
			//set a constant so we know this event doesn't need 'saving'
			if(!defined('UNTRASHING_'.$post_id)) define('UNTRASHING_'.$post_id, true);
			$EM_Event = em_get_event($post_id,'post_id');
			//only untrash other events if this isn't a draft-never-published event, because if so it never had other events to untrash
			if( !empty($EM_Event->event_id) ){
    			$events_array = EM_Events::get( array('recurring_event'=>$EM_Event->event_id, 'scope'=>'all', 'status'=>'everything' ) );
    			foreach($events_array as $event){
    				/* @var $event EM_Event */
    				if( $EM_Event->event_id == $event->get_recurrence_set()->event_id && $event->post_id ){
    					wp_untrash_post($event->post_id);
    				}
    			}
			}
		}
	}

	public static function untrashed_post($post_id){
		if ( Archetypes::is_repeating( get_post_type($post_id) ) ) {
			global $EM_Notices;
			$EM_Event = new EM_Event($post_id, 'post_id'); //get a refreshed $EM_Event because otherwise statuses don't get updated by WP
			$EM_Event->set_status( $EM_Event->get_status() );
			$EM_Notices->remove_all(); //no validation/notices needed
		}
	}

	public static function meta_boxes( $post ){
		global $EM_Event;
		//since this is the first point when the admin area loads event stuff, we load our EM_Event here
		if( empty($EM_Event) && !empty($post) ){
			$EM_Event = em_get_event($post->ID, 'post_id');
			$EM_Event->event_type = 'repeating';
		}
		$screens = Archetypes::get_cpts([], ['repeating']);
		if( !empty($EM_Event->event_owner_anonymous) ){
			add_meta_box('em-event-anonymous', __('Anonymous Submitter Info','events-manager'), array('EM_Event_Post_Admin','meta_box_anonymous'), $screens, 'side','high');
		}
		add_meta_box('em-event-when', __('When','events-manager'), array('EM_Event_Post_Admin','meta_box_date'), $screens, 'side','high');
		add_meta_box('em-event-recurring', __('Recurrences','events-manager'), array('EM_Event_Recurring_Post_Admin','meta_box_recurrence'), $screens, 'normal','high');
		//add_meta_box('em-event-meta', 'Event Meta (debugging only)', array('EM_Event_Post_Admin','meta_box_metadump'), $screens, 'normal','high');
		if(em_get_option('dbem_locations_enabled', true)){
			add_meta_box('em-event-where', __('Where','events-manager'), array('EM_Event_Post_Admin','meta_box_location'), $screens, 'normal','high');
		}
		if( em_get_option('dbem_rsvp_enabled') && $EM_Event->can_manage('manage_bookings','manage_others_bookings') ){
			add_meta_box('em-event-bookings', __('Bookings/Registration','events-manager'), array('EM_Event_Post_Admin','meta_box_bookings'), $screens, 'normal','high');
		}
		if( em_get_option('dbem_attributes_enabled') ){
			add_meta_box('em-event-attributes', __('Attributes','events-manager'), array('EM_Event_Post_Admin','meta_box_attributes'), $screens, 'normal','default');
		}
		if( EM_MS_GLOBAL && !is_main_site() && em_get_option('dbem_categories_enabled') ){
			add_meta_box('em-event-categories', __('Site Categories','events-manager'), array('EM_Event_Post_Admin','meta_box_ms_categories'), $screens, 'side','low');
		}
		if( defined('WP_DEBUG') && WP_DEBUG && defined('WP_DEBUG_DISPLAY') && WP_DEBUG_DISPLAY ){
		    add_meta_box('em-event-meta', 'Event Meta (debugging only)', array('EM_Event_Post_Admin','meta_box_metadump'), $screens, 'normal','high');
		}
	}

	public static function meta_box_recurrence( $post ){
		global $EM_Event;
		if ( empty($EM_Event) && !empty($post) ) {
			$EM_Event = em_get_event($post->ID, 'post_id');
			$EM_Event->event_type = 'repeating';
		} elseif ( Archetypes::is_repeating( $post ) ) {
			$EM_Event->event_type = 'repeating';
		}
		?>
		<div class="em">
			<?php em_locate_template('forms/event/when/recurring/recurrences.php', true); ?>
		</div>
		<?php
	}
}
add_action('admin_init',array('EM_Event_Recurring_Post_Admin','init'));
add_action('rest_api_init',array('EM_Event_Recurring_Post_Admin','init')); //also register save/edit hooks for REST-driven saves (e.g. Gutenberg)