<div class="em-location em-item">
	<div class="em-item-image {no_loc_image}has-placeholder{/no_loc_image}">
		{has_loc_image}
		<a href="#_LOCATIONURL">#_LOCATIONIMAGE{medium}</a>
		{/has_loc_image}
		{no_loc_image}
		<a href="#_LOCATIONURL" class="em-item-image-placeholder"></a>
		{/no_loc_image}
	</div>
	<div class="em-item-info">
		<h3 class="em-item-title">#_LOCATIONLINK</h3>
		<div class="em-event-meta em-item-meta">
			<div class="em-item-meta-line em-location-address">
				<span class="em-icon-location em-icon"></span>
				#_LOCATIONFULLBR
			</div>
			{has_events}
			<div class="em-item-meta-line em-location-events">
				<span class="em-icon-calendar em-icon"></span>
				<div>
					<p><?php esc_html_e('Next Event', 'events-manager'); ?></p>
					<p>#_LOCATIONNEXTEVENT</p>
					<p><a href="#_LOCATIONURL"><?php esc_html_e('See All', 'events-manager'); ?></a></p>
				</div>
			</div>
			{/has_events}
			{no_events}
			<div class="em-item-meta-line em-location-no-events">
				<span class="em-icon-calendar em-icon"></span>
				<div><?php esc_html_e('No upcoming events', 'events-manager'); ?></p></div>
			</div>
			{/no_events}
		</div>
		<div class="em-item-desc">
			#_LOCATIONEXCERPT{25}
		</div>
		<div class="em-item-actions input">
			<a class="em-item-read-more button" href="#_LOCATIONURL"><?php esc_html_e('More Info', 'events-manager'); ?></a>
		</div>
	</div>
</div>