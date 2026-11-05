<?php
/**
 * Deprecated - see em-actions.php - this will be removed at some point in 6.0
 * Check if there's any admin-related actions to take for bookings. All actions are caught here.
 * @return null
 * @todo remove in 6.0
 */
function em_admin_actions_bookings() {
	global $EM_Event;	
	if( is_object($EM_Event) && !empty($_REQUEST['action']) ){
		if( $_REQUEST['action'] == 'bookings_export_csv' && wp_verify_nonce($_REQUEST['_wpnonce'],'bookings_export_csv') ){
			$EM_Event->get_bookings()->export_csv();
			exit();
		}
	}
}
add_action('admin_init','em_admin_actions_bookings',100);

/**
 * Whether a bookings admin action names a hook Events Manager already owns in the em_bookings_* namespace.
 *
 * Matched on prefix: that namespace also carries the booking lifecycle (em_bookings_add, em_bookings_deleted) and the admin templates (em_bookings_admin_*, em_bookings_table_*), whose listeners are called with arguments an admin action has none of.
 *
 * @param string $action Sanitized action name.
 * @return bool
 */
function em_bookings_admin_action_is_reserved( $action ){
	$reserved = array( 'add', 'admin_', 'build_sql_', 'dashboard', 'delete', 'event_', 'get', 'has_', 'is_', 'load', 'pending_count', 'person_', 'single_', 'sql_', 'table', 'ticket_' );
	foreach( $reserved as $prefix ){
		if( strpos( $action, $prefix ) === 0 ) return true;
	}
	return false;
}

/**
 * Decide what content to show in the bookings section. 
 */
function em_bookings_page(){
	//First any actions take priority
	do_action('em_bookings_admin_page');
	if( !empty($_REQUEST['_wpnonce']) ){ $_REQUEST['_wpnonce'] = $_GET['_wpnonce'] = $_POST['_wpnonce'] = esc_attr($_REQUEST['_wpnonce']); } //XSS fix just in case here too
	$action = !empty($_REQUEST['action']) ? sanitize_key($_REQUEST['action']) : '';
	if( $action !== '' && substr($action,0,7) != 'booking' && $action !== 'em_bookings_table' ){ //actions not starting with booking_
		?>
		<div class="wrap em-bookings-admin-custom-<?php echo esc_attr($action); ?> <?php em_template_classes('bookings-admin'); ?>">
			<div class="input">
			<?php
			do_action('em_bookings_admin_action_'.$action, $action);
			if( !em_bookings_admin_action_is_reserved($action) ){
				do_action('em_bookings_'.$action); //deprecated by the hook above, kept one release so custom actions registered on this name keep working
			}
			?>
			</div>
		</div>
		<?php
	}elseif( !empty($_REQUEST['booking_id']) ){
		em_bookings_single();
	}elseif( !empty($_REQUEST['person_id']) ){
		em_bookings_person();
	}elseif( !empty($_REQUEST['ticket_id']) ){
		em_bookings_ticket();
	}elseif( !empty($_REQUEST['event_id']) ){
		em_bookings_event();
	}else{
		em_bookings_dashboard();
	}
}

/**
 * Generates the bookings dashboard, showing information on all events
 */
function em_bookings_dashboard(){
	global $EM_Notices;
	?>
	<div class='em-bookings-admin-dashboard em-bookings-dashboard <?php em_template_classes('bookings-admin'); ?>'>
		<div class="input">
			<?php if( is_admin() ): ?>
		        <h1><?php esc_html_e('Event Bookings Dashboard', 'events-manager'); ?></h1>
		        <?php else: echo $EM_Notices; ?>
	        <?php endif; ?>
			<?php if( em_get_option('dbem_booking_charts_dashboard') && class_exists('\EM\Admin\Dashboard') ): ?>
				<div class="em-bookings-stats wrap">
					<div class="inside">
						<?php \EM\Admin\Dashboard::output('dashboard'); ?>
					</div>
				</div>
			<?php endif; ?>
	        <div class="em-bookings-recent wrap">
				<h2><?php esc_html_e('Recent Bookings','events-manager'); ?></h2>
		        <?php
				$EM_Bookings_Table = new EM_Bookings_Table();
			    $EM_Bookings_Table->display();
		        ?>
	        </div>
	        <br class="clear">
	        <div class="em-bookings-events wrap">
				<h2><?php esc_html_e('Events With Bookings Enabled','events-manager'); ?></h2>
			    <?php
				$EM_Events_Table = new EM\List_Table\Events_Bookings();
				$EM_Events_Table->display();
				?>
			</div>
			<?php do_action('em_bookings_dashboard'); ?>
		</div>
	</div>
	<?php
}

/**
 * Shows all booking data for a single event 
 */
function em_bookings_event(){
	global $EM_Event,$EM_Person,$EM_Notices;
	//check that user can access this page
	if( is_object($EM_Event) && !$EM_Event->can_manage('manage_bookings','manage_others_bookings') ){
		?>
		<div class="wrap <?php em_template_classes('bookings-admin'); ?>">
			<h2><?php esc_html_e('Unauthorized Access','events-manager'); ?></h2>
			<p><?php esc_html_e('You do not have the rights to manage this event.','events-manager'); ?></p>
		</div>
		<?php
		return false;
	}
	$label_single = \EM\Archetypes::get( $EM_Event->event_archetype )['label_single'];
	$header_button_classes = is_admin() ? 'page-title-action':'button add-new-h2';
	?>
	<div class='em-bookings-admin-event <?php em_template_classes('bookings-admin'); ?>'>
		<div class="input">
			
			<?php if( is_admin() ): ?><h1 class="wp-heading-inline"><?php else: ?><h2><?php endif; ?>
  			<?php echo sprintf(__('Manage %s Bookings', 'events-manager'), "'{$EM_Event->event_name}'"); ?>
  		    <?php if( !is_admin() ): ?></h2><?php else: ?></h1><?php endif; // inverted to help IDEs ?>
  			<a href="<?php echo $EM_Event->get_permalink(); ?>" class="button button-secondary"><?php echo sprintf(__('View %s','events-manager'), __('Event', 'events-manager')) ?></a>
  			<a href="<?php echo $EM_Event->get_edit_url(); ?>" class="button button-secondary"><?php echo sprintf(__('Edit %s','events-manager'), __('Event', 'events-manager')) ?></a>
  			<?php if( locate_template('plugins/events-manager/templates/csv-event-bookings.php', false) ): //support for legacy template ?>
  			<a href='<?php echo EM_ADMIN_URL ."&amp;page=events-manager-bookings&amp;action=bookings_export_csv&amp;_wpnonce=".wp_create_nonce('bookings_export_csv')."&amp;event_id=".$EM_Event->event_id ?>' class="button button-secondary"><?php esc_html_e('Export CSV','events-manager')?></a>
  			<?php endif; ?>
  			<?php do_action('em_admin_event_booking_options_buttons'); ?>
			<hr class="wp-header-end">

			<?php if ( $EM_Event->is_timeslot() || $EM_Event->has_timeslots() ): ?>
				<?php
					ob_start();
					// get parent timeslots if this is an individual timeslot
					$Timeslots = $EM_Event->is_timeslot() ? $EM_Event->get_parent()->get_timeranges()->get_timeslots() : $EM_Event->get_timeranges()->get_timeslots();
				?>
				<form action="" method="get" class="em-bookings-admin-event-timeslots">
					<label><?php echo sprintf( esc_html__('This %s has timeslots, you are viewing','events-manager'), $label_single ); ?>
						<select name="event_id">
							<option value="<?php echo absint( $EM_Event->get_event_id() ); ?>"><?php esc_html_e('All Timeslots', 'events-manager') ?></option>
							<?php foreach ( $Timeslots as $Timeslot ): ?>
								<option value="<?php $Timeslot->uid(); ?>" <?php selected( $Timeslot->get_uid(), $_GET['event_id'] ?? '' ) ?>>
									<?php echo $Timeslot->start->i18n('g:i A'); ?>
									<?php if ( $Timeslot->timeslot_status === 0 ) : ?>
									(<?php esc_html_e( 'Cancelled', 'events-manager' ); ?>)
									<?php endif; ?>
								</option>
							<?php endforeach; ?>
						</select>
					</label>
					<?php foreach ( $_GET as $key => $value ): if( $key === 'event_id' ) continue; ?>
						<input type="hidden" name="<?php echo esc_attr($key); ?>" value="<?php echo esc_attr($value); ?>" >
					<?php endforeach; ?>
					<button type="submit" class="button button-secondary"><?php esc_html_e('View Timeslot', 'events-manager'); ?></button>
				</form>
				<?php $timeslots = ob_get_clean(); ?>
			<?php endif; ?>

			<?php if ( $EM_Event->is_recurring() ) : ?>
			<div class="em-notice em-notice-icon" >
				<span class="em-icon em-icon-info"></span>
				<?php
				$recurrence_bookings = esc_html( sprintf( __('Recurrence %s', 'events-manager'), __('Bookings', 'events-manager') ) );
				$recurrence_bookings_link = '<a href="#event-bookings">'. strtolower($recurrence_bookings) .'</a>';
				$event_recurrences = esc_html( sprintf( __('%s Recurrences', 'events-manager'), $label_single ) );
				$event_recurrences_link = '<a href="#event-recurrences">'. strtolower($event_recurrences) .'</a>';
				?>
				<span><?php echo sprintf( esc_html__('This is a recurring %s. You can find all %s on this page, or click on individual %s to view recurrence-specific bookings.', 'events-manager'), $label_single, $recurrence_bookings_link, $event_recurrences_link ); ?></span>
				<?php if( !empty($timeslots) ) : ?>
					<span></span><?php echo $timeslots; ?>
				<?php endif; ?>
			</div>
			<?php elseif ( $EM_Event->is_recurrence() || ( $EM_Event->is_timeslot() && $EM_Event->get_parent()->is_recurrence() ) ) : ?>
				<div class="em-notice em-notice-icon" >
					<span class="em-icon em-icon-info"></span>
					<?php
					$recurring_link = '<a href="'. esc_url( add_query_arg('event_id', $EM_Event->get_recurring_event()->event_id) ) . '">' . $EM_Event->event_name . '</a>';
					?>
					<span><?php echo sprintf( esc_html__('This is a %s recurrence of %s.', 'events-manager'), strtolower( $label_single ), $recurring_link ); ?></span>
					<?php if( !empty($timeslots) ) : ?>
						<span></span><?php echo $timeslots; ?>
					<?php endif; ?>
				</div>
			<?php elseif ( !empty($timeslots) ): ?>
				<div class="em-notice em-notice-icon" >
					<span class="em-icon em-icon-info"></span>
					<?php echo $timeslots; ?>
				</div>
			<?php endif; ?>

	        <?php if( !is_admin() ) echo $EM_Notices; ?>
			<p>
				<strong><?php esc_html_e('Name','events-manager'); ?></strong> : <?php echo esc_html($EM_Event->event_name); ?>
			</p>
			<p>
				<strong><?php esc_html_e('Status','events-manager'); ?></strong> : <?php echo esc_html( $EM_Event->get_active_status() ); ?>
			</p>
			<?php do_action('em_admin_event_booking_before_availibility', $EM_Event); ?>
			<p>
				<strong><?php esc_html_e('Availability','events-manager'); ?></strong> :
				<?php echo $EM_Event->get_bookings()->get_booked_spaces() . '/'. $EM_Event->get_spaces() ." ". __('Spaces confirmed','events-manager'); ?>
				<?php if( em_get_option('dbem_bookings_approval_reserved') ): ?>
				, <?php echo $EM_Event->get_bookings()->get_available_spaces() . '/'. $EM_Event->get_spaces() ." ". __('Available spaces','events-manager'); ?>
				<?php endif; ?>
				<?php do_action('em_admin_event_booking_availibility', $EM_Event); ?>
			</p>
			<?php do_action('em_admin_event_booking_after_availibility', $EM_Event); ?>
			<p>
				<strong><?php esc_html_e('Date','events-manager'); ?></strong> :
				<?php echo $EM_Event->output_dates(false, " - "). ' @ ' . $EM_Event->output_times(false, ' - '); ?>
				<?php if ( $EM_Event->get_timezone()->getValue() !== get_option('timezone_string') ): ?>
				<?php echo ' ('. $EM_Event->get_timezone()->getName() .')'; ?>
				<?php endif; ?>
				<?php if ( !empty($timeslots) ) : ?>
				<span class="em-icon s-15 em-icon-info em-tooltip" aria-label="<?php esc_html_e('Multiple Timeslots','events-manager'); ?>"></span>
				<?php endif; ?>
			</p>
			<p>
				<strong><?php esc_html_e('Location','events-manager'); ?></strong> :
				<?php if( $EM_Event->location_id == 0 ): ?>
				<em><?php esc_html_e('No Location', 'events-manager'); ?></em>
				<?php else: ?>
				<a class="row-title" href="<?php echo admin_url(); ?>post.php?action=edit&amp;post=<?php echo $EM_Event->get_location()->post_id ?>"><?php echo ($EM_Event->get_location()->location_name); ?></a>
				<?php endif; ?>
			</p>
			<?php if( em_get_option('dbem_booking_charts_event') && class_exists('\EM\Admin\Dashboard') ): ?>
			<div class="wrap">
				<div class="em-bookings-stats">
					<div class="inside">
						<?php \EM\Admin\Dashboard::output('event', $EM_Event->event_id); ?>
					</div>
				</div>
			</div>
			<?php endif; ?>

			<div class="wrap" id="event-bookings">
				<h2>
					<?php
						if ( $EM_Event->is_recurring() ) {
							echo esc_html( sprintf( __('Recurrence %s', 'events-manager'), __('Bookings', 'events-manager') ) );
						} else {
							esc_html_e('Bookings','events-manager');
						}
					?>
				</h2>
				<?php
				$EM_Bookings_Table = new EM_Bookings_Table();
				$EM_Bookings_Table->status = 'all';
				if( empty($_REQUEST['legacy']) ) {
					$EM_Bookings_Table->display();
				}else{
					$EM_Bookings_Table->output();
				}
	            ?>
			</div>

			<?php if ( $EM_Event->is_recurring() ): ?>
			<div class="em-bookings-events wrap" id="event-recurrences">
				<h2><?php echo esc_html( sprintf( __('%s Recurrences', 'events-manager'), __('Event', 'events-manager') ) ); ?></h2>
				<?php
				$EM_Events_Table = new EM\List_Table\Events_Bookings();
				$EM_Events_Table->display();
				?>
			</div>
			<?php endif; ?>
			<?php do_action('em_bookings_event_footer', $EM_Event); ?>
		</div>
	</div>
	<?php
}

/**
 * Shows a ticket view
 */
function em_bookings_ticket(){
	global $EM_Ticket,$EM_Notices;
	$EM_Event = $EM_Ticket->get_event();
	//check that user can access this page
	if( is_object($EM_Ticket) && !$EM_Ticket->can_manage() ){
		?>
		<div class="wrap <?php em_template_classes('bookings-admin'); ?>">
			<h2><?php esc_html_e('Unauthorized Access','events-manager'); ?></h2>
			<p><?php esc_html_e('You do not have the rights to manage this ticket.','events-manager'); ?></p>
		</div>
		<?php
		return false;
	}
	?>
	<div class='em-bookings-admin-ticket <?php em_template_classes('bookings-admin'); ?>'>
		<div class="input">
			
			<?php if( is_admin() ): ?><h1 class="wp-heading-inline"><?php else: ?><h2><?php endif; ?>
			<?php echo sprintf(__('Ticket for %s', 'events-manager'), "'{$EM_Event->name}'"); ?><?php echo sprintf(__('Manage %s Bookings', 'events-manager'), "'{$EM_Event->event_name}'"); ?>
			<?php if( !is_admin() ): ?></h2><?php else: ?></h1><?php endif; // inverted to help IDEs ?>
	        <a href="<?php echo $EM_Event->get_edit_url(); ?>" class="button button-secondary"><?php esc_html_e('View/Edit Event','events-manager') ?></a>
	        <a href="<?php echo $EM_Event->get_bookings_url(); ?>" class="button button-secondary"><?php esc_html_e('View Event Bookings','events-manager') ?></a>
			<hr class="wp-header-end" />
				
	        <?php if( !is_admin() ) echo $EM_Notices; ?>
			<div>
				<table>
					<tr><td><?php echo __('Name','events-manager'); ?></td><td></td><td><?php echo $EM_Ticket->ticket_name; ?></td></tr>
					<tr><td><?php echo __('Description','events-manager'); ?>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</td><td></td><td><?php echo ($EM_Ticket->description) ? $EM_Ticket->description : '-'; ?></td></tr>
					<tr><td><?php echo __('Price','events-manager'); ?></td><td></td><td><?php echo ($EM_Ticket->price) ? $EM_Ticket->price : '-'; ?></td></tr>
					<tr><td><?php echo __('Spaces','events-manager'); ?></td><td></td><td><?php echo ($EM_Ticket->spaces) ? $EM_Ticket->spaces : '-'; ?></td></tr>
					<tr><td><?php echo __('Min','events-manager'); ?></td><td></td><td><?php echo ($EM_Ticket->min) ? $EM_Ticket->min : '-'; ?></td></tr>
					<tr><td><?php echo __('Max','events-manager'); ?></td><td></td><td><?php echo ($EM_Ticket->max) ? $EM_Ticket->max : '-'; ?></td></tr>
					<tr><td><?php echo __('Start','events-manager'); ?></td><td></td><td><?php echo ($EM_Ticket->start) ? $EM_Ticket->start()->formatDefault() : '-'; ?></td></tr>
					<tr><td><?php echo __('End','events-manager'); ?></td><td></td><td><?php echo ($EM_Ticket->end) ? $EM_Ticket->end()->formatDefault() : '-'; ?></td></tr>
					<?php do_action('em_booking_admin_ticket_row', $EM_Ticket); ?>
				</table>
			</div>
			<h2><?php esc_html_e('Bookings','events-manager'); ?></h2>
			<?php
			$EM_Bookings_Table = new EM_Bookings_Table();
			$EM_Bookings_Table->status = em_get_option('dbem_bookings_approval') ? 'needs-attention':'confirmed';
			$EM_Bookings_Table->ticket = $EM_Ticket;
			$EM_Bookings_Table->display();
	        ?>
			<?php do_action('em_bookings_ticket_footer', $EM_Ticket); ?>
		</div>
	</div>
	<?php	
}

/**
 * Shows a single booking for a single person. 
 */
function em_bookings_single(){
	global $EM_Booking, $EM_Notices; /* @var $EM_Booking EM_Booking */
	$id = rand(0,9999);
	//check that user can access this page
	if( is_object($EM_Booking) && !$EM_Booking->can_manage() ){
		?>
		<div class="wrap <?php em_template_classes('bookings-admin'); ?>">
			<h2><?php esc_html_e('Unauthorized Access','events-manager'); ?></h2>
			<p><?php esc_html_e('You do not have the rights to manage this event.','events-manager'); ?></p>
		</div>
		<?php
		return false;
	}
	do_action('em_booking_admin', $EM_Booking);
	?>
	<div class='wrap em-bookings-admin-single <?php em_template_classes('bookings-admin'); ?>' id="em-bookings-admin-booking">
		<div class="input">
		<?php if( is_admin() ): ?><h1><?php else: ?><h2><?php endif; ?>
  			<?php esc_html_e('Edit Booking', 'events-manager'); ?>
		<?php if( !is_admin() ): ?></h2><?php else: ?></h1><?php endif; ?>
  		<?php if( !is_admin() ) echo $EM_Notices; ?>
  		<div class="metabox-holder">
	  		<div class="postbox-container" style="width:99.5%">
				<div class="postbox">
					<h3>
						<?php esc_html_e( 'Event Details', 'events-manager'); ?>
					</h3>
					<div class="inside">
						<?php
						$EM_Event = $EM_Booking->get_event();
						?>
						<table class="em-form-fields">
							<tr class="em-booking-admin-event-name">
								<th><?php esc_html_e('Name','events-manager'); ?></th>
								<td>
									<a class="row-title" href="<?php echo $EM_Event->get_bookings_url(); ?>"><?php echo ($EM_Event->event_name); ?></a>
								</td>
							</tr>
							<tr class="em-booking-admin-event-date">
								<th><?php esc_html_e('Date/Time','events-manager'); ?>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</th>
								<td>
									<?php echo $EM_Event->output('#_EVENTDATES @ #_EVENTTIMES'); ?>
									<?php if ( $EM_Event->is_recurrence() && $EM_Event->get_recurring_event()->event_timezone != $EM_Event->event_timezone ): ?>
									( <?php echo $EM_Event->start()->getTimezone()->getName(); ?> )
									<?php endif; ?>
								</td>
							</tr>
							<?php do_action('em_bookings_admin_booking_event_row', $EM_Booking); ?>
						</table>
						<?php do_action('em_bookings_admin_booking_event', $EM_Event, $EM_Booking ); ?>
					</div>
				</div>
				<div class="postbox">
					<h3>
						<?php esc_html_e( 'Personal Details', 'events-manager'); ?>
					</h3>
					<div class="inside">
						<div class="em-booking-person-details">
							<?php echo $EM_Booking->get_person()->display_summary(); ?>
							<?php if( $EM_Booking->is_no_user() ): ?>
							<input type="button" class="button-secondary" id="em-booking-person-modify" value="<?php esc_attr_e('Edit Details','events-manager'); ?>" />
							<?php endif; ?>
						</div>
						<?php if( $EM_Booking->is_no_user() ): ?>
						<form action="" method="post" class="em-booking-person-form">
							<div class="em-booking-person-editor" style="display:none;">
								<?php echo $EM_Booking->get_person_editor(); ?>
							    <input type='hidden' name='action' value='booking_modify_person'/>
							    <input type='hidden' name='booking_id' value='<?php echo $EM_Booking->booking_id; ?>'/>
							    <input type='hidden' name='event_id' value='<?php echo $EM_Event->event_id; ?>'/>
							    <input type='hidden' name='_wpnonce' value='<?php echo wp_create_nonce('booking_modify_person_'.$EM_Booking->booking_id); ?>'/>
								<input type="submit" class="button-primary em-button em-booking-person-modify-submit" id="em-booking-person-modify-submit" value="<?php esc_attr_e('Submit Changes', 'events-manager'); ?>" />
								<input type="button" id="em-booking-person-modify-cancel" class="button-secondary em-button" value="<?php esc_attr_e('Cancel','events-manager'); ?>" />
							</div>
						</form>
						<script type="text/javascript">
							jQuery(document).ready( function($){
								$('#em-booking-person-modify').on('click', function(){
									$('.em-booking-person-details').hide();
									$('.em-booking-person-editor').show();
								});
								$('#em-booking-person-modify-cancel').on('click', function(){
									$('.em-booking-person-details').show();
									$('.em-booking-person-editor').hide();
								});
							});
						</script>
						<?php endif; ?>
						<?php do_action('em_bookings_admin_booking_person', $EM_Booking); ?>
					</div>
				</div>
				<div class="postbox">
					<h3>
						<?php esc_html_e( 'Booking Details', 'events-manager'); ?>
						<?php $icons_class = is_admin() ? 'dashicons dashicons-info-outline' : 'em-icons em-icons-at'; ?>
						<span class="em-tooltip <?php echo $icons_class ?>" aria-label="UUID : <?php echo esc_attr($EM_Booking->booking_uuid); ?>" data-tippy-interactive="true"></span>
					</h3>
					<div class="inside">
						<?php
						$EM_Event = $EM_Booking->get_event();
						$shown_tickets = array();
						?>
						<div class="em-booking-single-rsvp-actions">
							<form action="" method="post" class="em-booking-single-status-info">
								<strong><?php esc_html_e('Status','events-manager'); ?> : </strong>
								<?php echo $EM_Booking->get_status(); ?>
								<input type="button" class="button-secondary em-button em-booking-submit-status-modify" id="em-booking-submit-status-modify" value="<?php esc_attr_e('Change', 'events-manager'); ?>" />
								<input type="submit" class="button-primary em-button em-booking-resend-email" id="em-booking-resend-email" value="<?php esc_attr_e('Resend Email', 'events-manager'); ?>" />
							    <input type='hidden' name='action' value='booking_resend_email'/>
							    <input type='hidden' name='booking_id' value='<?php echo $EM_Booking->booking_id; ?>'/>
							    <input type='hidden' name='event_id' value='<?php echo $EM_Event->event_id; ?>'/>
							    <input type='hidden' name='_wpnonce' value='<?php echo wp_create_nonce('booking_resend_email_'.$EM_Booking->booking_id); ?>'/>
							</form>
							<form action="" method="post" class="em-booking-single-status-edit">
								<strong><?php esc_html_e('Status','events-manager'); ?> : </strong>
								<select name="booking_status">
									<?php foreach($EM_Booking->status_array as $status => $status_name): ?>
									<option value="<?php echo esc_attr($status); ?>" <?php if($status == $EM_Booking->booking_status){ echo 'selected="selected"'; } ?>><?php echo esc_html($status_name); ?></option>
									<?php endforeach; ?>
								</select>
								<input type="checkbox" checked="checked" name="send_email" value="1" />
								<?php esc_html_e('Send Email','events-manager'); ?>
								<input type="submit" class="button-primary em-button em-booking-submit-status" id="em-booking-submit-status" value="<?php esc_attr_e('Submit Changes', 'events-manager'); ?>" />
								<input type="button" class="button-secondary em-button em-booking-submit-status-cancel" id="em-booking-submit-status-cancel" value="<?php esc_attr_e('Cancel', 'events-manager'); ?>" />
							    <input type='hidden' name='action' value='booking_set_status'/>
							    <input type='hidden' name='booking_id' value='<?php echo $EM_Booking->booking_id; ?>'/>
							    <input type='hidden' name='event_id' value='<?php echo $EM_Event->event_id; ?>'/>
							    <input type='hidden' name='_wpnonce' value='<?php echo wp_create_nonce('booking_set_status_'.$EM_Booking->booking_id); ?>'/>
								<br><em><?php echo wp_kses_data(__('<strong>Notes:</strong> Ticket availability not taken into account when approving new bookings (i.e. you can overbook).','events-manager')); ?></em>
							</form>
							
							<?php do_action('em_bookings_admin_booking_details_actions', $EM_Booking); ?>
						</div>
						<?php if( em_get_option('dbem_bookings_rsvp') ): ?>
						<div class="em-booking-single-rsvp-status">
							<form action="" method="post" class="em-booking-single-status-info em-booking-single-rsvp-status-info">
								<strong class="em-tooltip" aria-label="<?php echo esc_attr('This represents whether the person has confirmed if they will be attending.', 'events-manager'); ?>"><?php esc_html_e('RSVP Status','events-manager'); ?> : </strong>
								<?php echo $EM_Booking->get_rsvp_status( true ); ?>
								<input type="button" class="button-secondary em-button em-booking-submit-status-modify" id="em-booking-submit-status-modify" value="<?php esc_attr_e('Change', 'events-manager'); ?>" />
							</form>
							<form action="" method="post" class="em-booking-single-status-edit em-booking-single-rsvp-status-info">
								<strong class="em-tooltip" aria-label="<?php echo esc_attr('This represents whether the person has confirmed if they will be attending.', 'events-manager'); ?>"><?php esc_html_e('RSVP Status','events-manager'); ?> : </strong>
								<select name="booking_rsvp_status">
									<?php foreach($EM_Booking::get_rsvp_statuses() as $status => $status_type): ?>
										<option value="<?php echo esc_attr($status); ?>" <?php if( $status === $EM_Booking->get_rsvp_status() ){ echo 'selected="selected"'; } ?>><?php echo esc_html($status_type->label); ?></option>
									<?php endforeach; ?>
								</select>
								<input type="submit" class="button-primary em-button em-booking-submit-status" id="em-booking-submit-status" value="<?php esc_attr_e('Submit Changes', 'events-manager'); ?>" />
								<input type="button" class="button-secondary em-button em-booking-submit-status-cancel" id="em-booking-submit-status-cancel" value="<?php esc_attr_e('Cancel', 'events-manager'); ?>" />
								<input type='hidden' name='action' value='booking_set_rsvp_status'/>
								<input type='hidden' name='booking_id' value='<?php echo $EM_Booking->booking_id; ?>'/>
								<input type='hidden' name='event_id' value='<?php echo $EM_Event->event_id; ?>'/>
								<input type='hidden' name='_wpnonce' value='<?php echo wp_create_nonce('booking_set_rsvp_status_'.$EM_Booking->booking_id); ?>'/>
							</form>
						</div>
						<?php endif; ?>
						<form action="" method="post" class="em-booking-form" id="em-booking-form-<?php echo $id; ?>" data-id="<?php echo $id; ?>" <?php if ( !em_get_option('dbem_uploads_ui') ) echo ' enctype="multipart/form-data"'; ?> data-noajax data-mode="view">
							<table class="em-tickets em-tickets-bookings-table" cellpadding="0" cellspacing="0">
								<thead>
									<tr>
										<th><?php esc_html_e('Ticket Type','events-manager'); ?></th>
										<th><?php esc_html_e('Spaces','events-manager'); ?></th>
										<th><?php esc_html_e('Price','events-manager'); ?></th>
									</tr>
								</thead>
								<?php
									/* Show booked tickets in this booking, we'll add on the unbooked tickets here to prevent redundant code */
									$EM_Tickets_Bookings = $EM_Booking->get_tickets_bookings();
									$tickets_bookings = array(); // we'll use this ordered with all tickets
									foreach( $EM_Event->get_bookings()->get_tickets()->tickets as $ticket_id => $EM_Ticket ){
										if( empty($EM_Tickets_Bookings[$ticket_id]) ) {
											$tickets_bookings[$ticket_id] = new EM_Ticket_Bookings(array('ticket' => $EM_Ticket, 'booking' => $EM_Booking));
										}else{
											$tickets_bookings[$ticket_id] = $EM_Tickets_Bookings[$ticket_id];
										}
									}
									$attendee_placeholder = esc_html__('Attendee %d', 'events-manager');
								?>
								<?php foreach($tickets_bookings as $ticket_id => $EM_Ticket_Bookings): /* @var $EM_Ticket_Bookings EM_Ticket_Bookings */ ?>
									<?php
									$ticket_id = absint($ticket_id); // sanitize for output
									$EM_Ticket = $EM_Ticket_Bookings->get_ticket();
									// Use the following for adding extra info, most appropriate place is within the edit area
									do_action('em_bookings_admin_ticket_bookings_before', $EM_Ticket_Bookings);
									?>
									<tr class="em-ticket em-ticket-<?php echo $ticket_id; ?>">
										<td class="ticket-type">
											<a class="row-title" href="<?php echo em_add_get_params($EM_Event->get_bookings_url(), array('ticket_id'=>$ticket_id)); ?>"><?php echo $EM_Ticket_Bookings->get_ticket()->ticket_name ?></a>
										</td>
										<td>
											<span class="em-booking-single-info"><?php echo $EM_Ticket_Bookings->get_spaces(); ?></span>
											<div class="em-booking-single-edit">
												<input type="number" name="em_tickets[<?php echo $ticket_id; ?>][spaces]" class="em-ticket-select em-ticket-spaces-<?php echo $ticket_id; ?>" value="<?php echo $EM_Ticket_Bookings->get_spaces(); ?>" data-ticket-id="<?php echo $ticket_id ?>"/>
											</div>
										</td>
										<td><?php echo $EM_Ticket_Bookings->get_price(true,true); ?></td>
									</tr>
									<?php do_action('em_bookings_admin_ticket_row', $EM_Ticket_Bookings->get_ticket(), $EM_Booking, $EM_Ticket_Bookings); /* Keeping as legacy support for EM Pro < v3 */ ?>
									<tbody class="em-ticket-bookings <?php if( !has_action('em_bookings_admin_ticket_booking_row') ) echo 'hidden'; ?> em-ticket-bookings-<?php echo $ticket_id; ?>" data-ticket-id="<?php echo $ticket_id; ?>">
										<?php
											// use the following
											$shown_tickets[] = $ticket_id;
											$ticket_attendee_num = 1;
											do_action('em_bookings_admin_ticket_bookings_rows_before', $EM_Ticket_Bookings);
										?>
										<?php foreach( $EM_Ticket_Bookings as $ticket_uuid => $EM_Ticket_Booking ): /* @var EM_Ticket_Booking $EM_Ticket_Booking */ ?>
											<?php do_action('em_bookings_admin_ticket_booking_row_before', $EM_Ticket_Booking, $ticket_attendee_num); ?>
											<tr class="em-ticket-booking em-ticket-booking-<?php echo absint($EM_Ticket_Booking->ticket_booking_id); ?>" data-ticket-id="<?php echo $ticket_id; ?>"><!-- this will eventually move out into an enveloping element class for all ticket bookings of this ticket -->
												<td colspan="3">
													<div>
														<p class="em-ticket-booking-attendee-number" data-placeholder="<?php echo $attendee_placeholder; ?>"><?php echo sprintf(esc_html__('Attendee %d', 'events-manager'), $ticket_attendee_num); ?></p>
														<span class="em-booking-single-edit em-icon em-icon-close em-ticket-booking-remove-trigger em-tooltip" aria-label="<?php esc_html_e('Remove this ticket booking', 'events-manager'); ?>"></span>
														<?php
															// create a consistent naming structure for post vars, others can/should add stuff to the uuid part of each ticket booking
															$name = "";
															do_action('em_bookings_admin_ticket_booking_row', $EM_Ticket_Booking, $ticket_attendee_num);
														?>
														<input name="em_tickets[<?php echo $ticket_id; ?>][ticket_bookings][<?php echo esc_attr($ticket_uuid); ?>][ticket_booking_id]" type="hidden" value="<?php echo absint($EM_Ticket_Booking->ticket_booking_id); ?>">
													</div>
												</td>
											</tr>
											<?php do_action('em_bookings_admin_ticket_booking_row_after', $EM_Ticket_Booking, $ticket_attendee_num); ?>
											<?php $ticket_attendee_num++; ?>
										<?php endforeach; ?>
										<?php
											do_action('em_bookings_admin_ticket_bookings_rows_after', $EM_Ticket_Bookings); // want $ticket_attendee_num? count the tickets
										?>
										<tr class="em-ticket-booking-template" data-ticket-id="<?php echo $ticket_id; ?>">
											<td colspan="3">
												<div>
													<p class="em-ticket-booking-attendee-number" data-placeholder="<?php echo $attendee_placeholder; ?>"><?php echo str_replace('%d', '#NUM#', $attendee_placeholder); ?></p>
													<span class="em-booking-single-edit em-icon em-icon-close em-ticket-booking-remove-trigger em-tooltip" aria-label="<?php esc_html_e('Remove this ticket booking', 'events-manager'); ?>"></span>
													<?php do_action('em_bookings_admin_ticket_booking_row_template', $EM_Ticket, $EM_Booking); ?>
												</div>
											</td>
										</tr>
										<?php
											// Use the following for adding extra info, most appropriate place is within the edit area
											do_action('em_bookings_admin_ticket_bookings_after', $EM_Ticket_Bookings);
										?>
									</tbody>
								<?php endforeach; ?>
								
								<tfoot>
									<?php
										do_action('em_bookings_admin_ticket_totals_header');
										$price_summary = $EM_Booking->get_price_summary_array();
										//we should now have an array of information including base price, taxes and post/pre tax discounts
									?>
									<tr>
										<th><?php esc_html_e('Price','events-manager'); ?></th>
										<th><?php echo sprintf(__('%d Spaces','events-manager'), $EM_Booking->get_spaces()); ?></th>
										<th><?php echo $EM_Booking->get_price_base(true); ?></th>
									</tr>
									<?php if( count($price_summary['discounts_pre_tax']) > 0 ): ?>
										<?php foreach( $price_summary['discounts_pre_tax'] as $discount_summary ): ?>
										<tr>
											<th><?php echo $discount_summary['name']; ?></th>
											<th><?php echo $discount_summary['adjustment']; ?></th>
											<th>- <?php echo $discount_summary['amount']; ?></th>
										</tr>
										<?php endforeach; ?>
									<?php endif; ?>
									<?php if( count($price_summary['surcharges_pre_tax']) > 0 ): ?>
										<?php foreach( $price_summary['surcharges_pre_tax'] as $surcharge_summary ): ?>
										<tr>
											<th><?php echo $surcharge_summary['name']; ?></th>
											<th><?php echo $surcharge_summary['adjustment']; ?></th>
											<th><?php echo $surcharge_summary['amount']; ?></th>
										</tr>
										<?php endforeach; ?>
									<?php endif; ?>
									<?php if( !empty($price_summary['taxes']['amount'])  ): ?>
									<tr>
										<th><?php esc_html_e('Tax','events-manager'); ?></th>
										<th>
											<span class="em-booking-single-info"><?php echo $price_summary['taxes']['rate'] ?></span>
											<div class="em-booking-single-edit"><input name="booking_tax_rate" value="<?php echo esc_attr($EM_Booking->get_tax_rate()); ?>">%</div>
										</th>
										<th><?php echo $price_summary['taxes']['amount']; ?></th>
									</tr>
									<?php endif; ?>
									<?php if( count($price_summary['discounts_post_tax']) > 0 ): ?>
										<?php foreach( $price_summary['discounts_post_tax'] as $discount_summary ): ?>
										<tr>
											<th><?php echo $discount_summary['name']; ?></th>
											<th><?php echo $discount_summary['adjustment']; ?></th>
											<th>- <?php echo $discount_summary['amount']; ?></th>
										</tr>
										<?php endforeach; ?>
									<?php endif; ?>
									<?php if( count($price_summary['surcharges_post_tax']) > 0 ): ?>
										<?php foreach( $price_summary['surcharges_post_tax'] as $surcharge_summary ): ?>
										<tr>
											<th><?php echo $surcharge_summary['name']; ?></th>
											<th><?php echo $surcharge_summary['adjustment']; ?></th>
											<th><?php echo $surcharge_summary['amount']; ?></th>
										</tr>
										<?php endforeach; ?>
									<?php endif; ?>
									<tr class="em-hr">
										<th><?php esc_html_e('Total Price','events-manager'); ?></th>
										<th>&nbsp;</th>
										<th><?php echo $price_summary['total']; ?></th>
									</tr>
									<?php do_action('em_bookings_admin_ticket_totals_footer', $EM_Booking); ?>
								</tfoot>
							</table>
							<table class="em-form-fields" cellspacing="0" cellpadding="0">
								<?php if( !has_action('em_bookings_single_custom') ): //default behavior ?>
								<tr>
									<th><?php esc_html_e('Comment','events-manager'); ?></th>
									<td>
										<span class="em-booking-single-info"><?php echo esc_html($EM_Booking->booking_comment); ?></span>
										<div class="em-booking-single-edit"><textarea name="booking_comment"><?php echo esc_html($EM_Booking->booking_comment); ?></textarea></div>
									</td>
								</tr>
								<?php else: do_action('em_bookings_single_custom',$EM_Booking); //do your own thing, e.g. pro ?>
								<?php endif; ?>
							</table>
							<p class="em-booking-single-info">
								<input type="button" class="button-secondary em-button em-booking-submit-modify" id="em-booking-submit-modify" value="<?php esc_attr_e('Modify Booking', 'events-manager'); ?>" />
							</p>
							<p class="em-booking-single-edit">
								<em><?php _e('<strong>Notes:</strong> Ticket availability not taken into account (i.e. you can overbook). Emails are not resent automatically.','events-manager'); ?></em>
								<br /><br />
								<input type="submit" class="button-primary em-button em-booking-submit" id="em-booking-submit" value="<?php esc_attr_e('Submit Changes', 'events-manager'); ?>" />
								<input type="button" class="button-secondary em-button em-booking-submit-cancel" id="em-booking-submit-cancel" value="<?php esc_attr_e('Cancel', 'events-manager'); ?>" />
							    <input type='hidden' name='action' value='booking_save'/>
							    <input type='hidden' name='booking_id' value='<?php echo $EM_Booking->booking_id; ?>'/>
							    <input type='hidden' name='event_id' value='<?php echo $EM_Event->event_id; ?>'/>
							    <input type='hidden' name='_wpnonce' value='<?php echo wp_create_nonce('booking_save_'.$EM_Booking->booking_id); ?>'/>
							</p>
						</form>
						<script type="text/javascript">
							jQuery(document).ready( function($){
								$('#em-booking-submit-modify').on('click', function( e ){
									e.target.closest('form').dataset.mode = 'edit';
								});
								$('#em-booking-submit-cancel').on('click', function( e ){
									e.target.closest('form').dataset.mode = 'view';
								});

								$('.em-booking-submit-status-modify').on('click', function(){
									let el = $(this).closest('.em-booking-single-status-info');
									el.hide();
									el.next('.em-booking-single-status-edit').first().show();
								});
								$('.em-booking-submit-status-cancel').on('click', function(){
									let el = $(this).closest('.em-booking-single-status-edit');
									el.hide();
									el.prev('.em-booking-single-status-info').first().show();
								});
								$('.em-booking-single-status-info').show();
								$('.em-booking-single-status-edit').hide();
							});
						</script>
						<?php do_action('em_bookings_single_details_footer', $EM_Booking); ?>
					</div>
				</div>
				<div id="em-booking-notes" class="postbox">
					<h3>
						<?php esc_html_e( 'Booking Notes', 'events-manager'); ?>
					</h3>
					<div class="inside">
						<p><?php esc_html_e('You can add private notes below for internal reference that only event managers will see.','events-manager'); ?></p>
						<?php foreach( $EM_Booking->get_notes() as $note ):
							$user = new EM_Person($note['author']);
						?>
						<div>
							<?php echo sprintf(esc_html_x('%1$s - %2$s wrote','[Date] - [Name] wrote','events-manager'), date(em_get_option('date_format'), $note['timestamp']), $user->get_name()); ?>:
							<p style="background:#efefef; padding:5px;"><?php echo nl2br($note['note']); ?></p>
						</div>
						<?php endforeach; ?>
						<form method="post" action="" style="padding:5px;">
							<textarea class="widefat" rows="5" name="booking_note"></textarea>
							<input type="hidden" name="action" value="bookings_add_note" />
							<input type="hidden" name="_wpnonce" value="<?php echo wp_create_nonce('bookings_add_note'); ?>" />
							<input type="submit" class="em-button button-primary" value="<?php esc_html_e('Add Note', 'events-manager'); ?>" />
						</form>
					</div>
				</div>
				<?php do_action('em_bookings_single_metabox_footer', $EM_Booking); ?>
			</div>
		</div>
		<br style="clear:both;" />
		<?php do_action('em_bookings_single_footer', $EM_Booking); ?>
		</div>
	</div>
	<?php
	
}

/**
 * Shows all bookings made by one person.
 */
function em_bookings_person(){	
	global $EM_Person, $EM_Notices;
	if( !$EM_Person->can_manage_bookings() ){
		?>
		<div class="wrap <?php em_template_classes('bookings-admin'); ?>">
			<h2><?php esc_html_e('Unauthorized Access','events-manager'); ?></h2>
			<p><?php esc_html_e('You do not have the rights to manage this event.','events-manager'); ?></p>
		</div>
		<?php
		return false;
	}
	?>
	<div class='em-bookings-admin-person <?php em_template_classes('bookings-admin'); ?>'>
		<div class="input">
			<?php if( is_admin() ): ?><h1 class="wp-heading-inline"><?php else: ?><h2><?php endif; ?>
					<?php esc_html_e('Manage Person\'s Booking', 'events-manager'); ?>
			<?php if( !is_admin() ): ?></h2><?php else: ?></h1><?php endif; // inverted to help IDEs ?>
			<?php if( current_user_can('edit_users') ) : ?>
				<a href="<?php echo admin_url('user-edit.php?user_id='.$EM_Person->ID); ?>" class="button button-secondary"><?php esc_html_e('Edit User','events-manager') ?></a>
			<?php endif; ?>
			<?php if( current_user_can('delete_users') ) : ?>
				<a href="<?php echo wp_nonce_url( admin_url("users.php?action=delete&amp;user=$EM_Person->ID"), 'bulk-users' ); ?>" class="button button-secondary"><?php esc_html_e('Delete User','events-manager') ?></a>
			<?php endif; ?>
			<hr class="wp-header-end">
			
	        <?php if( !is_admin() ) echo $EM_Notices; ?>
			<?php do_action('em_bookings_person_header'); ?>
	        <div id="poststuff" class="metabox-holder">
			    <div class="postbox-container" style="width:99.5%">
					<div id="event_name" class="postbox">
						<h3>
							<?php esc_html_e( 'Personal Details', 'events-manager'); ?>
						</h3>
						<div class="inside">
							<?php echo $EM_Person->display_summary(); ?>
						</div>
					</div>
					<?php do_action('em_bookings_person_body_1'); ?>
			    </div>
		    </div>
			<div class="wrap">
				<h2><?php esc_html_e('Past And Present Bookings','events-manager'); ?></h2>
				<?php
				$EM_Bookings_Table = new EM_Bookings_Table();
				$EM_Bookings_Table->status = 'all';
				$EM_Bookings_Table->scope = 'all';
				$EM_Bookings_Table->display();
		        ?>
				<?php do_action('em_bookings_person_footer', $EM_Person); ?>
			</div>
		</div>
	</div>
	<?php
}

function em_printable_booking_report() {
	global $EM_Event;
	//check that user can access this page
	if( isset($_GET['page']) && $_GET['page']=='events-manager-bookings' && isset($_GET['action']) && $_GET['action'] == 'bookings_report' && is_object($EM_Event)){
		if( is_object($EM_Event) && !$EM_Event->can_manage('edit_events','edit_others_events') ){
			?>
			<div class="wrap <?php em_template_classes('bookings-admin'); ?>">
				<h2><?php esc_html_e('Unauthorized Access','events-manager'); ?></h2>
				<p><?php esc_html_e('You do not have the rights to manage this event.','events-manager'); ?></p>
			</div>
			<?php
			return false;
		}
		em_locate_template('templates/bookings-event-printable.php', true);
		die();
	}
} 
add_action('admin_init', 'em_printable_booking_report');
?>