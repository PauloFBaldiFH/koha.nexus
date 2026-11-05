<?php
namespace EM;

use libphonenumber\PhoneNumberUtil;

/**
 * Implements the libphonenumber PHP library for phone number validation and formatting.
 * This library is an implementation of the Google libphonenumber library.
 */
class Phone {
	
	/**
	 * @return PhoneNumberUtil instance
	 */
	public static function init() {
		if( static::is_enabled() ) {
			add_filter('em_booking_get_person_post', [static::class, 'em_booking_get_person_post'], 10, 3);
			add_filter('em_registration_errors', [static::class, 'em_registration_errors'], 10, 4);
		}
	}
	
	public static function get() {
		include_once( EM_DIR . '/includes/php/autoload.php' );
		return PhoneNumberUtil::getInstance();
	}
	
	/**
	 * Takes a number and parses it as best as possible, including validation before returning the number or false on failure.
	 * If no country code is provided, it adds the default country code, validates and returns the number in full international mode.
	 *
	 * @param string $number
	 *
	 * @return string
	 */
	public static function parse( $number ) {
		try {
			$phoneUtil = static::get();
			if ( !preg_match('/^\+/', $number) ) {
				$phone = $phoneUtil->parse( $number, em_get_option('dbem_phone_default_country') );
			} else {
				$phone = $phoneUtil->parse( $number, em_get_option('dbem_phone_default_country') );
			}
			if( $phoneUtil->isValidNumber( $phone ) ) {
				return $phoneUtil->format($phone, \libphonenumber\PhoneNumberFormat::INTERNATIONAL);
			}
			return false;
		} catch ( \Exception $e ) {
			return false;
		}
	}
	
	/**
	 * Checks if the libphonenumber library is enabled for EM via settings.
	 * @return boolean
	 */
	public static function is_enabled() {
		$enabled_hardcoded = apply_filters( 'em_phone_intl_enabled', !defined('EM_PHONE_INTL_ENABLED') || EM_PHONE_INTL_ENABLED );
		if( is_admin() && !empty($_REQUEST['page']) && $_REQUEST['page'] === 'events-manager-options' && PHP_VERSION_ID >= 80000 ) {
			return true;
		}
		return $enabled_hardcoded && em_get_option('dbem_phone_enabled') && PHP_VERSION_ID >= 80000;
	}
	
	/**
	 * Validates a phone number based on give options, which can override those saved in admin settings.
	 * @param $options
	 *
	 * @return boolean
	 */
	public static function validate( $value, $options = array() ) {
		$phoneUtil = static::get();
		try {
			// Parse against the configured default country, the same region parse() uses, so a stored national-format number (e.g. a value saved before validation was enabled, or an admin profile edit where the E.164 input script hasn't run) validates the way it is displayed instead of throwing for want of a leading "+".
			$region = !empty($options['country']) ? $options['country'] : em_get_option('dbem_phone_default_country');
			$phone = $phoneUtil->parse( $value, $region );
			if ( $phoneUtil->isValidNumber( $phone ) ) {
				return true;
			}
			return false;
		} catch ( \Exception $e ) {
			return false;
		}
	}
	
	/**
	 * Returns a libphonenumber-derived E.164 example for $country (ISO alpha-2),
	 * preferring a mobile sample where available. Falls back to the site's default
	 * phone country and finally to null if libphonenumber is unavailable.
	 *
	 * Surfaced through the REST API's booking-requirements payload so AI clients
	 * (and any other UI) can show a country-tuned example instead of a generic
	 * "5551234567" that fails E.164 validation.
	 *
	 * @param string|null $country ISO 3166-1 alpha-2 (e.g. 'GB'). Falls back to dbem_phone_default_country.
	 * @return string|null E.164 example (e.g. '+447400123456') or null if unobtainable.
	 */
	public static function example_number( $country = null ) {
		if ( !$country ) {
			$country = em_get_option( 'dbem_phone_default_country' );
		}
		$country = $country ? strtoupper( (string) $country ) : '';
		if ( !$country || !static::is_enabled() ) {
			return null;
		}
		try {
			$phoneUtil = static::get();
			$sample = null;
			if ( class_exists( '\\libphonenumber\\PhoneNumberType' ) ) {
				$sample = $phoneUtil->getExampleNumberForType( $country, \libphonenumber\PhoneNumberType::MOBILE );
			}
			if ( !$sample ) {
				$sample = $phoneUtil->getExampleNumber( $country );
			}
			if ( !$sample ) {
				return null;
			}
			return $phoneUtil->format( $sample, \libphonenumber\PhoneNumberFormat::E164 );
		} catch ( \Exception $e ) {
			return null;
		}
	}

	/**
	 * Hooks into pre-registration filter and checks phone number before a user is created in Events Manager
	 * @param \WP_Error $errors
	 * @param string $sanitized_user_login
	 * @param string $user_email
	 * @param array $user_data
	 *
	 * @return false
	 */
	public static function em_registration_errors( $errors, $sanitized_user_login, $user_email, $user_data ) {
		if( !empty($user_data['dbem_phone']) && !static::validate( $user_data['dbem_phone'] ) ) {
			$errors->add( 'invalid_phone', __('Please provide a valid phone number.', 'events-manager') );
		}
		return $errors;
	}
	
	/**
	 * Validates no-user booking data during registration and booking in Events Manager
	 * @param $result
	 * @param $EM_Booking
	 * @param $user_data
	 *
	 * @return false|mixed
	 */
	public static function em_booking_get_person_post( $result, $EM_Booking, $user_data ) {
		if( !empty($user_data['dbem_phone']) && !static::validate( $user_data['dbem_phone'] ) ) {
			$result = false;
			$EM_Booking->add_error( esc_html__('Please provide a valid phone number.', 'events-manager') );
		}
		return $result;
	}
}
Phone::init();