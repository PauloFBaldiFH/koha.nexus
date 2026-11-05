module.exports = function(grunt) {

	let sourceSets = {
		'events-manager': [
			'parts/index.js',
			'parts/list-table.js',
			'parts/list-table-bookings.js',
			'parts/datepicker.js',
			'parts/timepicker.js',
			'parts/selectize.js',
			'parts/tippy.js',
			'parts/maps.js',
			'parts/modal.js',
			'parts/search.js',
			'parts/calendar.js',
			'parts/phone.js',
			'parts/externals.js',
			'parts/final.js'
		],
		'events-manager-event-editor': [
			'parts/timeranges-editor.js',
			'parts/event-editor.js',
			'parts/event-editor/recurrences/add-remove.js',
			'parts/event-editor/recurrences/drag-drop.js',
			'parts/event-editor/recurrences/reschedule.js',
			'parts/event-editor/recurrences/recurring-datetimes.js',
			'parts/event-editor/recurrences/ui-functions.js',
			'parts/event-editor/recurrences/ui-form.js',
			'parts/event-editor/recurrences/ui-advanced.js',
			'parts/event-editor/recurrences/ui-elements.js',
			'parts/event-editor/tickets/ticket-editor.js'
		]
	};

	// Build dynamic configuration
	let concatConfig = {
		options: {
			sourceMap: true,
			separator: '\n\n',
		}
	};

	let terserConfig = {
		options: {
			compress: true,
			mangle: true,
			sourceMap: {
				root: 'src'
			},
		}
	};

	// Generate tasks for each source set
	Object.keys(sourceSets).forEach(function(setName) {
		let sources = sourceSets[setName];

		// Add concat task for this set
		concatConfig[setName] = {
			sourceMap: true,
			src: sources,
			dest: '../' + setName + '.js',
		};

		// Add terser task for this set
		terserConfig[setName] = {
			options: {
				sourceMap: {
					root: 'src',
					url: setName + '.min.js.map'
				}
			},
			src: sources,
			dest: '../' + setName + '.min.js'
		};
	});

	// Project configuration.
	grunt.initConfig({
		concat: concatConfig,
		terser: terserConfig,
	});

	grunt.loadNpmTasks('grunt-contrib-concat');
	grunt.loadNpmTasks('grunt-terser');

	// Default task(s).
	grunt.registerTask('default', ['concat','terser']);

};