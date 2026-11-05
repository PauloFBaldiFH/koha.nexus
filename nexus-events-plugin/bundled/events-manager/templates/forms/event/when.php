<?php
global $EM_Event, $post;
$required = apply_filters('em_required_html','<i>*</i>');
$days_names = em_get_days_names();
$hours_format = em_get_hour_format();
$classes = array();
$id = rand();
?>
<div class="em event-form-when input" id="em-form-when">
	<?php if ( em_get_option('dbem_recurrence_enabled') || em_get_option('dbem_repeating_enabled') || ( $EM_Event->is_recurring( true ) ) ): ?>
		<?php if ( $EM_Event->is_recurring( true ) ): ?>
			<input type="hidden" id="em-recurrence-checkbox-<?php echo $id; ?>" class="em-recurrence-checkbox event_type" name="event_type" value="<?php echo $EM_Event->is_repeating() ? 'repeating':'recurring'; ?>">
			<p>
				<?php
				if ( $EM_Event->is_repeating() ) {
					echo esc_html( sprintf( __('This is a %s event.', 'events-manager'), __('repeating', 'events-manager') ) );
				} else {
					echo esc_html( sprintf( __('This is a %s event.', 'events-manager'), __('recurring', 'events-manager') ) );
				}
				?>
			</p>
		<?php elseif ( !$EM_Event->event_id ): ?>
			<p class="em-event-type">
				<label data-nostyle>
					<?php if ( !is_admin() && em_get_option('dbem_recurrence_enabled') && em_get_option('dbem_repeating_enabled') ):  ?>
						<?php ob_start(); ?>
						<select id="em-recurrence-checkbox-<?php echo $id; ?>" class="em-recurrence-checkbox event_type inline" name="event_type" data-nostyle>
							<option value="single"><?php esc_html_e('Single', 'events-manager'); ?></option>
							<option value="recurring"><?php esc_html_e('Recurring', 'events-manager'); ?></option>
							<option value="repeating"><?php esc_html_e('Repeating', 'events-manager'); ?></option>
						</select>
						<?php echo sprintf( esc_html__('This is a %s event.', 'events-manager'), ob_get_clean() ); ?>
					<?php else: ?>
						<?php echo esc_html( sprintf( __('This is a %s event.', 'events-manager'), __('recurring', 'events-manager') ) ); ?>
						<input type="checkbox" id="em-recurrence-checkbox-<?php echo $id; ?>" class="em-recurrence-checkbox event_type" name="event_type" value="recurring" <?php if($EM_Event->is_recurring( true )) echo 'checked' ?> >
					<?php endif; ?>
				</label>
			</p>
		<?php elseif ( $EM_Event->is_recurring( true ) ): ?>
			<input type="hidden" id="em-recurrence-checkbox-<?php echo $id; ?>" class="em-recurrence-checkbox event_type" name="event_type" value="<?php echo esc_html( $EM_Event->event_type ); ?>">
		<?php endif; ?>
	<?php endif; ?>

	<div class="em-event-datetimes single-event-data">
		<?php if( em_get_option('dbem_dates_range_double_inputs', false) ): ?>
			<?php include( em_locate_template('forms/event/when/dates-separate.php') ); ?>
		<?php else: ?>
			<?php include( em_locate_template('forms/event/when/dates.php') ); ?>
		<?php endif; ?>
		<?php include( em_locate_template('forms/event/when/times.php') ); ?>
		<?php include( em_locate_template('forms/event/when/timezone.php') ); ?>
		<p class="multi-day-event-info"><?php esc_html_e( 'This event spans every day between the beginning and end date, with start/end times applying to each day.', 'events-manager'); ?></p>
		<?php if( em_get_option('dbem_event_status_enabled') ) : ?>
			<?php include( em_locate_template('forms/event/when/active-status.php') ); ?>
		<?php endif; ?>
	</div>

	<?php if ( em_get_option('dbem_recurrence_enabled') || em_get_option('dbem_repeating_enabled') || ( $EM_Event->is_recurring( true ) ) ): ?>
		<?php include em_locate_template('forms/event/when/recurring/recurring-summary.php'); ?>
	<?php endif; ?>
</div>