<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var EM_Event $EM_Event */
?>
<?php if( em_get_option('dbem_timezone_enabled') || $EM_Event->event_timezone !== em_get_option('timezone_string') ): ?>
	<p class="em-timezone">
		<label for="event-timezone-<?php echo $id; ?>"><?php esc_html_e('Timezone', 'events-manager'); ?></label>
		<select id="event-timezone-<?php echo $id; ?>" name="event_timezone" class="em-selectize event_timezone">
			<?php echo wp_timezone_choice( $EM_Event->get_timezone()->getValue(), get_user_locale() ); ?>
		</select>
	</p>
<?php endif; ?>