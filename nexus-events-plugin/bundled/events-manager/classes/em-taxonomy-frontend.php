<?php
class EM_Taxonomy_Frontend {
	
	/**
	 * The name of this taxonomy, e.g. event-categories, which is defined in child class.
	 * @var string
	 */
	public static $taxonomy_name = 'EM_TAXONOMY_NAME';
	/**
	 * The name of the child class, used for now whilst late static binding isn't guaranteed since we may be running on PHP <5.3
	 * Once PHP 5.3 is a minimum requirement in WP, we can get rid of this one. 
	 * @var string
	 */
	public static $this_class = 'EM_Taxonomy_Frontend';
	/**
	 * Currently used to instantiate a class of the specific term. Eventually we could just use EM_Taxonomy since these will be standardized functions for any taxonomy.
	 * @var string
	 */
	public static $tax_class = 'EM_Taxonomy';
	/**
	 * Name of taxonomy for reference in saving to database, e.g. category will be used to save category-image.
	 * This may differ from the name of the taxonomy, such as event-category can be category
	 * @var string
	 */
	public static $option_name = 'taxonomy';
	public static $option_name_plural = 'taxonomies';
	
	public static function init(){
		if( !is_admin() ){
			add_filter('taxonomy_template', array(static::$this_class,'template'), 99);
			add_filter('parse_query', array(static::$this_class,'parse_query'));
		}
	}
	
	/**
	 * Overrides archive pages e.g. locations, events, event categories, event tags based on user settings
	 * @param string $template
	 * @return string
	 */
	public static function template($template = ''){
		global $wp_query, $wp_the_query, $em_the_query, $post;
		if( is_tax(static::$taxonomy_name) && !locate_template('taxonomy-'.static::$taxonomy_name.'.php') && em_get_option('dbem_cp_'. static::$option_name_plural .'_formats', true) ){
			do_action('em_pre_'. static::$option_name .'_taxonomy_template');
			do_action('em_pre_taxonomy_template', get_called_class(), static::$tax_class);
			$em_the_query = $wp_the_query; //use this for situations where other plugins need to access 'original' query data, which you can switch back/forth.
			$EM_Taxonomy = $GLOBALS[static::$tax_class] = EM_Taxonomy_Term::get($wp_query->queried_object->term_id, static::$tax_class);
			if( static::get_page_id() ){
			    //less chance for things to go wrong with themes etc. so just reset the WP_Query to think it's a page rather than taxonomy
				$wp_query = new WP_Query(array('page_id'=> static::get_page_id()));
				$wp_query->queried_object = $wp_query->post;
				$wp_query->queried_object_id = $wp_query->post->ID;
				$wp_query->post->post_title = $wp_query->posts[0]->post_title = $wp_query->queried_object->post_title = $EM_Taxonomy->output(em_get_option('dbem_'. static::$option_name .'_page_title_format'));
				if( !function_exists('yoast_breadcrumb') ){ //not needed by WP SEO Breadcrumbs, we deal with it in a filter further down - wpseo_breadcrumb_links
					$wp_query->post->post_parent = $wp_query->posts[0]->post_parent = $wp_query->queried_object->post_parent = static::get_page_id();
				}
				$post = $wp_query->post;
				$wp_the_query = $wp_query; //we won't do this to the else section because we should deprecate it due to its instability
			}else{
			    //we don't have a categories page, so we create a fake page
				// some themes or plugins may not like this, the only real option is to use a dedicated categories page so the above if block gets triggered.
			    $wp_query->posts = array();
			    $wp_query->posts[0] = new stdClass();
			    $wp_query->posts[0]->post_title = $wp_query->queried_object->post_title = $EM_Taxonomy->output(em_get_option('dbem_'. static::$option_name .'_page_title_format'));
				$wp_query->posts[0]->post_type = 'page';
			    $post_array = array('ID', 'post_author', 'post_date','post_date_gmt','post_content','post_excerpt','post_status','comment_status','ping_status','post_password','post_name','to_ping','pinged','post_modified','post_modified_gmt','post_content_filtered','post_parent','guid','menu_order','post_mime_type','comment_count','filter');
			    foreach($post_array as $post_array_item){
			    	$wp_query->posts[0]->{$post_array_item} = '';
			    }
			    $wp_query->post = $wp_query->posts[0];
			    $wp_query->post_count = 1;
			    $wp_query->found_posts = 1;
			    $wp_query->max_num_pages = 1;
			    //tweak flags for determining page type
			    $wp_query->is_tax = 0;
			    $wp_query->is_page = 1;
			    $wp_query->is_single = 0;
			    $wp_query->is_singular = 1;
			    $wp_query->is_archive = 0;
				// override shortlink so we don't get php warnings
				add_filter( 'pre_get_shortlink', [ static::class, 'pre_get_shortlink' ], 10, 2 );
			}
			//set taxonomy id to globals and query object
			$em_taxonomy_property = 'em_'. static::$option_name .'_id';
			$wp_query->{$em_taxonomy_property} = $wp_the_query->{$em_taxonomy_property} = $GLOBALS[$em_taxonomy_property] = $EM_Taxonomy->term_id; //we assign global taxononmy id just in case other themes/plugins do something out of the ordinary to WP_Query
			//set the template, if not blank, because FSEs may not be setting a template anymore
			if ( $template ) {
				$template = locate_template( array( 'page.php', 'index.php' ), false ); //category becomes a page
			}
			//sort out filters
			remove_action('wp_head', 'em_add_content_filter', 1000);
			remove_action('template_include', 'add_content_filter_template_include');
			add_filter('the_content', array(static::$this_class,'the_content')); //come in slightly early and consider other plugins
			// Meta Tag Manager Tweaks
			if( defined('MTM_VERSION') ) {
				add_filter('mtm_is_taxonomy_page', '__return_true');
				add_filter('mtm_is_cpt_page', '__return_false');
				add_filter('mtm_get_queried_object', function(){
					global $em_the_query;
					return $em_the_query->get_queried_object();
				});
			}
			//Yoast WP SEO Tweals
			if( defined('WPSEO_VERSION') ){
				add_filter('wpseo_breadcrumb_links',array(static::class,'wpseo_breadcrumb_links'));
				add_filter('wpseo_head', array(static::class,'flip_the_query'), 1);
				add_filter('wpseo_head', array(static::class,'flip_the_query'), 1000000);
			}
			do_action('em_'. static::$option_name .'_taxonomy_template');
			do_action('em_taxonomy_template', get_called_class(), static::$tax_class);
		}
		return $template;
	}
	
	public static function the_content($content){
		global $wp_query, $post;
		$em_taxonomy_property = 'em_'. static::$option_name .'_id'; //could be em_category_name or em_tag_name
		$is_taxonomy_page = $post->ID == static::get_page_id();
		if( !empty($GLOBALS[$em_taxonomy_property]) ) $taxonomy_id = $GLOBALS[$em_taxonomy_property];
		if( !empty($wp_query->{$em_taxonomy_property}) ) $taxonomy_id = $wp_query->{$em_taxonomy_property};
		$taxonomy_flag = (!empty($wp_query->{$em_taxonomy_property}) || !empty($GLOBALS[$em_taxonomy_property]));
		if( ($is_taxonomy_page && !empty($taxonomy_id)) || (empty($post->ID) && !empty($taxonomy_id)) ){
			$GLOBALS[static::$tax_class] = EM_Taxonomy_Term::get($taxonomy_id, static::$tax_class);
			ob_start();
			$args = array('id' => 8); // 4 is for categories, stable reference for view
			em_locate_template('templates/'.static::$option_name.'-single.php',true, array('args' => $args));
			return ob_get_clean();
		}
		return $content;
	}
	
	/**
	 * Removes the em_content filter from firing, which should be triggered by wp_head after EM has added this filter
	 */
	public static function remove_em_the_content(){
		remove_filter('the_content', 'em_content');
	}
	
	/**
	 * Parses the query on regular taxonomy archives so events are cronologically ordered.
	 * @param WP_Query $wp_query
	 */
	public static function parse_query( $wp_query ){
	    global $post;
	    if( !$wp_query->is_main_query() ) return;
		if( $wp_query->is_tax(static::$taxonomy_name) ){
			//Scope is future
			$today = current_time('mysql');
			if( em_get_option('dbem_events_current_are_past') ){
				$wp_query->query_vars['meta_query'][] = array( 'key' => '_event_start', 'value' => $today, 'compare' => '>=', 'type' => 'DATETIME' );
			}else{
				$wp_query->query_vars['meta_query'][] = array( 'key' => '_event_end', 'value' => $today, 'compare' => '>=', 'type' => 'DATETIME' );
			}
		  	if( em_get_option('dbem_'. static::$option_name_plural .'_default_archive_orderby') == 'title'){
		  		$wp_query->query_vars['orderby'] = 'title';
		  	}else{
			  	$wp_query->query_vars['orderby'] = 'meta_value';
			  	$wp_query->query_vars['meta_key'] = em_get_option('dbem_'. static::$option_name_plural .'_default_archive_orderby');
			  	if( in_array($wp_query->query_vars['meta_key'], array('_event_start', '_event_end', '_event_start_local', '_event_end_local')) ){
			  		$wp_query->query_vars['meta_type'] = 'DATETIME';
			  	}
		  	}
			$wp_query->query_vars['order'] = em_get_option('dbem_'. static::$option_name_plural .'_default_archive_order','ASC');
			$post_types = $wp_query->get( 'post_type');
			$post_types = is_array($post_types) ? $post_types + array(EM_POST_TYPE_EVENT) : EM_POST_TYPE_EVENT; 
			if( !em_get_option('dbem_cp_events_search_results') ) $wp_query->set( 'post_type', $post_types ); //in case events aren't publicly searchable due to 'bug' in WP - https://core.trac.wordpress.org/ticket/17592
		}elseif( !empty($wp_query->{'em_'.static::$option_name.'_id'}) ){
		    $post = $wp_query->post;
		}
	}
	
	public static function get_page_id(){
		return em_get_option('dbem_'.static::$option_name_plural.'_page');
	}
	
	public static function wpseo_breadcrumb_links( $links ){
	    global $wp_query;
	    array_pop($links);
	    if( static::get_page_id() ){
		    $links[] = array('id'=> static::get_page_id());
	    }
	    $links[] = array('text'=> $wp_query->posts[0]->post_title);
	    return $links;
	}
		
	/**
	 * Switches the query back/forth from the original query if EM has interferred to add formatting for taxonomy pages.
	 * Useful if you want plugins to temporarily access the old WP_Query which indicated we were looking at a taxonomy.
	 * For example, with WordPress SEO by Yoast, for wpseo_head we can switch at priority 1 and switch back at a really low priority so meta data is correctly generated.
	 * @param string $template
	 * @return string
	 */
	public static function flip_the_query(){
		global $wp_query, $wp_the_query, $em_the_query;
		if( !empty($em_the_query) ){
			$old_query = $wp_the_query;
			$wp_query = $wp_the_query = $em_the_query;
			$em_the_query = $old_query;
		}
	}
	
	/**
	 * Short-circuits shortlink request if the post id is 0. This filter should only be called if we are messing with main wp_query due to formatting the taxonomy page by switching the template to a fake page.
	 *
	 * @param $shortlink
	 * @param $post_id
	 *
	 * @return mixed|string
	 */
	public static function pre_get_shortlink( $shortlink, $post_id ) {
		return $post_id === 0 ? '' : $shortlink;
	}
}