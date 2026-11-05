<?php
/**
 * @var EM_Event $EM_Event
 */
?>
<div class="em-recurring-summary recurring-event-data">
	<div class="recurring-summary-dates<?php if ( !$EM_Event->event_id ) echo ' hidden'; if ( $EM_Event->event_all_day ) echo ' is-all-day'; ?>" >
		<!-- Start date/time section -->
		<div class="label label-time label-start-time"><?php esc_html_e('Recurrences will start from:', 'events-manager'); ?></div>
		<div class="label all-day label-start-day"><?php echo esc_html__('Recurrences will span between:', 'events-manager'); ?></div>

		<div class="recurring-datetime recurring-datetime-start">
			<span class="start-date date"><?php echo $EM_Event->start()->i18n( em_get_datepicker_format() ); ?></span>
			<span class="start-time time"><?php echo ' @ ' . $EM_Event->start()->i18n( em_get_hour_format() ); ?></span>
		</div>

		<!-- End date/time section -->
		<div class="label label-time end-time"><?php _e('Recurrences will end on:','events-manager'); ?></div>
		<div class="label all-day label-end-day"> - </div>

		<div class="recurring-datetime recurring-datetime-end">
			<span class="end-date date"><?php echo $EM_Event->end()->i18n( em_get_datepicker_format() ); ?></span>
			<span class="end-time time"><?php echo ' @ ' . $EM_Event->end()->i18n( em_get_hour_format() ); ?></span>
		</div>

		<?php if( em_get_option('dbem_timezone_enabled') || ( $EM_Event->event_timezone && $EM_Event->event_timezone !== em_get_option('timezone_string') ) ): ?>
		<!-- Timezone section - now adjacent to times -->
		<div class="recurring-timezone">
			<span class="label">Default Timezone:</span>
			<span class="timezone"><?php echo esc_html( $EM_Event->start()->getTimezone()->getName() ); ?></span>
		</div>
		<?php endif; ?>

		<!-- All day text at the bottom -->
		<div class="recurring-all-day all-day"><?php echo esc_html__('Recurrences last all day.', 'events-manager'); ?></div>
	</div>
	<p class="recurring-summary-missing <?php if ( $EM_Event->event_id ) echo 'hidden'; ?>">
		<?php esc_html_e('Please enter dates and times for your first recurrence pattern in the recurrence section.', 'events-manager'); ?>
	</p>
</div>