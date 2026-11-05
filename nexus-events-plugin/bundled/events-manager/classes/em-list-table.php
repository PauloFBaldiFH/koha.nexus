<?php
namespace EM {
	use WP_List_Table;
	
	// WP_List_Table is not loaded automatically so we need to load it in our application
	if( ! class_exists( 'WP_List_Table' ) ) {
		require_once( ABSPATH . 'wp-admin/includes/class-wp-list-table.php' );
	}
	
	/**
	 * Create a new table class that will extend the WP_List_Table
	 */
	class List_Table extends WP_List_Table {
		/**
		 * Results of given table search.
		 * @var array[]|\EM_Object[]
		 */
		public $items = array();
		/**
		 * array containing the columns to display, the keys and values would be the column key, information about the column is referred to in $cols_template
		 * @var array
		 */
		public $cols = array();
		/**
		 * Asoociative array of available collumn keys and corresponding headers, which will be used to display this table of items
		 * @var array
		 */
		public $cols_template = array();
		public $cols_template_groups = array();
		public static $cols_allowed_html = array();
		
		/**
		 * Object context we're viewing bookings in relation to, such as events, locations, tickets, etc. used for saving view settings like columns and determining what data to show
		 * @var string
		 */
		public $context;
		public $context_views = array();
		/**
		 * Status filter value, set directly by admin pages before display() on tables that support it (e.g. bookings).
		 * @var string
		 */
		public $status;
		/**
		 * Scope filter value, set directly by admin pages before display() on tables that support it.
		 * @var string
		 */
		public $scope;
		/**
		 * Link/Data for available actions on each row for this table. Populated by self::get_action_data() method.
		 * @var array
		 */
		public $action_data = array();
		
		public static $basename = 'em_list_table';
		public static $template_component_name = 'list-table';
		public static $export_action = 'em_list_table_export';
		public static $export_delimiter = ',';
		/**
		 * Class is in the process of exporting when true. Assume that nonce has been verified once set to true.
		 * @var bool
		 */
		public static $exporting = false;
		/**
		 * Added to the form wrapping the actual list table, use this for unique class names
		 * @var string
		 */
		public static $form_class = '';
		/**
		 * Set to the base name used for a class or unique ID
		 * @var string
		 */
		public $id = 'em-list-table';
		/**
		 * Set to a unique id made up of $this->id dash rand() int during __construct
		 * @var string
		 */
		public $uid = 'em-list-table-0';
		/**
		 * Maximum number of rows to show
		 * @var int
		 */
		public $limit = 20;
		public $order = 'ASC';
		/**
		 * Field to order by default, overriding classes must set this!
		 * @var string
		 */
		public $orderby;
		public $page = 1;
		public $offset = 0;
		public $filters = array();
		
		public $per_page = 20;
		public $total_items = 0;
		public $per_page_var = 'limit';
		/**
		 * Destination output this is intended for, for example html is default, but could be csv, excel, etc.
		 * @var string
		 */
		public $format = 'html';
		/**
		 * Does this table have checkboxes and, therefore, are bulk actions available? If this is overriden with an id (booking_id, event_id etc.) then it is assumed checkboxes and bulk actions are available.
		 * @var bool
		 */
		public $checkbox_id = false;
		/**
		 * Whether results can be exported.
		 * @var bool
		 */
		public static $is_exportable = true;
		/**
		 * Flag for whether this is a frontend or backend table display.
		 * @var bool
		 */
		public static $is_frontend = null;
		/**
		 * Set to true if current class has filters by extending the extra_tablenav() base method. This allows for adding classes to table without using things like ReflectionClass to figure it out.
		 * @var bool
		 */
		public static $has_filters = false;
		/**
		 * If there are filters, child classes can add the post values here and they can be automatically saved in the settings page, otherwise handle them via the set_default_settings() method.
		 * @var array
		 */
		public static $filter_vars = [
			'search' => [
				'param' => 'em_search',
				'default' => '',
			],
			'scope' => [ 'default' => 'future' ]
		];
		/**
		 * Show or hide filters by default
		 * @var bool
		 */
		public static $show_filters = true;
		/**
		 * Show or prevent repeating tablenav at bottom of table, including pagination
		 * @var bool
		 */
		public static $show_bottom_tablenav = true;
		/**
		 * Show or prevent repeating tablenav actions at bottom of table, such as filters and bulk actions. If set to false, bulk actions and filters are ommitted regardless of other settings.
		 * @var bool
		 */
		public static $show_bottom_tablenav_actions = false;
		/**
		 * Show or prevent repeating bulk actions at bottom of table, including settings, export, show/hide filter and expand/collapse (responsive) icons.
		 * @var bool
		 */
		public static $show_bottom_tablenav_bulkactions = true;
		/**
		 * Show or prevent repeating the filters at bottom of table.
		 * @var bool
		 */
		public static $show_bottom_tablenav_extra_tablenav = true;
		/**
		 * Show or prevent repeating the pagination at bottom of table.
		 * @var bool
		 */
		public static $show_bottom_tablenav_pagination = true;
		/*
		 * Show or hide responsive meta line below the primary column line when in responsive mode
		 */
		public static $show_responsive_meta = true;
		
		public function __construct ( $args = array() ) {
			// unique ID
			$this->uid = $this->id . '-' . rand(1,99999);
			
			// load settings, then let query data override
			$this->load_current_context();
			
			//Set basic vars
			$this->order = ( !empty($_REQUEST['order']) && ($_REQUEST['order'] == 'DESC' || $_REQUEST['order'] == 'desc') ) ? 'DESC':'ASC';
			$this->orderby = ( !empty($_REQUEST['orderby']) ) ? sanitize_sql_orderby($_REQUEST['orderby']): $this->orderby;
			if( defined('DOING_AJAX') ) {
				$_GET['order'] = strtolower($this->order); // for WP_List_Table
				$_GET['orderby'] = $this->orderby;
			}
			$this->limit = ( !empty($_REQUEST['limit']) && is_numeric($_REQUEST['limit'])) ? $_REQUEST['limit'] : $this->limit;//Default limit
			$this->page = ( !empty($_REQUEST['pno']) && is_numeric($_REQUEST['pno']) ) ? $_REQUEST['pno']:1;
			$_REQUEST['paged'] = $this->page;
			$this->offset = ( $this->page > 1 ) ? ($this->page-1)*$this->limit : 0;
			
			// Basic Vars for List_Table
			$this->per_page = $this->limit;
			em_list_table_create_funcitions();
			
			// load the columns now
			$this->load_columns();
			
			//calculate collumns if post requests
			if( !empty($_REQUEST['cols']) ){
				$this->cols = array();
				if( is_array($_REQUEST['cols']) ){
					$cols = $_REQUEST['cols'];
				}else{
					$cols = explode(',',$_REQUEST['cols']);
				}
				foreach( $cols as $col ){
					if( array_key_exists($col, $this->cols_template) ){
						$this->cols[$col] = $col;
					}
				}
			}
			
			//save collumns depending on context and user preferences
			if( !empty($_REQUEST['cols']) && !empty($_REQUEST['save']) && wp_verify_nonce($_REQUEST['_emnonce'], static::$basename) ){ //save view settings for next time
				$settings = $this->set_default_settings();
				$this->save_default_settings( $settings );
			}
			
			// parent
			parent::__construct( $args );
			
			$this->constructor();
			
			// do action
			do_action( static::$basename, $this );
			
			// clean any columns from saved views that no longer exist - at this point they shoudl have been added
			foreach($this->cols as $col_key => $col_name){
				if( !is_string($col_name) || !array_key_exists($col_name, $this->cols_template)){
					unset($this->cols[$col_key]);
				}
			}
		}
		
		/**
		 * Fired after __constructor(), so that child classes can overwrite this method and do more just before the static::$basename action is fired.
		 * @return void
		 */
		public function constructor(){}
		
		public function load_columns(){
			_doing_it_wrong( __FUNCTION__, 'This method must be overwritten in child classes', '6.4.11' );
		}
		
		public function __get( $prop ) {
			if ( $prop === 'cols_view' ) {
				return $this->context;
			}
			return parent::__get( $prop );
		}
		
		public function __set( $prop, $value ) {
			if ( $prop === 'cols_view' ) {
				$this->context = $value;
			}
			parent::__set( $prop, $value );
		}
		
		public function __isset ( $prop ) {
			if ( $prop === 'cols_view' ) {
				return isset($this->context);
			}
			return parent::__isset( $prop );
		}
		
		/**
		 * Loads the current context and writes the current settings into the object.
		 *
		 * Child classes should overwrite this method to set the context first, or do it before this function is executed in the constructor.
		 *
		 * @return mixed|null
		 */
		public function load_current_context() {
			// get the actual context
			$settings = $this->get_current_context();
			// set things like limit, cols, etc.
			$this->cols = $settings['cols'] ?? $this->cols;
			$this->limit = absint( $settings['limit'] ?? $this->limit ) ?: 10;
			$this->filters = $settings['filters'] ?? $this->filters;
			$this->orderby = $settings['orderby'] ?? $this->orderby;
			// set default filters - child classes could set them here or after this parent constructor is called
			foreach ( static::$filter_vars as $filter_key => $filter_vars ) {
				$default = false;
				if( is_array($filter_vars) ) {
					$filter_var = $filter_vars['param'] ?? $filter_key; // allows for further expansion such as special filtering etc.
					$default = $filter_vars['default'] ?? false;
					if( !empty($filter_vars['in_array']) ) {
						$in_array = $filter_vars['in_array'];
					}
				} else {
					if ( is_int($filter_key) ) {
						$filter_key = $filter_vars;
					}
					$filter_var = $filter_vars;
				}
				if( isset($_REQUEST[$filter_var]) ) {
					static::$show_filters = true;
				}
				if ( isset($_REQUEST[$filter_var]) ) {
					// check in_array validation
					if( !empty($in_array) ) {
						if( is_array($in_array) && in_array($_REQUEST[$filter_var], $in_array) ) {
							$this->filters[$filter_key] = $_REQUEST[$filter_var];
						} elseif ( !empty($this->{$in_array}) &&  in_array($_REQUEST[$filter_var], $this->{$in_array}) ) {
							$this->filters[$filter_key] = $_REQUEST[$filter_var];
						}
					} elseif( !empty($array_key) ) {
						if ( !empty($this->{$array_key}) &&  array_key_exists($_REQUEST[$filter_var], $this->{$in_array}) ) {
							$this->filters[$filter_key] = $_REQUEST[$filter_var];
						} elseif ( is_array($array_key) && array_key_exists($_REQUEST[$filter_var], $array_key) ) {
							$this->filters[$filter_key] = $_REQUEST[$filter_var];
						}
					} else {
						$this->filters[$filter_key] = sanitize_text_field($_REQUEST[$filter_var]);
					}
				}
				$this->filters[$filter_key] = $this->filters[$filter_key] ?? $default;
			}
			return apply_filters( static::$basename . 'load_current_context', $settings, $this);
		}
		
		public function get_current_context() {
			$default_settings = $this->get_default_settings();
			if ( $this->context ) {
				if ( !empty($default_settings['contexts'][$this->context]) ) {
					$settings = $default_settings['contexts'][$this->context];
				} else {
					$settings = $default_settings;
				}
				$settings['context'] = $this->context;
			} else {
				$settings = $default_settings;
			}
			if( empty($settings['cols']) || !is_array($settings['cols']) ){
				// check if we have template views in place
				$context_default = $this->get_current_context_default();
				$default_cols = $context_default['cols'] ?? $this->cols;
				// load default cols
				$settings = array(
					'cols' => $default_cols,
				);
			}
			// merge current settings into default settings without contexts, so base settings fill out any missing settings (if set)
			$current_context = static::merge_settings( $default_settings, $settings );
			unset( $current_context['contexts'] );
			return apply_filters( 'em_list_table_get_current_context', $current_context, $this);
		}
		
		public function get_current_context_default() {
			if( $this->context && !empty( $this->context_views[ $this->context ] ) ) {
				return $this->context_views[$this->context];
			}
			return false;
		}
		
		public function get_default_settings() {
			$settings = get_user_meta(get_current_user_id(), static::$basename . '_settings', true );
			if( !is_array($settings) ) $settings = array();
			return apply_filters( static::$basename . '_get_default_settings', $settings, $this);
		}
		
		/**
		 * Sets default settings for this table under the current context. If $settings is provided, it is considered the context to be saved under.
		 * Otherwise, the default context settings will be loaded and overwritten with currently loaded settings.
		 *
		 * @param $settings
		 *
		 * @return array
		 */
		public function set_default_settings( $settings = array() ) {
			if ( empty($settings) ) $settings = $this->get_current_context();
			$settings['cols'] = $this->cols;
			$settings['limit'] = $this->limit;
			// if filters are also to be saved, do it here
			if( !empty($_REQUEST['save_filters']) ){
				// go through filters array and save stuff here
				$filters = array();
				foreach ( static::$filter_vars as $filter_key => $filter_var ) {
					if( is_array($filter_var) ) {
						$filter_var = $filter_var['param'] ?? $filter_key; // allows for further expansion such as special filtering etc.
					} elseif ( is_int($filter_key) ) {
						$filter_key = $filter_var;
					}
					if( isset($_REQUEST[$filter_var]) ) {
						$filters[$filter_key] = wp_kses_post_deep($_REQUEST[$filter_var]);
					}
				}
				if( !empty($filters) ) {
					$settings['filters'] = $filters;
				} else {
					unset( $settings['filters'] );
				}
				// save orderby as well
				if( $this->orderby ) {
					$settings['orderby'] = $this->orderby;
				} else {
					unset( $settings['orderby'] );
				}
			}
			return $settings;
		}
		
		public function save_default_settings( $current_settings ) {
			$settings = $this->get_default_settings();
			if ( !empty($current_settings['context']) ) {
				// we're in a context, so we add it to settings as a context
				if ( empty($settings['contexts'] ) ) {
					$settings['contexts'] = array();
				}
				$context = $current_settings['context'];
				$context_settings = $settings['contexts'][$context] ?? array();
				$current_settings = static::merge_settings( $context_settings, $current_settings );
				$current_settings = apply_filters( static::$basename . '_save_default_settings_current', $current_settings, $this );
				unset( $context_settings['contexts'], $current_settings['contexts'], $current_settings['context'] ); // delete any errant or unecessary data
				$settings['contexts'][$context] = $current_settings;
			} else {
				$context = false;
				$current_settings = apply_filters( static::$basename . '_save_default_settings_current', $current_settings, $this );
				$settings = static::merge_settings( $settings, $current_settings );
			}
			$settings = apply_filters( static::$basename . '_save_default_settings_pre', $settings, $current_settings, $this, ['context' => $context] );
			update_user_meta(get_current_user_id(), static::$basename . '_settings', $settings );
			do_action( static::$basename . '_save_default_settings', $settings, $current_settings, $this, ['context' => $context] );
			return $settings;
		}
		
		/**
		 * Merges two settings array together, by either replacing the key value in $default with $settings, or merging within the arrays by replacing equivalent keys in $settings.
		 * The only exception is the cols key which is overwritten by $settings if it exists.
		 *
		 * @param $default
		 * @param $settings
		 *
		 * @return mixed
		 */
		public static function merge_settings ( $default, $settings ) {
			foreach( $settings as $key => $value ) {
				if ( is_array($value) ) {
					// anything but cols gets merged in joining values
					if ( $key !== 'cols' && !empty($default[$key]) && is_array($default[$key]) ) {
						$default[$key] = static::merge_settings( $default[$key], $value );
					} else {
						$default[$key] = $value;
					}
				} else {
					$default[$key] = $value;
				}
			}
			return $default;
		}
		
		public static function get_item_limits() {
			$limits = [ 5, 10, 20, 50, 100 ];
			return apply_filters( static::$basename . '_get_item_limits', $limits );
		}
		
		/* ------------------ Static and AJAX Methods ------------------ */
		
		public static function init(){
			add_action('wp_ajax_'. static::$basename, array( static::class, 'em_ajax_table') );
			add_action('wp_ajax_'. static::$basename .'_row', array( static::class, 'em_ajax_table_row') );
			
			if ( static::$is_exportable ) {
				add_action( 'wp_loaded', array( static::class, 'export_init' ) );
			}
			// determine if we're public or not, can't determine that when doing AJAX
			if( static::$is_frontend === null ){
				static::$is_frontend = !is_admin() || !empty($_REQUEST['is_public']);
			}
		}
		
		/**
		 * Handles AJAX Bookings admin table filtering, view changes and pagination
		 */
		public static function em_ajax_table(){
			if ( !empty($_REQUEST['event_archetype']) ) {
				Archetypes::set_current( $_REQUEST['event_archetype'] );
			}
			if( !empty($_REQUEST['_emnonce']) && check_admin_referer( static::$basename, '_emnonce') ){
				$class_name = static::class;
				$EM_List_Table = new $class_name();
				$EM_List_Table->display();
			}else{
				check_admin_referer(static::$basename);
				$class_name = static::class;
				$EM_List_Table = new $class_name();
				if( !empty($_REQUEST['table_id']) ) { // so modals work linked to the ID
					$EM_List_Table->uid = $EM_List_Table->id . '-' . absint($_REQUEST['table_id']);
				}
				$EM_List_Table->output_table();
			}
			exit();
		}
		
		public static function em_ajax_table_row(){
			if( !empty($_REQUEST['_emnonce']) && check_admin_referer(static::$basename, '_emnonce') && !empty($_REQUEST['row_action']) ){
				static::em_ajax_table_row_action( $_REQUEST['row_action'] );
			}
			exit();
		}
		
		public static function em_ajax_table_row_action( $requested_action ){}
		
		/* ------------------ Bulk and Row action links/options ------------------ */
	
		public function get_action_url( $item ) {
			return esc_url_raw ( add_query_arg( array( 'action' => static::$basename . '_row', 'row_id' => $item->ID ) ) );
		}
		
		public function get_action_data() {
			if( !empty($this->action_data) ) return $this->action_data;
			$actions = $this->get_action_data_items();
			// add confirmation messages context
			foreach( $actions as $action => $action_data ) {
				// get link confirmation messages
				if( isset($action_data['actions']) ) {
					// sub-array of actions
					foreach( $action_data['actions'] as $the_action => $the_action_data ) {
						// get bulk and link confirmation messages - confirmation messages according to context on each action
						$actions[ $action ]['actions'][ $the_action ]['confirm'] = $this->get_action_message( $the_action, $the_action_data['data']['context'] );
						$actions[ $action ]['actions'][ $the_action ]['confirm-bulk'] = $this->get_bulk_action_message( $the_action, $the_action_data['data']['context'] );
					}
				} else {
					$actions[ $action ]['confirm'] = $this->get_action_message( $action, $action_data['data']['context'] );
					$actions[ $action ]['confirm-bulk'] = $this->get_bulk_action_message( $action, $action_data['data']['context'] );
				}
			}
			$this->action_data = apply_filters( static::$basename . '_get_action_data', $actions, $this );
			return $this->action_data;
		}
		
		public function get_action_data_items() {
			$data_template = [ 'action' => static::$basename . '_row', 'context' => $this->context ];
			$actions = [
				'delete' => [
					'label' => __('Delete','events-manager'),
					'data' => array_merge( $data_template, [ 'row_action' => 'delete' ] ),
				],
			];
			return apply_filters( 'em_list_table_get_action_data_items', $actions, $this, ['data_template' => $data_template] );
		}
		
		/**
		 * Gets action data and appends extra data to the 'data' of each action.
		 * @param array $extra_data
		 *
		 * @return array
		 */
		public function get_action_data_extra( $extra_data ) {
			$actions = $this->get_action_data();
			foreach( $actions as $action => $action_data ) {
				if ( isset($action_data['actions']) ) {
					// go one level deeper
					foreach( $action_data['actions'] as $the_action => $the_action_data ) {
						$actions[$action]['actions'][$the_action]['data'] = array_merge( $the_action_data['data'], $extra_data );
					}
				} else {
					$actions[$action]['data'] = array_merge( $actions[$action]['data'], $extra_data );
				}
			}
			return apply_filters( 'em_list_table_get_action_data_extra', $actions, $this, ['extra_data' => $extra_data] );;
		}
		
		public function get_action_message( $action, $context ) {
			if( $action === 'delete' ) {
				$message = __("Are you sure you want to delete? This action cannot be undone.",'events-manager');
			}
			return apply_filters( 'em_list_table_get_action_message', $message ?? false, $this );
		}
		
		public function get_bulk_action_message( $action, $context ) {
			if ( $action === 'delete' ) {
				$message = __( "Are you sure you want to delete this item? This action cannot be undone.", 'events-manager' );
			}
			return apply_filters( 'em_list_table_get_bulk_action_message', $message ?? '', $this );
		}
		
		/**
		 * Generate a list of booking action links
		 *
		 * @param $item
		 *
		 * @return array
		 */
		public function get_action_links( $item ) {
			$action_data = $this->get_action_data();
			$url = $this->get_action_url( $item );
			$booking_actions = $this->build_action_link( $action_data, $url );
			return apply_filters(static::$basename . '_cols_col_action', $booking_actions, $item, $this);
		}
		
		public function build_action_link ( $data, $url = '' ) {
			$action_links = array();
			foreach( $data as $action => $action_data ) {
				if( !empty($action_data['actions']) ) {
					$action_links[$action] = [
						'actions' => $this->build_action_link( $action_data['actions'], $url ),
						'label' => $action['label'] ?? '',
					];
				} else {
					$data = array_merge( $action_data['data'], ['nonce' => wp_create_nonce( $action_data['data']['action'] ?? $action )] );
					$attributes = array();
					foreach( $data as $att => $att_val ) {
						$attributes[] = 'data-' . esc_html($att) . '="' . esc_attr($att_val) . '"';
					}
					$action_links[$action] = '<a class="em-list-table-row-action" href="'.em_add_get_params($url, $action_data['data']).'"'. implode(' ', $attributes) .'>'.$action_data['label'].'</a>';
				}
			}
			return $action_links;
		}
		
		public function get_bulk_actions() {
			$bulk_actions = $this->get_action_data();
			return apply_filters(static::$basename . '_get_bulk_actions', $bulk_actions, $this);
		}
		
		public function output_action_links ( $action_links ) {
			ob_start();
			foreach( $action_links as $action => $action_link ) {
				if( isset($action_link['actions']) ) {
					echo '<section class="'. esc_attr($action) .'">';
					echo $this->output_action_links( $action_link['actions'] );
					echo '</section>';
				} else {
					echo $action_link;
				}
			}
			return ob_get_clean();
		}
		
		/* ------------------ Table Data ------------------ */
		
		public static function sanitize_spreadsheet_cell( $cell ){
			if ( !empty($cell) || is_numeric($cell) ) {
				if ( is_array($cell) ) {
					$cell = implode( ',', $cell );
				}
				if ( !is_array( $cell ) ) {
					$cell = html_entity_decode( $cell ); //remove things like &amp; which may have been saved to the DB directly
					return preg_replace( '/^([;=@\+\-])/', "'$1", $cell );
				}
			}
			return '';
		}
		
		/**
		 * Prepare the items for the table to process
		 *
		 * @return Void
		 */
		public function prepare_items(){
			$columns = $this->get_columns();
			// wrap column data up in case we have html in them
			$hidden = $this->get_hidden_columns();
			$sortable = $this->get_sortable_columns();
			
			$this->per_page = $this->get_items_per_page( $this->per_page_var, $this->per_page );
			$this->items = $this->table_data();
			
			$this->set_pagination_args( array(
				'total_items' => $this->total_items,
				'per_page'    => $this->per_page,
				'total_pages' => ceil($this->total_items / $this->per_page),
			) );
			
			$this->_column_headers = array( $columns, $hidden, $sortable );
		}
		
		protected function get_items_per_page( $option, $default_value = 20 ) {
			return $this->limit;
		}
		
		/* ------------------ Table Output ------------------ */
		
		/**
		 * Displays the table
		 * @return void
		 */
		public function display(){
			do_action(static::$basename . '_header', $this); //won't be overwritten by JS
			$this->prepare_items();
			$uid = esc_attr($this->uid);
			// setup additional classes
			$extra_classes = $this->display_classes();
			$atts = array();
			foreach( $this->display_attributes() as $att => $att_val ) {
				$atts[] = esc_html($att) . '="' . esc_attr($att_val) . '"';
			}
			// get confirmation messages for actions and put it in the form element, to keep the wrapper a little less cluttered
			$actions = $this->get_action_data();
			$action_messages = [];
			foreach ( $actions as $action => $action_data ) {
				if( isset($action_data['actions']) ) {
					foreach ( $action_data['actions'] as $the_action => $the_action_data ) {
						if ( !empty($the_action_data['confirm']) ) {
							$action_messages[ $the_action ] = esc_attr( $the_action_data['confirm'] );
						}
					}
				} else {
					if ( !empty($action_data['confirm']) ) {
						$action_messages[$action] = esc_attr($action_data['confirm']);
					}
				}
			}
			$action_messages = apply_filters( static::$basename . '_action_messages', $action_messages, $this );
			?>
			<div class="em-list-table <?php em_template_classes(static::$template_component_name); echo ' ' . implode(' ', $extra_classes); ?>" id="<?php echo $uid; ?>" data-basename="<?php echo static::$basename; ?>" <?php echo implode(' ', $atts); ?>>
				<form class='<?php echo static::$form_class ?> em-list-table-form' method='post' action='' id="<?php echo $uid; ?>-form" data-action-messages='<?php echo esc_attr(json_encode($action_messages)); ?>'>
					<input type="hidden" name="is_public" value="<?php echo ( static::$is_frontend ) ? 1:0; ?>">
					<input type="hidden" name="pno" value='<?php echo esc_attr($this->page); ?>'>
					<input type="hidden" name="order" value='<?php echo esc_attr($this->order); ?>' data-persist>
					<input type="hidden" name="orderby" value='<?php echo esc_attr($this->orderby); ?>' data-persist>
					<input type="hidden" name="action" value="<?php echo static::$basename; ?>">
					<input type="hidden" name="cols" value="<?php if ( !empty($_REQUEST['cols']) ) echo esc_attr(implode(',', $this->cols)); ?>">
					<input type="hidden" name="limit" value="<?php echo esc_attr($this->limit); ?>">
					<input type="hidden" name="_emnonce" value="<?php echo wp_create_nonce(static::$basename); ?>">
					<input type="hidden" name="save" value="0">
					<input type="hidden" name="save_filters" value="0">
					<input type="hidden" name="table_id" value="<?php echo esc_attr( str_replace($this->id . '-', '', $uid)); ?>">
					<input type="hidden" name="event_archetype" value="<?php echo esc_attr(Archetypes::get_current()); ?>">
					<?php
						$this->display_hidden_input();
						parent::display();
					?>
				</form>
				<?php
					$this->output_overlays();
				?>
			</div>
			<?php
			do_action(static::$basename . '_footer',$this); //won't be overwritten by JS
		}
		
		public function display_classes() {
			$extra_classes = array();
			$extra_classes[] = $this->total_items && $this->checkbox_id ? 'has-checkboxes':'no-checkboxes';
			$extra_classes[] = $this->total_items && static::$is_exportable ? 'has-export':'no-export';
			$extra_classes[] = static::$has_filters ? 'has-filter':'no-filter';
			$extra_classes[] = static::$is_frontend ? 'frontend':'backend';
			return $extra_classes;
		}
		
		public function display_attributes() {
			return array();
		}
		
		/**
		 * Override to output table-specific hidden columns
		 * @return void
		 */
		public function display_hidden_input() {}
		
		/**
		 * Copies and overrides the parent WP_List_Table method.
		 *
		 * Adds a wrapper to the top/bottom of the actual table of values, and wraps the tablenav actions in another div.alignleft.actions
		 *
		 * This will allow for better responsive reactions with regards to pagination.
		 *
		 * @param $which
		 *
		 * @return void
		 */
		protected function display_tablenav( $which ) {
			if ( 'top' === $which ) {
				wp_nonce_field( 'bulk-' . $this->_args['plural'] );
			} else {
				echo '</div>';
				if ( !self::$show_bottom_tablenav ) return;
			}
			?>
			<div class="tablenav <?php echo esc_attr( $which ); ?>">
				<?php if ( 'top' === $which || self::$show_bottom_tablenav_actions ) : ?>
					<?php
					if ( ( 'top' === $which || self::$show_bottom_tablenav_bulkactions ) && $this->has_items() ) {
						?>
						<div class="alignleft actions bulkactions">
							<?php $this->bulk_actions( $which ); ?>
						</div>
						<?php
					}
					if ( ( 'top' === $which || self::$show_bottom_tablenav_extra_tablenav ) ) {
						$this->extra_tablenav( $which );
					}
					?>
				<?php endif; ?>
				<?php
				if( ( 'top' === $which || self::$show_bottom_tablenav_pagination ) ) {
					$this->pagination( $which );
				}
				?>
			</div>
			<?php
			if ( 'top' === $which ) {
				echo '<div class="table-wrap">';
			}
		}
		
		function output_overlays(){
			$this->output_overlay_settings();
			if( static::$is_exportable ) {
				$this->output_overlay_export();
			}
		}
		
		function output_overlay_export(){
			// join all fields into one set of cols, with general taking precendence over events, then tickets then attendees
			$cols_template = $this->get_cols_template();
			$grouped_fields = array();
			foreach( $this->cols_template_groups as $group_data ){
				$grouped_fields = array_merge($grouped_fields, $group_data['fields']);
			}
			$ungrouped_fields = array_diff(array_keys($cols_template), $grouped_fields);
			$uid = esc_attr($this->uid);
			$id = esc_attr($this->id);
			?>
			<div class="em pixelbones em-modal em-list-table-export em-list-table-modal" id="<?php echo $uid; ?>-export-modal">
				<form id="<?php echo $uid; ?>-export-form" class="em-list-table-form em-list-table-export-form" action="" method="post" rel="#<?php echo $uid . '-form'; ?>">
					<div class="em-modal-popup">
						<header>
							<a class="em-close-modal"></a><!-- close modal -->
							<div class="em-modal-title"><?php esc_attr_e('Bookings Table Settings','events-manager'); ?></div>
						</header>
						<div class="em-modal-content input">
							<p><?php esc_html_e('Select the options below and export all the records you have currently filtered (all pages) into a spreadsheet format.','events-manager') ?></p>
							<?php do_action( static::$basename . '_export_options', $this); ?>
							<?php
							static::output_overlay_columns_selection(  array(
								'text' => array(
									'show' => array(
										'title' => __('Columns to export','events-manager'),
									),
									'choose' => array(
										'title' => __('Exporter','events-manager'),
									)
								),
							));
							?>
						</div>
						<footer class="em-submit-section input">
							<div>
								<div class="<?php echo $id; ?>-filters em-list-table-filters" style="display:none; visibility:hidden;"><!-- houses filter data as modified for export --></div>
								<input type="hidden" name="no_save" value='1'>
								<input type="hidden" name="_wpnonce" value="<?php echo wp_create_nonce( static::$export_action ); ?>">
								<input type="hidden" name="_emnonce" value="<?php echo wp_create_nonce( static::$export_action ); ?>">
								<input type="hidden" name="action" value="<?php echo esc_attr(static::$export_action); ?>">
								<button type="submit" class="button button-primary"><?php esc_html_e('Export', 'events-manager'); ?></button>
							</div>
						</footer>
					</div>
				</form>
			</div>
			<br class="clear">
			<?php
		}
		
		function output_overlay_settings(){
			$uid = esc_attr($this->uid);
			$id = esc_attr($this->id);
			?>

			<div class="em pixelbones em-modal em-list-table-settings em-list-table-modal" id="<?php echo $uid; ?>-settings-modal">
				<form id="<?php echo $uid; ?>-settings-form" class="em-list-table-form em-list-table-settings-form" action="" method="post" rel="#<?php echo $uid . '-form'; ?>">
					<div class="em-modal-popup">
						<header>
							<a class="em-close-modal"></a><!-- close modal -->
							<div class="em-modal-title"><?php esc_attr_e('Bookings Table Settings','events-manager'); ?></div>
						</header>
						<div class="em-modal-content input">
							<p><?php _e('Modify what information is displayed in this booking table.','events-manager') ?></p>
							<div class="<?php echo $uid; ?>-rows-setting em-list-table-setting">
								<label for="<?php echo $uid; ?>-rows-setting"><strong><?php esc_html_e('Results per Page', 'events-manager'); ?></strong></label>
								<select name="limit" class="<?php echo $id; ?>-filter" id="<?php echo $uid; ?>-rows-setting">
									<?php foreach ( static::get_item_limits() as $limit ) : ?>
									<option value="<?php echo esc_attr($limit) ?>" <?php selected($limit, $this->limit); ?>><?php echo esc_html(sprintf(__('%s Rows','events-manager'),$limit)); ?></option>
									<?php endforeach; ?>
								</select>
							</div>
							<?php do_action( static::$basename . '_settings_options', $this); ?>
							<?php static::output_overlay_columns_selection(); ?>
						</div>
						<footer class="em-submit-section input">
							<div>
								<button type="submit" class="button button-primary"><?php esc_html_e('Save Settings', 'events-manager'); ?></button>
							</div>
							<div class="em-list-table-settings-remember">
								<label>
									<?php esc_html_e('Remember these settings', 'events-manager'); ?>
									<?php $this->output_overlay_settings_remember_tooltip(); ?>
									<input type="checkbox" name="save" value="1" checked="checked" data-setting>
								</label>
								<label>
									<?php esc_html_e('Remember filtering options', 'events-manager'); ?>
									<?php $this->output_overlay_settings_remember_filters_tooltip(); ?>
									<input type="checkbox" name="save_filters" value="1" data-setting>
								</label>
							</div>
						</footer>
					</div>
				</form>
			</div>
			<?php
		}
		
		public function output_overlay_settings_remember_tooltip() {}
		
		public function output_overlay_settings_remember_filters_tooltip() {
			?>
			<span class="em-icon em-icon-info s-15 em-tooltip" aria-label="<?php esc_html_e('Your search filter settings will be selected automatically.', 'events-manager'); ?>" data-tippy-maxWidth="250px"></span>
			<?php
		}
		
		public function output_overlay_columns_selection ( $options = array() ) {
			$options = array_replace_recursive( array(
				'text' => array(
					'show' => array(
						'title' => __('Columns to show','events-manager'),
						'description' => __('Remove or reorder columns below.','events-manager')
					
					),
					'choose' => array(
						'title' => __('Columns to choose','events-manager'),
						'description' => __('Add to your table from the columns below.','events-manager')
					),
				),
			), $options);
			// join all fields into one set of cols, with general taking precendence over events, then tickets then attendees
			$cols_template = $this->get_cols_template();
			$grouped_field_keys = array();
			$grouped_fields = array();
			// get the keys of all grouped data, and also get the labels into grouped array so we can order alphabetically now whilst we're at it
			foreach( $this->cols_template_groups as $group_key => $group_data ){
				$grouped_field_keys = array_merge($grouped_field_keys, $group_data['fields']);
				$grouped_fields[$group_key] = [];
				foreach( $group_data['fields'] as $col ) {
					$grouped_fields[$group_key][$col] = $cols_template[$col]['column_header'] ?? $cols_template[$col];
				}
				uasort( $grouped_fields[$group_key], function ( $a, $b ){
					$col_label_a = $a['label'] ?? $a;
					$col_label_b = $b['label'] ?? $b;
					return strnatcasecmp($col_label_a, $col_label_b);
				});
			}
			// get ungrouped keys and sort them alphabetically too
			$ungrouped_fields = array_diff_key($cols_template, array_combine($grouped_field_keys, $grouped_field_keys));
			uasort( $ungrouped_fields, function ( $a, $b ){
				$col_label_a = $a['label'] ?? $a;
				$col_label_b = $b['label'] ?? $b;
				return strnatcasecmp($col_label_a, $col_label_b);
			});
			?>
			<div class="em-list-table-cols">
				<div class="em-list-table-cols-selected">
					<p>
						<strong><?php echo $options['text']['show']['title']; ?></strong><br>
						<?php echo $options['text']['show']['description'] ?>
					</p>
					<div class="em-list-table-cols-sortable">
						<?php foreach( $this->cols as $col_key ): ?>
							<div class="item" data-value="<?php echo esc_attr($col_key); ?>">
								<span>
									<?php
										$col_header = $this->cols_template[$col_key]['column_header'] ?? $this->cols_template[$col_key];
										echo esc_html($col_header);
									?>
								</span>
								<a href="#" class="remove" tabindex="-1" title="Remove">×</a>
								<input type="hidden" name="cols[<?php echo esc_attr($col_key); ?>]" value="1" class="em-bookings-col-item">
							</div>
						<?php endforeach; ?>
					</div>
				</div>
				<div class="em-list-table-cols-select">
					<p>
						<strong><?php echo $options['text']['choose']['title']; ?></strong><br>
						<?php echo $options['text']['choose']['description'] ?>
					</p>
					<select class="em-list-table-cols-inactive em-selectize always-open checkboxes" multiple>
						<?php foreach( $grouped_fields as $group_key => $cols ): ?>
							<optgroup label="<?php echo esc_attr($this->cols_template_groups[$group_key]['label']); ?>" data-data='{"type":"<?php echo esc_attr($group_key) ?>"}'>
								<?php foreach( $cols as $col_key => $col_data ): ?>
									<?php
									$col_header = $col_data['column_header'] ?? $col_data;
									$col_label = $col_data['label'] ?? $col_data;
									?>
									<option value="<?php echo esc_attr($col_key); ?>" data-data='{"type":"<?php echo esc_attr($col_label) ?>", "header":"<?php echo esc_attr($col_header); ?>"}' <?php if( in_array($col_key, $this->cols) ) echo 'selected'; ?>>
										<?php echo esc_html($col_label); ?>
									</option>
								<?php endforeach; ?>
							</optgroup>
						<?php endforeach; ?>
						<optgroup label="<?php esc_html_e('Other', 'events-manager'); ?>" data-data='{"type":"other"}'>
							<?php foreach( $ungrouped_fields as $col_key => $col_data  ): ?>
								<?php
								$col_header = $col_data['column_header'] ?? $col_data;
								$col_label = $col_data['label'] ?? $col_data;
								?>
								<option value="<?php echo esc_attr($col_key); ?>" data-data='{"type":"other", "header":"<?php echo esc_attr($col_header); ?>"}' <?php if( in_array($col_key, $this->cols) ) echo 'selected'; ?>>
									<?php echo esc_html($col_label); ?>
								</option>
							<?php endforeach; ?>
						</optgroup>
					</select>
				</div>
			</div>
			<?php
		}
		
		/**
		 * Overrides default by adding and then unsetting $_GET['orderby'] to show the inisial ordering mechanism
		 *
		 * @param bool $with_id Whether to set the ID attribute or not
		 */
		public function print_column_headers( $with_id = true ) {
			if( $this->orderby && !isset($_GET['orderby']) ) {
				// set and unset $_GET to have a default ordering
				$_GET['orderby'] = $this->orderby;
				parent::print_column_headers( $with_id );
				unset($_GET['orderby']);
			} else {
				// just output witout modifying $_GET
				parent::print_column_headers( $with_id );
			}
		}
		
		/**
		 * Define which columns are hidden
		 *
		 * @return array
		 */
		public function get_hidden_columns(){
			return array();
		}
		
		/**
		 * Get the table data, can get overrwritten for more customization.
		 *
		 * @return array
		 * @uses $this->get_items()
		 */
		protected function table_data(){
			// Do the search and return result
			return $this->get_items();
		}
		
		/**
		 * Performs a search based on requested table data and populates the $this->items array with the results, returning the same.
		 *
		 * @return array
		 */
		protected function get_items () {
			return array();
		}
		
		/**
		 * Gets header columns for this list table.
		 * @deprecated @param bool $csv
		 *
		 * @return mixed|null
		 */
		function get_headers( $csv = false ) {
			// temp switch $this->format so we're consistent but adhere to the deprecated $csv parameter
			$old_format = $this->format;
			$this->format = $csv ? 'csv' : $this->format;
			$headers = array();
			foreach ( $this->cols as $col ) {
				$spreadsheet_format = in_array( $this->format, ['csv', 'xls', 'xlsx'] );
				if ( $col == 'actions' ) {
					if ( !$spreadsheet_format ) {
						$headers[ $col ] = '&nbsp;';
					}
				} elseif ( array_key_exists( $col, $this->cols_template ) ) {
					if( is_array($this->cols_template[ $col ]) ) {
						$v = $this->cols_template[ $col ]['column_header'] ?? $this->cols_template[ $col ]['label'];
					} else {
						$v = $this->cols_template[ $col ];
					}
					//csv/excel escaping
					if ( $spreadsheet_format ) {
						$v = static::sanitize_spreadsheet_cell( $v );
						$headers[ $col ] = $v;
					} else {
						$headers[ $col ] = $v;
					}
				}
			}
			$headers = apply_filters( 'em_list_table_get_headers', $headers, $this );
			$headers = apply_filters( static::$basename . '_get_headers', $headers, $this );
			if ( $csv ) {
				// undo backpat for $csv
				$this->format = $old_format;
			}
			
			return $headers;
		}
		
		/**
		 * Gets a single row in HTML format for output to table HTML format.
		 * @param \EM_Object $item
		 *
		 * @return void
		 */
		public function single_row( $item ) {
			echo '<tr data-id="'. esc_attr($item->id) .'">';
			$this->single_row_columns( $item );
			echo '</tr>';
		}
		
		/**
		 * Simlar to single_row(), but returns an array of data, excluding checkboxes and actions, which can be used for export.
		 *
		 * IMPORTANT - this function will return an array of arrays, where each array is a row of data. This allows for splitting of data into multiple rows for export.
		 *
		 * @param $EM_Object
		 * @param $format
		 *
		 * @return array[]
		 */
		public function get_row( $EM_Object ) {
			$cols = array();
			foreach( $this->cols as $col ){
				//TODO fix urls so this works in all pages in front as well
				//add to cols
				$cols[$col] = $this->default_column_data( $EM_Object, $col );
			}
			// the specific basename filter will provide a single-dimensional array, you can return a multi-dimensional array at this point
			$cols = apply_filters( static::$basename. '_get_row', $cols, $EM_Object, $this );
			if( !is_array( current($cols) ) ) {
				$cols = array($cols);
			}
			return apply_filters( 'em_list_table_get_row', $cols, $EM_Object, $this );
		}
		
		function get_cols_template(){
			return $this->cols_template;
		}
		
		/**
		 * Override the parent columns method. Defines the columns to use in your listing table
		 *
		 * @return array
		 */
		public function get_columns() {
			$columns = array();
			if( $this->checkbox_id ) {
				$columns['cb'] = '<input type="checkbox" />';
			}
			return $columns  + $this->get_headers();
		}
		
		
		
		/**
		 * Define what data to show on each column of the table
		 *
		 * @param  \EM_Object   $item             Data, usually an EM_Object for this class. Override this method to use your own data.
		 * @param  string       $column_name      Current column name
		 *
		 * @return string
		 */
		function column_default( $item, $column_name ){
			$val = '';
			if( in_array($column_name, $this->cols) ){
				// get the column values
				$primary_column = array_values($this->cols)[0]; // changed from reset() to avoid potential issues resetting nested foreaches
				if( $primary_column === $column_name && $this->format == 'html' ){
					$val = $this->primary_column_meta( $item, $column_name );
					$val .= '<div class="primary-column-content" data-colname="'. $this->_column_headers[0][$column_name] .'">'. $this->default_column_data( $item, $column_name ) . '</div>';
					if( static::$show_responsive_meta ) {
						$val .= '<div class="em-list-table-row-responsive-meta">' . $this->primary_column_responsive_meta( $item, $column_name ) . '</div>';
					}
				} else {
					$val = $this->default_column_data( $item, $column_name );
				}
			}
			return $val;
		}
		
		public function primary_column_meta( $item, $column_name ) {
			$content = '';
			// ajax status icons
			if( !empty( $item->feedback_message) ){
				$css_icon = empty( $item->errors ) ? 'updated' : 'cross-circle';
				$content = '<span href="#" class="em-icon em-icon-'.$css_icon.' em-tooltip" aria-label="'. $item->feedback_message .'"></span> ';
			}
			return $content;
		}
		
		public function primary_column_responsive_meta( $item, $column_name ) { return ''; }
		
		/**
		 * Gets data for columns that don't have a specific method defined.
		 *
		 * This method MUST be overwritten by child classes and ALSO must run the return value through the default_column_sanitize_data() method.
		 * @param $item
		 * @param $col
		 *
		 * @return string
		 */
		public function default_column_data( $item, $col ){
			$val = $this->get_default_column_data( $item, $col );
			// interept data before it is sanitized
			$val = apply_filters( 'em_list_table_rows_col_'.$col, $val, $item, $this );
			$val = apply_filters( static::$basename.'_rows_col_'.$col, $val, $item, $this, $this->format, $this); // IGNORE LAST $this in your filters (bottom one too), typo and we don't want to remove it just in case it breaks sites implementing it by mistake
			$val = apply_filters( static::$basename.'_rows_col', $val, $col, $item, $this, $this->format, $this); // use the above filter instead for better performance
			// sanitize data, intercepting data should set and unset (0) itself each time accordingly from the $this->allow_html array
			return $this->default_column_sanitize_data( $val, $col, $item );
		}
		
		public function get_default_column_data( $item, $col ) {
			_doing_it_wrong( __METHOD__, 'You must overwrite this method in your child class.', '5.9.0' );
			return '';
		}
		
		public function default_column_sanitize_data( $val, $col, $item, $allow_html = false ) {
			$format = $this->format;
			//escape all HTML if destination is HTML or not defined
			if( empty($allow_html) && ($format == 'html' || empty($format)) && empty(static::$cols_allowed_html[$col]) ){
				$val = esc_html($val);
			}
			//csv/excel escaping
			if( in_array( $format, ['csv', 'xls', 'xlsx'] ) ){
				$val = self::sanitize_spreadsheet_cell($val);
			}
			return $val;
		}
		
		/**
		 * Bulk Edit Checkbox
		 * @param array $item
		 * @return string
		 */
		function column_cb( $item ) {
			if( is_object($item) ){
				$id = $item->{$this->checkbox_id};
			}else{
				$id = $item[$this->checkbox_id];
			}
			return sprintf('<input type="checkbox" name="column_id[]" value="%s" />', $id);
		}
		
		public function bulk_actions ( $which = '' ) {
			$uid = esc_attr($this->uid);
			$id = esc_attr($this->id);
			?>
			<div class="alignleft actions <?php echo $id; ?>-settings em-list-table-triggers">
				<a href="#" class="<?php echo $id; ?>-export <?php echo $id; ?>-trigger em-list-table-trigger em-list-table-export-trigger em-icon em-icon-download em-tooltip" id="<?php echo $id; ?>-export-trigger" rel="#<?php echo $uid; ?>-export-modal" aria-label="<?php _e('Export these bookings.','events-manager'); ?>"></a>
				<a href="#" class="<?php echo $id; ?>-settings <?php echo $id; ?>-trigger em-list-table-trigger  em-list-table-settings-trigger em-icon em-icon-settings em-tooltip" id="<?php echo $id; ?>-settings-trigger" rel="#<?php echo $uid; ?>-settings-modal" aria-label="<?php _e('Settings','events-manager'); ?>"></a>
			</div>
			<?php $this->extra_tablenav_trigger( $which ); ?>
			<?php
			if( $this->checkbox_id ) {
				$this->bulk_actions_input( $which );
			}
		}
		
		public function bulk_actions_input( $which = '' ) {
			$id = esc_attr($this->id);
			$uid = esc_attr($this->uid);
			?>
			<div class="alignleft actions bulkactions-input">
				<label for="<?php echo $uid; ?>-bulk-action-selector-top" class="screen-reader-text"><?php esc_html_e('Select bulk action'); ?></label>
				<select class="bulk-action-selector em-list-table-bulk-action" id="<?php echo $uid; ?>-bulk-action-selector<?php if( $which ) echo '-'.$which; ?>">
					<option value="-1"><?php esc_html_e('Bulk actions', 'events-manager'); ?></option>
					<?php foreach( $this->get_bulk_actions() as $action => $action_data ): ?>
						<?php if( !empty($action_data['actions']) ): ?>
							<optgroup label="<?php echo esc_attr($action_data['label'] ?? '---'); ?>">
								<?php foreach( $action_data['actions'] as $sub_action => $sub_action_data ): ?>
									<?php
									$data = array();
									$sub_action_data['data']['confirm'] = $sub_action_data['confirm-bulk'] ?? '';
									foreach( $sub_action_data['data'] as $key => $value ){
										if( $value ) $data[] = 'data-' .esc_attr($key) . '="' . esc_attr($value) . '"';
									}
									?>
									<option value="<?php echo esc_attr($sub_action); ?>" <?php echo implode(' ', $data); ?>><?php echo esc_html($sub_action_data['label']); ?></option>
								<?php endforeach; ?>
							</optgroup>
						<?php else: ?>
							<?php
							$data = array();
							$action_data['data']['confirm'] = $action_data['confirm-bulk'] ?? ''; // add bulk message
							foreach( $action_data['data'] as $key => $value ){
								if( $value ) $data[] = 'data-' . esc_attr($key) . '="' . esc_attr($value) . '"';
							}
							?>
							<option value="<?php echo esc_attr($action); ?>" <?php echo implode(' ', $data); ?>><?php echo esc_html($action_data['label']); ?></option>
						<?php endif; ?>
					<?php endforeach; ?>
				</select>
				<button class="button <?php echo $id; ?>-bulk-action em-list-table-bulk-action"><?php esc_html_e('Apply'); ?></button>
			</div>
			<?php
		}
		
		public function extra_tablenav_trigger ( $which = '' ) {
			$tooltip_text = static::$show_filters ? esc_html__('Hide Search', 'events-manager') : esc_html__('Show Search', 'events-manager');
			$id = esc_attr($this->id);
			?>
			<div class="alignleft actions <?php echo $id; ?>-settings">
				<button class="button filters-trigger <?php echo esc_attr($this->id); ?>-filters-trigger em-tooltip <?php if ( !static::$show_filters ) echo 'hidden'; ?>" aria-label="<?php echo $tooltip_text; ?>"
				        data-label-show="<?php esc_html_e('Show Search', 'events-manager'); ?>"
				        data-label-hide="<?php esc_html_e('Hide Search', 'events-manager'); ?>"
				><?php esc_html_e('Show/Hide Search'); ?></button>
				<button class="button small-expand-trigger <?php echo esc_attr($this->id); ?>-small-expand-trigger"><?php esc_html_e('Expand Columns'); ?></button>
			</div>
			<?php
		}
		
		/* START EXPORTING */
		/**
		 * Invoked on wp_loaded, allowing for exports via AJAX or directly on any page, checks $_REQUEST vars and verifies nonce, triggers an export if request is valid.
		 * @return void
		 */
		public static function export_init() {
			if ( !empty($_REQUEST['action']) && !empty($_REQUEST['_emnonce']) && $_REQUEST['action'] === static::$export_action )  {
				if( wp_verify_nonce($_REQUEST['_emnonce'], static::$export_action) ) {
					static::$exporting = true;
					static::export_csv();
				} else {
					wp_die( 'Cannot export, security nonce verification failed.' );
				}
			}
		}
		
		/**
		 * Exports and outputs a CSV downloadable file to requester.
		 * @return void
		 */
		public static function export_csv () {
			do_action( 'export_csv_pre', static::class );
			
			// open the file handle
			$handle = fopen("php://output", "w");
			
			// setup delimiter
			$delimiter = !defined('EM_CSV_DELIMITER') ? static::$export_delimiter : EM_CSV_DELIMITER;
			static::$export_delimiter = apply_filters('em_csv_delimiter', $delimiter); // set it static, we're exiting after export finishes
			
			// send headers
			static::export_csv_http_headers();
			
			// output header title
			static::export_csv_header_title( $handle );
			
			// prep table headers $_REQUEST cols and limit for use when setting up list table
			if( !empty($_REQUEST['cols']) && is_array($_REQUEST['cols']) ){
				$cols = array();
				foreach($_REQUEST['cols'] as $col => $active){
					if( $active ){ $cols[] = $col; }
				}
				$_REQUEST['cols'] = $cols;
			}
			$_REQUEST['limit'] = 0;
			
			// setup list table
			$EM_List_Table = static::export_setup_list_table( $handle );
			
			// output table headers
			static::export_csv_table_headers( $EM_List_Table, $handle );
			
			// output table rows
			static::export_csv_table_rows( $EM_List_Table, $handle );
			
			// close and exit
			fclose($handle);
			exit();
		}
		
		public static function export_csv_http_headers() {
			//generate bookings export according to search request
			if( !empty($_REQUEST['event_id']) ){
				$EM_Event = em_get_event( $_REQUEST['event_id'] );
			}
			header("Content-Type: application/octet-stream; charset=utf-8");
			$file_name = $EM_Event->event_slug ?? get_bloginfo();
			header("Content-Disposition: Attachment; filename=".sanitize_title($file_name)."-export.csv");
			do_action('em_csv_header_output');
			echo "\xEF\xBB\xBF"; // UTF-8 for MS Excel (a little hacky... but does the job)
		}
		
		public static function export_csv_header_title( $handle ) {
			// get Event ID
			if( !empty($_REQUEST['event_id']) ){
				$EM_Event = em_get_event( $_REQUEST['event_id'] );
			}
			// csv headers
			if ( !defined('EM_CSV_DISABLE_HEADERS') || !EM_CSV_DISABLE_HEADERS ) {
				if( !empty($_REQUEST['event_id']) ) {
					fputcsv($handle, array( __('Event','events-manager') . ' : ' . $EM_Event->event_name ), static::$export_delimiter);
					if( $EM_Event->location_id > 0 ) {
						fputcsv($handle, array( __('Where','events-manager') . ' - ' . $EM_Event->get_location()->location_name ), static::$export_delimiter);
					}
					fputcsv($handle, array( __('When','events-manager') . ' : ' . $EM_Event->output('#_EVENTDATES - #_EVENTTIMES') ), static::$export_delimiter);
				}
				$EM_DateTime = new \EM_DateTime(current_time('timestamp'));
				fputcsv($handle, array( sprintf(__('Exported on %s','events-manager'), $EM_DateTime->format('D d M Y h:i')) ), static::$export_delimiter);
				fputcsv($handle, array(), static::$export_delimiter);
			}
		}
		
		public static function export_setup_list_table( $handle, $format = 'csv' ) {
			$class = static::class;
			$EM_List_Table = new $class();
			$EM_List_Table->format = $format;
			$EM_List_Table->limit = 150; //if you're having server memory issues, try messing with this number
			return $EM_List_Table;
		}
		
		public static function export_csv_table_headers( $EM_List_Table, $handle ) {
			fputcsv($handle, $EM_List_Table->get_headers(true), static::$export_delimiter);
		}
		
		/**
		 * @param resource $handle
		 * @param List_Table $EM_List_Table
		 *
		 * @return void
		 */
		public static function export_csv_table_rows( $EM_List_Table, $handle ) {
			$items = $EM_List_Table->table_data();
			while( !empty($items) ){
				foreach( $items as $item ) {
					static::export_csv_table_row( $item, $EM_List_Table, $handle );
				}
				//reiterate loop
				$EM_List_Table->offset += $EM_List_Table->limit;
				$items = $EM_List_Table->table_data();
			}
		}
		
		/**
		 * Exports a single or multiple rows based on what is provided from $this->get_row( $item );
		 * @param \EM_Object $item
		 * @param List_Table $EM_List_Table
		 * @param resource $handle
		 *
		 * @return void
		 */
		public static function export_csv_table_row( $item, $EM_List_Table, $handle ) {
			$rows = $EM_List_Table->get_row( $item );
			foreach( $rows as $row ) {
				fputcsv( $handle, $row, static::$export_delimiter );
			}
		}
		/* END EXPORTING */
	}
}

namespace {
	function em_list_table_create_funcitions(){
		// handle convert_to_screen lacking in places
		if( !function_exists('convert_to_screen')){
			function convert_to_screen( $hook_name ) {
				return new \EM\WP_Screen;
			}
		}
		if( !function_exists('get_column_headers') ){
			function get_column_headers( $screen ) {
				return array();
			}
		}
		// slightly risky situation... if WP_Screen wasn't loaded but convert_to_screen was defined, we need to make sure WP_Screen exists and hope another plugin isn't adding it later in the page
		if( !class_exists('WP_Screen') ) {
			class WP_Screen extends \EM\WP_Screen {}
		}
	}
	include('em-wp-screen.php');
}