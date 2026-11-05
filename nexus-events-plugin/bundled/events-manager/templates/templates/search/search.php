<?php
// This file will eventually become the mian 'Search'.php entry point, any templates overriding this file previously may have been overriding the file which is now search-text.php, and should rename it subsequently.
$template = em_locate_template('templates/search/search-term.php', false);
include( $template );