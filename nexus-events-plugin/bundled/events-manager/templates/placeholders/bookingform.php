<?php  
/* 
 * This is where the booking form is generated.
 * For non-advanced users, It's SERIOUSLY NOT recommended you edit this form directly if avoidable, as you can change booking form settings in various less obtrusive and upgrade-safe ways:
 * - check your booking form options panel in the Booking Options tab in your settings.
 * - use CSS or jQuery to change the look of your booking forms
 * - edit the files in the forms/bookingform folder individually instead of this file, to make it more upgrade-safe
 * - hook into WP action/filters below to modify/generate information
 * Again, even if you're an advanced user, consider NOT editing this form and using other methods instead.
 */
/* @var EM_Event $EM_Event */
/* @var EM_Booking $EM_Booking booking intent */
/* @var bool $tickets_count */
/* @var bool $available_tickets_count */
/* @var bool $can_book */
/* @var bool $is_open whether there are any available tickets right now */
/* @var bool $is_free */
/* @var bool $show_tickets */
/* @var bool $id */
/* @var bool $already_booked */

global $EM_Notices;

// first hook before anything is checked
do_action('em_booking_form_start', $EM_Event); // do not delete
?>
<div class="<?php em_template_classes('event-booking-form'); ?> input" id="event-booking-form-<?php echo $id; ?>" data-id="<?php echo $id; ?>">
	<?php
		do_action('em_booking_form_top', $EM_Event); // do not delete
	?>
	<?php if( $already_booked && !em_get_option('dbem_bookings_double') ): //Double bookings not allowed ?>
		<?php do_action('em_booking_form_status_already_booked', $EM_Event); // do not delete ?>
	<?php elseif( !$EM_Event->event_rsvp ): //bookings not enabled ?>
		<?php do_action('em_booking_form_status_disabled', $EM_Event); // do not delete ?>
	<?php elseif( $EM_Event->event_active_status === 0 ): //event is cancelled ?>
		<?php do_action('em_booking_form_status_cancelled', $EM_Event); // do not delete ?>
	<?php elseif( $EM_Event->get_bookings()->get_available_spaces() <= 0 && !EM_Bookings::$disable_restrictions ): ?>
		<?php do_action('em_booking_form_status_full', $EM_Event); // do not delete ?>
	<?php elseif( !$is_open ): //event has started ?>
		<?php do_action('em_booking_form_status_closed', $EM_Event); // do not delete ?>
	<?php else: ?>
		<?php
			// output notices only if not in admin area, as it's already output via the admin_notices hook
			if( !did_action('admin_notices') ) {
				echo $EM_Notices;
			}
		?>
		<?php 
		if( !is_user_logged_in() && em_get_option('dbem_bookings_login_form') ){
			//User is not logged in, show login form (enabled on settings page)
			em_locate_template('forms/bookingform/login.php',true, array('EM_Event'=>$EM_Event));
		}
		?>
		<?php if( $tickets_count > 0) : ?>
			<?php //Tickets exist, so we show a booking form. ?>
			<form class="em-booking-form" name='booking-form' method='post' action='<?php echo apply_filters('em_booking_form_action_url',''); ?>#em-booking' id="em-booking-form-<?php echo $id; ?>" data-id="<?php echo $id; ?>" data-is-free="<?php echo $is_free ? 1:0; ?>" data-spaces="<?php echo esc_attr($EM_Booking->get_spaces()); ?>">
				<?php do_action('em_booking_form_header', $EM_Event, $EM_Booking); ?>
			 	<input type='hidden' name='action' value='booking_add'>
			 	<input type='hidden' name='event_id' value='<?php echo $EM_Event->event_id; ?>'>
			 	<input type='hidden' name='_wpnonce' value='<?php echo wp_create_nonce('booking_add'); ?>'>
				<?php echo $EM_Booking->output_intent_html(); ?>
				<?php
				/*
				 * BOOKING FORM TICKETS
				 */
				?>
				<?php do_action('em_booking_form_before_tickets_section', $EM_Event, $EM_Booking); // do not delete ?>
				<section class="em-booking-form-section-tickets" id="em-booking-form-section-tickets-<?php echo $id; ?>">
					<?php if( em_get_option('dbem_bookings_header_tickets') ): ?>
				    <h3 class="em-booking-section-title em-booking-form-tickets-title"><?php echo esc_html(em_get_option('dbem_bookings_header_tickets')); ?></h3>
					<?php endif; ?>
					<div class="em-booking-form-tickets em-booking-section">
					<?php
						// Tickets Form
						if( $show_tickets && ($can_book || em_get_option('dbem_bookings_tickets_show_loggedout')) ){ //show if more than 1 ticket, or if in forced ticket list view mode
							do_action('em_booking_form_before_tickets', $EM_Event, $EM_Booking); // do not delete
							//Show multiple tickets form to user, or single ticket list if settings enable this
							
							if ( $available_tickets_count == 1 && !em_get_option('dbem_bookings_tickets_single_form')) {
								$EM_Ticket = $EM_Event->get_bookings()->get_available_tickets()->get_first();
								em_locate_template('forms/bookingform/ticket-single.php', true, array('EM_Event' => $EM_Event, 'EM_Ticket' => $EM_Ticket, 'id' => $id));
							} else {
								//If logged out, can be allowed to see this in settings witout the register form
								em_locate_template('forms/bookingform/tickets-list.php', true, array('EM_Event' => $EM_Event, 'EM_Booking' => $EM_Booking));
							}
							do_action('em_booking_form_after_tickets', $EM_Event, $EM_Booking); // do not delete
							$show_tickets = false;
						}
					?>
					</div>
				</section>
				<?php do_action('em_booking_form_after_tickets_section', $EM_Event, $EM_Booking); // do not delete ?>
				
				<?php if( $can_book ): ?>
					<?php
					/*
					 * BOOKING FORM FIELDS
					 */
					?>
					<?php do_action('em_booking_form_before_registration_info', $EM_Event, $EM_Booking); // do not delete ?>
					<section class="em-booking-form-section-details" id="em-booking-form-section-details-<?php echo $id; ?>">
						<?php if( em_get_option('dbem_bookings_header_reg_info') ): ?>
						<h3 class="em-booking-section-title em-booking-form-details-title"><?php echo em_get_option('dbem_bookings_header_reg_info'); ?></h3>
						<?php endif; ?>
						<div class="em-booking-form-details em-booking-section">
							<?php if( !is_user_logged_in() && em_get_option('dbem_bookings_login_form') ): ?>
							<div class="em-login-trigger">
								<?php echo sprintf(esc_html__('Do you already have an account with us? %s','events-manager'), '<a href="#">'. esc_html__('Sign In', 'events-manager') .'</a>'); ?>
							</div>
							<?php endif; ?>
							<?php
								do_action('em_booking_form_before_user_details', $EM_Event, $EM_Booking); // do not delete
								if( has_action('em_booking_form_custom') ){
									//Pro Custom Booking Form. You can create your own custom form by hooking into this action and setting the option above to true
									do_action('em_booking_form_custom', $EM_Event, $EM_Booking); // do not delete
								}else{
									//If you just want to modify booking form fields, you could do so here
									em_locate_template('forms/bookingform/booking-fields.php',true, array('EM_Event'=>$EM_Event, 'EM_Booking' => $EM_Booking));
								}
								do_action('em_booking_form_after_user_details', $EM_Event, $EM_Booking); // do not delete
							?>
						</div>
					</section>
					<?php do_action('em_booking_form_after_registration_info', $EM_Event, $EM_Booking); // do not delete ?>
					
					<?php
					/*
					 * BOOKING SUMMARY
					 */
					if( em_get_option('dbem_bookings_summary') && (!$EM_Event->is_free() || em_get_option('dbem_bookings_summary_free')) ){
						do_action('em_booking_form_before_summary', $EM_Event, $EM_Booking); // do not delete
						?>
						<section class="em-booking-form-section-summary" id="em-booking-form-section-summary-<?php echo $id; ?>">
							<?php if( em_get_option('dbem_bookings_header_summary') ): ?>
							<h3 class="em-booking-section-title em-booking-form-summary-title"><?php echo em_get_option('dbem_bookings_header_summary'); ?></h3>
							<?php endif; ?>
							<?php do_action('em_booking_form_summary_header', $EM_Event, $EM_Booking); // do not delete ?>
							<div class="em-booking-form-summary em-booking-section no-booking">
								<?php
									em_locate_template('forms/bookingform/summary.php', true, array( 'EM_Event' => $EM_Event, 'EM_Booking' => $EM_Booking )); // no booking as of yet on load
								?>
							</div>
							<?php
								em_locate_template('forms/bookingform/summary-skeleton.php', true, array( 'EM_Event' => $EM_Event, 'EM_Booking' => $EM_Booking )); // no booking as of yet on load
								do_action('em_booking_form_summary_footer', $EM_Event, $EM_Booking); // do not delete
							?>
						</section>
						<?php do_action('em_booking_form_after_summary', $EM_Event, $EM_Booking); // do not delete
					}
					?>

					<?php
					/*
					 * BOOKING CONFIRMATION/PAYMENT
					 */
					?>
					<?php do_action('em_booking_form_before_confirm', $EM_Event, $EM_Booking); // do not delete	?>
					<section class="em-booking-form-section-confirm" id="em-booking-form-section-confirm-<?php echo $id; ?>">
						<?php if( em_get_option('dbem_bookings_header_confirm') ): ?>
						<h3 class="em-booking-section-title em-booking-form-confirm-title em-booking-form-confirm-title-paid <?php if ( $EM_Booking->get_spaces() == 0 || $EM_Booking->get_price() == 0 ) echo 'hidden'; ?>"><?php echo esc_html( em_get_option('dbem_bookings_header_confirm') ); ?></h3>
						<?php endif; ?>
						<?php if( em_get_option('dbem_bookings_header_confirm_free') ): ?>
						<h3 class="em-booking-section-title em-booking-form-confirm-title em-booking-form-confirm-title-free <?php if ( $EM_Booking->get_spaces() == 0 || $EM_Booking->get_price() > 0 ) echo 'hidden'; ?>"><?php echo esc_html( em_get_option('dbem_bookings_header_confirm_free') ); ?></h3>
						<?php endif; ?>
						<?php do_action('em_booking_form_confirm_header', $EM_Event, $EM_Booking); // do not delete ?>
						<?php if( has_action('em_booking_form_confirm') ): ?>
						<div class="em-booking-form-confirm em-booking-section">
							<?php do_action('em_booking_form_confirm', $EM_Event, $EM_Booking); // do not delete ?>
						</div>
						<?php endif; ?>
						<?php do_action('em_booking_form_confirm_footer', $EM_Event, $EM_Booking); // do not delete ?>
						<?php
						if( apply_filters('em_booking_form_show_button', true, $EM_Event ) ){
							em_locate_template('forms/bookingform/button.php', true, array( 'EM_Booking' => $EM_Booking, 'EM_Event' => $EM_Event ));
						}
						?>
					</section>
					<?php do_action('em_booking_form_after_confirm', $EM_Event, $EM_Booking); // do not delete ?>

				<?php else: ?>
					<p class="em-booking-form-details"><?php echo em_get_option('dbem_booking_feedback_log_in'); ?></p>
				<?php endif; ?>
				<?php do_action('em_booking_form_bottom', $EM_Event, $EM_Booking); // do not delete ?>
			</form>  
		<?php endif; ?>
	<?php endif; ?>
	<?php do_action('em_booking_form_after_form', $EM_Event, $EM_Booking); // do not delete ?>
</div>