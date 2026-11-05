{is_cancelled}
<div class="em-event-cancelled em-notice em-notice-error em-notice-icon">
	<span class="em-icon em-icon-cross-circle"></span>
	<?php esc_html_e('This event has been cancelled.', 'events-manager'); ?>
</div>
{/is_cancelled}
<section class="em-item-header"  style="--default-border:#_CATEGORYCOLOR;">
	{has_image}
	<div class="em-item-image {no_image}has-placeholder{/no_image}">
		#_EVENTIMAGE{medium}
	</div>
	{/has_image}
	<div class="em-item-meta">
		<section class="em-item-meta-column">
			<section class="em-event-when">
				<h3><?php esc_html_e('When', 'events-manager'); ?></h3>
				<div class="em-item-meta-line em-event-date em-event-meta-datetime">
					<span class="em-icon-calendar em-icon"></span>
					#_EVENTDATES&nbsp;&nbsp;&nbsp;&nbsp;
				</div>
				<div class="em-item-meta-line em-event-time em-event-meta-datetime">
					<span class="em-icon-clock em-icon"></span>
					#_EVENTTIMES
				</div>
				#_EVENTADDTOCALENDAR
			</section>
	
			{has_bookings}
			<section class="em-event-bookings-meta">
				<h3><?php esc_html_e('Bookings', 'events-manager'); ?></h3>
				{bookings_open}
				<div class="em-item-meta-line em-event-prices">
					<span class="em-icon-ticket em-icon"></span>
					#_EVENTPRICERANGE
				</div>
				<a href="#em-event-booking-form" class="button input with-icon-right">
					<?php esc_html_e(em_get_option('dbem_booking_button_msg_book')); ?>
					<span class="em-icon-ticket em-icon"></span>
				</a>
				{/bookings_open}
				{bookings_closed}
				<div class="em-item-meta-line em-event-prices">
					<span class="em-icon-ticket em-icon"></span>
					<?php esc_html_e('Bookings closed', 'events-manager'); ?>
				</div>
				{/bookings_closed}
			</section>
			{/has_bookings}
		</section>

		<section class="em-item-meta-column">
			{has_location_venue}
			<section class="em-event-where">
				<h3><?php esc_html_e('Where', 'events-manager'); ?></h3>
				<div class="em-item-meta-line em-event-location">
					<span class="em-icon-location em-icon"></span>
					<div>
						#_LOCATIONLINK<br>
						#_LOCATIONFULLLINE
					</div>
				</div>
			</section>
			{/has_location_venue}
			{has_event_location}
			<section class="em-event-where">
				<h3><?php esc_html_e('Where', 'events-manager'); ?></h3>
				<div class="em-item-meta-line em-event-location">
					<span class="em-icon-at em-icon"></span>
					#_EVENTLOCATION
				</div>
			</section>
			{/has_event_location}
			
			{has_taxonomy}
			<section class="em-item-taxonomies">
				<h3><?php esc_html_e('Event Type', 'events-manager'); ?></h3>
				{has_category}
				<div class="em-item-meta-line em-item-taxonomy em-event-categories">
					<span class="em-icon-category em-icon"></span>
					<div>#_EVENTCATEGORIES</div>
				</div>
				{/has_category}
				{has_tag}
				<div class="em-item-meta-line em-item-taxonomy em-event-tags">
					<span class="em-icon-tag em-icon"></span>
					<div>#_EVENTTAGS</div>
				</div>
				{/has_tag}
			</section>
			{/has_taxonomy}
		</section>
	</div>
</section>
{has_location_venue}
<section class="em-event-location">
	#_LOCATIONMAP{100%,0}
</section>
{/has_location_venue}
<section class="em-event-content">
	#_EVENTNOTES
</section>
{has_bookings}
<section class="em-event-bookings">
	<a name="em-event-booking-form"></a>
	<h2><?php esc_html_e('Bookings', 'events-manager'); ?></h2>
	#_BOOKINGFORM
</section>
{/has_bookings}