<?php
namespace EM\Notifications;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Sends messages through Expo's push service (https://docs.expo.dev/push-notifications/sending-notifications/). The app is an Expo build, so this abstracts APNs/FCM behind one HTTPS POST that any WordPress host can make with wp_remote_post.
 *
 * Deliberately NO shared Expo access token: in this distributed model (every customer site sends its own pushes) a per-account token on every site would let one compromised site spam every app user. Per-device Expo tokens cap the blast radius to a single site's registered devices, and the payload carries no personal data — just the event name and ids, with the app fetching detail over its authenticated REST connection.
 */
class Expo {

	const ENDPOINT  = 'https://exp.host/--/api/v2/push/send';
	const BATCH_SIZE = 100; // Expo accepts up to 100 messages per request.

	/**
	 * Send a list of messages. Each is array( 'to' => ExpoToken, 'title' => ..., 'body' => ..., 'data' => array ). Returns nothing; tokens the service reports as permanently dead are pruned from the registry so they aren't retried.
	 */
	public static function send( array $messages ) {
		$messages = array_values( array_filter( $messages, function ( $m ) {
			return ! empty( $m['to'] ) && self::is_expo_token( $m['to'] );
		} ) );
		if ( empty( $messages ) ) {
			return;
		}
		foreach ( array_chunk( $messages, self::BATCH_SIZE ) as $batch ) {
			self::send_batch( $batch );
		}
	}

	protected static function send_batch( array $batch ) {
		$response = wp_remote_post( self::ENDPOINT, array(
			'timeout' => 15,
			'headers' => array(
				'Accept'           => 'application/json',
				'Accept-Encoding'  => 'gzip, deflate',
				'Content-Type'     => 'application/json',
			),
			'body'    => wp_json_encode( $batch ),
		) );
		if ( is_wp_error( $response ) ) {
			return; // transient network failure — the next launch/booking re-reports; nothing to prune.
		}
		$body = json_decode( wp_remote_retrieve_body( $response ), true );
		if ( ! is_array( $body ) || empty( $body['data'] ) || ! is_array( $body['data'] ) ) {
			return;
		}
		// Tickets come back positionally aligned with the batch we sent. A DeviceNotRegistered error means the user uninstalled or disabled notifications, so the token is dead — prune it.
		foreach ( $body['data'] as $i => $ticket ) {
			if ( isset( $ticket['status'], $batch[ $i ]['to'] ) && 'error' === $ticket['status'] ) {
				$error = isset( $ticket['details']['error'] ) ? $ticket['details']['error'] : '';
				if ( 'DeviceNotRegistered' === $error ) {
					Devices::prune( $batch[ $i ]['to'] );
				}
			}
		}
	}

	/** Expo tokens look like ExponentPushToken[xxxxxxxx] or ExpoPushToken[xxxxxxxx]; reject anything else before hitting the network. */
	public static function is_expo_token( $token ) {
		return is_string( $token ) && (bool) preg_match( '/^Expo(nent)?PushToken\[[^\]]+\]$/', $token );
	}
}
