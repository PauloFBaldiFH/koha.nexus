<?php
// The following are included in the scope of this recurrence date range picker
/* @var int $id */
/* @var int $type */
/* @var int $i */
/* @var EM\Recurrences\Recurrence_Set $Recurrence_Set */
$disabled = $Recurrence_Set->recurrence_set_id ? 'disabled' : '';
$start_date = esc_attr($Recurrence_Set->recurrence_start_date);
$end_date = esc_attr($Recurrence_Set->recurrence_end_date);
?>
<div class="em-event-dates em-recurrence-dates em-recurrence-interval em-datepicker em-datepicker-until reschedulable">
	<fieldset class="inline">
		<legend data-nostyle><?php echo sprintf( esc_html__( '%s Span Between', 'events-manager'), esc_html__('Recurrences') ); ?></legend>
		<div class="em-datepicker-until-fields" data-nostyle>
			<input id="em-date-start-<?php echo $i ?>-<?php echo $id ?>" type="hidden" class="em-date-input em-date-input-start" aria-hidden="true" placeholder="<?php _e ( 'Start Date', 'events-manager'); ?>" aria-label="<?php _e ( 'Start Date', 'events-manager'); ?>" <?php echo $disabled; ?>>
			<label for="em-date-end-<?php echo $i ?>-<?php echo $id ?>" class="inline" data-nostyle><?php _e('until','events-manager'); ?></label>
			<input id="em-date-end-<?php echo $i ?>-<?php echo $id ?>" type="hidden" class="em-date-input em-date-input-end" aria-hidden="true" placeholder="<?php _e ( 'End Date', 'events-manager'); ?>" <?php echo $disabled; ?>>
		</div>

		<div class="em-datepicker-data inline-inputs">
			<input type="date" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_start_date]" value="<?php echo $start_date; ?>" aria-label="<?php _e ( 'From ', 'events-manager'); ?>" data-undo="<?php echo $start_date; ?>" class="recurrence_start_date">
			<span class="separator"><?php _e('to','events-manager'); ?></span>
			<input type="date" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_end_date]" value="<?php echo $end_date; ?>" aria-label="<?php _e('to','events-manager'); ?>" data-undo="<?php echo $end_date; ?>" class="recurrence_end_date">
		</div>
	</fieldset>
	<?php if ( $disabled ) : ?>
		<button type="button" class="reschedule-trigger em-icon em-icon-edit em-tooltip" data-nostyle data-nonce="#reschedule-dates-nonce-<?php echo $i . '-' . $id; ?>" aria-label="<?php esc_html_e('Reschedule', 'events-manager'); ?>"></button>
		<input type="hidden" id="reschedule-dates-nonce-<?php echo $i . '-' . $id; ?>" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][reschedule][dates]" value="<?php echo wp_create_nonce('reschedule-dates-'. $Recurrence_Set->id); ?>" disabled data-nonce>
	<?php endif; ?>
</div>
