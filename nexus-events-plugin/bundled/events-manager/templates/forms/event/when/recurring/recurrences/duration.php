<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var int $type */
/* @var int $i */
/* @var EM\Recurrences\Recurrence_Set $Recurrence_Set */
$duration = esc_attr($Recurrence_Set->recurrence_duration);
?>
<div class="em-recurrence-duration em-recurring-text only-include-type">
	<label for="recurrence-days-<?php echo $i . '-' . $id; ?>" data-nostyle><?php esc_html_e('Events Duration','events-manager'); ?></label>
	<input id="recurrence-days-<?php echo $i . '-' . $id; ?>" type="text" size="2" maxlength="8" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_duration]" class="em-recurrence-duration inline recurrence_duration" value="<?php echo $duration; ?>" placeholder="0" data-undo="<?php echo $duration; ?>">
	<span class="recurrence-days-desc em-singular hidden"><?php esc_html_e('day', 'events-manager'); ?></span>
	<span class="recurrence-days-desc em-plural"><?php esc_html_e('days', 'events-manager'); ?></span>
</div>