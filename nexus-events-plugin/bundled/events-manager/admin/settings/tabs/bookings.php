<?php if( !function_exists('current_user_can') || !current_user_can('manage_options') ) return; ?>
<!-- BOOKING OPTIONS -->
<div class="em-menu-bookings em-menu-group"  <?php if( !defined('EM_SETTINGS_TABS') || !EM_SETTINGS_TABS) : ?>style="display:none;"<?php endif; ?>>
	
	<?php do_action('em_options_page_bookings_general_before'); ?>
	<div  class="postbox " id="em-opt-bookings-general" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php echo sprintf(__( '%s Options', 'events-manager'),__('General','events-manager')); ?> </span></h3>
	<div class="inside">
		<table class='form-table'>
			<?php
			do_action('em_options_page_bookings_general_top');
			em_options_radio_binary ( __( 'Allow guest bookings?', 'events-manager'), 'dbem_bookings_anonymous', __( 'If enabled, guest visitors can supply an email address and a user account will automatically be created for them along with their booking. They will be also be able to log back in with that newly created account.', 'events-manager') );
			$gateway_approval = '<br><strong>' . __( 'This setting will not apply to bookings using payment gateways, see individual gateways for approval settings.', 'events-manager') . '</strong>';
			em_options_radio_binary ( __( 'Approval Required?', 'events-manager'), 'dbem_bookings_approval', __( 'Bookings will not be confirmed until the event administrator approves it.', 'events-manager').' '. $gateway_approval);
			em_options_radio_binary ( __( 'Reserved unconfirmed spaces?', 'events-manager'), 'dbem_bookings_approval_reserved', __( 'By default, event spaces become unavailable once there are enough CONFIRMED bookings. To reserve spaces even if unapproved, choose yes.', 'events-manager').' '. $gateway_approval );
			em_options_radio_binary ( __( 'Allow overbooking when approving?', 'events-manager'), 'dbem_bookings_approval_overbooking', __( 'If you get a lot of pending bookings and you decide to allow more bookings than spaces allow, setting this to yes will allow you to override the event space limit when manually approving.', 'events-manager') );
			em_options_radio_binary ( __( 'Allow double bookings?', 'events-manager'), 'dbem_bookings_double', __( 'If enabled, users can book an event more than once.', 'events-manager') );
			do_action('em_options_page_bookings_cancellations_before');
			?>
			<tr class="em-header"><td colspan='2'><h4><?php echo sprintf(__( '%s Options', 'events-manager'),__('Cancellation','events-manager')); ?></h4></td></tr>
			<?php
			$uncancel_desc = __( 'Once cancelled, you can allow susers to re-instate their booking, provided there are still enough spaces.', 'events-manager');
			$uncancel_desc = __( 'Bookings that are uncancelled are returned to their previous state (if available), the %1$s PHP constant value or if previous options are not available then pending/approved according to your booking approval settings.', 'events-manager');
			$uncancel_desc = sprintf( $uncancel_desc, "<code>EM_BOOKINGS_UNCANCEL_STATUS</code>");
			em_options_radio_binary ( __( 'Can users cancel their booking?', 'events-manager'), 'dbem_bookings_user_cancellation', __( 'If enabled, users can cancel their bookings themselves from their bookings page.', 'events-manager'), '', '#dbem_bookings_user_cancellation_time_row, #dbem_bookings_user_uncancellation_row, .booking-cancellation' );
			em_options_radio_binary ( __( 'Can users uncancel their booking?', 'events-manager'), 'dbem_bookings_user_uncancellation', $uncancel_desc );
			$cancellation_hours_desc = __( 'Enter the number of hours before an event starts for when users can cancel a booking. Leave blank for the start time of the event.', 'events-manager');
			$cancellation_hours_desc_2 = __('%s are also accepted, for example %s equals 1 month and 12 hours before the event starts.', 'events-manager');
			$cancellation_hours_desc .= ' '. sprintf($cancellation_hours_desc_2, '<a href="https://www.php.net/manual/en/dateinterval.construct.php" target="_blank">'.esc_html_x('PHP date intevals', 'Refer to PHP docs for translation.', 'events-manager').'</a>', '<code>P1MT12H</code>');
			if( (!defined('EM_DIASBLE_EMP_HINTS') || EM_DIASBLE_EMP_HINTS) && (!defined('EMP_VERSION') || version_compare('3.0.3', get_option('em_pro_version'), '>') ) ){
				$pro_notice = sprintf(__('Need event-specific cancellation settings or support for hours after an event started? This is included in our %s.', 'events-manager'), '<a href="https://wp-events-plugin.com/features/">'.esc_html__('Pro Add-On', 'events-manager') . '</a>');
				$cancellation_hours_desc .= '<br>'. $pro_notice;
			}elseif( defined('EMP_VERSION') && version_compare('3.0.3', get_option('em_pro_version'), '<=') ){
				$pro_notice = esc_html__('Add a negative number or minus sign to the start of the date interval to allow cancellations after events have started.', 'events-manager');
				$cancellation_hours_desc .= ' ' . $pro_notice;
			}
			em_options_input_text ( __( 'How long before an event can users cancel?', 'events-manager'), 'dbem_bookings_user_cancellation_time',  $cancellation_hours_desc);
			do_action('em_options_page_bookings_cancellations_after');
			do_action('em_options_page_bookings_general_bottom');
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	<?php do_action('em_options_page_bookings_general_after'); ?>
	
	<div  class="postbox " id="em-opt-pricing-options" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php echo sprintf(__( '%s Options', 'events-manager'),__('Pricing','events-manager')); ?> </span></h3>
	<div class="inside">
		<table class='form-table'>
			<?php
			/* Tax & Currency */
			em_options_select ( __( 'Currency', 'events-manager'), 'dbem_bookings_currency', em_get_currencies()->names, __( 'Choose your currency for displaying event pricing.', 'events-manager') );
			em_options_input_text ( __( 'Thousands Separator', 'events-manager'), 'dbem_bookings_currency_thousands_sep', '<code>'.get_option('dbem_bookings_currency_thousands_sep')." = ".em_get_currency_symbol().'100<strong>'.get_option('dbem_bookings_currency_thousands_sep').'</strong>000<strong>'.get_option('dbem_bookings_currency_decimal_point').'</strong>00</code>' );
			em_options_input_text ( __( 'Decimal Point', 'events-manager'), 'dbem_bookings_currency_decimal_point', '<code>'.get_option('dbem_bookings_currency_decimal_point')." = ".em_get_currency_symbol().'100<strong>'.get_option('dbem_bookings_currency_decimal_point').'</strong>00</code>' );
			em_options_input_text ( __( 'Currency Format', 'events-manager'), 'dbem_bookings_currency_format', __('Choose how prices are displayed. <code>@</code> will be replaced by the currency symbol, and <code>#</code> will be replaced by the number.','events-manager').' <code>'.get_option('dbem_bookings_currency_format')." = ".em_get_currency_formatted('10000000').'</code>');
			em_options_input_text ( __( 'Tax Rate', 'events-manager'), 'dbem_bookings_tax', __( 'Add a tax rate to your ticket prices (entering 10 will add 10% to the ticket price).', 'events-manager') );
			em_options_radio_binary ( __( 'Add tax to ticket price?', 'events-manager'), 'dbem_bookings_tax_auto_add', __( 'When displaying ticket prices and booking totals, include the tax automatically?', 'events-manager') );
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	
	<div  class="postbox " id="em-opt-booking-feedbacks" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e( 'Customize Feedback Messages', 'events-manager'); ?> </span></h3>
	<div class="inside">
		<p><?php _e('Below you will find texts that will be displayed to users in various areas during the bookings process, particularly on booking forms.','events-manager'); ?></p>
		<table class='form-table'>
			<tr class="em-header"><td colspan='2'><h4><?php _e('My Bookings messages','events-manager') ?></h4></td></tr>
			<?php
			em_options_input_text ( __( 'Booking Cancelled', 'events-manager'), 'dbem_booking_feedback_cancelled', __( 'When a user cancels their booking, this message will be displayed confirming the cancellation.', 'events-manager') );
			em_options_input_text ( __( 'Booking Cancellation Warning', 'events-manager'), 'dbem_booking_warning_cancel', __( 'When a user chooses to cancel a booking, this warning is displayed for them to confirm.', 'events-manager') );
			?>
			<tr class="em-header"><td colspan='2'><h4><?php _e('Booking form texts/messages','events-manager') ?></h4></td></tr>
			<?php
			em_options_input_text ( __( 'Bookings disabled', 'events-manager'), 'dbem_bookings_form_msg_disabled', __( 'An event with no bookings.', 'events-manager') );
			em_options_input_text ( __( 'Bookings closed', 'events-manager'), 'dbem_bookings_form_msg_closed', __( 'Bookings have closed (e.g. event has started).', 'events-manager') );
			em_options_input_text ( __( 'Event cancelled ', 'events-manager'), 'dbem_bookings_form_msg_cancelled', '');
			em_options_input_text ( __( 'Fully booked', 'events-manager'), 'dbem_bookings_form_msg_full', __( 'Event is fully booked.', 'events-manager') );
			em_options_input_text ( __( 'Already attending', 'events-manager'), 'dbem_bookings_form_msg_attending', __( 'If already attending and double bookings are disabled, this message will be displayed, followed by a link to the users booking page.', 'events-manager') );
			em_options_input_text ( __( 'Manage bookings link text', 'events-manager'), 'dbem_bookings_form_msg_bookings_link', __( 'Link text used for link to user bookings.', 'events-manager') );
			?>
			<tr class="em-header"><td colspan='2'><h4><?php _e('Booking form feedback messages','events-manager') ?></h4></td></tr>
			<tr><td colspan='2'><?php _e('When a booking is made by a user, a feedback message is shown depending on the result, which can be customized below.','events-manager'); ?></td></tr>
			<?php
			em_options_input_text ( __( 'Successful booking', 'events-manager'), 'dbem_booking_feedback', __( 'When a booking is registered and confirmed.', 'events-manager') );
			em_options_input_text ( __( 'Successful pending booking', 'events-manager'), 'dbem_booking_feedback_pending', __( 'When a booking is registered but pending.', 'events-manager') );
			em_options_input_text ( __( 'Not enough spaces', 'events-manager'), 'dbem_booking_feedback_full', __( 'When a booking cannot be made due to lack of spaces.', 'events-manager') );
			em_options_input_text ( __( 'Errors', 'events-manager'), 'dbem_booking_feedback_error', __( 'When a booking cannot be made due to an error when filling the form. Below this, there will be a dynamic list of errors.', 'events-manager') );
			em_options_input_text ( __( 'Email Exists', 'events-manager'), 'dbem_booking_feedback_email_exists', __( 'When a guest tries to book using an email registered with a user account.', 'events-manager') );
			em_options_input_text ( __( 'User must log in', 'events-manager'), 'dbem_booking_feedback_log_in', __( 'When a user must log in before making a booking.', 'events-manager') );
			em_options_input_text ( __( 'Error mailing user', 'events-manager'), 'dbem_booking_feedback_nomail', __( 'If a booking is made and an email cannot be sent, this is added to the success message.', 'events-manager') );
			em_options_input_text ( __( 'Already booked', 'events-manager'), 'dbem_booking_feedback_already_booked', __( 'If the user made a previous booking and cannot double-book.', 'events-manager') );
			em_options_input_text ( __( 'No spaces booked', 'events-manager'), 'dbem_booking_feedback_min_space', __( 'If the user tries to make a booking without requesting any spaces.', 'events-manager') );$notice_full = __('Sold Out', 'events-manager');
			em_options_input_text ( __( 'Maximum spaces per booking', 'events-manager'), 'dbem_booking_feedback_spaces_limit', __( 'If the user tries to make a booking with spaces that exceeds the maximum number of spaces per booking.', 'events-manager').' '. __('%d will be replaced by a number.','events-manager') );
			?>
			<tr class="em-header"><td colspan='2'><h4><?php _e('Booking button feedback messages','events-manager') ?></h4></td></tr>
			<tr><td colspan='2'><?php echo sprintf(__('With the %s placeholder, the below texts will be used.','events-manager'),'<code>#_BOOKINGBUTTON</code>'); ?></td></tr>
			<?php
			em_options_input_text ( __( 'User can book', 'events-manager'), 'dbem_booking_button_msg_book', '');
			em_options_input_text ( __( 'Booking in progress', 'events-manager'), 'dbem_booking_button_msg_booking', '');
			em_options_input_text ( __( 'Booking complete', 'events-manager'), 'dbem_booking_button_msg_booked', '');
			em_options_input_text ( __( 'Booking already made', 'events-manager'), 'dbem_booking_button_msg_already_booked', '');
			em_options_input_text ( __( 'Booking error', 'events-manager'), 'dbem_booking_button_msg_error', '');
			em_options_input_text ( __( 'Event fully booked', 'events-manager'), 'dbem_booking_button_msg_full', '');
			em_options_input_text ( __( 'Event cancelled', 'events-manager'), 'dbem_booking_button_msg_event_cancelled', '');
			em_options_input_text ( __( 'Bookings closed', 'events-manager'), 'dbem_booking_button_msg_closed', '');
			em_options_input_text ( __( 'Cancel', 'events-manager'), 'dbem_booking_button_msg_cancel', '');
			em_options_input_text ( __( 'Cancelation in progress', 'events-manager'), 'dbem_booking_button_msg_canceling', '');
			em_options_input_text ( __( 'Cancelation complete', 'events-manager'), 'dbem_booking_button_msg_cancelled', '');
			em_options_input_text ( __( 'Cancelation error', 'events-manager'), 'dbem_booking_button_msg_cancel_error', '');
			
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	
	<div  class="postbox " id="em-opt-booking-form-options" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php echo sprintf(__( '%s Options', 'events-manager'),__('Booking Form','events-manager')); ?> </span></h3>
	<div class="inside">
		<table class='form-table'>
			<?php
			em_options_radio_binary ( __( 'Display login form?', 'events-manager'), 'dbem_bookings_login_form', __( 'Choose whether or not to display a login form in the booking form area to remind your members to log in before booking.', 'events-manager') );
			em_options_radio_binary ( __( 'Hide form until tickets selected?', 'events-manager'), 'dbem_bookings_form_hide_dynamic', __( 'If enabled, the entire booking form will show once a space is selected, or if an ticket is already pre-selected with minimum spaces.', 'events-manager') );
			em_options_select ( __( 'Recurring Events Picker', 'events-manager'), 'dbem_recurrence_picker', ['select' => __('Dropdown Selection', 'events-manager'), 'calendar' => __('Calendar Selection', 'events-manager')], __( 'Recurring events have a picker in order to load the right booking form, choose your picker style for your booking forms.', 'events-manager') );
			em_options_input_text ( __( 'Submit button text', 'events-manager'), 'dbem_bookings_submit_button', sprintf(__( 'The text used by the submit button. To use an image instead, enter the full url starting with %s or %s.', 'events-manager'), '<code>http://</code>','<code>https://</code>') ). ' ' . __( 'This button text would be shown for a free booking', 'events-manager');
			em_options_input_text ( __( 'Submit button text (payment)', 'events-manager'), 'dbem_bookings_submit_button_paid', sprintf(__( 'The text shown when a booking is not free, %s will be replaced by the total amount due.', 'events-manager'), '<code>%s</code>'). ' <strong>' . __( 'This text will be shown only if the default (free) button is not an image.', 'events-manager') . '</strong>' );
			em_options_input_text ( __( 'Submit button text (processing)', 'events-manager'), 'dbem_bookings_submit_button_processing', sprintf(__( 'The text shown when a booking is being submitted, %s will be replaced by the total amount due.', 'events-manager'), '<code>%s</code>'). ' <strong>' . __( 'This text will be shown only if the default (free) button is not an image.', 'events-manager') . '</strong>' );
			?>
			<tr class="em-header"><td colspan='2'><h4><?php esc_html_e('Booking Summary','events-manager') ?></h4></td></tr>
			<tr><td colspan='2'><?php echo esc_html__('When selecting tickets on a booking form, the price will dynamically be broken down in a summary before the booking confirmation button.','events-manager'); ?></td></tr>
			<?php
			em_options_radio_binary ( __( 'Display booking summary?', 'events-manager'), 'dbem_bookings_summary', __( 'Displays a booking summary including itemized subtotals, taxes, discounts, surcharges and totals where applicable.', 'events-manager'), '', '.em-booking-summmary-options, #dbem_bookings_header_summary_row' );
			?>
			<tbody class="em-booking-summmary-options">
				<?php
				em_options_radio_binary ( __( 'Display free booking summary?', 'events-manager'), 'dbem_bookings_summary_free', __( 'Display the booking summary if the event is free. If there are any available tickets worth more than 0 then the event is not considered free.', 'events-manager') );
				em_options_input_text ( __( 'Booking summary default text', 'events-manager'), 'dbem_bookings_summary_message', __( 'When no tickets are selected, this text will appear in place of a booking summary, prompting users to select a ticket.', 'events-manager'));
				em_options_radio_binary ( __( 'Display taxes separately?', 'events-manager'), 'dbem_bookings_summary_taxes_itemized', __( 'Display ticket prices without tax and calculate the tax total separately.', 'events-manager'), '', '#dbem_bookings_summary_subtotal_exc_taxes_row', true );
				em_options_radio_binary ( __( 'Exclude taxes from subtotal?', 'events-manager'), 'dbem_bookings_summary_subtotal_exc_taxes', __( 'Subtotals will exclude taxes and display taxes separately.', 'events-manager') );
				em_options_radio_binary ( __( 'Display subsection titles?', 'events-manager'), 'dbem_bookings_summary_subsections', __( 'Display subsection titles above groups of line items, such as taxes, discounts and surcharges.', 'events-manager') );
				?>
			</tbody>
			<tr class="em-header"><td colspan='2'><h4><?php esc_html_e('Booking form section headers','events-manager') ?></h4></td></tr>
			<tr><td colspan='2'><?php echo esc_html__('These headings appear above sections of the booking form. Leave blank for no heading.','events-manager'); ?></td></tr>
			<?php
			em_options_input_text ( esc_html__('Tickets', 'events-manager'), 'dbem_bookings_header_tickets' );
			em_options_input_text ( esc_html__('Registration Information', 'events-manager'), 'dbem_bookings_header_reg_info' );
			em_options_input_text ( esc_html__('Booking Summary', 'events-manager'), 'dbem_bookings_header_summary' );
			$paid_description = esc_html__('The default value is blank so that the booking submission button appears just below the %s section.', 'events-manager');
			em_options_input_text ( esc_html__('Payment and Confirmation', 'events-manager'), 'dbem_bookings_header_confirm', sprintf($paid_description, '<em>'.esc_html__('Booking Summary', 'events-manager').'</em>' ) );
			$free_description = esc_html__('If the booking is free, this will be displayed instead of the %s heading.', 'events-manager') . ' ' . esc_html__('The default value is blank so that the booking submission button appears just below the %s section.', 'events-manager');
			$free_description = sprintf($free_description, '<em>'.esc_html__('Payment and Confirmation', 'events-manager').'</em>', '<em>'.esc_html__('Booking Summary', 'events-manager').'</em>' );
			em_options_input_text ( esc_html__('Booking Confirmation', 'events-manager'), 'dbem_bookings_header_confirm_free', $free_description );
			?>
			<tr class="em-header"><td colspan='2'><h4><?php esc_html_e('Timeslots','events-manager') ?></h4></td></tr>
			<tr><td colspan='2'><?php echo esc_html__('Choose how timeslots are listed in booking forms for recurring events and events with multiple timeslots.','events-manager'); ?></td></tr>
			<?php
			em_options_radio_binary ( __( 'Show fully booked timeslots?', 'events-manager'), 'dbem_bookings_timeslots_show_unavailable', __( 'If enabled, fully booked timeslots remain visible but cannot be selected.', 'events-manager') );
			em_options_radio_binary ( __( 'Show spaces left?', 'events-manager'), 'dbem_bookings_timeslots_show_spaces', __( 'Display the number of available spaces (or booking status if full/closed/cancelled) in each timeslot button or dropdown option.', 'events-manager') );
			em_options_radio_binary ( __( 'Show dates in timeslots?', 'events-manager'), 'dbem_bookings_timeslots_show_dates', __( 'Display the timeslot date as well as the time when viewing a specific calendar day.', 'events-manager'), '' );
			em_options_input_text ( __( 'Timeslot date format', 'events-manager'), 'dbem_bookings_timeslots_date_format', sprintf( __( 'Optional PHP date format for timeslot dates. Leave blank to use the default event date format. Example: %s', 'events-manager'), '<code>j F Y</code>' ) );
			em_options_input_text ( __( 'Timeslot time format', 'events-manager'), 'dbem_bookings_timeslots_time_format', sprintf( __( 'Optional PHP date format for timeslot times. Leave blank to use the default event time format. Example: %s', 'events-manager'), '<code>g:i a</code>' ) );
			em_options_radio_binary ( __( 'Show upcoming timeslots?', 'events-manager'), 'dbem_bookings_timeslots_show_upcoming', __( 'Show upcoming timeslots on the initial booking form load before a visitor chooses a calendar date.', 'events-manager'), '' );
			em_options_input_text ( __( 'Upcoming timeslot limit', 'events-manager'), 'dbem_bookings_timeslots_upcoming_limit', __( 'Maximum number of upcoming timeslots to show on initial page load. Enter 0 to show all upcoming timeslots.', 'events-manager') );

			do_action('em_options_booking_form_options');
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	
	<div  class="postbox " id="em-opt-ticket-options" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php echo sprintf(__( '%s Options', 'events-manager'),__('Ticket','events-manager')); ?> </span></h3>
	<div class="inside">
		<table class='form-table'>
			<?php
			em_options_radio_binary ( __( 'Single ticket mode?', 'events-manager'), 'dbem_bookings_tickets_single', __( 'In single ticket mode, users can only create one ticket per event (and will not see options to add more tickets).', 'events-manager') );
			em_options_radio_binary ( __( 'Show ticket table in single ticket mode?', 'events-manager'), 'dbem_bookings_tickets_single_form', __( 'If you prefer a ticket table like with multiple tickets, even for single ticket events, enable this.', 'events-manager') );
			em_options_radio_binary ( __( 'Show unavailable tickets?', 'events-manager'), 'dbem_bookings_tickets_show_unavailable', __( 'You can choose whether or not to show unavailable tickets to visitors.', 'events-manager') );
			em_options_radio_binary ( __( 'Show member-only tickets?', 'events-manager'), 'dbem_bookings_tickets_show_member_tickets', sprintf(__('%s must be set to yes for this to work.', 'events-manager'), '<strong>'.__( 'Show unavailable tickets?', 'events-manager').'</strong>').' '.__( 'If there are member-only tickets, you can choose whether or not to show these tickets to guests.','events-manager') );
			
			em_options_radio_binary ( __( 'Show multiple tickets if logged out?', 'events-manager'), 'dbem_bookings_tickets_show_loggedout', __( 'If guests cannot make bookings, they will be asked to register in order to book. However, enabling this will still show available tickets.', 'events-manager') );
			em_options_radio_binary ( __( 'Enable custom ticket ordering?', 'events-manager'), 'dbem_bookings_tickets_ordering', __( 'When enabled, users can custom-order their tickets using drag and drop. If enabled, saved ordering supercedes the default ticket ordering below.', 'events-manager') );
			$ticket_orders = apply_filters('em_tickets_orderby_options', array(
				'ticket_price DESC, ticket_name ASC'=>__('Ticket Price (Descending)','events-manager'),
				'ticket_price ASC, ticket_name ASC'=>__('Ticket Price (Ascending)','events-manager'),
				'ticket_name ASC, ticket_price DESC'=>__('Ticket Name (Ascending)','events-manager'),
				'ticket_name DESC, ticket_price DESC'=>__('Ticket Name (Descending)','events-manager')
			));
			em_options_select ( __( 'Order Tickets By', 'events-manager'), 'dbem_bookings_tickets_orderby', $ticket_orders, __( 'Choose which order your tickets appear.', 'events-manager') );
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->


	<div  class="postbox " id="em-opt-rsvp" >
		<div class="handlediv" title="<?php esc_html_e('Click to toggle', 'events-manager'); ?>"><br /></div><h3><?php esc_html_e( 'Booking RSVP', 'events-manager' ); ?></h3>
		<div class="inside">
			<table class='form-table'>
				<tr class="em-boxheader">
					<td colspan='2'>
						<p>
							<?php _e( 'Once a booking has been made, you can also allow a user to RSVP that booking, which confirms their intention of attending. This can be independent of the booking status itself.', 'events-manager' );  ?>
						</p>
					</td>
				</tr>
				<?php
					em_options_radio_binary ( sprintf(_x( 'Enable %s?', 'Enable a feature in settings page', 'events-manager' ), __('Booking RSVP','events-manager')), 'dbem_bookings_rsvp', '', '', '.rsvp-options');
				?>
				<tbody class="rsvp-options">
					<?php
					em_options_radio_binary( __( 'Allow Maybe?', 'events-manager' ), 'dbem_bookings_rsvp_maybe', __("Allow users to respond with a 'Maybe' status rather than Attending or Not Attending", 'events-manager') );
					?>
					<tr class="em-header"><td colspan='2'><h4><?php echo sprintf(__('%s Pages','events-manager'),__('My Bookings','events-manager')); ?></h4></td></tr>
					<tr><td colspan='2'><?php echo esc_html__('Choose what to show users on their booking management page.','events-manager'); ?></td></tr>
					<?php
					em_options_radio_binary( __( 'Display Status', 'events-manager' ), 'dbem_bookings_rsvp_my_bookings' );
					em_options_radio_binary( __( 'Allow RSVP Actions', 'events-manager' ), 'dbem_bookings_rsvp_my_bookings_buttons' );
					em_options_radio_binary( __( 'RSVP Modifications', 'events-manager' ), 'dbem_bookings_rsvp_can_change', esc_html__('Can attendees change their RSVP status? You can choose whether they can uncancel an RSVP below as well.', 'events-manager') );
					?>

					<tr class="em-header"><td colspan='2'><h4><?php echo sprintf(__('%s Pages','events-manager'),__('RSVP Syncing','events-manager')); ?></h4></td></tr>
					<tr><td colspan='2'><?php echo esc_html__( 'If syncing is turned on for a booking status below, when a user RSVPs, the booking status will automatically be changed along with RSVP status.', 'events-manager' ); ?></td></tr>
					<?php
					em_options_radio_binary( __( 'Cancellations', 'events-manager' ), 'dbem_bookings_rsvp_sync_cancel' );
					em_options_radio_binary( __( 'Confirmations', 'events-manager' ), 'dbem_bookings_rsvp_sync_confirm', esc_html__('In this case, a user can confirm their own booking even if the booking is pending.', 'events-manager') );
					/*
						em_options_radio_binary( __( 'Allow Un-Cancel?', 'events-manager' ), 'dbem_bookings_rsvp_uncancel', __("Allow users to change their minds from 'Not Attending' to 'Attending' if event still has availability, changing their booking status to 'Confirmed' or 'Pending' according to your settings.", 'events-manager') );
					*/
					?>
				</tbody>
				<?php do_action('em_options_bookings_rsvp_footer'); ?>
				<?php echo $save_button; ?>
			</table>
		</div> <!-- . inside -->
	</div> <!-- .postbox -->
	
	<div  class="postbox " id="em-opt-no-user-bookings" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e('No-User Booking Mode','events-manager'); ?> </span></h3>
	<div class="inside">
		<table class='form-table'>
			<tr><td colspan='2'>
				<p><?php _e('The option below allows you to disable user accounts, yet you will still see the supplied personal information for each booking.','events-manager'); ?></p>
				<p><?php _e('By default, when a booking is made by a user, this booking is tied to a user account, if the user is not registered nor logged in and guest bookings are enabled, an account will be created for them.','events-manager'); ?></p>
				<p><?php _e('Users with accounts (which would be created by other means when this mode is enabled) will still be able to log in and make bookings linked to their account as normal.','events-manager'); ?></p>
				<p><?php _e('<strong>Warning : </strong> Various features afforded to users with an account will not be available, e.g. viewing bookings. Once you enable this and select a user, modifying these values will prevent older non-user bookings from displaying the correct information.','events-manager'); ?></p>
			</td></tr>
			<?php
			em_options_radio_binary ( __( 'Enable No-User Booking Mode?', 'events-manager'), 'dbem_bookings_registration_disable', __( 'This disables user registrations for bookings.', 'events-manager') );
			em_options_radio_binary ( __( 'Allow bookings with registered emails?', 'events-manager'), 'dbem_bookings_registration_disable_user_emails', __( 'By default, if a guest tries to book an event using the email of a user account on your site they will be asked to log in, selecting yes will bypass this security measure.', 'events-manager').'<br />'.__('<strong>Warning : </strong> By enabling this, registered users will not be able to see bookings they make as guests in their "My Bookings" page.','events-manager') );
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->

	<div  class="postbox " id="em-opt-pricing-options" >
		<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php echo sprintf(__( '%s Options', 'events-manager'),__('Booking Chart','events-manager')); ?> </span></h3>
		<div class="inside">
			<table class='form-table'>
				<?php
				em_options_radio_binary ( __( 'Display on WP Dashboard', 'events-manager'), 'dbem_booking_charts_wpdashboard');
				em_options_radio_binary ( __( 'Display on Frontend', 'events-manager'), 'dbem_booking_charts_frontend');
				?>
				<tbody class="em-opt-chart-options-settings hidden">
				<?php
				em_options_radio_binary ( __( 'Display on bookings dashboard', 'events-manager'), 'dbem_booking_charts_dashboard');
				em_options_radio_binary ( __( 'Display on event bookings admin', 'events-manager'), 'dbem_booking_charts_event');
				?>
				</tbody>
				<?php
				echo $save_button;
				?>
			</table>
			<script>
				document.addEventListener('DOMContentLoaded', function(){
					document.querySelectorAll('[name="dbem_booking_charts_wpdashboard"],[name="dbem_booking_charts_frontend"]').forEach( function(el) {
						el.addEventListener('click', function(){
							if ( el.value === '1' ) {
								document.querySelector('.em-opt-chart-options-settings').classList.remove('hidden');
							} else {
								// check if there are any yes checked
								let checked = document.querySelectorAll('[name="dbem_booking_charts_wpdashboard"][value="1"]:checked,[name="dbem_booking_charts_frontend"][value="1"]:checked');
								if ( checked && checked.length === 0 ) {
									document.querySelector('.em-opt-chart-options-settings').classList.add('hidden');
								}
							}
						});
						let checked = document.querySelectorAll('[name="dbem_booking_charts_wpdashboard"][value="1"]:checked,[name="dbem_booking_charts_frontend"][value="1"]:checked');
						if ( checked && checked.length > 0 ) {
							document.querySelector('.em-opt-chart-options-settings').classList.remove('hidden');
						}
					});
				})
			</script>
		</div> <!-- . inside -->
	</div> <!-- .postbox -->

	<?php do_action('em_options_page_footer_bookings'); ?>
	
</div> <!-- .em-menu-bookings -->
