<?php
/**
 * EU right-of-withdrawal ("Widerrufsbutton") support for Events Manager.
 *
 * Provides a guest-accessible cancellation flow that satisfies the EU statutory right of withdrawal (Art. 11a of the Consumer Rights Directive 2011/83/EU, as amended by Directive (EU) 2023/2673), implemented in Germany as the Widerrufsbutton under § 356a BGB and mandatory from 19 June 2026. This class is the central home for the feature: settings accessors, locale-aware default copy, and — in later increments — the front-end two-step flow, the magic-link guest access path, and the acknowledgment email.
 *
 * Scope boundary: EM ships only the *mechanism*. The legal text itself (Widerrufsbelehrung / model withdrawal form) is supplied by the operator (their lawyer, IT-Recht-Kanzlei, Händlerbund, etc.) — we provide the slot, never the legal copy.
 *
 * The feature is opt-in and off by default: most EM sites sell fixed-date events, which are exempt from the right of withdrawal (§ 312g Abs. 2 Nr. 9 BGB — leisure services tied to a specific date), so the obligation only bites for non-dated services, digital content, memberships and the like.
 */
class EM_Withdrawal {

	/**
	 * Locale-aware default copy for the legally-critical, operator-editable strings. These deliberately bypass gettext: the translation files won't carry these brand-new strings by the deadline, and legal-register copy shouldn't go through community translation anyway. Keyed by locale bucket; the bucket is derived from get_locale() with an English fallback.
	 *
	 * @var array<string,array<string,string>>
	 */
	protected static $label_defaults = array(
		'en' => array(
			'button'  => 'Withdraw from contract',
			'confirm' => 'Confirm withdrawal',
			'heading' => 'Withdraw from a contract',
		),
		'de' => array(
			'button'  => 'Vertrag widerrufen',
			'confirm' => 'Widerruf bestätigen',
			'heading' => 'Vertrag widerrufen',
		),
	);

	/**
	 * Locale-aware defaults for the acknowledgment-of-receipt email. Like the labels these bypass gettext and are operator-editable. The body is worded to confirm receipt only (not validity) and carries the two legally-required pieces: the withdrawal statement and the exact receipt timestamp.
	 *
	 * @var array<string,array<string,string>>
	 */
	protected static $email_defaults = array(
		'en' => array(
			'link_subject' => 'Your withdrawal link',
			'link_body'    => "Hello,\n\nYou asked to withdraw from a booking. Use the secure link below to choose the booking and confirm your withdrawal. The link is valid for 24 hours:\n\n#_WITHDRAWAL_LINK\n\nIf you did not request this, you can safely ignore this email.",
			'subject' => 'Withdrawal received — #_BOOKINGID',
			'body'    => "Hello #_BOOKINGNAME,\n\nThis confirms that we have received your declaration of withdrawal for the following booking:\n\n#_WITHDRAWAL_STATEMENT\n\nReceived on: #_WITHDRAWAL_TIMESTAMP\n\nThis message confirms receipt of your declaration only — it does not constitute confirmation that the withdrawal is valid. We will review it and contact you regarding any refund due.\n\n#_EVENTNAME\n#_EVENTDATES",
		),
		'de' => array(
			'link_subject' => 'Ihr Widerrufs-Link',
			'link_body'    => "Hallo,\n\nSie haben den Widerruf einer Buchung angefordert. Über den folgenden sicheren Link können Sie die Buchung auswählen und Ihren Widerruf bestätigen. Der Link ist 24 Stunden gültig:\n\n#_WITHDRAWAL_LINK\n\nFalls Sie dies nicht angefordert haben, können Sie diese E-Mail ignorieren.",
			'subject' => 'Widerruf eingegangen — #_BOOKINGID',
			'body'    => "Hallo #_BOOKINGNAME,\n\nhiermit bestätigen wir den Eingang Ihrer Widerrufserklärung für folgende Buchung:\n\n#_WITHDRAWAL_STATEMENT\n\nEingegangen am: #_WITHDRAWAL_TIMESTAMP\n\nDiese Nachricht bestätigt ausschließlich den Eingang Ihrer Erklärung und stellt keine Bestätigung der Wirksamkeit des Widerrufs dar. Wir prüfen Ihren Widerruf und melden uns wegen einer etwaigen Rückerstattung.\n\n#_EVENTNAME\n#_EVENTDATES",
		),
	);

	/**
	 * Whether the withdrawal feature is switched on. Opt-in by design (see class doc).
	 *
	 * @return bool
	 */
	public static function is_enabled() {
		return (bool) get_option( 'dbem_eu_withdrawal_enabled' );
	}

	/**
	 * Length of the withdrawal window in days (statutory minimum 14). Used to flag late submissions for the operator's manual review rather than to silently reject them, since the law leaves the validity judgement to the trader.
	 *
	 * @return int
	 */
	public static function period_days() {
		$days = (int) get_option( 'dbem_eu_withdrawal_period_days', 14 );
		return $days > 0 ? $days : 14;
	}

	/**
	 * ID of the page hosting the [em_withdrawal_form] shortcode, or 0 if not configured.
	 *
	 * @return int
	 */
	public static function page_id() {
		return (int) get_option( 'dbem_eu_withdrawal_page' );
	}

	/**
	 * The locale default bucket: 'de' for any German locale, otherwise 'en'.
	 *
	 * @return string
	 */
	protected static function locale_bucket() {
		$locale = strtolower( (string) get_locale() );
		return strpos( $locale, 'de' ) === 0 ? 'de' : 'en';
	}

	/**
	 * Resolve a legally-critical label: the operator's saved override if present, otherwise the locale-aware built-in default. $key is one of: button, confirm, heading.
	 *
	 * @param string $key
	 * @return string
	 */
	public static function label( $key ) {
		$stored = trim( (string) get_option( 'dbem_eu_withdrawal_label_' . $key ) );
		return $stored !== '' ? $stored : self::label_default( $key );
	}

	/**
	 * The built-in locale-aware default for a label key, independent of any stored setting. Exposed so the settings screen can show it as the placeholder/default value.
	 *
	 * @param string $key
	 * @return string
	 */
	public static function label_default( $key ) {
		$bucket = self::locale_bucket();
		if ( isset( self::$label_defaults[ $bucket ][ $key ] ) ) {
			return self::$label_defaults[ $bucket ][ $key ];
		}
		return isset( self::$label_defaults['en'][ $key ] ) ? self::$label_defaults['en'][ $key ] : '';
	}

	/**
	 * The built-in locale-aware default for an acknowledgment-email key (subject|body), independent of any stored override.
	 *
	 * @param string $key
	 * @return string
	 */
	public static function email_default( $key ) {
		$bucket = self::locale_bucket();
		if ( isset( self::$email_defaults[ $bucket ][ $key ] ) ) {
			return self::$email_defaults[ $bucket ][ $key ];
		}
		return isset( self::$email_defaults['en'][ $key ] ) ? self::$email_defaults['en'][ $key ] : '';
	}

	/**
	 * Acknowledgment email subject: operator override if set, otherwise the locale default.
	 *
	 * @return string
	 */
	public static function ack_subject() {
		$stored = trim( (string) get_option( 'dbem_eu_withdrawal_email_subject' ) );
		return $stored !== '' ? $stored : self::email_default( 'subject' );
	}

	/**
	 * Acknowledgment email body: operator override if set, otherwise the locale default.
	 *
	 * @return string
	 */
	public static function ack_body() {
		$stored = trim( (string) get_option( 'dbem_eu_withdrawal_email_body' ) );
		return $stored !== '' ? $stored : self::email_default( 'body' );
	}

	/**
	 * Register the feature's hooks. Called once at load (see bottom of file). Callbacks gate on is_enabled() at call time so the master toggle takes effect without re-registering.
	 */
	public static function init() {
		add_shortcode( 'em_withdrawal_form', array( __CLASS__, 'shortcode' ) );
		add_action( 'wp_footer', array( __CLASS__, 'footer_link' ) );
		if ( is_admin() ) {
			add_action( 'em_options_page_footer_bookings', array( __CLASS__, 'settings_page' ) );
		}
	}

	/**
	 * Render the "Right of Withdrawal" settings box on the Bookings settings tab. All fields are dbem_* options, which Events Manager's settings save loop persists automatically, so no changes to the core save handler are needed.
	 */
	public static function settings_page() {
		?>
		<div class="postbox" id="em-opt-eu-withdrawal">
			<div class="handlediv" title="<?php esc_attr_e( 'Click to toggle', 'events-manager' ); ?>"><br /></div>
			<h3><span><?php esc_html_e( 'Right of Withdrawal (EU)', 'events-manager' ); ?></span></h3>
			<div class="inside">
				<table class="form-table">
					<tr><td colspan="2">
						<p><?php echo wp_kses( __( 'A guest-accessible cancellation flow for the EU statutory <strong>right of withdrawal</strong>. Enable this only if you sell to consumers who have a right of withdrawal — <strong>fixed-date events are generally exempt</strong>. Events Manager provides the mechanism; you supply your own legal withdrawal policy text below.', 'events-manager' ), array( 'strong' => array() ) ); ?></p>
					</td></tr>
					<?php
					em_options_radio_binary( __( 'Enable right-of-withdrawal button?', 'events-manager' ), 'dbem_eu_withdrawal_enabled', __( 'Adds a guest-accessible withdrawal flow and, optionally, a site-wide footer link.', 'events-manager' ) );
					em_options_select_page( __( 'Withdrawal page', 'events-manager' ), 'dbem_eu_withdrawal_page', array( 'none' => __( '[Select a page]', 'events-manager' ) ), sprintf( __( 'The page containing the %s shortcode. Create a page with that shortcode and select it here.', 'events-manager' ), '<code>[em_withdrawal_form]</code>' ) );
					em_options_radio_binary( __( 'Show footer link?', 'events-manager' ), 'dbem_eu_withdrawal_footer_link', __( 'Display a prominent "Withdraw from contract" link in the site footer, since the law expects the function to be continuously and easily reachable.', 'events-manager' ) );
					em_options_input_text( __( 'Withdrawal period (days)', 'events-manager' ), 'dbem_eu_withdrawal_period_days', __( 'The statutory cooling-off period is 14 days. Late submissions are still accepted and flagged for your review rather than silently rejected.', 'events-manager' ) );
					?>
					<tr class="em-header"><td colspan="2"><h4><?php esc_html_e( 'Button & page labels', 'events-manager' ); ?></h4></td></tr>
					<tr><td colspan="2"><?php esc_html_e( "Leave blank to use the built-in default for your site's language.", 'events-manager' ); ?></td></tr>
					<?php
					self::field_text( __( 'Step 1 button', 'events-manager' ), 'dbem_eu_withdrawal_label_button', self::label_default( 'button' ) );
					self::field_text( __( 'Confirm button', 'events-manager' ), 'dbem_eu_withdrawal_label_confirm', self::label_default( 'confirm' ) );
					self::field_text( __( 'Page heading', 'events-manager' ), 'dbem_eu_withdrawal_label_heading', self::label_default( 'heading' ) );
					?>
					<tr class="em-header"><td colspan="2"><h4><?php esc_html_e( 'Acknowledgment email', 'events-manager' ); ?></h4></td></tr>
					<tr><td colspan="2"><?php esc_html_e( 'Sent to the consumer as the legally-required acknowledgment of receipt. It records the withdrawal statement and the exact date and time of receipt, and confirms receipt only — not the validity of the withdrawal.', 'events-manager' ); ?></td></tr>
					<?php
					self::field_text( __( 'Acknowledgment email subject', 'events-manager' ), 'dbem_eu_withdrawal_email_subject', self::email_default( 'subject' ) );
					self::field_textarea( __( 'Acknowledgment email body', 'events-manager' ), 'dbem_eu_withdrawal_email_body', self::email_default( 'body' ), sprintf( __( 'Placeholders: %1$s and %2$s plus the usual booking placeholders.', 'events-manager' ), '<code>#_WITHDRAWAL_STATEMENT</code>', '<code>#_WITHDRAWAL_TIMESTAMP</code>' ) );
					em_options_input_text( __( 'Notify admin email(s)', 'events-manager' ), 'dbem_eu_withdrawal_admin_email', __( 'Comma-separated address(es) notified of each withdrawal for manual review. Leave blank to use the site admin email.', 'events-manager' ) );
					?>
					<tr class="em-header"><td colspan="2"><h4><?php esc_html_e( 'Your withdrawal policy text', 'events-manager' ); ?></h4></td></tr>
					<?php
					em_options_textarea( __( 'Withdrawal policy / instructions', 'events-manager' ), 'dbem_eu_withdrawal_policy', __( 'Your own legal withdrawal policy and model withdrawal form, shown on the withdrawal page. Events Manager does not generate legal text — paste your own from your legal adviser.', 'events-manager' ) );
					echo '<tr><th>&nbsp;</th><td><p class="submit" style="margin:0; padding:0; text-align:right;"><input type="submit" class="button-primary" name="Submit" value="' . esc_attr__( 'Save Changes', 'events-manager' ) . '" /></p></td></tr>';
					?>
				</table>
			</div>
		</div>
		<?php
	}

	/**
	 * Render a settings text field that shows its default as a placeholder. The stored option stays empty unless the operator types an override, so the locale-aware default still resolves at runtime.
	 */
	protected static function field_text( $title, $name, $placeholder = '', $description = '' ) {
		?>
		<tr valign="top" id="<?php echo esc_attr( $name ); ?>_row">
			<th scope="row"><?php echo esc_html( $title ); ?></th>
			<td>
				<input type="text" name="<?php echo esc_attr( $name ); ?>" id="<?php echo esc_attr( $name ); ?>" value="<?php echo esc_attr( get_option( $name ) ); ?>" size="45" placeholder="<?php echo esc_attr( $placeholder ); ?>">
				<?php if ( $description ) : ?><br><em><?php echo wp_kses( $description, array( 'code' => array() ) ); ?></em><?php endif; ?>
			</td>
		</tr>
		<?php
	}

	/**
	 * Render a settings textarea that shows its default as a placeholder, leaving the stored option empty so the runtime default still applies.
	 */
	protected static function field_textarea( $title, $name, $placeholder = '', $description = '' ) {
		?>
		<tr valign="top" id="<?php echo esc_attr( $name ); ?>_row">
			<th scope="row"><?php echo esc_html( $title ); ?></th>
			<td>
				<textarea name="<?php echo esc_attr( $name ); ?>" id="<?php echo esc_attr( $name ); ?>" rows="6" placeholder="<?php echo esc_attr( $placeholder ); ?>"><?php echo esc_textarea( get_option( $name ) ); ?></textarea>
				<?php if ( $description ) : ?><br><em><?php echo wp_kses( $description, array( 'code' => array() ) ); ?></em><?php endif; ?>
			</td>
		</tr>
		<?php
	}

	/* -------------------------------------------------------------------------
	 *  Front-end withdrawal flow
	 * ---------------------------------------------------------------------- */

	/**
	 * [em_withdrawal_form] — renders the guest-accessible withdrawal flow and processes its submissions. Returns empty for visitors when the feature is disabled (admins see a hint).
	 *
	 * @return string
	 */
	public static function shortcode( $atts = array() ) {
		if ( ! self::is_enabled() ) {
			return current_user_can( 'manage_options' ) ? '<p>' . esc_html__( 'The right-of-withdrawal feature is currently disabled in Events Manager settings.', 'events-manager' ) . '</p>' : '';
		}
		$view = self::handle();
		ob_start();
		em_locate_template( 'templates/withdrawal-form.php', true, array( 'view' => $view ) );
		return ob_get_clean();
	}

	/**
	 * Resolve the current step of the flow and process any submission, returning a view array the template renders from.
	 *
	 * @return array
	 */
	protected static function handle() {
		$view = array(
			'step'       => 'request',
			'errors'     => array(),
			'reference'  => '',
			'email'      => '',
			'labels'     => self::labels(),
			'policy'     => (string) get_option( 'dbem_eu_withdrawal_policy' ),
			'action_url' => self::page_url(),
		);
		if ( isset( $_GET['em_wd'] ) && $_GET['em_wd'] === 'access' ) {
			return self::handle_access( $view );
		}
		if ( strtoupper( $_SERVER['REQUEST_METHOD'] ?? 'GET' ) === 'POST' && ! empty( $_POST['em_wd_action'] ) ) {
			switch ( sanitize_key( wp_unslash( $_POST['em_wd_action'] ) ) ) {
				case 'lookup':
					return self::handle_lookup( $view );
				case 'select':
					return self::handle_select( $view );
				case 'confirm':
					return self::handle_confirm( $view );
			}
		}
		return $view;
	}

	/**
	 * Step 1: validate the supplied booking reference against the email and move to the confirmation step. (The reference-less magic-link path is added in a later increment.)
	 */
	protected static function handle_lookup( $view ) {
		if ( ! wp_verify_nonce( $_POST['em_wd_nonce'] ?? '', 'em_wd_lookup' ) ) {
			$view['errors'][] = __( 'Your session expired, please try again.', 'events-manager' );
			return $view;
		}
		// Honeypot — a genuine user leaves this empty.
		if ( ! empty( $_POST['em_wd_hp'] ) ) {
			return $view;
		}
		$reference = sanitize_text_field( wp_unslash( $_POST['em_wd_reference'] ?? '' ) );
		$email     = sanitize_email( wp_unslash( $_POST['em_wd_email'] ?? '' ) );
		$view['reference'] = $reference;
		$view['email']     = $email;
		if ( ! is_email( $email ) ) {
			$view['errors'][] = __( 'Please enter a valid email address.', 'events-manager' );
			return $view;
		}
		if ( $reference === '' ) {
			// Path B: no reference supplied, so email a secure magic link instead. The response is identical whether or not bookings exist, to avoid disclosing which emails have bookings.
			self::send_access_link( $email );
			$view['step'] = 'sent';
			return $view;
		}
		// Only the unguessable booking UUID proves the visitor holds the booking. A sequential booking ID plus a known email does not, so it gets the emailed link, with the same response as a blank reference.
		$reference = strtolower( $reference );
		if ( ! preg_match( '/^[a-f0-9]{32}$/', $reference ) ) {
			self::send_access_link( $email );
			$view['step'] = 'sent';
			return $view;
		}
		$EM_Booking = em_get_booking( $reference );
		if ( ! is_object( $EM_Booking ) || ! hash_equals( (string) $EM_Booking->booking_uuid, $reference ) || ! self::booking_matches( $EM_Booking, $email ) ) {
			$view['errors'][] = __( 'We could not find a booking matching that reference and email address. Please check both and try again.', 'events-manager' );
			return $view;
		}
		$view['step']    = 'confirm';
		$view['booking'] = $EM_Booking;
		$view['token']   = self::issue_confirm_token( $EM_Booking, $email );
		return $view;
	}

	/**
	 * Step 2: the consumer has confirmed. Record the declaration of withdrawal — the statement text plus the exact receipt timestamp — against the booking, then show the acknowledgment. (Emailing the acknowledgment and notifying the admin are wired in a later increment.)
	 */
	protected static function handle_confirm( $view ) {
		if ( ! wp_verify_nonce( $_POST['em_wd_nonce'] ?? '', 'em_wd_confirm' ) ) {
			$view['errors'][] = __( 'Your session expired, please try again.', 'events-manager' );
			return $view;
		}
		// The booking and email come from the token issued once the visitor proved they hold the booking, never from the posted fields, so this step can't be driven directly with a guessed booking ID.
		$token = preg_replace( '/[^a-f0-9]/', '', (string) ( $_POST['em_wd_token'] ?? '' ) );
		$data  = $token !== '' ? get_transient( 'em_wd_cf_' . $token ) : false;
		if ( ! is_array( $data ) || empty( $data['booking_id'] ) || empty( $data['email'] ) ) {
			$view['errors'][] = __( 'We could not verify that booking. Please start again.', 'events-manager' );
			return $view;
		}
		$booking_id = (int) $data['booking_id'];
		$email      = $data['email'];
		$reason     = sanitize_textarea_field( wp_unslash( $_POST['em_wd_reason'] ?? '' ) );
		$EM_Booking = em_get_booking( $booking_id );
		if ( ! self::booking_matches( $EM_Booking, $email ) ) {
			$view['errors'][] = __( 'We could not verify that booking. Please start again.', 'events-manager' );
			return $view;
		}
		delete_transient( 'em_wd_cf_' . $token );
		$timestamp = current_time( 'mysql' );
		$statement = self::build_statement( $EM_Booking, $email, $reason );
		$record    = array(
			'statement'     => $statement,
			'timestamp'     => $timestamp,
			'email'         => $email,
			'reason'        => $reason,
			'ip'            => self::client_ip(),
			'within_period' => self::within_period( $EM_Booking ),
		);
		$EM_Booking->update_meta( 'withdrawal', $record );
		self::send_notifications( $EM_Booking, $record );
		do_action( 'em_withdrawal_received', $EM_Booking, $record );
		$view['step']      = 'done';
		$view['booking']   = $EM_Booking;
		$view['statement'] = $statement;
		$view['timestamp'] = $timestamp;
		return $view;
	}

	/* ----- helpers ----- */

	/**
	 * True when $EM_Booking is a real booking whose on-file email matches $email (case-insensitive). Works for guest bookings, whose email lives in the registration meta and surfaces on the person object.
	 */
	protected static function booking_matches( $EM_Booking, $email ) {
		if ( ! is_object( $EM_Booking ) || empty( $EM_Booking->booking_id ) || ! is_email( $email ) ) {
			return false;
		}
		$booking_email = $EM_Booking->get_person()->user_email;
		return strtolower( trim( (string) $booking_email ) ) === strtolower( trim( $email ) );
	}

	/**
	 * Issue a single-use, one-hour token that lets the confirmation step record a withdrawal for this booking only.
	 */
	protected static function issue_confirm_token( $EM_Booking, $email ) {
		$token = bin2hex( random_bytes( 16 ) );
		set_transient( 'em_wd_cf_' . $token, array( 'booking_id' => (int) $EM_Booking->booking_id, 'email' => $email ), HOUR_IN_SECONDS );
		return $token;
	}

	/**
	 * The email-keyed magic-link record for a hash and token pair, or false if the link is unknown, expired or doesn't match.
	 */
	protected static function access_data( $u, $t ) {
		$u    = preg_replace( '/[^a-f0-9]/', '', (string) $u );
		$t    = preg_replace( '/[^a-f0-9]/', '', (string) $t );
		$data = $u !== '' ? get_transient( 'em_wd_token_' . $u ) : false;
		if ( ! is_array( $data ) || empty( $data['token'] ) || empty( $data['email'] ) || ! hash_equals( $data['token'], $t ) ) {
			return false;
		}
		return $data;
	}

	/**
	 * Whether the booking is still inside the configured withdrawal window, measured from when it was made. Late submissions are still recorded — this flag just lets the operator and notifications distinguish them.
	 */
	protected static function within_period( $EM_Booking ) {
		$made = ! empty( $EM_Booking->booking_date ) ? strtotime( $EM_Booking->booking_date ) : false;
		if ( ! $made ) {
			return true;
		}
		return ( time() - $made ) <= ( self::period_days() * DAY_IN_SECONDS );
	}

	/**
	 * Build the plain-text declaration of withdrawal that is recorded and reproduced verbatim in the acknowledgment.
	 */
	protected static function build_statement( $EM_Booking, $email, $reason = '' ) {
		$event = $EM_Booking->get_event();
		$name  = $EM_Booking->get_person()->get_name();
		$lines = array();
		$lines[] = sprintf( __( 'I hereby withdraw from the contract for the following booking: %1$s (#%2$d).', 'events-manager' ), $event ? $event->event_name : '', $EM_Booking->booking_id );
		$lines[] = sprintf( __( 'Name: %s', 'events-manager' ), $name );
		$lines[] = sprintf( __( 'Email: %s', 'events-manager' ), $email );
		if ( $reason !== '' ) {
			$lines[] = sprintf( __( 'Note: %s', 'events-manager' ), $reason );
		}
		return implode( "\n", $lines );
	}

	/**
	 * The resolved, display-ready labels for the templates.
	 */
	protected static function labels() {
		return array(
			'button'  => self::label( 'button' ),
			'confirm' => self::label( 'confirm' ),
			'heading' => self::label( 'heading' ),
		);
	}

	/**
	 * URL of the configured withdrawal page (the form posts to itself, and magic links point here). Empty string if no page is configured, in which case the form posts to the current URL.
	 */
	public static function page_url() {
		$page_id = self::page_id();
		return ( $page_id && get_post_status( $page_id ) ) ? get_permalink( $page_id ) : '';
	}

	/**
	 * Inject a prominent, site-wide footer link to the withdrawal page, since the law expects the withdrawal function to be continuously and easily reachable from anywhere on the site. Only shown when enabled, opted-in, and a withdrawal page is configured.
	 */
	public static function footer_link() {
		if ( is_admin() || ! self::is_enabled() || ! get_option( 'dbem_eu_withdrawal_footer_link' ) ) {
			return;
		}
		$url = self::page_url();
		if ( $url === '' ) {
			return;
		}
		printf(
			'<div class="em-withdrawal-footer-link" style="text-align:center;padding:1em;"><a href="%1$s">%2$s</a></div>',
			esc_url( $url ),
			esc_html( self::label( 'button' ) )
		);
	}

	/**
	 * Best-effort client IP for the audit record.
	 */
	protected static function client_ip() {
		return isset( $_SERVER['REMOTE_ADDR'] ) ? sanitize_text_field( wp_unslash( $_SERVER['REMOTE_ADDR'] ) ) : '';
	}

	/* -------------------------------------------------------------------------
	 *  Path B — magic-link guest access
	 * ---------------------------------------------------------------------- */

	/**
	 * Email a secure, single-use magic link that lets the consumer pick their booking without knowing its reference. The link is keyed to a 24h transient named by a hash of the email (so guest, account-less bookings can be found), with light per-email and per-IP rate limiting in lieu of a CAPTCHA. Callers must show an identical "sent" message regardless of outcome to avoid email enumeration.
	 */
	protected static function send_access_link( $email ) {
		$email = strtolower( trim( $email ) );
		if ( ! is_email( $email ) ) {
			return;
		}
		$hash = hash( 'sha256', $email );
		// Rate limit per-email and per-IP, silently dropping once exceeded.
		$email_rl = 'em_wd_rl_' . $hash;
		if ( (int) get_transient( $email_rl ) >= 3 ) {
			return;
		}
		set_transient( $email_rl, (int) get_transient( $email_rl ) + 1, HOUR_IN_SECONDS );
		$ip_rl = 'em_wd_rlip_' . md5( self::client_ip() );
		if ( (int) get_transient( $ip_rl ) >= 10 ) {
			return;
		}
		set_transient( $ip_rl, (int) get_transient( $ip_rl ) + 1, HOUR_IN_SECONDS );
		// Only actually send if there is something to manage; the caller's message doesn't change either way.
		if ( ! self::find_bookings_by_email( $email ) ) {
			return;
		}
		$token = bin2hex( random_bytes( 16 ) );
		set_transient( 'em_wd_token_' . $hash, array( 'token' => $token, 'email' => $email ), DAY_IN_SECONDS );
		$base = self::page_url();
		if ( $base === '' ) {
			$base = home_url( strtok( $_SERVER['REQUEST_URI'] ?? '/', '?' ) );
		}
		$link    = add_query_arg( array( 'em_wd' => 'access', 'u' => $hash, 't' => $token ), $base );
		$subject = self::email_default( 'link_subject' );
		$body    = str_replace( '#_WITHDRAWAL_LINK', $link, self::email_default( 'link_body' ) );
		global $EM_Mailer;
		if ( ! is_object( $EM_Mailer ) ) {
			$EM_Mailer = new EM_Mailer();
		}
		$EM_Mailer->send( $subject, $body, $email );
	}

	/**
	 * Magic-link return: validate the token against its email-keyed transient and, if good, present the consumer's bookings to choose from.
	 */
	protected static function handle_access( $view ) {
		$u    = isset( $_GET['u'] ) ? preg_replace( '/[^a-f0-9]/', '', $_GET['u'] ) : '';
		$t    = isset( $_GET['t'] ) ? preg_replace( '/[^a-f0-9]/', '', $_GET['t'] ) : '';
		$data = self::access_data( $u, $t );
		if ( ! $data ) {
			$view['errors'][] = __( 'This link is invalid or has expired. Please request a new one.', 'events-manager' );
			return $view;
		}
		$email    = $data['email'];
		$bookings = self::find_bookings_by_email( $email );
		if ( empty( $bookings ) ) {
			$view['errors'][] = __( 'We could not find any active bookings for your email address.', 'events-manager' );
			return $view;
		}
		$view['step']     = 'select';
		$view['email']    = $email;
		$view['bookings'] = $bookings;
		$view['access']   = array( 'u' => $u, 't' => $t );
		return $view;
	}

	/**
	 * The consumer picked a booking from the magic-link list; move to the shared confirmation step. The chosen booking is re-validated against the link-verified email.
	 */
	protected static function handle_select( $view ) {
		if ( ! wp_verify_nonce( $_POST['em_wd_nonce'] ?? '', 'em_wd_select' ) ) {
			$view['errors'][] = __( 'Your session expired, please try again.', 'events-manager' );
			return $view;
		}
		// Re-check the magic link itself so a booking can only be picked from the list the link-verified email owns.
		$data       = self::access_data( $_POST['em_wd_u'] ?? '', $_POST['em_wd_t'] ?? '' );
		$booking_id = absint( $_POST['em_wd_booking_id'] ?? 0 );
		$bookings   = $data ? self::find_bookings_by_email( $data['email'] ) : array();
		if ( empty( $bookings[ $booking_id ] ) ) {
			$view['errors'][] = __( 'We could not verify that booking. Please start again.', 'events-manager' );
			return $view;
		}
		$EM_Booking      = $bookings[ $booking_id ];
		$view['step']    = 'confirm';
		$view['booking'] = $EM_Booking;
		$view['token']   = self::issue_confirm_token( $EM_Booking, $data['email'] );
		return $view;
	}

	/**
	 * Find a consumer's withdrawable bookings by email, covering account bookings (matched on the user id) and guest/account-less bookings (matched on the registration email stored in the serialized booking meta). Already cancelled (3) and rejected (2) bookings are excluded, and each candidate is re-checked with booking_matches so a coincidental meta hit can't leak.
	 *
	 * @return EM_Booking[] keyed by booking_id
	 */
	protected static function find_bookings_by_email( $email ) {
		global $wpdb;
		$email = strtolower( trim( $email ) );
		if ( ! is_email( $email ) ) {
			return array();
		}
		$ids  = array();
		$user = get_user_by( 'email', $email );
		if ( $user ) {
			$ids = array_merge( $ids, $wpdb->get_col( $wpdb->prepare( 'SELECT booking_id FROM ' . EM_BOOKINGS_TABLE . ' WHERE person_id=%d', $user->ID ) ) );
		}
		$ids = array_merge( $ids, $wpdb->get_col( $wpdb->prepare( 'SELECT booking_id FROM ' . EM_BOOKINGS_TABLE . ' WHERE booking_meta LIKE %s', '%' . $wpdb->esc_like( $email ) . '%' ) ) );
		$ids = array_values( array_unique( array_map( 'intval', $ids ) ) );
		$bookings = array();
		foreach ( $ids as $id ) {
			$EM_Booking = em_get_booking( $id );
			if ( is_object( $EM_Booking ) && $EM_Booking->booking_id && ! in_array( (int) $EM_Booking->booking_status, array( 2, 3 ), true ) && self::booking_matches( $EM_Booking, $email ) ) {
				$bookings[ $id ] = $EM_Booking;
			}
		}
		return $bookings;
	}

	/* -------------------------------------------------------------------------
	 *  Notifications
	 * ---------------------------------------------------------------------- */

	/**
	 * Send the legally-required acknowledgment of receipt to the consumer (durable medium = email, reproducing the withdrawal statement and the exact receipt timestamp, confirming receipt only) and a notification to the operator for manual review. The two withdrawal placeholders are substituted first so they reach the email verbatim; the remaining booking placeholders are then resolved by EM's own output().
	 */
	protected static function send_notifications( $EM_Booking, $record ) {
		global $EM_Mailer;
		if ( ! is_object( $EM_Mailer ) ) {
			$EM_Mailer = new EM_Mailer();
		}
		$search  = array( '#_WITHDRAWAL_STATEMENT', '#_WITHDRAWAL_TIMESTAMP' );
		$replace = array( $record['statement'], $record['timestamp'] );
		// Acknowledgment of receipt to the consumer.
		$subject = $EM_Booking->output( str_replace( $search, $replace, self::ack_subject() ), 'raw' );
		$body    = $EM_Booking->output( str_replace( $search, $replace, self::ack_body() ), 'email' );
		$EM_Mailer->send( $subject, $body, $record['email'] );
		// Notification to the operator, who reviews validity and actions any refund manually.
		$admin = trim( (string) get_option( 'dbem_eu_withdrawal_admin_email' ) );
		if ( $admin === '' ) {
			$admin = get_option( 'admin_email' );
		}
		if ( $admin ) {
			$within     = $record['within_period'] ? __( 'within the withdrawal period', 'events-manager' ) : __( 'AFTER the withdrawal period — please review carefully', 'events-manager' );
			$admin_link = $EM_Booking->output( '#_BOOKINGADMINURL', 'raw' );
			$asubject   = sprintf( __( 'Withdrawal received for booking #%d', 'events-manager' ), $EM_Booking->booking_id );
			$abody      = $record['statement'] . "\n\n"
				. sprintf( __( 'Received: %s', 'events-manager' ), $record['timestamp'] ) . "\n"
				. sprintf( __( 'Status: %s', 'events-manager' ), $within ) . "\n"
				. sprintf( __( 'Email: %s', 'events-manager' ), $record['email'] ) . "\n"
				. sprintf( __( 'IP: %s', 'events-manager' ), $record['ip'] ) . "\n\n"
				. sprintf( __( 'Manage booking: %s', 'events-manager' ), $admin_link );
			$EM_Mailer->send( $asubject, $abody, $admin );
		}
	}
}

EM_Withdrawal::init();
