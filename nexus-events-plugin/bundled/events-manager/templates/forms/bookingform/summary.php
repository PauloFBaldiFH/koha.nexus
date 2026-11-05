<?php
// set up init vars
/* @var EM_Booking $EM_Booking */
/* @var EM_Event $EM_Event */
if( $EM_Booking->get_spaces() > 0 ){
	$show_subsections = em_get_option('dbem_bookings_summary_subsections');
	$itemize_taxes    = em_get_option('dbem_bookings_summary_taxes_itemized'); // display tickets without taxes and apply taxes to pre_ discount/surcharges manually here so it all adds up
	$price_summary    = $EM_Booking->get_price_summary_array(); //we should now have an array of information including base price, taxes and post/pre tax discounts, show subtotals section if there's more than one item here
	if( !empty($price_summary['discounts_pre_tax']) ){
		// if we have discounts pre-tax, it's very difficult to accurately show discounts and/or subsequent surcharges with tax adjustments as they affect the total price, and would also confuse users with adjusted discounts with tax included/excluded
		$itemize_taxes = true;
	}
	$currency = $EM_Booking->get_currency();
	$base_price = $EM_Booking->get_price_base();
	$total_price = $EM_Booking->get_price();
	$total_price_formatted = $EM_Booking->get_price( true );
	$display_taxes = ($itemize_taxes || em_get_option('dbem_bookings_summary_subtotal_exc_taxes')) && !empty($price_summary['taxes']['amount']); // will we be displaying taxes? useful so we can decide if we also display a subtotal
}else{
	$itemize_taxes         = false;
	$display_taxes         = false;
	$show_subsections      = false;
	$base_price            = 0;
	$total_price           = 0;
	$total_price_formatted = $EM_Event->format_price(0);
	$currency              = em_get_option('dbem_bookings_currency','USD');
}
?>
<div class="em-booking-summary <?php if( empty($EM_Booking) ) echo 'no-booking'; ?>" id="em-booking-summary-<?php echo esc_attr($EM_Event->event_id); ?>"
     data-amount="<?php echo esc_attr($total_price); ?>"
     data-amount-formatted="<?php echo esc_attr( $total_price_formatted ); ?>"
     data-tax-itemized="<?php echo $itemize_taxes ? 1:0; ?>"
     data-amount-base="<?php echo esc_attr($base_price); ?>"
     data-currency="<?php echo esc_attr($currency) ?>"
     data-spaces="<?php echo esc_attr( $EM_Booking->get_spaces() ); ?>"
     data-uuid="<?php echo esc_attr($EM_Booking->booking_uuid); ?>"
	>
	<?php
		do_action( 'em_booking_form_summary_top', $EM_Booking );
	?>
	<?php if( $EM_Booking->get_spaces() > 0 ): ?>
		<div class="em-bs-section em-bs-section-items">
			<?php foreach($EM_Booking->get_tickets_bookings() as $EM_Ticket_Booking): /* @var $EM_Ticket_Booking EM_Ticket_Booking */ ?>
				<?php
					if( $itemize_taxes ){
						$amount = $EM_Ticket_Booking->get_price(true);
						$amount_raw = $EM_Ticket_Booking->get_price();
					}else{
						$amount = $EM_Ticket_Booking->get_price_with_taxes(true);
						$amount_raw = $EM_Ticket_Booking->get_price_with_taxes();
					}
					$qty = $EM_Ticket_Booking->get_spaces();
					$name = $EM_Ticket_Booking->get_ticket()->name;
				?>
				<div class="em-bs-row em-bs-row-item" data-amount="<?php echo esc_attr($amount_raw); ?>" data-qty="<?php echo esc_attr($qty); ?>" data-name="<?php echo esc_attr($name); ?>">
					<div class="em-bs-cell-qty" title="<?php esc_html_e('Quantity','events-manager'); ?>">
						<?php echo esc_html($qty); ?>
					</div>
					<div class="em-bs-cell-desc" title="<?php esc_html_e('Ticket','events-manager'); ?>">
						<span class="em-bs-qty-x">x</span> <?php echo wp_kses($name, 'em_ticket_name'); ?>
					</div>
					<div class="em-bs-cell-price" title="<?php esc_html_e('Price','events-manager'); ?>">
						<?php echo esc_html($amount); ?>
					</div>
				</div>
			<?php endforeach; ?>
		</div>
	
		<?php
		do_action( 'em_booking_form_summary_after_tickets', $EM_Booking );
		
		// Subtotal - calculate now in case we don't display subtotals at all due to taxes not being displayed and no extra charges
		do_action( 'em_booking_form_summary_before_subtotals', $EM_Booking );
		if ( $itemize_taxes || em_get_option('dbem_bookings_summary_subtotal_exc_taxes') ) {
			$base_tax = 0;
			$subtotal_raw = $base_price;
		} else {
			$base_tax   = $base_price * ( $EM_Booking->get_tax_rate() / 100 );
			$subtotal_raw = $base_price + $base_tax;
		}
		$subtotal_raw = apply_filters('em_booking_form_summary_subtotal_amount', $subtotal_raw, $EM_Booking, ['base_tax' => $base_tax, 'amount_raw' => $subtotal_raw, 'itemize_taxes' => $itemize_taxes, 'base_price' => $base_price] );
		?>
		<?php if( $display_taxes || $subtotal_raw !== $total_price || !empty($price_summary['discounts_pre_tax']) || !empty($price_summary['surcharges_pre_tax']) || !empty($price_summary['discounts_post_tax']) || !empty($price_summary['surcharges_post_tax']) ): ?>
		<div class="em-bs-section em-bs-section-subtotals">
			<div class="em-bs-row em-bs-row-subtotal" data-amount="<?php echo esc_attr($subtotal_raw); ?>" data-amount-base="<?php echo esc_attr($EM_Booking->get_price_base()); ?>">
				<div class="em-bs-cell-desc">
					<?php esc_html_e('Sub Total','events-manager'); ?>
				</div>
				<div class="em-bs-cell-price">
					<?php echo esc_html($EM_Booking->format_price( $subtotal_raw )); ?>
				</div>
			</div>
			
			<?php
			// Discounts Pre Tax
			do_action( 'em_booking_form_summary_before_discounts_pre', $EM_Booking, $price_summary );
			?>
			<?php if( !empty($price_summary['discounts_pre_tax']) ): ?>
				<?php if( $show_subsections ) : ?>
				<div class="em-bs-subtitle em-bs-subsection-pre-tax-discounts">
					<?php esc_html_e('Discounts Before Taxes','events-manager'); ?>
				</div>
				<?php endif; ?>
				<?php foreach( $price_summary['discounts_pre_tax'] as $discount ): ?>
					<div class="em-bs-row em-bs-row-discount em-bs-row-discount-pre <?php echo $show_subsections ? 'em-bs-subsection':''; ?>" data-amount="<?php echo esc_attr($discount['amount_adjusted']); ?>" data-name="<?php echo esc_attr($discount['name']); ?>">
						<div class="em-bs-cell-desc">
							<?php echo esc_html($discount['name']); ?>
							<?php if( !empty($discount['desc']) ): ?>
							<span class="em-icon em-icon-info em-tooltip" aria-label="<?php echo esc_attr($discount['desc']); ?>"></span>
							<?php endif; ?>
						</div>
						<div class="em-bs-cell-price">
							- <?php echo esc_html($discount['amount']); ?>
						</div>
					</div>
				<?php endforeach; ?>
			<?php endif; ?>
			
			<?php
			// Surcharges Pre Tax
			do_action( 'em_booking_form_summary_before_surcharges_pre', $EM_Booking, $price_summary );
			?>
			<?php if( !empty($price_summary['surcharges_pre_tax']) ): ?>
				<?php if( $show_subsections ) : ?>
				<div class="em-bs-subtitle em-bs-subsection-pre-tax-surcharges">
					<?php esc_html_e('Surcharges Before Taxes','events-manager'); ?>
				</div>
				<?php endif; ?>
				<?php foreach( $price_summary['surcharges_pre_tax'] as $surcharge ): ?>
					<?php
					if( $itemize_taxes ){
						$amount_raw = $surcharge['amount_adjusted'];
						$amount = $surcharge['amount'];
					}else{
						$surcharge_tax = $surcharge['amount_adjusted'] * ( $EM_Booking->get_tax_rate() / 100);
						$amount_raw = $surcharge['amount_adjusted'] + $surcharge_tax;
						$amount = $EM_Booking->format_price( $surcharge['amount_adjusted'] + $surcharge_tax );
					}
					?>
					<div class="em-bs-row em-bs-row-surcharge em-bs-row-surcharge-pre <?php echo $show_subsections ? 'em-bs-subsection':''; ?>" data-amount="<?php echo esc_attr($amount_raw); ?>" data-name="<?php echo esc_attr($surcharge['name']); ?>" data-amount-base="<?php echo esc_attr($surcharge['amount_adjusted']); ?>">
						<div class="em-bs-cell-desc">
							<?php echo esc_html($surcharge['name']); ?>
							<?php if( !empty($surcharge['desc']) ): ?>
							<span class="em-icon em-icon-info em-tooltip" aria-label="<?php echo esc_attr($surcharge['desc']); ?>"></span>
							<?php endif; ?>
						</div>
						<div class="em-bs-cell-price">
							<?php echo esc_html($amount); ?>
						</div>
					</div>
				<?php endforeach; ?>
			<?php endif; ?>
			
			<?php
			// Taxes
			do_action( 'em_booking_form_summary_before_taxes', $EM_Booking, $price_summary );
			?>
			<?php if( $display_taxes ): ?>
				<?php if( $show_subsections ) : ?>
				<div class="em-bs-subtitle em-bs-subsection-taxes">
					<?php esc_html_e('Taxes','events-manager'); ?>
				</div>
				<?php endif; ?>
				<div class="em-bs-row em-bs-row-taxes <?php echo $show_subsections ? 'em-bs-subsection':''; ?>" data-amount="<?php echo esc_attr($EM_Booking->get_price_taxes()); ?>">
					<div class="em-bs-cell-desc">
						<?php esc_html_e('Taxes','events-manager'); ?> ( <?php echo esc_html($price_summary['taxes']['rate']); ?> )
						<?php if( !empty($price_summary['taxes']['desc']) ): ?>
						<span class="em-icon em-icon-info em-tooltip" aria-label="<?php echo esc_attr($price_summary['taxes']['desc']); ?>"></span>
						<?php endif; ?>
					</div>
					<div class="em-bs-cell-price">
						<?php echo esc_html($price_summary['taxes']['amount']); ?>
					</div>
				</div>
			<?php endif; ?>
			
			<?php
			// Discounts Post Tax
			do_action( 'em_booking_form_summary_before_discounts_post', $EM_Booking, $price_summary );
			?>
			<?php if( !empty($price_summary['discounts_post_tax']) ): ?>
				<?php if( $show_subsections ) : ?>
				<div class="em-bs-subtitle em-bs-subsection-post-tax-discounts">
					<?php esc_html_e('Discounts (After Taxes)','events-manager'); ?>
				</div>
				<?php endif; ?>
				<?php foreach( $price_summary['discounts_post_tax'] as $discount ): ?>
					<div class="em-bs-row em-bs-row-discount em-bs-row-discount-post <?php echo $show_subsections ? 'em-bs-subsection':''; ?>" data-amount="<?php echo esc_attr($discount['amount_adjusted']); ?>" data-name="<?php echo esc_attr($discount['name']); ?>">
						<div class="em-bs-cell-desc">
							<?php echo esc_html($discount['name']); ?>
							<?php if( !empty($discount['desc']) ): ?>
							<span class="em-icon em-icon-info em-tooltip" aria-label="<?php echo esc_attr($discount['desc']); ?>"></span>
							<?php endif; ?>
						</div>
						<div class="em-bs-cell-price">
							- <?php echo esc_html($discount['amount']); ?>
						</div>
					</div>
				<?php endforeach; ?>
			<?php endif; ?>
			
			<?php
			// Surcharges Post Tax
			do_action( 'em_booking_form_summary_before_surcharges_post', $EM_Booking, $price_summary );
			?>
			<?php if( !empty($price_summary['surcharges_post_tax']) ): ?>
				<?php if( $show_subsections ) : ?>
				<div class="em-bs-subtitle em-bs-subsection-post-tax-surcharges">
					<?php esc_html_e('Surcharges (After Taxes)','events-manager'); ?>
				</div>
				<?php endif; ?>
				<?php foreach( $price_summary['surcharges_post_tax'] as $surcharge ): ?>
					<div class="em-bs-row em-bs-row-surcharge em-bs-row-surcharge-post <?php echo $show_subsections ? 'em-bs-subsection':''; ?>" data-amount="<?php echo esc_attr($surcharge['amount_adjusted']); ?>" data-name="<?php echo esc_attr($surcharge['name']); ?>">
						<div class="em-bs-cell-desc">
							<?php echo esc_html($surcharge['name']); ?>
							<?php if( !empty($surcharge['desc']) ): ?>
							<span class="em-icon em-icon-info em-tooltip" aria-label="<?php echo esc_attr($surcharge['desc']); ?>"></span>
							<?php endif; ?>
						</div>
						<div class="em-bs-cell-price">
							<?php echo esc_html($surcharge['amount']); ?>
						</div>
					</div>
				<?php endforeach; ?>
			<?php endif; ?>
			<?php
			do_action( 'em_booking_form_summary_after_extras', $EM_Booking );
			?>
		</div>
		<?php endif; ?>
		
		<?php
		// Total
		do_action( 'em_booking_form_summary_before_total', $EM_Booking );
		?>
		<div class="em-bs-section em-bs-section-total">
			<div class="em-bs-row em-bs-row-total">
				<div class="em-bs-cell-desc">
					<?php esc_html_e('Total Price','events-manager'); ?>
				</div>
				<div class="em-bs-cell-price">
					<?php echo esc_html($price_summary['total']); ?>
					<?php if( !$itemize_taxes ): ?>
						<span class="em-bs-total-taxes-inc"><?php esc_html_e('Taxes included', 'events-manager'); ?></span>
					<?php endif; ?>
				</div>
			</div>
		</div>
		<?php do_action('em_booking_form_summary_after_total', $EM_Booking); ?>
	<?php else: ?>
		<?php do_action('em_booking_form_summary_before_none'); ?>
		<?php echo esc_html( em_get_option('dbem_bookings_summary_message') ); ?>
		<?php do_action('em_booking_form_summary_after_none'); ?>
	<?php endif; ?>
	<?php do_action('em_booking_form_summary_bottom', $EM_Booking); ?>
</div>