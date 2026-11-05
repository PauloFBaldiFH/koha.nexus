<?php
/*
 * This file is called by templates/forms/location-editor.php to display fields for uploading images on your location form on your website. This does not affect the admin featured image section.
* You can override this file by copying it to /wp-content/themes/yourtheme/plugins/events-manager/forms/location/ and editing it there.
*/
global $EM_Location;
/* @var $EM_Location EM_Location */
?>
<div class="em-input-upload em-input-upload-post-image input">
	<label for='location-image'><?php _e('Upload/change picture', 'events-manager') ?></label>
	<?php EM\Uploads\Uploader::post_image_uploader( $EM_Location, 'location-image', 'location_image' ); ?>
</div>
