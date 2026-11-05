<?php
/*
* This file is called by templates/forms/location-editor.php to display fields for uploading images on your event form on your website. This does not affect the admin featured image section.
* You can override this file by copying it to /wp-content/themes/yourtheme/plugins/events-manager/forms/event/ and editing it there.
*/
global $EM_Event;
/* @var $EM_Event EM_Event */
?>
<div class="em-input-upload em-input-upload-post-image input">
	<label for='event_image'><?php _e('Upload/change picture', 'events-manager') ?></label>
	<?php EM\Uploads\Uploader::post_image_uploader( $EM_Event, 'event-image', 'event_image' ); ?>
</div>