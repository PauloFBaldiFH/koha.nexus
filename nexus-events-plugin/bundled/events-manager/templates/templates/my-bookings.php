<?php do_action('em_template_my_bookings_header'); ?>
<?php
	global $wpdb, $current_user, $EM_Notices, $EM_Person;
	if( is_user_logged_in() ):
		$EM_Person = new EM_Person( get_current_user_id() );
		$EM_Bookings = $EM_Person->get_bookings();
		$bookings_count = count($EM_Bookings->bookings);
		if($bookings_count > 0){
			//Get events here in one query to speed things up
			$event_ids = array();
			foreach($EM_Bookings as $EM_Booking){
				$event_ids[] = $EM_Booking->event_id;
			}
		}
		$limit = ( !empty($_GET['limit']) ) ? $_GET['limit'] : 20;//Default limit
		$page = ( !empty($_GET['pno']) ) ? $_GET['pno']:1;
		$offset = ( $page > 1 ) ? ($page-1)*$limit : 0;
		echo $EM_Notices;
		?>
		<div class='<?php em_template_classes('my-bookings'); ?>'>
				<?php if ( $bookings_count >= $limit ) : ?>
				<div class='tablenav'>
					<?php 
					if ( $bookings_count >= $limit ) {
						$link = em_add_get_params($_SERVER['REQUEST_URI'], array('pno'=>'%PAGE%'), false); //don't html encode, so em_paginate does its thing
						$bookings_nav = em_paginate( $link, $bookings_count, $limit, $page);
						echo $bookings_nav;
					}
					?>
					<div class="clear"></div>
				</div>
				<?php endif; ?>
				<div class="clear"></div>
				<?php if( $bookings_count > 0 ): ?>
				<div class='table-wrap'>
				<table id='dbem-bookings-table' class='widefat post fixed'>
					<thead>
						<tr>
							<th class='manage-column' scope='col'><?php _e('Event', 'events-manager'); ?></th>
							<th class='manage-column' scope='col'><?php _e('Date', 'events-manager'); ?></th>
							<th class='manage-column' scope='col'><?php _e('Spaces', 'events-manager'); ?></th>
							<th class='manage-column' scope='col'><?php _e('Status', 'events-manager'); ?></th>
							<?php if( em_get_option('dbem_bookings_rsvp') && em_get_option('dbem_bookings_rsvp_my_bookings') ): ?>
							<th class='manage-column' scope='col'><?php _e('RSVP', 'events-manager'); ?></th>
							<?php endif; ?>
							<th class='manage-column' scope='col'>&nbsp;</th>
						</tr>
					</thead>
					<tbody>
						<?php 
						$rowno = 0;
						$event_count = 0;
						$nonce = wp_create_nonce('booking_cancel');
						$rsvp_nonce = wp_create_nonce('booking_rsvp');
						foreach ($EM_Bookings as $EM_Booking) {
							/* @var $EM_Booking EM_Booking */
							$EM_Event = $EM_Booking->get_event();						
							if( ($rowno < $limit || empty($limit)) && ($event_count >= $offset || $offset === 0) ) {
								$rowno++;
								?>
								<tr>
									<td><?php echo $EM_Event->output("#_EVENTLINK"); ?></td>
									<td><?php echo $EM_Event->start()->i18n( em_get_option('dbem_date_format') ); ?></td>
									<td><?php echo $EM_Booking->get_spaces() ?></td>
									<td>
										<?php echo $EM_Booking->get_status(); ?>
									</td>
									<?php if( em_get_option('dbem_bookings_rsvp') && em_get_option('dbem_bookings_rsvp_my_bookings') ): ?>
										<td>
											<?php echo $EM_Booking->get_rsvp_status( true ); ?>
										</td>
									<?php endif; ?>
									<td>
										<?php
										$cancel_links = array();
										$show_rsvp = em_get_option('dbem_bookings_rsvp') && em_get_option('dbem_bookings_rsvp_my_bookings_buttons');
										$show_cancel_rsvp = $EM_Booking->can_rsvp(0) && em_get_option('dbem_bookings_rsvp_sync_cancel');
										if( !$show_cancel_rsvp && (!in_array($EM_Booking->booking_status, array(2,3)) && $EM_Booking->can_cancel()) ){
											$cancel_url = em_add_get_params($_SERVER['REQUEST_URI'], array('action'=>'booking_cancel', 'booking_id'=>$EM_Booking->booking_id, '_wpnonce'=>$nonce));
											$cancel_links[] = '<a class="em-bookings-cancel" href="'. esc_url($cancel_url) .'" onclick="if( !confirm(EM.booking_warning_cancel) ){ return false; }">'.__('Cancel','events-manager').'</a>';
										}
										if ( $show_rsvp ) {
											if( $EM_Booking->can_rsvp(1) ) {
												$url = em_add_get_params($_SERVER['REQUEST_URI'], array('action'=>'booking_rsvp_change', 'status' => 1, 'booking_id'=>$EM_Booking->booking_id, '_wpnonce'=>$rsvp_nonce));
												$cancel_links[] = '<a class="em-bookings-rsvp-confirm" href="'.esc_url($url).'">'. EM_Booking::get_rsvp_statuses(1)->label_action .'</a>';
											}
											if( $EM_Booking->can_rsvp(0) ) {
												$url = em_add_get_params($_SERVER['REQUEST_URI'], array('action'=>'booking_rsvp_change', 'status' => 0, 'booking_id'=>$EM_Booking->booking_id, '_wpnonce'=>$rsvp_nonce));
												$cancel_links[] = '<a class="em-bookings-rsvp-cancel" href="'.esc_url($url).'">'. EM_Booking::get_rsvp_statuses(0)->label_action .'</a>';
											}
											if( $EM_Booking->can_rsvp(2) ) {
												$url = em_add_get_params($_SERVER['REQUEST_URI'], array('action'=>'booking_rsvp_change', 'status' => 2, 'booking_id'=>$EM_Booking->booking_id, '_wpnonce'=>$rsvp_nonce));
												$cancel_links[] = '<a class="em-bookings-rsvp-maybe" href="'.esc_url($url).'">'. EM_Booking::get_rsvp_statuses(2)->label_action .'</a>';
											}
										}
										$action_links = apply_filters('em_my_bookings_booking_action_links', $cancel_links, $EM_Booking, $cancel_links);
										$action_text = '';
										if( !empty($action_links) ) {
											if (is_array($action_links) ) {
												?>
												<button type="button" class="em-tooltip-ddm em-clickable input button-secondary" data-button-width="match" data-tooltip-class="em-my-bookings-actions-tooltip"><?php esc_html_e('Actions', 'events-manager'); ?></button>
												<div class="em-tooltip-ddm-content em-my-bookings-actions-content">
													<?php foreach( $action_links as $link ): ?>
														<?php echo $link; ?>
													<?php endforeach; ?>
												</div>
												<?php
											} else {
												// if something messed up the em_my_bookings_booking_action_links filter, just output the links as text further down
												$action_text = $action_links;
											}
										}
										// if we have legacy stuff running, just output links as probably expected
										// @deprecated - stop using this and use em_my_bookings_booking_action_links above
										echo apply_filters('em_my_bookings_booking_actions', $action_text, $EM_Booking, $cancel_links);
										do_action( 'em_my_bookings_booking_actions_bottom', $EM_Booking );
										?>
									</td>
								</tr>								
								<?php
							}
							do_action('em_my_bookings_booking_loop',$EM_Booking);
							$event_count++;
						}
						?>
					</tbody>
				</table>
				</div>
				<?php else: ?>
					<?php _e('You do not have any bookings.', 'events-manager'); ?>
				<?php endif; ?>
			<?php if( !empty($bookings_nav) && $bookings_count >= $limit ) : ?>
			<div class='tablenav'>
				<?php echo $bookings_nav; ?>
				<div class="clear"></div>
			</div>
			<?php endif; ?>
		</div>
		<?php do_action('em_template_my_bookings_footer', $EM_Bookings); ?>
<?php else: ?>
	<p><?php echo sprintf(__('Please <a href="%s">Log In</a> to view your bookings.','events-manager'),site_url('wp-login.php?redirect_to=' . urlencode(get_permalink()), 'login'))?></p>
<?php endif; ?>