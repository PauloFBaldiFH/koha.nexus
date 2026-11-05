<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var int $type */
/* @var int $i */
/* @var EM\Recurrences\Recurrence_Set $Recurrence_Set */
$can_cancel = em_get_option('dbem_event_status_enabled') && array_key_exists( 0, EM_Event::get_active_statuses() );
?>
<div class="<?php em_template_classes('recurrence-set-reshedule-modal', 'modal'); ?> only-include-type">
	<div class="em-modal-popup">
		<header>
			<a class="em-close-modal"></a><!-- close modal -->
			<div class="em-modal-title">
				<?php esc_html_e('Reschedule Recurrences?', 'events-manager'); ?>
			</div>
		</header>
		<div class="em-modal-content no-overflow">
			<p><strong><?php esc_html_e('You have chosen to edit your recurrence date ranges. Please read this warning carefully!', 'events-manager'); ?></strong></p>
			<p class="primary-recurrence"><?php esc_html_e( 'By editing your primary recurrence set, you will change all subsequent default values of your other recurrences.', 'events-manager' ); ?></p>
			<?php
			$consequence = $action = $can_cancel ? __('cancelled or deleted as per your settings below', 'events-manager') : __('deleted', 'events-manager');
			?>
			<p><?php echo esc_html( sprintf( __( 'If you shorten the date range or limit your recurrence dates, any recurrences falling outside the new date range will be %s.', 'events-manager' ), $consequence ) ); ?></p>
			<p><?php esc_html_e('If you extend or add more dates, the new recurrences will be added to your recurrence set without affecting previously created ones.', 'events-manager'); ?></p>
			<div class="recurrence-reschedule-action reschedule-action-delete-cancel input">
				<label data-nostyle>
					<span class="reschedule-warning"><span class="em-icon em-icon-warning"></span> <?php esc_html_e('Pending reschedule.', 'events-manager'); ?></span>
					<?php  if( $can_cancel ) : ob_start(); ?>
					<select class="inline" name="recurrences[<?php echo esc_attr($type); ?>][<?php echo esc_attr($i); ?>][reschedule][action]" data-nostyle>
						<option value="cancel"><?php esc_html_e('Cancelled', 'events-manager') ?></option>
						<option value="delete"><?php esc_html_e( 'Deleted' ); ?></option>
					</select>
					<?php $action = ob_get_clean(); endif; ?>
					<?php echo sprintf( esc_html__('Resheduled recurrences that fall outside new pattern will be %s', 'events-manager'), $action ); ?>
					<button type="button" class="undo em-icon em-icon-undo em-tooltip" aria-label="<?php esc_html_e('Undo', 'events-manager'); ?>" data-nostyle></button>
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