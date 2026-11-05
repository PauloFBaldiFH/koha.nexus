<?php
/* 
 * This file generates the default login form within the booking form (if enabled in options).
 */
?>
<div class="em-login">
	<div class="em-login-trigger">
		<?php echo sprintf(esc_html__('Do you already have an account with us? %s','events-manager'), '<a href="#">'. esc_html__('Sign In', 'events-manager') .'</a>'); ?>
	</div>
	<div class="em-login-content">
		<p><?php esc_html_e('Log in if you already have an account with us.','events-manager'); ?></p>
		<form class="em-form em-login-form" action="<?php echo wp_login_url(); ?>" method="post">
		    <p>
				<label><?php esc_html_e( 'Username','events-manager') ?></label>
				<input type="text" name="log" class="input" value="">
			</p>
			<p>
				<label><?php esc_html_e( 'Password','events-manager') ?></label>
				<input type="password" name="pwd" class="input" value="">
		    </p>
		    <?php do_action('login_form'); ?>
			<div class="em-login-actions">
				<div class="em-login-buttons">
					<button type="submit" name="wp-submit" class="button-primary em-login-submit"><?php esc_attr_e('Log In', 'events-manager'); ?></button>
					<button type="button" class="em-login-cancel"><?php esc_html_e('Cancel', 'events-manager'); ?></button>
					<input type="hidden" name="redirect_to" value="<?php echo esc_url($_SERVER['REQUEST_URI']); ?>#em-event-booking-form">
				</div>
				<div class="em-login-meta">
					<label class="em-login-rememberme"><input name="rememberme" type="checkbox" value="forever"> <?php esc_html_e( 'Remember Me','events-manager') ?></label>
					<div class="em-login-links">
						<?php
						//Signup Links
						if ( em_get_option('users_can_register') ) {
							if ( function_exists('bp_get_signup_page') ) { //Buddypress
								$register_link = bp_get_signup_page();
							}elseif ( file_exists( ABSPATH."/wp-signup.php" ) ) { //MU + WP3
								$register_link = site_url('wp-signup.php', 'login');
							} else {
								$register_link = wp_registration_url();
							}
							?>
							<a href="<?php echo $register_link ?>"><?php esc_html_e('Sign Up','events-manager') ?></a>
							<span>&nbsp;&nbsp;|&nbsp;&nbsp;</span>
							<?php
						}
						?>
						<a href="<?php echo wp_lostpassword_url(); ?>" title="<?php esc_html_e('Password Lost and Found', 'events-manager') ?>"><?php esc_html_e('Lost your password?', 'events-manager') ?></a>
					</div>
				</div>
			</div>
		</form>
	</div>
	<?php do_action('em_login_footer'); ?>
</div>