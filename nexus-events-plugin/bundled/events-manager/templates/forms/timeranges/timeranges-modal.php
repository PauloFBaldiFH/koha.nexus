<?php
// The following are included in the scope of this event date range picker
/* @var EM_Event $EM_Event */
/* @var int $id */
/* @var int $type */
/* @var int $i */
/* @var EM\Recurrences\Recurrence_Set $Recurrence_Set */
$archetype = EM\Archetypes::get( $EM_Event->event_archetype )['label_single'];
$can_cancel = $EM_Event->get_option('dbem_event_status_enabled') && array_key_exists( 0, EM_Event::get_active_statuses() );
?>
<div class="<?php em_template_classes('timeranges-editor-modal', 'modal'); ?>">
	<div class="em-modal-popup">
		<header>
			<a class="em-close-modal"></a><!-- close modal -->
			<div class="em-modal-title">
				<?php echo esc_html( sprintf( __('Reschedule %s Times?', 'events-manager'), $archetype ) ); ?>
			</div>
		</header>
		<div class="em-modal-content no-overflow">
			<p><strong><?php echo esc_html( sprintf( __('You have chosen to edit your %s times. Please read this warning carefully!', 'events-manager'), $archetype ) ); ?></strong></p>
			<?php
			$consequence = $action = $can_cancel ? __('cancelled or deleted as per your settings below', 'events-manager') : __('deleted', 'events-manager');
			?>
			<p><?php echo esc_html( sprintf( __( 'If you change time patterns such as start times or durations, any previously created timeslots falling outside the new settings will be %s.', 'events-manager' ), $consequence ) ); ?></p>
			<p><?php esc_html_e('If you extend or add more times, this will not affect previous timeslots.', 'events-manager'); ?></p>
			<div class="timeranges-edit-action input">
				<label data-nostyle>
					<?php  if( $can_cancel ) : ob_start(); ?>
						<select class="inline" name="em_timeranges_edit_action" data-nostyle>
							<option value="cancel"><?php esc_html_e( 'Cancelled', 'events-manager') ?></option>
							<option value="delete"><?php esc_html_e( 'Deleted' ); ?></option>
						</select>
						<?php $action = ob_get_clean(); endif; ?>
					<?php echo sprintf( esc_html__('Changed timeslots get %s', 'events-manager'), $action ); ?>
				</label>
			</div>
		</div><!-- content -->
		<footer class="em-submit-section input">
			<div>
				<button type="button" class="button button-secondary unlock-cancel"><?php esc_html_e('Cancel', 'events-manager'); ?></button>
				<button type="button" class="button button-primary unlock-confirm"><?php esc_html_e('Confirm', 'events-manager'); ?></button>
			</div>
		</footer>

	</div><!-- modal -->
</div>