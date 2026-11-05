<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var string|int $i */
/* @var string $type */
/* @var EM\Recurrences\Recurrence_Set $Recurrence_Set */
$days_names = em_get_days_names();
$disabled = $Recurrence_Set->recurrence_set_id ? 'disabled' : '';
?>
<div class="em-recurrence-pattern em-recurring-text reschedulable">
	<select class="em-recurrence-frequency recurrence_freq inline" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_freq]" <?php echo $disabled; ?> data-undo="<?php echo esc_attr($Recurrence_Set->recurrence_freq); ?>">
		<?php
		$freq_options = array ("daily" => __ ( 'Daily', 'events-manager'), "weekly" => __ ( 'Weekly', 'events-manager'), "monthly" => __ ( 'Monthly', 'events-manager'), 'yearly' => __('Yearly','events-manager'), 'on' => __('On', 'events-manager') );
		em_option_items ( $freq_options, $Recurrence_Set->recurrence_freq );
		?>
	</select>
	<span class="interval-desc-intro"><?php _e ( 'every', 'events-manager')?></span>
	<input type="text" class="em-recurrence-interval inline" name='recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_interval]' size='2' value='<?php echo $Recurrence_Set->recurrence_interval ; ?>' aria-label="<?php esc_html_e('Recurrence Interval', 'events-manager'); ?>" <?php echo $disabled; ?> data-undo="<?php echo esc_attr($Recurrence_Set->recurrence_interval); ?>">
	<span class="interval-desc interval-daily-singular"><?php _e ( 'day', 'events-manager')?></span>
	<span class="interval-desc interval-daily-plural"><?php _e ( 'days', 'events-manager') ?></span>
	<span class="interval-desc interval-weekly-singular"><?php _e ( 'week on', 'events-manager'); ?></span>
	<span class="interval-desc interval-weekly-plural"><?php _e ( 'weeks on', 'events-manager'); ?></span>
	<span class="interval-desc interval-monthly-singular"><?php _e ( 'month on the', 'events-manager')?></span>
	<span class="interval-desc interval-monthly-plural"><?php _e ( 'months on the', 'events-manager')?></span>
	<span class="interval-desc interval-yearly-singular"><?php _e ( 'year', 'events-manager')?></span>
	<span class="interval-desc interval-yearly-plural"><?php _e ( 'years', 'events-manager') ?></span>
	<span class="alternate-selector em-monthly-selector">
		<select name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_byweekno]" class="recurrence_byweekno inline" <?php echo $disabled; ?> data-undo="<?php echo esc_attr($Recurrence_Set->recurrence_byweekno); ?>">
			<?php
			$weekno_options = array ("1" => __ ( 'first', 'events-manager'), '2' => __ ( 'second', 'events-manager'), '3' => __ ( 'third', 'events-manager'), '4' => __ ( 'fourth', 'events-manager'), '5' => __ ( 'fifth', 'events-manager'), '-1' => __ ( 'last', 'events-manager') );
			em_option_items ( $weekno_options, $Recurrence_Set->recurrence_byweekno  );
			?>
		</select>
		<select name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_byday]" class="recurrence_byday inline" <?php echo $disabled; ?> data-undo="<?php echo esc_attr($Recurrence_Set->recurrence_byday); ?>">
			<?php em_option_items ( $days_names, $Recurrence_Set->recurrence_byday  ); ?>
		</select>
		<?php _e('of each month','events-manager'); ?>
	</span>
	<?php
	//em_checkbox_items ( 'recurrences[' . esc_attr($type) . ']['. esc_attr($i). '][recurrence_bydays][]', $days_names, $saved_bydays );
	?>
	<label class="alternate-selector em-weekly-selector" data-nostyle>
		<span class="screen-reader-text"><?php esc_html_e('Days of week', 'events-manager'); ?></span>
		<select class="em-selectize recurrence_bydays" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_bydays][]" multiple placeholder="<?php esc_attr_e('Days of week', 'events-manager'); ?>" <?php echo $disabled; ?> data-undo="<?php echo esc_attr($Recurrence_Set->recurrence_byday); ?>">
			<?php
			$saved_bydays = !empty($Recurrence_Set->recurrence_byday) ? explode ( ",", $Recurrence_Set->recurrence_byday ) : array();
			foreach($days_names as $key => $day_name) {
				$selected =  in_array( $key, $saved_bydays ) ? "selected='selected'" : '';
				echo "<option value='".esc_attr($key)."' $selected >".esc_html($day_name)."</option>\n";
			}
			?>
		</select>
	</label>
	<span class="alternate-selector em-monthly-selector em-weekly-selector em-daily-selector em-yearly-selector">
		<button type="button" class="em-icon em-icon-edit reschedule-trigger reschedule-pattern-weekdays em-tooltip" data-nostyle data-nonce="#reschedule-pattern-nonce-<?php echo $i . '-' . $id; ?>" aria-label="<?php esc_html_e('Reschedule', 'events-manager'); ?>"></button>
	</span>
	<div class="alternate-selector em-on-selector em-datepicker em-datepicker-multiple">

		<label class="em-date-input button button-secondary <?php echo $disabled; ?>">
			<span class="em-icon em-icon-calendar em-tooltip" aria-hidden="true" aria-label="<?php _e ( 'Select dates', 'events-manager'); ?>" data-toggle></span>
			<input type="hidden" style="visibility:hidden;" aria-hidden="true" placeholder="<?php _e ( 'Select date range', 'events-manager'); ?>" data-input <?php echo $disabled; ?>>
			<?php _e ( 'Add Dates ', 'events-manager'); ?>
		</label>
		<button type="button" class="em-icon em-icon-edit reschedule-trigger reschedule-pattern-weekdays em-tooltip" data-nostyle data-nonce="#reschedule-pattern-nonce-<?php echo $i . '-' . $id; ?>" aria-label="<?php esc_html_e('Reschedule', 'events-manager'); ?>"></button>

		<div class="em-datepicker-data">
			<?php $recurrence_dates = $Recurrence_Set->recurrence_dates ? esc_attr( implode(',', $Recurrence_Set->recurrence_dates) ) : ''; ?>
			<input type="text" class="recurrence_dates" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][recurrence_dates]" value="<?php echo $recurrence_dates; ?>" aria-label="<?php _e ( 'From ', 'events-manager'); ?>" data-undo="<?php echo $recurrence_dates; ?>" >
		</div>
		<div class="em-datepicker-dates <?php echo $disabled; ?>">
			<div class="item clear-all"><span><?php esc_html_e('Clear All', 'events-manager'); ?></span><a href="javascript:void(0)" class="remove" tabindex="-1" title="<?php esc_attr__('Remove', 'events-manager'); ?>">×</a></div>
		</div>
	</div>
	<?php if ( $disabled ) : ?>
		<input type="hidden" id="reschedule-pattern-nonce-<?php echo $i . '-' . $id; ?>" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][reschedule][pattern]" value="<?php echo wp_create_nonce('reschedule-pattern-'. $Recurrence_Set->id); ?>" disabled data-nonce>
	<?php endif; ?>
</div>