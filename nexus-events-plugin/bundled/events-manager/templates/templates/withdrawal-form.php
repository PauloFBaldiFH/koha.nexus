<?php
/**
 * Front-end template for the EU right-of-withdrawal flow, output by the [em_withdrawal_form] shortcode.
 *
 * Override by copying to: yourtheme/plugins/events-manager/templates/withdrawal-form.php
 *
 * @var array $view Supplied by EM_Withdrawal::shortcode() — keys: step, labels, errors, reference, email, policy, action_url, and (per step) booking, token, bookings, access, statement, timestamp.
 */
if ( ! defined( 'ABSPATH' ) ) exit;
$labels = $view['labels'];
$step   = $view['step'];
$id     = rand(); // unique per-render view id, following the EM template convention
?>
<div class="<?php em_template_classes( 'booking-withdrawal' ); ?> em-withdrawal-step-<?php echo esc_attr( $step ); ?>" id="em-withdrawal-<?php echo $id; ?>" data-view-id="<?php echo $id; ?>">
	<h2 class="em-withdrawal-heading"><?php echo esc_html( $labels['heading'] ); ?></h2>

	<?php if ( ! empty( $view['errors'] ) ) : ?>
		<div class="em-withdrawal-errors" role="alert">
			<?php foreach ( $view['errors'] as $error ) : ?>
				<p class="em-booking-message em-booking-message-error"><?php echo esc_html( $error ); ?></p>
			<?php endforeach; ?>
		</div>
	<?php endif; ?>

	<?php if ( $step === 'request' ) : ?>
		<?php if ( ! empty( $view['policy'] ) ) : ?>
			<div class="em-withdrawal-policy"><?php echo wp_kses_post( wpautop( $view['policy'] ) ); ?></div>
		<?php endif; ?>
		<p class="em-withdrawal-intro"><?php esc_html_e( 'Enter your booking reference and email to withdraw. No account or login is required.', 'events-manager' ); ?></p>
		<form method="post" action="<?php echo esc_url( $view['action_url'] ); ?>" class="em-withdrawal-form input">
			<p class="em-withdrawal-field">
				<label for="em_wd_reference"><?php esc_html_e( 'Booking reference', 'events-manager' ); ?></label>
				<input type="text" name="em_wd_reference" id="em_wd_reference" value="<?php echo esc_attr( $view['reference'] ); ?>" autocomplete="off">
				<em class="em-withdrawal-hint"><?php esc_html_e( "Don't have it? Leave this blank and we'll email you a secure link to choose your booking.", 'events-manager' ); ?></em>
			</p>
			<p class="em-withdrawal-field">
				<label for="em_wd_email"><?php esc_html_e( 'Email address', 'events-manager' ); ?></label>
				<input type="email" name="em_wd_email" id="em_wd_email" value="<?php echo esc_attr( $view['email'] ); ?>" required>
			</p>
			<?php /* Honeypot: a CSS-hidden text field genuine users never see or fill. Bots that auto-complete every input trip it and we drop the request. It must be a real text input, not type="hidden" — bots skip hidden inputs, so a hidden field gives no signal. Stand-in until CAPTCHA support lands. */ ?>
			<div class="em-withdrawal-hp" style="position:absolute;left:-9999px;" aria-hidden="true">
				<label for="em_wd_hp"><?php esc_html_e( 'Leave this field empty', 'events-manager' ); ?></label>
				<input type="text" name="em_wd_hp" id="em_wd_hp" value="" tabindex="-1" autocomplete="off">
			</div>
			<div class="em-withdrawal-actions">
				<input type="hidden" name="em_wd_action" value="lookup">
				<?php wp_nonce_field( 'em_wd_lookup', 'em_wd_nonce' ); ?>
				<button type="submit" class="button button-primary em-withdrawal-submit"><?php echo esc_html( $labels['button'] ); ?></button>
			</div>
		</form>

	<?php elseif ( $step === 'confirm' && ! empty( $view['booking'] ) ) :
		$EM_Booking = $view['booking'];
		$EM_Event   = $EM_Booking->get_event();
		?>
		<p class="em-withdrawal-confirm-intro"><?php esc_html_e( 'Please confirm that you wish to withdraw from the following booking. This step submits your declaration of withdrawal.', 'events-manager' ); ?></p>
		<table class="em-withdrawal-summary">
			<tr><th><?php esc_html_e( 'Event', 'events-manager' ); ?></th><td><?php echo esc_html( $EM_Event ? $EM_Event->event_name : '' ); ?></td></tr>
			<tr><th><?php esc_html_e( 'Booking reference', 'events-manager' ); ?></th><td><?php echo esc_html( $EM_Booking->booking_id ); ?></td></tr>
			<tr><th><?php esc_html_e( 'Name', 'events-manager' ); ?></th><td><?php echo esc_html( $EM_Booking->get_person()->get_name() ); ?></td></tr>
		</table>
		<form method="post" action="<?php echo esc_url( $view['action_url'] ); ?>" class="em-withdrawal-form input">
			<p class="em-withdrawal-field">
				<label for="em_wd_reason"><?php esc_html_e( 'Reason (optional)', 'events-manager' ); ?></label>
				<textarea name="em_wd_reason" id="em_wd_reason" rows="3"></textarea>
			</p>
			<input type="hidden" name="em_wd_action" value="confirm">
			<input type="hidden" name="em_wd_booking_id" value="<?php echo esc_attr( $EM_Booking->booking_id ); ?>">
			<input type="hidden" name="em_wd_email" value="<?php echo esc_attr( $EM_Booking->get_person()->user_email ); ?>">
			<input type="hidden" name="em_wd_token" value="<?php echo esc_attr( $view['token'] ?? '' ); ?>">
			<?php wp_nonce_field( 'em_wd_confirm', 'em_wd_nonce' ); ?>
			<div class="em-withdrawal-actions">
				<button type="submit" class="button button-primary em-withdrawal-confirm"><?php echo esc_html( $labels['confirm'] ); ?></button>
				<a href="<?php echo esc_url( $view['action_url'] ); ?>" class="em-withdrawal-cancel-link"><?php esc_html_e( 'Cancel', 'events-manager' ); ?></a>
			</div>
		</form>

	<?php elseif ( $step === 'select' && ! empty( $view['bookings'] ) ) : ?>
		<p class="em-withdrawal-select-intro"><?php esc_html_e( 'Select the booking you wish to withdraw from.', 'events-manager' ); ?></p>
		<form method="post" action="<?php echo esc_url( $view['action_url'] ); ?>" class="em-withdrawal-form input">
			<p class="em-withdrawal-field">
				<label for="em_wd_booking_id"><?php esc_html_e( 'Booking', 'events-manager' ); ?></label>
				<select name="em_wd_booking_id" id="em_wd_booking_id">
					<?php foreach ( $view['bookings'] as $bid => $EM_Booking ) :
						$EM_Event = $EM_Booking->get_event(); ?>
						<option value="<?php echo esc_attr( $bid ); ?>"><?php echo esc_html( ( $EM_Event ? $EM_Event->event_name : __( 'Booking', 'events-manager' ) ) . ' (#' . $bid . ')' ); ?></option>
					<?php endforeach; ?>
				</select>
			</p>
			<input type="hidden" name="em_wd_action" value="select">
			<input type="hidden" name="em_wd_email" value="<?php echo esc_attr( $view['email'] ); ?>">
			<input type="hidden" name="em_wd_u" value="<?php echo esc_attr( $view['access']['u'] ?? '' ); ?>">
			<input type="hidden" name="em_wd_t" value="<?php echo esc_attr( $view['access']['t'] ?? '' ); ?>">
			<?php wp_nonce_field( 'em_wd_select', 'em_wd_nonce' ); ?>
			<div class="em-withdrawal-actions">
				<button type="submit" class="button button-primary em-withdrawal-submit"><?php echo esc_html( $labels['button'] ); ?></button>
			</div>
		</form>

	<?php elseif ( $step === 'sent' ) : ?>
		<p class="em-booking-message"><?php esc_html_e( 'If a booking exists for that email address, we have sent a link to manage your withdrawal. Please check your inbox.', 'events-manager' ); ?></p>

	<?php elseif ( $step === 'done' ) : ?>
		<div class="em-withdrawal-done">
			<p class="em-booking-message em-booking-message-success"><?php esc_html_e( 'Your declaration of withdrawal has been received.', 'events-manager' ); ?></p>
			<?php if ( ! empty( $view['timestamp'] ) ) : ?>
				<p class="em-withdrawal-receipt"><?php printf( esc_html__( 'Received on: %s', 'events-manager' ), esc_html( $view['timestamp'] ) ); ?></p>
			<?php endif; ?>
			<?php if ( ! empty( $view['statement'] ) ) : ?>
				<blockquote class="em-withdrawal-statement"><?php echo nl2br( esc_html( $view['statement'] ) ); ?></blockquote>
			<?php endif; ?>
			<p><?php esc_html_e( 'This confirms receipt of your declaration only. We will review it and contact you regarding any refund due.', 'events-manager' ); ?></p>
		</div>
	<?php endif; ?>
</div>
