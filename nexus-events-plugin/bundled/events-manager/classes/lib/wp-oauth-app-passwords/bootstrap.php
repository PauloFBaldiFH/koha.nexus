<?php
/**
 * Bootstrap for the winning copy of the library.
 *
 * Required once by loader.php for the highest registered version only. Guards on
 * class existence so a second invocation (or a same-version sibling copy) is a
 * no-op. All internal references use __NAMESPACE__ / ::class so the namespace
 * can be renamed — or removed entirely — by editing only the `namespace`
 * declarations and `use` statements.
 *
 * @package Pixelite\OAuth_App_Passwords
 */

namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

// If any copy already booted the classes, stand down.
if ( class_exists( __NAMESPACE__ . '\\Server' ) ) {
	return;
}

$dir = defined( 'PIXELITE_OAUTH_APP_PASSWORDS_DIR' ) ? PIXELITE_OAUTH_APP_PASSWORDS_DIR : __DIR__;

require_once $dir . '/src/Support.php';
require_once $dir . '/src/I18n.php';
require_once $dir . '/src/PKCE.php';
require_once $dir . '/src/Clients.php';
require_once $dir . '/src/Codes.php';
require_once $dir . '/src/Grants.php';
require_once $dir . '/src/App_Passwords.php';
require_once $dir . '/src/Scope_Guard.php';
require_once $dir . '/src/Consent.php';
require_once $dir . '/src/Endpoints/Metadata.php';
require_once $dir . '/src/Endpoints/Authorize.php';
require_once $dir . '/src/Endpoints/Token.php';
require_once $dir . '/src/Endpoints/Revoke.php';
require_once $dir . '/src/Endpoints/Register.php';
require_once $dir . '/src/Admin.php';
require_once $dir . '/src/Server.php';

Server::boot();
