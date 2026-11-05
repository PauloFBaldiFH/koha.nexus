<?php
namespace EM;

class WP_Screen {
	public $action;
	public $base;
	private $columns = 0;
	public $id;
	protected $in_admin;
	public $is_network;
	public $is_user;
	public $parent_base;
	public $parent_file;
	public $post_type;
	public $taxonomy;
	private $_help_tabs = array();
	private $_help_sidebar = '';
	private $_screen_reader_content = array();
	private static $_old_compat_help = array();
	private $_options = array();
	private static $_registry = array();
	private $_show_screen_options;
	private $_screen_settings;
	public $is_block_editor = false;
	
	public function __get($prop){
		return '';
	}
	
	public static function __callStatic( $string, $args ){
		return '';
	}
	
	public function __call( $string, $args ){
		return '';
	}
	
	public static function get(){
		return new WP_Screen();
	}
}