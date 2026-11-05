<?php
/* @var EM_Event $EM_Event */
/* @var $args */
/* @var $calendar */
echo $EM_Event->output( $EM_Event->get_option('dbem_calendar_preview_tooltip_event_format') );