<?php
/* WARNING! This file may change in the near future as we intend to add features to the event editor. If at all possible, try making customizations using CSS, jQuery, or using our hooks and filters. - 2012-02-14 */
/* 
 * To ensure compatability, it is recommended you maintain class, id and form name attributes, unless you now what you're doing. 
 * You also must keep the _wpnonce hidden field in this form too.
 */
global $EM_Event, $EM_Notices, $bp;
$template = isset($args['css_template']) ? esc_attr($args['css_template']) : implode(' ', em_get_template_classes('event-editor', 'event-editor-section', true));

//check that user can access this page
if( is_object($EM_Event) && !$EM_Event->can_manage('edit_events','edit_others_events') ){
	?>
	<div class="wrap"><h2><?php esc_html_e('Unauthorized Access','events-manager'); ?></h2><p><?php echo sprintf(__('You do not have the rights to manage this %s.','events-manager'),__('Event','events-manager')); ?></p></div>
	<?php
	return false;
}elseif( !is_object($EM_Event) ){
	$EM_Event = new EM_Event();
}
$required = apply_filters('em_required_html','<i>*</i>');

$id = rand(); // not related to searches, so we'll just add an ID for good practice
?>
<div class="<?php em_template_classes('view-container'); ?>" id="em-view-<?php echo $id; ?>" data-view="event">
	<?php
		echo $EM_Notices;
		//Success notice
		if( !empty($_REQUEST['success']) ){
			if(!em_get_option('dbem_events_form_reshow')){
				echo '</div>'; // close the div and exit if we're not showing the form again
				return false;
			}
		}
	?>
	<form enctype='multipart/form-data' id="event-form-<?php echo $id; ?>" class="<?php em_template_classes('event-editor'); ?> <?php if( $EM_Event->is_recurring( true ) ) echo 'em-event-admin-recurring' ?>"
	      method="post" action="<?php echo esc_url(add_query_arg(array('success'=>null, 'action'=>null))); ?>" data-view-id="<?php echo $id; ?>">
		<?php do_action('em_front_event_form_header', $EM_Event); ?>
		<section class="event-form-submitter <?php echo $template; ?>">
			<?php if(em_get_option('dbem_events_anonymous_submissions') && !is_user_logged_in()): ?>
				<h3><?php esc_html_e( 'Your Details', 'events-manager'); ?></h3>
				<div class="input">
					<p>
						<label><?php esc_html_e('Name', 'events-manager'); ?></label>
						<input type="text" name="event_owner_name" id="event-owner-name" value="<?php echo esc_attr($EM_Event->event_owner_name); ?>" >
					</p>
					<p>
						<label><?php esc_html_e('Email', 'events-manager'); ?></label>
						<input type="text" name="event_owner_email" id="event-owner-email" value="<?php echo esc_attr($EM_Event->event_owner_email); ?>" >
					</p>
					<?php do_action('em_front_event_form_guest'); ?>
					<?php do_action('em_font_event_form_guest'); //deprecated ?>
				</div>
			<?php endif; ?>
		</section>
		
		<section class="event-form-name <?php echo $template; ?>">
			<h3><label for="event-name"><?php esc_html_e( 'Event Name', 'events-manager'); ?></label></h3>
			<div class="input">
				<input type="text" name="event_name" id="event-name" value="<?php echo esc_attr($EM_Event->event_name); ?>" placeholder="<?php esc_html_e( 'Event Name', 'events-manager'); echo ' *';  ?>">
				<?php esc_html_e('The event name. Example: Birthday party', 'events-manager'); ?>
				<?php em_locate_template('forms/event/group.php',true); ?>
			</div>
		</section>

		<section class="event-form-when  <?php echo $template; ?>">
			<h3><?php esc_html_e( 'When', 'events-manager'); ?></h3>
			<div class="input">
			<?php em_locate_template('forms/event/when.php',true); ?>
			</div>
		</section>

		<section class="event-form-recurrences recurring-event-editor <?php echo $template; ?>">
			<h4><?php esc_html_e( 'Recurrences', 'events-manager'); ?></h4>
			<div class="input">
				<?php em_locate_template('forms/event/when/recurring/recurrences.php',true); ?>
			</div>
		</section>

		<section class="event-form-where">
			<?php if( em_get_option('dbem_locations_enabled') ): ?>
			<h3><?php esc_html_e( 'Where', 'events-manager'); ?></h3>
			<div>
				<?php em_locate_template('forms/event/location.php',true); ?>
			</div>
			<?php endif; ?>
		</section>
		
		<section class="event-form-details">
			<div class="<?php echo $template; ?>"><h3><?php esc_html_e( 'Details', 'events-manager'); ?></h3></div>
			<div>
				<div class="event-editor">
					<?php if( em_get_option('dbem_events_form_editor') && function_exists('wp_editor') ): ?>
						<?php
							$post_content = !empty($EM_Event->post_content) ? $EM_Event->post_content : '';
							wp_editor($post_content, 'em-editor-content', array('textarea_name'=>'content') );
						?>
					<?php else: ?>
						<textarea name="content" rows="10" style="width:100%"><?php echo $EM_Event->post_content ?></textarea>
						<br >
						<?php esc_html_e( 'Details about the event.', 'events-manager')?> <?php esc_html_e( 'HTML allowed.', 'events-manager')?>
					<?php endif; ?>
				</div>
				<div class="event-extra-details <?php echo $template; ?>">
					<div class="input">
					<?php if(em_get_option('dbem_attributes_enabled')) { em_locate_template('forms/event/attributes-public.php',true); }  ?>
					<?php if(em_get_option('dbem_categories_enabled')) { em_locate_template('forms/event/categories-public.php',true); }  ?>
					</div>
				</div>
			</div>
		</section>

		<section class="event-form-image  <?php echo $template; ?>">
			<?php if( $EM_Event->can_manage('upload_event_images','upload_event_images') ): ?>
			<h3><?php esc_html_e( 'Event Image', 'events-manager'); ?></h3>
			<div class="input">
				<?php em_locate_template('forms/event/featured-image-public.php',true); ?>
			</div>
			<?php endif; ?>
		</section>

		<section class="event-form-bookings <?php echo $template; ?>">
			<?php if( em_get_option('dbem_rsvp_enabled') && $EM_Event->can_manage('manage_bookings','manage_others_bookings') ) : ?>
			<!-- START Bookings -->
			<h3><?php esc_html_e('Bookings/Registration','events-manager'); ?></h3>
			<div class="input">
				<?php em_locate_template('forms/event/bookings.php',true); ?>
			</div>
			<!-- END Bookings -->
			<?php endif; ?>
		</section>
		
		<?php do_action('em_front_event_form_footer', $EM_Event); ?>
		
		<section class="event-form-submit <?php echo $template; ?>">
			<p class="input submit">
			    <?php if( empty($EM_Event->event_id) ): ?>
			    <input type='submit' class='button-primary' value='<?php echo esc_attr(sprintf( __('Submit %s','events-manager'), __('Event','events-manager') )); ?>' >
			    <?php else: ?>
			    <input type='submit' class='button-primary' value='<?php echo esc_attr(sprintf( __('Update %s','events-manager'), __('Event','events-manager') )); ?>' >
			    <?php endif; ?>
			</p>
			<input type="hidden" name="event_id" value="<?php echo $EM_Event->event_id; ?>" >
			<input type="hidden" name="_wpnonce" value="<?php echo wp_create_nonce('wpnonce_event_save'); ?>" >
			<input type="hidden" name="action" value="event_save" >
			<?php if( !empty($_REQUEST['redirect_to']) ): ?>
			<input type="hidden" name="redirect_to" value="<?php echo esc_attr($_REQUEST['redirect_to']); ?>" >
			<?php endif; ?>
		</section>
	</form>
</div>