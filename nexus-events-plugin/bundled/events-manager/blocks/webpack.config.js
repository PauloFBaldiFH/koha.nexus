/**
 * Extends the default @wordpress/scripts webpack config so that, in addition to
 * auto-discovering blocks via src/<block>/block.json, we also bundle a
 * standalone editor script for the Gutenberg validation guard.
 */
const path = require( 'path' );
const defaultConfig = require( '@wordpress/scripts/config/webpack.config' );

const baseEntry =
	typeof defaultConfig.entry === 'function'
		? defaultConfig.entry()
		: defaultConfig.entry;

module.exports = {
	...defaultConfig,
	entry: {
		...baseEntry,
		'gutenberg-validation/index': path.resolve(
			__dirname,
			'src/gutenberg-validation/index.js'
		),
	},
};
