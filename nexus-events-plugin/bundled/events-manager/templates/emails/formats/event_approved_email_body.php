<?php echo sprintf(__("Dear %s", 'events-manager'), '#_CONTACTNAME'); ?>


<?php esc_html_e('Your event #_EVENTNAME on #_EVENTDATES has been approved.', 'events-manager'); ?>


{not_recurring}<?php esc_html_e('You can view your event here:', 'events-manager'); ?> #_EVENTURL{/not_recurring}