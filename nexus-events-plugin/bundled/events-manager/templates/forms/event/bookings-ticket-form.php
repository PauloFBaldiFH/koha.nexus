<?php 
/* 
 * Used for both multiple and single tickets. $col_count will always be 1 in single ticket mode, and be a unique number for each ticket starting from 1 
 * This form should have $EM_Ticket and $col_count available globally. 
 */
global $col_count, $EM_Ticket; /* @var EM_Ticket $EM_Ticket */
$col_count = absint($col_count); //now we know it's a number
$price = $EM_Ticket->ticket_price === null ? '' : $EM_Ticket->get_price_precise(true);
?>
<div class="em-ticket-form">
	<?php if ( $EM_Ticket->parent ) : ?>
	<p class="em-ticket-form-parent-warning">
		<span class="em-icon em-icon-warning"></span>
		<?php echo sprintf( esc_html__('This ticket is the child of a recurring event ticket. Values can be overriden for this recurrence. Blank text values will default to the parent ticket value, checkboxes like this %s will inherit parent ticket values.','events-manager'), '<input type="checkbox" indeterminate readonly>'); ?>
	</p>
	<?php endif; ?>
	<input type="hidden" name="em_tickets[<?php echo $col_count; ?>][ticket_id]" class="ticket_id" value="<?php echo esc_attr($EM_Ticket->ticket_id) ?>">
	<input type="hidden" name="em_tickets[<?php echo $col_count; ?>][ticket_uuid]" class="ticket_uuid" value="<?php echo wp_generate_uuid4(); ?>">
	<input type="hidden" name="em_tickets[<?php echo $col_count; ?>][delete]" class="delete" value="<?php echo wp_create_nonce('delete_ticket_'.$EM_Ticket->ticket_id); ?>" data-nonce disabled>
	<div class="em-ticket-form-main">
		<div class="ticket-name">
			<label title="<?php esc_attr_e('Enter a ticket name.','events-manager'); ?>"><?php esc_html_e('Name','events-manager') ?></label>
			<input type="text" name="em_tickets[<?php echo $col_count; ?>][ticket_name]" value="<?php echo esc_attr($EM_Ticket->ticket_name) ?>" class="ticket_name" placeholder="<?php echo $EM_Ticket->get_input_placeholder('name'); ?>">
		</div>
		<div class="ticket-description">
			<label><?php esc_html_e('Description','events-manager') ?></label>
			<textarea name="em_tickets[<?php echo $col_count; ?>][ticket_description]" class="ticket_description" placeholder="<?php echo $EM_Ticket->get_input_placeholder('description'); ?>"><?php echo esc_html(wp_unslash($EM_Ticket->ticket_description)) ?></textarea>
		</div>
		<div class="ticket-price"><label><?php esc_html_e('Price','events-manager') ?></label><input type="text" name="em_tickets[<?php echo $col_count; ?>][ticket_price]" class="ticket_price" value="<?php echo esc_attr($price) ?>" placeholder="<?php echo $EM_Ticket->get_input_placeholder('price'); ?>"></div>
		<div class="ticket-spaces">
			<label title="<?php esc_attr_e('Enter a maximum number of spaces (required).','events-manager'); ?>"><?php esc_html_e('Spaces','events-manager') ?></label>
			<input type="text" name="em_tickets[<?php echo $col_count; ?>][ticket_spaces]" value="<?php echo esc_attr($EM_Ticket->ticket_spaces) ?>" class="ticket_spaces" placeholder="<?php echo $EM_Ticket->get_input_placeholder('spaces'); ?>">
		</div>
		<div class="ticket-status">
			<?php
			// get the default value text depending if overridden by parent and current value is blank, also add a state to the default select so we can show the restriction valuese
			$default_value = 1;
			// check if parent overrides, if not then resort to Everyone
			if ( $EM_Ticket->ticket_parent ) {
				if ( $EM_Ticket->get_parent()->status ) {
					$default_text = __( 'Enabled', 'events-manager' ) . ' ' . _x( '(inherited)', 'value inherited from another parent item', 'events-manager' );
					$default_value = 1;
				} else {
					$default_text = __( 'Disabled', 'events-manager' ) . ' ' . _x( '(inherited)', 'value inherited from another parent item', 'events-manager' );
					$default_value = 0;
				}
			}
			?>
			<label><?php esc_html_e('Status','events-manager') ?></label>
			<select name="em_tickets[<?php echo $col_count; ?>][ticket_status]" class="ticket_status" data-default="<?php echo $default_value; ?>">
				<?php if ( !empty($default_text) ): ?>
					<option value="-1"><?php echo esc_html( $default_text ); ?></option>
				<?php endif; ?>
				<option value="1" <?php if ( $EM_Ticket->ticket_status ) echo 'selected'; ?>><?php esc_html_e('Enabled', 'events-manager'); ?></option>
				<option value="0" <?php if ( $EM_Ticket->ticket_status === 0 ) echo 'selected'; ?>><?php esc_html_e('Disabled', 'events-manager'); ?></option>
			</select>
		</div>
	</div>
	<div class="em-ticket-form-advanced" style="display:none;">
		<div class="ticket-spaces ticket-spaces-min inline-inputs">
			<label title="<?php esc_attr_e('Leave either blank for no upper/lower limit.','events-manager'); ?>"><?php echo esc_html_x('At least','spaces per booking','events-manager');?></label>
			<input type="text" name="em_tickets[<?php echo $col_count; ?>][ticket_min]" value="<?php echo esc_attr($EM_Ticket->ticket_min) ?>" class="ticket_min" placeholder="<?php echo $EM_Ticket->get_input_placeholder('min'); ?>">
			<?php esc_html_e('spaces per booking', 'events-manager')?>
		</div>
		<div class="ticket-spaces ticket-spaces-max inline-inputs">
			<label title="<?php esc_attr_e('Leave either blank for no upper/lower limit.','events-manager'); ?>"><?php echo esc_html_x('At most','spaces per booking', 'events-manager'); ?></label>
			<input type="text" name="em_tickets[<?php echo $col_count; ?>][ticket_max]" value="<?php echo esc_attr($EM_Ticket->ticket_max) ?>" class="ticket_max" placeholder="<?php echo $EM_Ticket->get_input_placeholder('max'); ?>">
			<?php esc_html_e('spaces per booking', 'events-manager')?>
		</div>
		<div class="ticket-dates em-time-range">
			<div class="ticket-dates-from inline-inputs">
				<label title="<?php esc_attr_e('Add a start or end date (or both) to impose time constraints on ticket availability. Leave either blank for no upper/lower limit.','events-manager'); ?>">
					<?php esc_html_e('Available from','events-manager') ?>
				</label>
				<div class="ticket-dates-from-normal em-datepicker em-datepicker-until" data-until-id="em-ticket-dates-until-<?php echo $col_count; ?>">
					<input type="hidden" class="em-date-input em-date-input-start">
					<span class="em-datepicker-data">
						<input type="date" name="em_tickets[<?php echo $col_count; ?>][ticket_start]" value="<?php echo ( !empty($EM_Ticket->ticket_start) ) ? $EM_Ticket->start()->format("Y-m-d"):''; ?>">
					</span>
				</div>
				<div class="ticket-dates-from-recurring ">
					<input type="text" name="em_tickets[<?php echo $col_count; ?>][ticket_start_recurring_days]" size="3" value="<?php if( !empty($EM_Ticket->ticket_meta['recurrences']['start_days']) && is_numeric($EM_Ticket->ticket_meta['recurrences']['start_days'])) echo absint($EM_Ticket->ticket_meta['recurrences']['start_days']); ?>" >
					<?php esc_html_e('day(s)','events-manager'); ?>
					<select name="em_tickets[<?php echo $col_count; ?>][ticket_start_recurring_when]" class="ticket-dates-from-recurring-when">
						<option value="before" <?php if( isset($EM_Ticket->ticket_meta['recurrences']['start_days']) && $EM_Ticket->ticket_meta['recurrences']['start_days'] <= 0) echo 'selected="selected"'; ?>><?php echo esc_html(sprintf(_x('%s the event starts','before or after','events-manager'),__('Before','events-manager'))); ?></option>
						<option value="after" <?php if( !empty($EM_Ticket->ticket_meta['recurrences']['start_days']) && $EM_Ticket->ticket_meta['recurrences']['start_days'] > 0) echo 'selected="selected"'; ?>><?php echo esc_html(sprintf(_x('%s the event starts','before or after','events-manager'),__('After','events-manager'))); ?></option>
					</select>
				</div>
				<?php echo esc_html_x('at', 'time','events-manager'); ?>
				<input class="em-time-input em-time-start" type="text" size="8" maxlength="8" name="em_tickets[<?php echo $col_count; ?>][ticket_start_time]" value="<?php echo ( !empty($EM_Ticket->ticket_start) ) ? $EM_Ticket->start()->format( em_get_hour_format() ):''; ?>" >
			</div>
			<div class="ticket-dates-to inline-inputs">
				<label title="<?php esc_attr_e('Add a start or end date (or both) to impose time constraints on ticket availability. Leave either blank for no upper/lower limit.','events-manager'); ?>">
					<?php esc_html_e('Available until','events-manager') ?>
				</label>
				<div class="ticket-dates-to-normal em-datepicker" id="em-ticket-dates-until-<?php echo $col_count; ?>">
					<input type="hidden" class="em-date-input em-date-input-end">
					<span class="em-datepicker-data">
						<input type="date" name="em_tickets[<?php echo $col_count; ?>][ticket_end]" value="<?php echo ( !empty($EM_Ticket->ticket_end) ) ? $EM_Ticket->end()->format("Y-m-d"):''; ?>" >
					</span>
				</div>
				<div class="ticket-dates-to-recurring">
					<input type="text" name="em_tickets[<?php echo $col_count; ?>][ticket_end_recurring_days]" size="3" value="<?php if( isset($EM_Ticket->ticket_meta['recurrences']['end_days']) && $EM_Ticket->ticket_meta['recurrences']['end_days'] !== false ) echo absint($EM_Ticket->ticket_meta['recurrences']['end_days']); ?>" >
					<?php esc_html_e('day(s)','events-manager'); ?>
					<select name="em_tickets[<?php echo $col_count; ?>][ticket_end_recurring_when]" class="ticket-dates-to-recurring-when">
						<option value="before" <?php if( isset($EM_Ticket->ticket_meta['recurrences']['end_days']) && $EM_Ticket->ticket_meta['recurrences']['end_days'] <= 0) echo 'selected="selected"'; ?>><?php echo esc_html(sprintf(_x('%s the event starts','before or after','events-manager'),__('Before','events-manager'))); ?></option>
						<option value="after" <?php if( !empty($EM_Ticket->ticket_meta['recurrences']['end_days']) && $EM_Ticket->ticket_meta['recurrences']['end_days'] > 0) echo 'selected="selected"'; ?>><?php echo esc_html(sprintf(_x('%s the event starts','before or after','events-manager'),__('After','events-manager'))); ?></option>
					</select>
				</div>
				<?php echo esc_html_x('at', 'time','events-manager'); ?>
				<input class="em-time-input em-time-end ticket-times-to-normal" type="text" size="8" maxlength="8" name="em_tickets[<?php echo $col_count; ?>][ticket_end_time]" value="<?php echo ( !empty($EM_Ticket->ticket_end) ) ? $EM_Ticket->end()->format( em_get_hour_format() ):''; ?>" >
			</div>
		</div>
		<?php if( !em_get_option('dbem_bookings_tickets_single') || count($EM_Ticket->get_event()->get_tickets()->tickets) > 1 ): ?>
		<div class="ticket-required inline-inputs">
			<label title="<?php esc_attr_e('If checked every booking must select one or the minimum number of this ticket.','events-manager'); ?>" class="inline-right"><?php esc_html_e('Required?','events-manager') ?></label>
			<?php
			$state = $EM_Ticket->ticket_required ? 'checked ' : '';
			if ( $EM_Ticket->ticket_parent ) {
				$state .= $EM_Ticket->ticket_required === null ? 'indeterminate readonly' : 'indeterminate';
			}
			$hidden_value = $state == 'checked ' ? 1 : ( $state === 'indeterminate readonly' ? 'default' : 0 );
			?>
			<input type="checkbox" value="1" class="ticket_required possibly-indeterminate" <?php echo $state ?>>
			<input type="hidden" value="<?php echo $hidden_value; ?>" name="em_tickets[<?php echo $col_count; ?>][ticket_required]" class="ticket_required">
			<?php if ( $EM_Ticket->ticket_parent ): ?>
			<span class="ticket_required-default"><?php echo esc_html( sprintf( __('Default: %s', 'events-manager'), $EM_Ticket->get_parent()->required ? __('Required', 'events-manager') : __('Not Required', 'events-manager') ) ); ?></span>
			<?php endif; ?>
		</div>
		<?php endif; ?>
		<div class="ticket-type">
			<label><?php esc_html_e('Available for','events-manager') ?></label>
			<?php
			// get the default value text depending if overridden by parent and current value is blank, also add a state to the default select so we can show the restriction valuese
			$default_value = '';
			// check if parent overrides, if not then resort to Everyone
			if ( $EM_Ticket->ticket_parent ) {
				if ( $EM_Ticket->members ) {
					$default_text = __( 'Logged In Users', 'events-manager' ) . ' ' . _x( '(inherited)', 'value inherited from another parent item', 'events-manager' );
					$default_value = 'members';
				} elseif ( $EM_Ticket->guests ) {
					$default_text = __( 'Guest Users', 'events-manager' ) . ' ' . _x( '(inherited)', 'value inherited from another parent item', 'events-manager' );
					$default_value = 'guests';
				} else {
					$default_text = __( 'Everyone', 'events-manager' ) . ' ' . _x( '(inherited)', 'value inherited from another parent item', 'events-manager' );
					$default_value = '';
				}
			}
			?>
			<select name="em_tickets[<?php echo $col_count; ?>][ticket_type]" class="ticket_type" data-default="<?php echo $default_value; ?>">
				<?php if ( !empty($default_text) ): ?>
				<option value="-1"><?php echo esc_html( $default_text ); ?></option>
				<?php endif; ?>
				<option value=""><?php esc_html_e('Everyone','events-manager'); ?></option>
				<option value="members" <?php if($EM_Ticket->ticket_members) echo 'selected="selected"'; ?>><?php esc_html_e('Logged In Users','events-manager'); ?></option>
				<option value="guests" <?php if($EM_Ticket->ticket_guests) echo 'selected="selected"'; ?>><?php esc_html_e('Guest Users','events-manager'); ?></option>
			</select>
		</div>
		<div class="ticket-roles" <?php if( !$EM_Ticket->ticket_members ): ?>style="display:none;"<?php endif; ?>>
			<label><?php _e('Restrict to','events-manager'); ?></label>
			<div>
				<?php 
				$WP_Roles = new WP_Roles();
				foreach($WP_Roles->roles as $role => $role_data){ /* @var WP_Role $WP_Role */
					$state = in_array($role, $EM_Ticket->ticket_members_roles) ? 'checked' : '';
					if ( $EM_Ticket->ticket_parent && $EM_Ticket->get_parent()->ticket_members && in_array($role, $EM_Ticket->get_parent()->ticket_members_roles) ) { // set indeterminate state if not checked
						$state .= $state && $EM_Ticket->ticket_members ? ' indeterminate' : ' indeterminate readonly';
					}
					?>
					<label data-nostyle>
						<input type="checkbox" name="em_tickets[<?php echo $col_count; ?>][ticket_members_roles][]" value="<?php echo esc_attr($role); ?>" class="ticket_members_roles" <?php echo $state ?>>
						<?php echo esc_html($role_data['name']); ?>
					</label>
					<br >
					<?php
				}
				?>
			</div>
		</div>
		<?php do_action('em_ticket_edit_form_fields', $col_count, $EM_Ticket); //do not delete, add your extra fields this way, remember to save them too! ?>
	</div>
	<div class="ticket-options">
		<a href="#" class="ticket-options-advanced show button"><span class="show-advanced"><?php esc_html_e('Show Advanced Options','events-manager'); ?></span><span class="hide-advanced" style="display:none;"><?php esc_html_e('Hide Advanced Options','events-manager'); ?></span></a>
	</div>
</div>