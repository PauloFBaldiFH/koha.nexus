<?php
/* @var string $name */
/* @var string $name_template */
/* @var EM\Timerange $Timerange */
/* @var int $i */
$name = esc_attr($name);
$placeholder_start = esc_attr__('Start Time', 'events-manager');
$placeholder_end = esc_attr__('End Time', 'events-manager');
?>
<fieldset class="inline em-timerange em-time-range">
	<legend data-nostyle><?php _e('Timerange','events-manager'); ?></legend>
	<div class="em-timerange-inputs em-time-range">
		<label class="inline" data-nostyle>
			<span class="screen-reader-text"><?php esc_html_e('Start Time', 'events-manager'); ?></span>
			<input class="em-time-input em-time-start inline recurrence_start_time" type="text" size="8" maxlength="8" name="<?php echo $name; ?>[start]" value="<?php echo $Timerange->start; ?>" placeholder="<?php esc_html_e('Start Time', 'events-manager'); ?>">
		</label>
		<?php _e('to','events-manager'); ?>
		<label class="inline" data-nostyle>
			<span class="screen-reader-text"><?php esc_html_e('End Time', 'events-manager'); ?></span>
			<input class="em-time-input em-time-end inline recurrence_end_time" type="text" size="8" maxlength="8" name="<?php echo $name; ?>[end]" value="<?php echo $Timerange->end; ?>" placeholder="<?php esc_html_e('End Time', 'events-manager'); ?>">
		</label>
		<label class="em-timerange-allday em-checkbox-icon em-tooltip" data-nostyle title="<?php echo esc_attr( sprintf(__('Enable %s', 'events-manager'), __('All day','events-manager')) ); ?>">
			<span class="em-icon em-icon-24h" role="button" tabindex="0" aria-label="<?php echo esc_attr( sprintf(__('Enable %s', 'events-manager'), __('All day','events-manager')) ); ?>"></span>
			<span><?php esc_html_e('All day','events-manager'); ?></span>
			<input type="checkbox" class="em-time-all-day recurrence_time_allday" name="<?php echo $name; ?>[all_day]" value="1" <?php echo $Timerange->all_day ? 'checked="checked"' : ''; ?> data-undo="<?php echo $Timerange->all_day ? 1:0; ?>"  data-nostyle>
		</label>
		<?php if ( $Timerange->allow_timeslots ) : ?>
		<label class="em-timerange-timeslots-trigger em-checkbox-icon em-tooltip" data-nostyle aria-label="<?php esc_attr_e('Advanced settings','events-manager'); ?>" style="--checked-icon: var(--icon-filter-hide)" data-checked-icon>
			<span class="em-icon em-icon-filter" role="button" tabindex="0"></span>
			<input type="checkbox" name="<?php echo $name; ?>[timeslots]" value="1" <?php echo $Timerange->has_timeslot_rules() ? 'checked' : ''; ?> data-nostyle>
			<span><?php esc_html_e('Advanced settings','events-manager'); ?></span>
		</label>
		<?php endif; ?>
		<button type="button" class="em-timerange-delete em-icon em-icon-trash em-tooltip" aria-label="<?php esc_attr_e('Delete','events-manager'); ?>" data-nostyle></button>
	</div>
	<?php if ( $Timerange->allow_timeslots ) : ?>
	<div class="em-timerange-timeslots">
		<div class="em-timerange-row">
			<label class="inline" data-nostyle><?php esc_html_e( 'Duration', 'events-manager' ); ?></label>
			<?php $duration = $Timerange->get_time_value( 'duration' ); ?>
			<input type="text" name="<?php echo $name; ?>[duration][qty]" class="em-timerange-duration" placeholder="0" value="<?php echo esc_attr( $duration['value'] ?: '' ); ?>" data-nostyle>
			<select name="<?php echo $name; ?>[duration][unit]" class="em-timerange-duration-unit" data-nostyle>
				<option value="M" <?php selected( $duration['unit'], 'M' ); ?>><?php esc_html_e( 'Minutes', 'events-manager' ); ?></option>
				<option value="H" <?php selected( $duration['unit'], 'H' ); ?>><?php esc_html_e( 'Hours', 'events-manager' ); ?></option>
			</select>
		</div>
		<div class="em-timerange-row">
			<label class="inline" data-nostyle><?php esc_html_e( 'Buffer', 'events-manager' ); ?></label>
			<?php $buffer = $Timerange->get_time_value( 'buffer' ); ?>
			<input type="text" name="<?php echo $name; ?>[buffer][qty]" class="em-timerange-buffer" placeholder="0" value="<?php echo esc_attr( $buffer['value'] ?: '' ); ?>">
			<select name="<?php echo $name; ?>[buffer][unit]" class="em-timerange-buffer-unit">
				<option value="M" <?php selected( $buffer['unit'], 'M' ); ?>><?php esc_html_e( 'Minutes', 'events-manager' ); ?></option>
				<option value="H" <?php selected( $buffer['unit'], 'H' ); ?>><?php esc_html_e( 'Hours', 'events-manager' ); ?></option>
			</select>
		</div>
		<div class="em-timerange-row">
			<label class="inline" data-nostyle><?php esc_html_e( 'Frequency', 'events-manager' ); ?></label>
			<?php
			$frequency = $Timerange->get_time_value( 'frequency' );
			?>
			<input type="text" name="<?php echo $name; ?>[frequency][qty]" class="em-timerange-frequency" placeholder="<?php echo esc_attr( $duration['value'] ?: 0 ); ?>" value="<?php echo esc_attr( $frequency['value'] ?: '' ); ?>">
			<select name="<?php echo $name; ?>[frequency][unit]" class="em-timerange-frequency-unit">
				<option value="M" <?php selected( $frequency['unit'], 'M' ); ?>><?php esc_html_e( 'Minutes', 'events-manager' ); ?></option>
				<option value="H" <?php selected( $frequency['unit'], 'H' ); ?>><?php esc_html_e( 'Hours', 'events-manager' ); ?></option>
			</select>
		</div>
	</div>
	<?php endif; ?>
	<?php if ( $Timerange->timerange_id ) : ?>
		<input type="hidden" name="<?php echo $name; ?>[timerange_id]" value="<?php echo absint($Timerange->timerange_id); ?>">
		<input type="hidden" class="em-timerange-delete-nonce" name="<?php echo $name_template; ?>[delete][<?php echo absint($Timerange->timerange_id); ?>]" data-nonce="<?php echo wp_create_nonce('delete_timerange_' . $Timerange->timerange_id); ?>">
	<?php endif; ?>
</fieldset>