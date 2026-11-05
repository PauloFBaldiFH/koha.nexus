<?php
// The following are included in the scope of this recurrence time range picker
/* @var int $id */
/* @var int $type */
/* @var int $i */
/* @var EM\Recurrences\Recurrence_Set $Recurrence_Set */
$disabled = $Recurrence_Set->id ? 'disabled' : '';
$locked = $Recurrence_Set->get_event()->event_id ?: false;
$name = "recurrences[". esc_attr($type) ."][". esc_attr($i) . "][timeranges]";
$recurrence_name = $name;
$Timeranges = $Recurrence_Set->get_timeranges();
if ( $type === 'exclude' ) {
	$Timeranges->allow_timeranges = false;
}
$overriding = $Recurrence_Set->recurrence_start_time || $Recurrence_Set->recurrence_end_time;
// create a wrapper that will hide timerange editor if this recurrence set not primary or if recurrence set does not override default setting
?>
<fieldset class="em-recurrence-timeranges reschedulable <?php echo $disabled; ?>">
	<legend>
		<?php esc_html_e('Times'); ?>
		<?php if ( $disabled ) : ?>
			<button type="button" class="reschedule-trigger em-icon em-icon-edit em-tooltip" data-nostyle data-nonce="#reschedule-times-nonce-<?php echo $i . '-' . $id; ?>" aria-label="<?php esc_html_e('Reschedule', 'events-manager'); ?>"></button>
			<input type="hidden" id="reschedule-times-nonce-<?php echo $i . '-' . $id; ?>" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][reschedule][times]" value="<?php echo wp_create_nonce('reschedule-times-'. $Recurrence_Set->id); ?>" disabled data-reschedule>
		<?php endif; ?>
	</legend>
	<div class="recurrence-timeranges-default">
		<label>
			<?php esc_html_e('Override default times', 'events'); ?>
			<input type="checkbox" name="recurrences[<?php echo esc_attr($type) ."][". esc_attr($i) ; ?>][override_time]" value="1" class="recurrences-timeranges-default-trigger" <?php checked( $overriding ); ?> data-undo="<?php echo $overriding ? 1 : 0; ?>" <?php echo $disabled; ?>>
		</label>
	</div>
	<div class="recurrence-timeranges-editor">
		<?php include( em_locate_template('forms/timeranges/timeranges.php') ); ?>
	</div>
	<?php if ( $Recurrence_Set->recurrence_set_id ) : // output again in a template tag so we can just replace contents when undoing ?>
	<template class="recurrence-timeranges-undo">
		<?php
			$name = $recurrence_name;
			include( em_locate_template('forms/timeranges/timeranges.php') );
		?>
	</template>
	<?php endif; ?>
</fieldset>