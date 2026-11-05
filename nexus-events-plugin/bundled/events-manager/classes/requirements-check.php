<?php
namespace EM;

/* Thanks Mark Jaquith - https://markjaquith.wordpress.com/2018/02/19/handling-old-wordpress-and-php-versions-in-your-plugin/ */

use EM_Admin_Notice;

class Requirements_Check {
	private $title;
	private $php;
	private $wp;
	private $file;
	private $dependencies;
	private $version;
	private $installed;
	
	public function __construct( $args = [] ) {
		$args = array_merge( array(
			'title' => 'Events Manager',
			'file' => EM_DIR.'/events-manager.php',
			'php' => '7.4',
			'wp' => '5.3',
			'version' => EM_VERSION,
			'installed' => 'dbem_version',
			'dependencies' => array(),
		), $args );
		$this->title = $args['title'];
		$this->php = $args['php'];
		$this->wp = $args['wp'];
		$this->file = $args['file'];
		$this->dependencies = $args['dependencies'];
		$this->version = $args['version'];
		$this->installed = get_option($args['installed']);
	}
	
	public function passes( $deactivate = true ) {
		$passes = $this->php_passes() && $this->wp_passes() && $this->dependencies_passes();
		if ( ! $passes && $deactivate ) {
			add_action( 'admin_notices', array( $this, 'deactivate' ) );
		}
		return $passes;
	}
	
	public function deactivate() {
		if ( isset( $this->file ) ) {
			deactivate_plugins( plugin_basename( $this->file ) );
		}
	}
	
	private function php_passes() {
		if ( $this->__php_at_least( $this->php ) ) {
			return true;
		} else {
			add_action( 'admin_notices', array( $this, 'php_version_notice' ) );
			return false;
		}
	}
	
	private static function __php_at_least( $min_version ) {
		return version_compare( phpversion(), $min_version, '>=' );
	}
	
	public function php_version_notice() {
		echo '<div class="error">';
		echo "<p><code>" . esc_html( $this->title ) . "</code> cannot run on PHP versions older than " . $this->php . '. Please contact your host and ask them to upgrade.</p>';
		echo '</div>';
	}
	
	private function wp_passes() {
		if ( $this->__wp_at_least( $this->wp ) ) {
			return true;
		} else {
			add_action( 'admin_notices', array( $this, 'wp_version_notice' ) );
			return false;
		}
	}
	
	private static function __wp_at_least( $min_version ) {
		return version_compare( get_bloginfo( 'version' ), $min_version, '>=' );
	}
	
	public function wp_version_notice() {
		echo '<div class="error">';
		echo "<p>The &#8220;" . esc_html( $this->title ) . "&#8221; plugin cannot run on WordPress versions older than " . $this->wp . '. Please update WordPress.</p>';
		echo '</div>';
	}
	
	private function dependencies_passes() {
		foreach( $this->dependencies as $dependency ){
			$check = $this->check_dependency( $dependency );
			if( $check !== true ){
				if( $check === 'recommended' ) {
					if ( version_compare( $this->version, $this->installed, '>' ) ) {
						// add admin notice that can be dismissed, so it's not naggy
						// translators: plugin names and version numbers
						$warning = __('%1$s recommends %2$s version %3$s or greater installed. Earlier versions may cause unexpected issues.', 'events-manager');
						$warning = sprintf( esc_html($warning), '<code>' . $this->title . '</code>', '<a href="'. $dependency['url'] .'">' . $dependency['name'] . '</a>', $dependency['minimum']);
						$EM_Admin_Notice = new EM_Admin_Notice( $dependency['name'].'-minimum', 'warning', $warning );
						\EM_Admin_Notices::add( $EM_Admin_Notice );
					}
				} else {
					if( !has_action( 'admin_notices', array( $this, 'dependency_notices' ) ) ) {
						add_action( 'admin_notices', array( $this, 'dependency_notices' ) );
					}
					return false;
				}
			}
		}
		return true;
	}
	
	private function check_dependency( $dependency ){
		if( defined($dependency['version']) ){
			// check version required
			if( version_compare( $dependency['minimum'], constant($dependency['version']), '>' ) ) {
				return 'minimum';
			}
			if( !empty($dependency['recommended']) && version_compare( $dependency['recommended'], constant($dependency['version']), '>' ) ) {
				return 'recommended';
			}
		} elseif( isset($dependency['required']) && $dependency['required'] ) {
			// not installed
			return 'missing';
		}
		return true;
	}
	
	public function dependency_notices() {
		foreach( $this->dependencies as $dependency ){
			$check_dependency = $this->check_dependency( $dependency );
			if( $check_dependency === 'minimum' ){
				// check version required
				if( version_compare( $dependency['minimum'], $dependency['version'], '>' ) ) {
					// translators: plugin names and version numbers
					$warning = __('%1$s requires %2$s version %3$s or greater installed.', 'events-manager');
					?>
					<div class="error">
						<p style="font-weight:bold;">
							<?php echo sprintf( esc_html($warning), '<code>' . $this->title . '</code>', '<a href="'. $dependency['url'] .'">' . $dependency['name'] . '</a>', $dependency['minimum']); ?>
						</p>
					</div>
					<?php
				}
			} elseif ( $check_dependency === 'missing' ) {
				// translators: plugin names
				$warning = esc_html__('%1$s requires %2$s to be installed and active.', 'em-wc');
				?>
				<div class="error"><p><strong><?php echo sprintf($warning,  '<code>' . $this->title . '</code>', '<a href="'. $dependency['url'] .'">' . $dependency['name'] . '</a>'); ?></p></strong></div>
				<?php
			}
		}
	}
}