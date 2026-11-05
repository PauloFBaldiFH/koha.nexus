<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var int $type */
/* @var EM_Event $EM_Event */
$can_cancel = $EM_Event->get_option('dbem_event_status_enabled') && array_key_exists( 0, EM_Event::get_active_statuses() );
?>
<div class="<?php em_template_classes('recurrence-set-reshedule-modal', 'modal'); ?> only-exclude-type">
	<div class="em-modal-popup">
		<header>
			<a class="em-close-modal"></a><!-- close modal -->
			<div class="em-modal-title">
				<?php esc_html_e('Modify Unavailable Dates?', 'events-manager'); ?>
			</div>
		</header>
		<div class="em-modal-content no-overflow">
			<p><strong><?php esc_html_e('You have chosen to add or edit your current unavailable dates for all recurrences. Please read this warning carefully!', 'events-manager'); ?></strong></p>
			<?php
				$consequence = $action = $can_cancel ? __('cancelled or deleted as per your settings below', 'events-manager') : __('deleted', 'events-manager');
			?>
			<p><?php echo esc_html( sprintf( __( 'If you modify the dates where recurrences will not occur on, any recurrences falling within these dates will be %s. New recurrences will be created if you remove unavailable dates which previously blocked recurrnce dates.', 'events-manager' ), $consequence ) ); ?></p>
			<div class="recurrence-reschedule-action reschedule-action-delete-cancel input">
				<label data-nostyle>
					<span class="reschedule-warning">
						<span class="em-icon em-icon-warning"></span>
						<?php
							if ( count( $EM_Event->get_recurrence_sets()->exclude ) === 0 ) {
								esc_html_e('You are adding unavailable dates.', 'events-manager');
							} else {
								esc_html_e('Modified unavailable dates.', 'events-manager');
							}
						?>
					</span>
     <?php  if( $EM_Event->get_option('dbem_event_status_enabled') && array_key_exists( 0, EM_Event::get_active_statuses() ) ) : ob_start(); ?>
					<select class="inline" name="recurrences[exclude_reschedule][action]" data-nostyle>
						<option value="cancel"><?php esc_html_e('Cancelled', 'events-manager') ?></option>
						<option value="delete"><?php esc_html_e( 'Deleted' ); ?></option>
					</select>
					<?php $action = ob_get_clean(); endif; ?>
					<?php echo sprintf( esc_html__('Recurrences that currently take place within new unavailable dates will be %s', 'events-manager'), $action ); ?>
					<button type="button" class="undo em-icon em-icon-undo em-tooltip" aria-label="<?php esc_html_e('Undo', 'events-manager'); ?>" data-nostyle></button>
					<input type="hidden" id="reschedule-exclude-nonce-<?php echo $id; ?>" name="recurrences[exclude_reschedule][nonce]'" value="<?php echo wp_create_nonce('reschedule_exclude_' . get_current_user_id()); ?>" disabled data-nonce>
				</label>
			</div>
		</div><!-- content -->
		<footer class="em-submit-section input">
			<div>
				<button type="button" class="button button-secondary reschedule-cancel"><?php esc_html_e('Cancel', 'events-manager'); ?></button>
				<button type="button" class="button button-primary reschedule-confirm"><?php esc_html_e('Confirm', 'events-manager'); ?></button>
			</div>
		</footer>

	</div><!-- modal -->
</div>