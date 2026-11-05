<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var string|int $i */
/* @var string $type */
/* @var EM\Recurrences\Recurrence_Set $Recurrence_Set */
?>
<div class="em-recurrence-set-actions">
	<button type="button" class="em-recurrence-set-action-order    multi-button em-icon em-icon-drag em-tooltip" aria-label="<?php esc_attr_e('Re-order.', 'events-manager'); ?>" data-nostyle></button>
	<button type="button" class="em-recurrence-set-action-remove   multi-button em-icon em-icon-trash em-tooltip" aria-label="<?php esc_attr_e('Remove this recurrence.', 'events-manager'); ?>" data-nostyle></button>
	<button type="button" class="em-recurrence-set-action-advanced multi-button em-icon em-icon-filter em-tooltip" data-nostyle
		    aria-label="<?php echo esc_attr( sprintf( __('%s Advanced Options', 'events-manager'), __('Show', 'events-manager') ) ); ?>"
	        data-label-show="<?php echo esc_attr( sprintf( __('%s Advanced Options', 'events-manager'), __('Show', 'events-manager') ) ); ?>"
	        data-label-hide="<?php echo esc_attr( sprintf( __('%s Advanced Options', 'events-manager'), __('Hide', 'events-manager') ) ); ?>"
		></button>
	<button type="button" class="primary-reschedule-override-warning  multi-button em-icon em-icon-warning em-tooltip" aria-label="<?php esc_attr_e('Pending reschedule via primary recurrence.', 'events-manager'); ?>" data-nostyle></button>
	<button type="button" class="undo em-icon em-icon-undo em-tooltip" aria-label="<?php esc_html_e('Undo Changes', 'events-manager'); ?>" data-nostyle></button>
	<?php if ( defined('EM_DEBUG') && EM_DEBUG && $Recurrence_Set->recurrence_set_id ) echo '<span style="opacity:0.5; display: inline-block; float: left; margin: 10px 5px; font-size: 10px;">#'.$Recurrence_Set->id.'</span>'; // debugging help ?>
</div>
<div class="em-recurrence-set-data">
	<?php if ( $Recurrence_Set->id ) : ?>
		<input type="hidden" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][delete]" class="em-recurrence-set-delete-field" data-nonce="<?php echo wp_create_nonce('delete_recurrence_'. $Recurrence_Set->id  . '_' . get_current_user_id() ); ?>" value="0">
		<input type="hidden" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_set_id]" class="em-recurrence-set-id recurrence_set_id" value="<?php echo esc_attr($Recurrence_Set->id); ?>">
	<?php endif; ?>
	<input type="hidden" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_type]" class="em-recurrence-set-type recurrence_type" value="<?php echo esc_attr($Recurrence_Set->type); ?>">
	<input type="hidden" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_order]" class="em-recurrence-order recurrence_order" value="<?php echo esc_attr($Recurrence_Set->order); ?>">
	<?php
	include( em_locate_template('forms/event/when/recurring/recurrences/pattern.php') );
	include( em_locate_template('forms/event/when/recurring/recurrences/advanced-summary.php') );
	?>
	<div class="em-recurrence-advanced">
		<p class="em-recurrence-advanced-description-primary">
			<?php echo esc_html( sprintf( __('This is your primary recurrence, other recurring %s will use these advanced settings as their default settings if left blank.', 'events-manager'), __('events', 'events-manager') ) ); ?>
		</p>
		<?php
		if ( $type !== 'exclude' ) {
			include( em_locate_template('forms/event/when/recurring/recurrences/duration.php') );
		}
		if( em_get_option('dbem_dates_range_double_inputs', false) ){
			include( em_locate_template('forms/event/when/recurring/recurrences/dates-separate.php') );
		} else {
			include( em_locate_template('forms/event/when/recurring/recurrences/dates.php') );
		}
		include( em_locate_template('forms/event/when/recurring/recurrences/times.php') );
		include( em_locate_template('forms/event/when/recurring/recurrences/timezone.php') );
		if( $type !== 'exclude' && em_get_option('dbem_event_status_enabled') ) {
			include( em_locate_template('forms/event/when/recurring/recurrences/status.php') );
		}
		?>
	</div>
	<?php
		if( $type !== 'exclude' ) {
			include( em_locate_template( 'forms/event/when/recurring/recurrences/reschedule-modal.php' ) );
		}
	?>
</div>
