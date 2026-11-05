<div class="em-event em-item {is_cancelled}em-event-cancelled{/is_cancelled}" style="--default-border:#_CATEGORYCOLOR;">
	<div class="em-item-image {no_image}has-placeholder{/no_image}">
		{has_image}
		#_EVENTIMAGE{medium}
		{/has_image}
		{no_image}
		<div class="em-item-image-placeholder">
			<div class="date">
				<span class="day">#d</span>
				<span class="month">#M</span>
			</div>
		</div>
		{/no_image}
	</div>
	<div class="em-item-info">
		<h3 class="em-item-title">#_EVENTLINK</h3>
		{is_cancelled}
		<div class="em-event-cancelled em-notice em-notice-error em-notice-thin em-notice-icon">
			<span class="em-icon em-icon-cross-circle"></span>
			<?php esc_html_e('This event has been cancelled.', 'events-manager'); ?>
		</div>
		{/is_cancelled}
		<div class="em-event-meta em-item-meta">
			<div class="em-item-meta-line em-event-date em-event-meta-datetime">
				<span class="em-icon-calendar em-icon"></span>
				#_EVENTDATES&nbsp;&nbsp;&nbsp;&nbsp;
			</div>
			<div class="em-item-meta-line em-event-time em-event-meta-datetime">
				<span class="em-icon-clock em-icon"></span>
				#_EVENTTIMES
			</div>
			{bookings_open}
			<div class="em-item-meta-line em-event-prices">
				<span class="em-icon-ticket em-icon"></span>
				#_EVENTPRICERANGE
			</div>
			{/bookings_open}
			{has_location_venue}
			<div class="em-item-meta-line em-event-location">
				<span class="em-icon-location em-icon"></span>
				#_LOCATIONLINK
			</div>
			{/has_location_venue}
			{has_event_location}
			<div class="em-item-meta-line em-event-location">
				<span class="em-icon-at em-icon"></span>
				#_EVENTLOCATION
			</div>
			{/has_event_location}
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
		</div>
		<div class="em-item-desc">
			#_EVENTEXCERPT{25}
		</div>
		<div class="em-item-actions input">
			<a class="em-item-read-more button" href="#_EVENTURL"><?php esc_html_e('More Info', 'events-manager'); ?></a>
			{bookings_open}
			<a class="em-event-book-now button" href="#_EVENTURL#em-event-booking-form">
				<span class="em-icon em-icon-ticket"></span>
				<?php esc_html_e('Book Now!', 'events-manager'); ?>
			</a>
			{/bookings_open}
		</div>
	</div>
</div>