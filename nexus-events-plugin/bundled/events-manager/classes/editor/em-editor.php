<?php
/**
 * Events Manager — editor system loader.
 *
 * Loads the namespaced \EM\Editor\* classes (registry base + Event/Location registries + the layout controller) and boots the controller. Included from events-manager.php.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

require_once __DIR__ . '/em-editor-tabs.php';
require_once __DIR__ . '/em-editor-event.php';
require_once __DIR__ . '/em-editor-location.php';
require_once __DIR__ . '/em-editor-controller.php';

\EM\Editor\Editor::init();
