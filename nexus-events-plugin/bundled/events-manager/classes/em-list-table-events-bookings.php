<?php
namespace EM\List_Table;
use EM\List_Table;
use EM_Events, EM_Event, EM_Location;

//Builds a table of bookings, still work in progress...
class Events_Bookings extends List_Table {
	public static $basename = 'em_events_bookings_table';
	public static $cols_allowed_html = array('event_name', 'event_name_summary');
	public static $show_responsive_meta = false;
	
	public $cols = array('event_name_summary','event_datetimes');
	public $id = 'em-events-bookings-table';
	public $orderby = 'event_start';
	
	public $event;
	public $item_type;

	public static $has_filters = true;
	public static $filter_vars = [
		'event' => [
			'param' => 'event_id',
			'default' => '',
		],
		'scope' => [ 'default' => 'all' ],
		'search' => [
			'param' => 'em_search',
			'default' => '',
		],
	];
	
	public static $export_action = 'export_events_bookings_csv';
	
	public function load_columns () {
		//build template of possible collumns
		$this->cols_template = apply_filters('em_events_bookings_table_cols_template', array(
			'event_name' => __('Event Name', 'events-manager'),
			'event_name_summary' => __('Event Summary', 'events-manager'),
			'event_dates'=>__('Event Date(s)','events-manager'),
			'event_times'=>__('Event Time(s)','events-manager'),
			'event_datetimes'=>__('Date and Time','events-manager'),
			'booked_spaces'=>__('Booked Spaces','events-manager'),
			'booked_available_spaces' => __('Booked/Available', 'events-manager'),
			'pending_spaces'=>__('Pending Spaces','events-manager'),
		), $this);
		$this->cols_template_groups = apply_filters('em_events_bookings_table_cols_template_groups', array(
			'event'=> array(
				'label' => __('Event','events-manager'),
				'fields' => array('event_name', 'event_dates', 'event_times', 'event_datetimes'),
			),
			'booking' => array(
				'label' => __('Booking Data','events-manager'),
				'fields' => array('booked_spaces',  'pending_spaces', 'booked_available_spaces'),
			),
		), $this);
	}
	
	protected function get_items() {
		//Do the search
		$owner = !current_user_can('manage_others_bookings') ? get_current_user_id() : false;
		// tweak ordrerby for some columns as they are not in the events table
		$sortable_cols = $this->get_sortable_columns();
		$orderby = $this->orderby;
		if( !empty($sortable_cols[$this->orderby]) ) {
			$orderby = $sortable_cols[$this->orderby][0];
		}
		$args = [ 'search' => $this->filters['search'], 'scope'=>$this->filters['scope'], 'limit'=>$this->limit, 'offset' => $this->offset, 'order'=>$this->order, 'orderby'=> $orderby, 'bookings'=>true, 'owner' => $owner, 'pagination' => 1 ];
		if ( !empty( $this->filters['event'] ) ) {
			$EM_Event = em_get_event( $this->filters['event'] );
			if ( $EM_Event->is_recurring() ) {
				$args['recurring_event'] = $EM_Event->event_id;
			}
		}
		$events = EM_Events::get( $args );
		$this->total_items = EM_Events::$num_rows_found;
		//Prepare data
		return $events;
	}
	
	
	/**
	 * Define the sortable columns
	 *
	 * @return array
	 */
	public function get_sortable_columns(){
		$fields = EM_Events::get_sql_accepted_fields();
		$sortable_cols = array(
			'event_name' => array('event_name', false),
			'event_dates' => array('event_start', 'desc'),
			'event_times' => array('event_start_time', false),
			'event_datetimes' => array('event_start', 'desc'),
			'event_name_summary' => array('event_name', false),
		);
		foreach( $fields as $field => $col ){
			if( empty($sortable_cols[$field]) ) {
				$sortable_cols[ $field ] = array( $field, false );
			}
		}
		// some specific fields that still map
		$sortable_cols['event_date'] = array('event_start', false);
		return apply_filters('em_events_bookings_table_get_sortable_columns', $sortable_cols, $this);
	}
	
	/**
	 *
	 * @param EM_Event $item
	 * @param $col
	 *
	 * @return string
	 */
	public function default_column_data ( $item, $col ) {
		$EM_Event = $item;
		$val = '';
		if( $col == 'event_name'){
			if( $this->format == 'html' ){
				$val = $EM_Event->output( '#_BOOKINGSLINK' );
			}else{
				$val = $EM_Event->event_name;
			}
		}elseif( $col == 'event_name_summary'){
			if( $this->format == 'html' ){
				$val = '<strong><a href="' . $EM_Event->get_bookings_url() . '">' . esc_html($EM_Event->event_name)  . '</a></strong> - ' . esc_html__('Booked Spaces','events-manager') . ': ' . $EM_Event->get_bookings()->get_booked_spaces();
				if ( !$EM_Event->has_timeslots() ) {
					// only add 'out of' if this isn't a timeslotted event, since capacities may be per timeslot
					$val .=  '/' . $EM_Event->get_spaces();
				}
				if( em_get_option('dbem_bookings_approval') == 1 ) {
					$val .=  ' | ' . esc_html__('Pending','events-manager') . ': ' . $EM_Event->get_bookings()->get_pending_spaces();
				}
			}else{
				$val = $EM_Event->event_name;
			}
		}elseif( $col == 'booked_available_spaces'){
			$val = $EM_Event->get_bookings()->get_booked_spaces()."/".$EM_Event->get_spaces();
		}elseif( $col == 'booked_spaces'){
			$val = $EM_Event->get_bookings()->get_booked_spaces();
		}elseif( $col == 'pending_spaces'){
			$val = $EM_Event->get_bookings()->get_pending_spaces();
		} elseif ( $col === 'event_datetimes' ) {
			$val = $EM_Event->output_dates(false, " - "). ' @ ' . $EM_Event->output_times(false, ' - ');
			if ( $EM_Event->has_timeslots() ) {
				$val .= ' <span class="em-icon s-15 em-icon-info em-tooltip" aria-label="'. esc_html__('Multiple Timeslots','events-manager') .'"></span>';
			}
		} elseif ( $col === 'event_dates' ) {
			$val = $EM_Event->output_dates(false, " - ");
		} elseif ( $col === 'event_times' ) {
			$val = $EM_Event->output_times(false, ' - ');
		}
		return $val;
	}
	
	public function extra_tablenav( $which ) {
		if ( $which != 'top' ) {
			parent::extra_tablenav( $which );
			return null;
		}
		$id = esc_attr($this->id);
		?>
		<div class="alignleft actions filters em-list-table-filters <?php echo $id; ?>-filters <?php if ( !static::$show_filters ) echo 'hidden'; ?>">
			<?php if ( empty($this->filters['event']) ): ?>
			<input name="em_search" type="text" class="inline <?php echo $id; ?>-filter" placeholder="<?php echo esc_attr( sprintf( __('Search %s', 'events-manager'), __('Events', 'events-manager') ) ); ?> ..." value="<?php echo esc_attr($this->filters['search']);?>">
			<?php endif; ?>
			<select name="scope" class="<?php echo $id; ?>-filter">
				<?php
					foreach ( em_get_scopes() as $key => $value ) {
						$selected = "";
						if ($key == $this->filters['scope'])
							$selected = "selected='selected'";
						echo "<option value='".esc_attr($key)."' $selected>".esc_html($value)."</option>  ";
					}
				?>
			</select>
			<?php do_action('em_events_bookings_table_output_table_filters', $this); ?>
			<input name="pno" type="hidden" value="1">
			<?php if ( $this->filters['event'] ) : ?>
			<input name="event_id" type="hidden" value="<?php echo esc_attr($this->filters['event']) ?>">
			<?php endif; ?>
			<input id="post-query-submit" class="button-secondary" type="submit" value="<?php esc_attr_e( 'Filter' ); ?>">
		</div>
		<?php parent::extra_tablenav( $which ); ?>
		<?php
	}
}
Events_Bookings::init();
?>