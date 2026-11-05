<?php

use EM\Archetypes;

class EM_Event_Posts_Admin{
	public static function init(){
		global $pagenow;
		if( $pagenow == 'edit.php' && !empty($_REQUEST['post_type']) && Archetypes::is_event( $_REQUEST['post_type'] ) ){ //only needed for events list
			$post_type = $_REQUEST['post_type'];
			$class = Archetypes::is_repeating( $post_type ) ? 'EM_Event_Recurring_Posts_Admin' : 'EM_Event_Posts_Admin';
			if( !empty($_REQUEST['category_id']) && is_numeric($_REQUEST['category_id']) ){
				$term = get_term_by('id', absint($_REQUEST['category_id']), EM_TAXONOMY_CATEGORY);
				if( !empty($term->slug) ){
					$_REQUEST['category_id'] = $term->slug;
				}
			}
			//admin warnings
            add_action('admin_notices', [ $class, 'admin_notices' ]);
			//hide some cols by default:
			$screen = 'edit-'. $post_type;
			$hidden = get_user_option( 'manage' . $screen . 'columnshidden' );
			if( $hidden === false ){
				$hidden = array('event-id');
				update_user_option(get_current_user_id(), "manage{$screen}columnshidden", $hidden, true);
			}
			//deal with actions
			$row_action_type = is_post_type_hierarchical( $post_type ) ? 'page_row_actions' : 'post_row_actions';
			if ( ($_REQUEST['post_status'] ?? '') !== 'trash' ) {
				add_filter($row_action_type, [ $class, 'row_actions' ],10,2);
			}
			add_action('admin_head', [ $class, 'admin_head' ] );

		}
		foreach ( Archetypes::get_cpts(['location']) as $post_type ) {
			$class = Archetypes::is_repeating( $post_type ) ? 'EM_Event_Recurring_Posts_Admin' : 'EM_Event_Posts_Admin';
			//collumns
			add_filter('manage_'.$post_type.'_posts_columns' , array( $class,'columns_add'));
			add_action('manage_'.$post_type.'_posts_custom_column' , array( $class,'columns_output'),10,2 );
			add_filter('manage_edit-'.$post_type.'_sortable_columns', array( 'EM_Event_Posts_Admin','sortable_columns') );
			//clean up the views in the admin selection area - WIP
			//add_filter('views_edit-'.$post_type, array( $class,'restrict_views'),10,2);
			//add filters to event post list tables
		}
		add_action('restrict_manage_posts', array('EM_Event_Posts_Admin','restrict_manage_posts'));
	}
	
	public static function admin_head(){
		//quick hacks to make event admin table make more sense for events
		?>
		<script type="text/javascript">
			jQuery(document).ready( function($){
				$('.inline-edit-date').prev().css('display','none').next().css('display','none').next().css('display','none');
				$('.em-detach-link').on('click', function( event ){
					if( !confirm(EM.event_detach_warning) ){
						event.preventDefault();
						return false;
					}
				});
				$('.em-delete-recurrence-link').on('click', function( event ){
					if( !confirm(EM.delete_recurrence_warning) ){
						event.preventDefault();
						return false;
					}
				});
			});
		</script>
		<style>
			table.fixed{ table-layout:auto !important; }
			.tablenav select[name="m"] { display:none; }
		</style>
		<?php
	}
	
    public static function admin_notices(){
        if( !empty($_REQUEST['recurring_event']) && is_numeric($_REQUEST['recurring_event']) ){
			$EM_Event = em_get_event( absint($_REQUEST['recurring_event']) );
			if ( $EM_Event->is_repeating() ) {
				?>
				<div class="notice notice-info">
					<p><?php echo sprintf(esc_html__('You are viewing individual recurrences of %s.', 'events-manager'), '<a href="'.$EM_Event->get_edit_url().'">'.$EM_Event->event_name.'</a>'); ?></p>
					<p><?php echo sprintf( esc_html__('You can edit individual recurrences and disassociate them with this %s.', 'events-manager'), esc_html__('repeating event', 'events-manager')); ?></p>
					<?php
					if ( em_get_option('dbem_recurrence_enabled') && em_get_option('dbem_recurrence_convert_enabled') ) {
						$convert_url = esc_url( add_query_arg( ['action' => 'convert_to_recurrence', 'event_id' => $EM_Event->event_id, 'nonce' => 'x'] ) );
						$convert_nonce = wp_create_nonce('convert_to_recurrence_'.$EM_Event->event_id);
						?>
						<p><?php echo sprintf( esc_html__('You can also %s into a single recurring event.', 'events-manager'), '<a href="'. $convert_url .'" class="em-convert-recurrence-link" data-nonce="' . $convert_nonce . '">'. esc_html__('convert the entire repeating event series', 'events-manager') . '</a>'); ?></p>
						<?php
						$warning = esc_html__('This will delete all event recurrence posts/pages, and unify them into one URL. Any 404 pages resulting from these will automatically 302-redirect to the recurring event (which will be a new URL).', 'events-manager');
						EM\Scripts_and_Styles::add_js_var('convert_recurring_warning', __('Are you sure you want to convert this repeating event?', 'events-manager') . "\n\n" . __('WARNING: This action cannot be undone.', 'events-manager') . "\n\n" . $warning);
					}
					?>
				</div>
				<?php
			}
        }
    }
	
	/**
	 * Handles WP_Query filter option in the admin area, which gets executed before EM_Event_Post::parse_query
	 * Not yet in use 
	 */
	public static function parse_query(){
		global $wp_query;
		//Search Query Filtering
	    if( !empty($wp_query->query_vars[EM_TAXONOMY_CATEGORY]) && is_numeric($wp_query->query_vars[EM_TAXONOMY_CATEGORY]) ){
	        //sorts out filtering admin-side as it searches by id
	        $term = get_term_by('id', $wp_query->query_vars[EM_TAXONOMY_CATEGORY], EM_TAXONOMY_CATEGORY);
	        $wp_query->query_vars[EM_TAXONOMY_CATEGORY] = ( $term !== false && !is_wp_error($term) )? $term->slug:0;
	    }
		if( !empty($wp_query->query_vars['post_type']) && Archetypes::is_event( $wp_query->query_vars['post_type'] ) && ( empty($wp_query->query_vars['post_status']) || !in_array($wp_query->query_vars['post_status'], ['trash','pending','draft'] ) ) ) {
		    //Set up Scope for EM_Event_Post
			$wp_query->query_vars['scope'] = (!empty($_REQUEST['scope'])) ? $_REQUEST['scope']:'future';
		}
	}
	
	/**
	 * Adds Future view to make things simpler, and also changes counts if user doesn't have edit_others_events permission
	 * @param array $views
	 * @return array
	 */
	public static function restrict_views( $views ){
		global $wp_query;
		//TODO alter views of locations, events and recurrences, specifically find a good way to alter the wp_count_posts method to force user owned posts only
		$post_type = get_current_screen()->post_type;
		if( Archetypes::is_event( $post_type ) ){
			//get counts for future events
			$num_posts = wp_count_posts( $post_type, 'readable' );
			//prepare to alter cache if neccessary
			if( !isset($num_posts->em_future) ){
				$cache_key = $post_type;
				$user = wp_get_current_user();
				if ( is_user_logged_in() && !current_user_can('read_private_events') ) {
					$cache_key .= '_readable_' . $user->ID; //as seen on wp_count_posts
				}
				$args = array('scope'=>'future', 'status'=>'all');
				if( Archetypes::is_repeating( $post_type ) ) $args['recurring'] = 1;
				$num_posts->em_future = EM_Events::count($args);
				wp_cache_set($cache_key, $num_posts, 'counts');
			}
			$class = '';
			//highlight the 'Future' status if necessary
			if( empty($_REQUEST['post_status']) && !empty($wp_query->query_vars['scope']) && $wp_query->query_vars['scope'] == 'future'){
				$class = ' class="current"';
				foreach($views as $key => $view){
					$views[$key] = str_replace(' class="current"','', $view);
				}
			}
			//change the 'All' status to have scope=all
			$views['all'] = str_replace('edit.php?', 'edit.php?scope=all&', $views['all'] );
			//merge new custom status into views
			$old_views = $views;
			$views = array('em_future' => "<a href='edit.php?post_type=$post_type'$class>" . sprintf( _nx( 'Future <span class="count">(%s)</span>', 'Future <span class="count">(%s)</span>', $num_posts->em_future, 'events', 'events-manager'), number_format_i18n( $num_posts->em_future ) ) . '</a>');
			$views = array_merge($views, $old_views);
		}
		
		return $views;
	}
	
	public static function restrict_manage_posts(){
		global $wp_query;
		if( Archetypes::is_event( $wp_query->query_vars['post_type'] ) ){
			?>
			<select name="scope">
				<?php
				$scope = (!empty($wp_query->query_vars['scope'])) ? $wp_query->query_vars['scope']:'future';
				foreach ( em_get_scopes() as $key => $value ) {
					$selected = "";
					if ($key == $scope)
						$selected = "selected='selected'";
					echo "<option value='$key' $selected>$value</option>  ";
				}
				?>
			</select>
			<?php
			if( em_get_option('dbem_categories_enabled') ){
				//Categories
	            $selected = !empty($_GET['event-categories']) ? $_GET['event-categories'] : 0;
				wp_dropdown_categories(array( 'hide_empty' => 1, 'name' => EM_TAXONOMY_CATEGORY,
                              'hierarchical' => true, 'orderby'=>'name', 'id' => EM_TAXONOMY_CATEGORY,
                              'taxonomy' => EM_TAXONOMY_CATEGORY, 'selected' => $selected,
                              'show_option_all' => __('View all categories')));
			}
            if( !empty($_REQUEST['author']) ){
            	?>
            	<input type="hidden" name="author" value="<?php echo esc_attr($_REQUEST['author']); ?>" >
            	<?php            	
            }
		}
	}
	
	public static function views($views){
		if( !current_user_can('edit_others_events') ){
			//alter the views to reflect correct numbering
			 
		}
		return $views;
	}
	
	public static function columns_add($columns) {
		if( array_key_exists('cb', $columns) ){
			$cb = $columns['cb'];
	    	unset($columns['cb']);
	    	$id_array = array('cb'=>$cb, 'event-id' => sprintf(__('%s ID','events-manager'),__('Event','events-manager')));
		}else{
	    	$id_array = array('event-id' => sprintf(__('%s ID','events-manager'),__('Event','events-manager')));
		}
	    unset($columns['comments']);
	    unset($columns['date']);
	    unset($columns['author']);
	    $columns = array_merge($id_array, $columns, array(
	    	'location' => __('Location','events-manager'),
	    	'date-time' => __('Date and Time','events-manager'),
	    	'author' => __('Owner','events-manager'),
	    	'extra' => ''
	    ));
	    if( !em_get_option('dbem_locations_enabled') ){
	    	unset($columns['location']);
	    }
	    return $columns;
	}
	
	public static function columns_output( $column ) {
		global $post, $EM_Event;
		$EM_Event = em_get_event($post, 'post_id');
		/* @var $post EM_Event */
		switch ( $column ) {
			case 'event-id':
				echo $EM_Event->event_id;
				if ( defined('EM_DEBUG') && EM_DEBUG && $EM_Event->is_recurrence( true ) ) {
					echo ' | Set #' . $EM_Event->recurrence_set_id;
				}
				break;
			case 'location':
				//get meta value to see if post has location, otherwise
				$EM_Location = $EM_Event->get_location();
				if( $EM_Event->has_location() ){
					$actions = array();
					$actions[] = "<a href='". esc_url($EM_Location->get_permalink())."'>". esc_html__('View') ."</a>";
					if( $EM_Location->can_manage('edit_locations', 'edit_others_locations') ) {
						$actions[] = "<a href='". esc_url($EM_Location->get_edit_url())."'>". esc_html__('Edit') ."</a>";
					}
					echo "<strong><a href='". $EM_Location->get_permalink()."'>" . $EM_Location->location_name . "</a></strong>";
					echo "<span class='row-actions'> - ". implode(' | ', $actions) . "</span>";
					echo "<br/>" . $EM_Location->location_address . " - " . $EM_Location->location_town;
				}elseif( $EM_Event->has_event_location() ) {
					echo $EM_Event->get_event_location()->get_admin_column();
				}else{
					echo __('None','events-manager');
				}
				break;
			case 'date-time':
				//get meta value to see if post has location, otherwise
				$localised_start_date = $EM_Event->start()->i18n( $EM_Event->get_option('date_format'));
				$localised_end_date = $EM_Event->end()->i18n( $EM_Event->get_option('date_format'));
				if( $EM_Event->get_option('dbem_event_status_enabled') && $EM_Event->event_active_status === 0 ) {
					echo '<span class="event-cancelled">';
				}
				echo $localised_start_date;
				echo ($localised_end_date != $localised_start_date) ? " - $localised_end_date":'';
				if( $EM_Event->get_option('dbem_event_status_enabled') && $EM_Event->event_active_status === 0 ) {
					echo '</span>';
					echo '<span class="dashicons dashicons-info em-tooltip" style="font-size:16px; color:#ccc; padding-top:2px;" title="'. esc_html__('Cancelled', 'events-manager') .'"></span>';
				}
				echo "<br />";
				if(!$EM_Event->event_all_day){
					echo $EM_Event->start()->i18n( $EM_Event->get_option('time_format')) . " - " . $EM_Event->end()->i18n( $EM_Event->get_option('time_format'));
				}else{
					echo $EM_Event->get_option('dbem_event_all_day_message');
				}
				if( $EM_Event->get_timezone()->getName() != EM_DateTimeZone::create()->getName() ) {
					echo '<span class="dashicons dashicons-info em-tooltip" style="font-size:16px; color:#ccc; padding-top:2px;" title="'.esc_attr(str_replace('_', ' ', $EM_Event->event_timezone)).'"></span>';
				}
				break;
			case 'extra':
				if( $EM_Event->get_option('dbem_rsvp_enabled') == 1 && !empty($EM_Event->event_rsvp) && $EM_Event->can_manage('manage_bookings','manage_others_bookings')){
					?>
					<a href="<?php echo $EM_Event->get_bookings_url(); ?>"><?php echo __("Bookings",'events-manager'); ?></a> &ndash;
					<?php _e("Booked",'events-manager'); ?>: <?php echo $EM_Event->get_bookings()->get_booked_spaces()."/".$EM_Event->get_spaces(); ?>
					<?php if( $EM_Event->get_option('dbem_bookings_approval') == 1 ): ?>
						| <?php _e("Pending",'events-manager') ?>: <?php echo $EM_Event->get_bookings()->get_pending_spaces(); ?>
					<?php endif;
					echo ( $EM_Event->is_repeated() || $EM_Event->is_recurrence() || $EM_Event->is_recurring() ) ? '<br />':''; // decide here in case bookings disabled
				}
				if ( ( $EM_Event->is_repeated() || $EM_Event->is_recurring() ) && current_user_can('edit_recurring_events','edit_others_recurring_events') ) {
					$actions = array();
					if ( $EM_Event->is_repeated() ) {
						if ( $EM_Event->get_recurring_event()->can_manage( 'edit_recurring_events', 'edit_others_recurring_events' ) ) {
							$actions[] = '<a href="' . admin_url() . 'post.php?action=edit&amp;post=' . $EM_Event->get_recurring_event()->post_id . '">' . sprintf( esc_html__( 'Edit %s', 'events-manager' ), esc_html__( 'Repeating Events', 'events-manager' ) ) . '</a>';
							$actions[] = '<a class="em-detach-link" href="' . esc_url( $EM_Event->get_detach_url() ) . '">' . esc_html__( 'Detach', 'events-manager' ) . '</a>';
						}
						if ( $EM_Event->get_recurring_event()->can_manage( 'delete_recurring_events', 'delete_others_recurring_events' ) ) {
							$actions[] = '<span class="trash"><a class="em-delete-recurrence-link" href="' . get_delete_post_link( $EM_Event->get_recurring_event()->post_id ) . '">' . esc_html__( 'Delete', 'events-manager' ) . '</a></span>';
						}
					}
					?>
					<strong>
						<?php if ( $EM_Event->is_recurring() ) : ?>
							<span class="dashicons dashicons-update-alt em-recurring-event" style="color:#aaa; padding-top:-2px;"></span>
						<?php endif; ?>
						<?php echo $EM_Event->get_recurring_event()->get_recurrence_sets()->get_recurrence_description( !$EM_Event->is_recurring() ); ?>
					</strong>
					<?php if( $EM_Event->post_status !== 'trash' && !empty($actions) ): ?>
					<br >
					<div class="row-actions">
						<?php echo implode(' | ', $actions); ?>
					</div>
					<?php endif;
				}
				
				break;
		}
	}
	
	public static function row_actions($actions, $post){
		if( Archetypes::is_event( $post->post_type ) ){
			global $post, $EM_Event;
			$EM_Event = em_get_event($post, 'post_id');
			$actions['duplicate'] = '<a href="'.$EM_Event->duplicate_url().'" title="'.sprintf(__('Duplicate %s','events-manager'), __('Event','events-manager')).'">'.__('Duplicate','events-manager').'</a>';
		}
		return $actions;
	}
	
	public static function sortable_columns( $columns ){
		$columns['date-time'] = 'date-time';
		return $columns;
	}
	
}
add_action('admin_init', array('EM_Event_Posts_Admin','init'));

/*
 * Recurring Events
 */
class EM_Event_Recurring_Posts_Admin{
	
	public static function admin_notices(){
		?>
		<div class="notice notice-info">
			<p><?php esc_html_e( 'Modifications to repeating events will be applied to all recurrences and will overwrite any changes made to those individual event recurrences.', 'events-manager'); ?></p>
			<p><?php esc_html_e( 'Bookings to individual event recurrences will be preserved if event times and ticket settings are not modified.', 'events-manager'); ?></p>
			<p>
				<?php echo sprintf( esc_html__('You can edit individual recurrences and disassociate them with a %s to prevent getting overwritten.', 'events-manager'), esc_html__('repeating event', 'events-manager')); ?></strong>
	    	</p>
		</div>
		<?php
	}
	
	public static function admin_head(){
		//quick hacks to make event admin table make more sense for events
		?>
		<script type="text/javascript">
			jQuery(document).ready( function($){
				$('.inline-edit-date').prev().css('display','none').next().css('display','none').next().css('display','none');
			});
		</script>
		<style>
			table.fixed{ table-layout:auto !important; }
			.tablenav select[name="m"] { display:none; }
		</style>
		<?php
	}
	
	public static function columns_add($columns) {
		if( array_key_exists('cb', $columns) ){
			$cb = $columns['cb'];
	    	unset($columns['cb']);
	    	$id_array = array('cb'=>$cb, 'event-id' => sprintf(__('%s ID','events-manager'),__('Event','events-manager')));
		}else{
	    	$id_array = array('event-id' => sprintf(__('%s ID','events-manager'),__('Event','events-manager')));
		}
	    unset($columns['comments']);
	    unset($columns['date']);
	    unset($columns['author']);
	    $columns = array_merge($id_array, $columns, array(
	    	'location' => __('Location','events-manager'),
	    	'date-time' => __('Date and Time','events-manager'),
	    	'author' => __('Owner','events-manager'),
	    ));
		if( !em_get_option('dbem_locations_enabled') ){
			unset($columns['location']);
		}
		return $columns;
	}

	
	public static function columns_output( $column ) {
		global $post, $EM_Event;
		if( Archetypes::is_repeating( $post->post_type ) ){
			$post = $EM_Event = em_get_event($post);
			/* @var $post EM_Event */
			switch ( $column ) {
				case 'event-id':
					echo $EM_Event->event_id;
					break;
				case 'location':
					//get meta value to see if post has location, otherwise
					$EM_Location = $EM_Event->get_location();
					if( !empty($EM_Location->location_id) ){
						$actions = array();
						$actions[] = "<a href='". esc_url($EM_Location->get_permalink())."'>". esc_html__('View') ."</a>";
						if( $EM_Location->can_manage('edit_locations', 'edit_others_locations') ) {
							$actions[] = "<a href='". esc_url($EM_Location->get_edit_url())."'>". esc_html__('Edit') ."</a>";
						}
						echo "<strong><a href='". $EM_Location->get_permalink()."'>" . $EM_Location->location_name . "</a></strong>";
						echo "<span class='row-actions'> - ". implode(' | ', $actions) . "</span>";
						echo "<br/>" . $EM_Location->location_address . " - " . $EM_Location->location_town;
					}else{
						echo __('None','events-manager');
					}
					break;
				case 'date-time':
					echo $EM_Event->get_recurrence_description();
					$edit_url = add_query_arg(array('scope'=>'all', 'recurring_event'=>$EM_Event->event_id), em_get_events_admin_url());
					$link_text = sprintf(__('View %s', 'events-manager'), __('Recurrences', 'events-manager'));
					if  ( $EM_Event->post_status !== 'trash' ) {
						echo "<br /><span class='row-actions'>
							<a href='" . esc_url( $edit_url ) . "'>" . esc_html( $link_text ) . "</a>
						</span>";
					}
					break;
			}
		}
	}
	
	public static function row_actions($actions, $post){
		if( Archetypes::is_repeating( $post ) ){
			global $post, $EM_Event;
			$EM_Event = em_get_event($post, 'post_id');
			$actions['duplicate'] = '<a href="'.$EM_Event->duplicate_url().'" title="'.sprintf(__('Duplicate %s','events-manager'), __('Event','events-manager')).'">'.__('Duplicate','events-manager').'</a>';
			if ( em_get_option('dbem_recurrence_enabled') && em_get_option('dbem_recurrence_convert_enabled') ) {
				$convert_url = esc_url( add_query_arg( ['action' => 'convert_to_recurrence', 'event_id' => $EM_Event->event_id, 'nonce' => 'x'] ) );
				$convert_nonce = wp_create_nonce('convert_to_recurrence_'.$EM_Event->event_id);
				$actions['convert'] = '<a href="'. $convert_url .'" class="em-convert-recurrence-link" data-nonce="' . $convert_nonce . '">'. esc_html__('Convert Recurring', 'events-manager') . '</a>';
				$js_warning = esc_html__('This will delete all event recurrence posts/pages, and unify them into one URL. Any 404 pages resulting from these will automatically 302-redirect to the recurring event (which will be a new URL).', 'events-manager');
				EM\Scripts_and_Styles::add_js_var('convert_recurring_warning', __('Are you sure you want to convert this repeating event?', 'events-manager') . "\n\n" . __('WARNING: This action cannot be undone.', 'events-manager') . "\n\n" . $js_warning);
			}
		}
		return $actions;
	}
}