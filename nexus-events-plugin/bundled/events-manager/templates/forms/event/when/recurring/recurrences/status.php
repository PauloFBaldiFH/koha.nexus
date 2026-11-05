<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var int $type */
/* @var int $i */
/* @var EM\Recurrences\Recurrence_Set $Recurrence_Set */
$selected_value = $Recurrence_Set->recurrence_status === null ? '' : absint($Recurrence_Set->recurrence_status);
?>
<div class="em-input-field em-input-field-select em-recurrence-status only-include-type">
	<label for="recurrence-status-<?php echo $i . '-' . $id; ?>" data-nostyle><?php esc_html_e('Event Status', 'events-manager'); ?></label>
	<select id="recurrence-status-<?php echo $i . '-' . $id; ?>" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_status]" class="em-selectize recurrence_status" data-undo="<?php echo $selected_value ?>">
		<option <?php selected('', $selected_value); ?> value=""><?php esc_html_e( 'Select a status' ); ?></option>
		<?php foreach ( EM_Event::get_active_statuses() as $status => $label ): ?>
		<option value="<?php echo esc_attr($status); ?>"
			<?php selected($status, $selected_value); ?>><?php echo esc_html($label); ?></option>
		<?php endforeach; ?>
	</select>
</div>