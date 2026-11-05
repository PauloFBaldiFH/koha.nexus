{has_image}
<div class="em-item-meta em-event-image">
	#_EVENTIMAGE{300}
</div>
{/has_image}
<div class="em-item-info">
	<div class="em-item-title em-event-title">#_EVENTLINK</div>
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
			#_EVENTCATEGORIES
		</div>
		{/has_category}
		{has_tag}
		<div class="em-item-meta-line em-item-taxonomy em-event-tags">
			<span class="em-icon-tag em-icon"></span>
			<div>#_EVENTTAGS</div>
		</div>
		{/has_tag}
	</div>
</div>
<div class="em-item-desc">#_EVENTEXCERPT{25,...}</div>
<div class="em-item-actions input">
	<a class="em-event-read-more button" href="#_EVENTURL"><?php esc_html_e('More Info', 'events-manager') ?></a>
	{bookings_open}
	<a class="em-event-book-now button" href="#_EVENTURL#em-booking"><?php esc_html_e('Book Now!', 'events-manager') ?></a>
	{/bookings_open}
</div>