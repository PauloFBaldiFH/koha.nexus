<?php
// set up init vars
/* @var EM_Booking $EM_Booking */
/* @var EM_Event $EM_Event */
$show_subsections = em_get_option('dbem_bookings_summary_subsections');
$itemize_taxes    = em_get_option('dbem_bookings_summary_taxes_itemized') && em_get_option('dbem_bookings_tax') > 0;
?>

<template class="em-booking-summary-skeleton" id="em-booking-summary-skeleton-<?php echo esc_attr($EM_Event->event_id); ?>">
	<div class="em-booking-summary skeleton">
		<?php do_action( 'em_booking_form_summary_skeleton_top', $EM_Booking ); ?>
		<div class="em-bs-section em-bs-section-items">
			<div class="em-bs-row em-bs-row-item">
				<div class="em-bs-cell-qty item text" title="<?php esc_html_e('Quantity','events-manager'); ?>"></div>
				<div class="em-bs-cell-desc item text" title="<?php esc_html_e('Ticket','events-manager'); ?>"></div>
				<div class="em-bs-cell-price item text" title="<?php esc_html_e('Price','events-manager'); ?>"></div>
			</div>
		</div>
	
		<?php if( $itemize_taxes ): ?>
		<div class="em-bs-section em-bs-section-subtotals">
			<div class="em-bs-row em-bs-row-subtotal">
				<div class="em-bs-cell-descitem item text"></div>
				<div class="em-bs-cell-priceitem item text"></div>
			</div>
			<?php if( $show_subsections ) : ?>
			<div class="em-bs-subtitle em-bs-subsection-taxes item title"></div>
			<?php endif; ?>
			<div class="em-bs-row em-bs-row-taxes <?php echo $show_subsections ? 'em-bs-subsection':''; ?>">
				<div class="em-bs-cell-desc item text"></div>
				<div class="em-bs-cell-price item text"></div>
			</div>
		</div>
		<?php endif; ?>
		
		<?php
		// Total
		do_action( 'em_booking_form_summary_skeleton_before_total', $EM_Booking );
		?>
		<div class="em-bs-section em-bs-section-total">
			<div class="em-bs-row em-bs-row-total">
				<div class="em-bs-cell-desc item text"></div>
				<div class="em-bs-cell-price item text"></div>
			</div>
		</div>
		<?php do_action('em_booking_form_summary_skeleton_bottom', $EM_Booking); ?>
	</div>
</template>