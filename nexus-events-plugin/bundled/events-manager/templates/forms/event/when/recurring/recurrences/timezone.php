<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var int $type */
/* @var int $i */
/* @var EM\Recurrences\Recurrence_Set $Recurrence_Set */
$timezone = $i !== 'N%' ? $Recurrence_Set->start()->getTimezone()->getValue() : '';
?>
<?php if( em_get_option('dbem_timezone_enabled') || ( $Recurrence_Set->recurrence_timezone && $Recurrence_Set->recurrence_timezone !== em_get_option('timezone_string') ) ): ?>
	<p class="em-timezone em-recurrence-timezone">
		<label for="recurrence-timezone-<?php echo $i . '-' . $id; ?>" data-nostyle><?php esc_html_e('Timezone', 'events-manager'); ?></label>
		<select id="recurrence-timezone-<?php echo $i . '-' . $id; ?>" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_timezone]" class="em-selectize recurrence_timezone" data-undo="<?php echo esc_attr($timezone) ?>">
			<?php if ( !empty($Recurrence_Set->recurrence_timezone) ) : ?>
			<option selected="selected" value=""><?php _e( 'Select a city' ); ?></option>
			<?php endif; ?>
			<?php echo wp_timezone_choice( $timezone, get_user_locale() ); ?>
		</select>
	</p>
<?php endif; ?>