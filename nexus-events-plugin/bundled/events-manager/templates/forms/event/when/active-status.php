<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var EM_Event $EM_Event */
?>
<?php do_action('em_event_form_active_status_before', $EM_Event, $id); ?>
<div class="em-input-field em-input-field-select em-active-status">
	<?php do_action('em_event_form_active_status_header', $EM_Event, $id); ?>
	<label><?php esc_html_e('Event Status', 'events-manager'); ?></label>
	<select name="event_active_status" class="em-event-active-status event_active_status" id="em-event-active-status-<?php echo esc_attr($id); ?>">
		<?php foreach ( EM_Event::get_active_statuses() as $status => $label ): ?>
		<option value="<?php echo esc_attr($status); ?>" <?php selected($status, $EM_Event->event_active_status); ?>><?php echo esc_html($label); ?></option>
		<?php endforeach; ?>
	</select>
	<?php do_action('em_event_form_active_status_footer', $EM_Event, $id); ?>
</div>
<?php do_action('em_event_form_active_status_after', $EM_Event, $id); ?>