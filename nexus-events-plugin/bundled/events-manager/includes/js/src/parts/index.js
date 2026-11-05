jQuery(document).ready( function($){

	// backcompat changes 6.x to 5.x
	if( $('#recurrence-frequency').length > 0  ){
		$('#recurrence-frequency').addClass('em-recurrence-frequency');
		$('.event-form-when .interval-desc').each( function(){
			this.classList.add(this.id);
		});
		$('.event-form-when .alternate-selector').each( function(){
			this.classList.add('em-' + this.id);
		});
		$('#recurrence-interval').addClass('em-recurrence-interval');
	}
	$('#em-wrapper').addClass('em');

	// Add keyboard accessibility for em-icon button spans
	$(document).on('keydown', 'span.em-icon[role="button"]', function(e){
		if( e.key === 'Enter' || e.keyCode === 13 ){
			e.preventDefault();
			$(this).trigger('click');
		}
	});

	/* Time Entry - legacy @deprecated */
	$('#start-time').each(function(i, el){
		$(el).addClass('em-time-input em-time-start').next('#end-time').addClass('em-time-input em-time-end').parent().addClass('em-time-range');
	});

	/*
	 * ADMIN AREA AND PUBLIC FORMS (Still polishing this section up, note that form ids and classes may change accordingly)
	 */
	//Events List
	//Approve/Reject Links
	$('.events-table').on('click', '.em-event-delete', function(){
		if( !confirm("Are you sure you want to delete?") ){ return false; }
		window.location.href = this.href;
	});
	//Forms
	$('#event-form #event-image-delete, #location-form #location-image-delete').on('click', function(){
		var el = $(this);
		if( el.is(':checked') ){
			el.closest('.event-form-image, .location-form-image').find('#event-image-img, #location-image-img').hide();
		}else{
			el.closest('.event-form-image, .location-form-image').find('#event-image-img, #location-image-img').show();
		}
	});

	//Manual Booking
	$(document).on('click', 'a.em-booking-button', function(e){
		e.preventDefault();
		var button = $(this);
		if( button.text() != EM.bb_booked && $(this).text() != EM.bb_booking){
			button.text(EM.bb_booking);
			var button_data = button.attr('id').split('_');
			$.ajax({
				url: EM.ajaxurl,
				dataType: 'jsonp',
				data: {
					event_id : button_data[1],
					_wpnonce : button_data[2],
					action : 'booking_add_one'
				},
				success : function(response, statusText, xhr, $form) {
					if(response.result){
						button.text(EM.bb_booked);
						button.addClass('disabled');
					}else{
						button.text(EM.bb_error);
					}
					if(response.message != '') alert(response.message);
					$(document).triggerHandler('em_booking_button_response', [response, button]);
				},
				error : function(){ button.text(EM.bb_error); }
			});
		}
		return false;
	});
	$(document).on('click', 'a.em-cancel-button', function(e){
		e.preventDefault();
		var button = $(this);
		if( button.text() != EM.bb_cancelled && button.text() != EM.bb_canceling){
			button.text(EM.bb_canceling);
			// old method is splitting id with _ and second/third items are id and nonce, otherwise supply it all via data attributes
			var button_data = button.attr('id').split('_');
			let button_ajax = {};
			if( button_data.length < 3 || !('booking_id' in button[0].dataset) ){
				// legacy support
				button_ajax = {
					booking_id : button_data[1],
					_wpnonce : button_data[2],
					action : 'booking_cancel',
				};
			}
			let ajax_data = Object.assign( button_ajax, button[0].dataset);
			$.ajax({
				url: EM.ajaxurl,
				dataType: 'jsonp',
				data: ajax_data,
				success : function(response, statusText, xhr, $form) {
					if(response.result){
						button.text(EM.bb_cancelled);
						button.addClass('disabled');
					}else{
						button.text(EM.bb_cancel_error);
					}
				},
				error : function(){ button.text(EM.bb_cancel_error); }
			});
		}
		return false;
	});
	$(document).on('click', 'a.em-booking-button-action', function(e){
		e.preventDefault();
		var button = $(this);
		var button_data = {
			_wpnonce : button.attr('data-nonce'),
			action : button.attr('data-action'),
		}
		if( button.attr('data-event-id') ) button_data.event_id =  button.attr('data-event-id');
		if( button.attr('data-booking-id') ) button_data.booking_id =  button.attr('data-booking-id');
		if( button.text() != EM.bb_booked && $(this).text() != EM.bb_booking){
			if( button.attr('data-loading') ){
				button.text(button.attr('data-loading'));
			}else{
				button.text(EM.bb_booking);
			}
			$.ajax({
				url: EM.ajaxurl,
				dataType: 'jsonp',
				data: button_data,
				success : function(response, statusText, xhr, $form) {
					if(response.result){
						if( button.attr('data-success') ){
							button.text(button.attr('data-success'));
						}else{
							button.text(EM.bb_booked);
						}
						button.addClass('disabled');
					}else{
						if( button.attr('data-error') ){
							button.text(button.attr('data-error'));
						}else{
							button.text(EM.bb_error);
						}
					}
					if(response.message != '') alert(response.message);
					$(document).triggerHandler('em_booking_button_action_response', [response, button]);
				},
				error : function(){
					if( button.attr('data-error') ){
						button.text(button.attr('data-error'));
					}else{
						button.text(EM.bb_error);
					}
				}
			});
		}
		return false;
	});

	//Datepicker - legacy
	var load_ui_css; //load jquery ui css?
	if( $('.em-date-single, .em-date-range, #em-date-start').length > 0 ){
		load_ui_css = true;
	}
	if( load_ui_css ) em_load_jquery_css();

	//previously in em-admin.php
	$('#em-wrapper input.select-all').on('change', function(){
		if($(this).is(':checked')){
			$('input.row-selector').prop('checked', true);
			$('input.select-all').prop('checked', true);
		}else{
			$('input.row-selector').prop('checked', false);
			$('input.select-all').prop('checked', false);
		}
	});

	/* Load any maps */
	if( $('.em-location-map').length > 0 || $('.em-locations-map').length > 0 || $('#em-map').length > 0 || $('.em-search-geo').length > 0 ){
		em_maps_load();
	}

	/* Location Type Selection */
	$('.em-location-types .em-location-types-select').on('change', function(){
		let el = $(this);
		if( el.val() == 0 ){
			$('.em-location-type').hide();
		}else{
			let location_type = el.find('option:selected').data('display-class');
			$('.em-location-type').hide();
			$('.em-location-type.'+location_type).show();
			if( location_type != 'em-location-type-place' ){
				jQuery('#em-location-reset a').trigger('click');
			}
		}
		if( el.data('active') !== '' && el.val() !== el.data('active') ){
			$('.em-location-type-delete-active-alert').hide();
			$('.em-location-type-delete-active-alert').show();
		}else{
			$('.em-location-type-delete-active-alert').hide();
		}
	}).trigger('change');

	//Finally, add autocomplete here
	if( jQuery( 'div.em-location-data [name="location_name"]' ).length > 0 ){
		$('div.em-location-data [name="location_name"]').em_selectize({
			plugins: ["restore_on_backspace"],
			valueField: "id",
			labelField: "label",
			searchField: "label",
			create:true,
			createOnBlur: true,
			maxItems:1,
			persist: false,
			addPrecedence : true,
			selectOnTab : true,
			diacritics : true,
			render: {
				item: function (item, escape) {
					return "<div>" + escape(item.label) + "</div>";
				},
				option: function (item, escape) {
					let meta = '';
					if( typeof(item.address) !== 'undefined' ) {
						if (item.address !== '' && item.town !== '') {
							meta = escape(item.address) + ', ' + escape(item.town);
						} else if (item.address !== '') {
							meta = escape(item.address);
						} else if (item.town !== '') {
							meta = escape(item.town);
						}
					}
					return  '<div class="em-locations-autocomplete-item">' +
						'<div class="em-locations-autocomplete-label">' + escape(item.label) + '</div>' +
						'<div style="font-size:11px; text-decoration:italic;">' + meta + '</div>' +
						'</div>';

				},
			},
			load: function (query, callback) {
				if (!query.length) return callback();
				$.ajax({
					url: EM.locationajaxurl,
					data: {
						q : query,
						method : 'selectize'
					},
					dataType : 'json',
					type: "POST",
					error: function () {
						callback();
					},
					success: function ( data ) {
						callback( data );
					},
				});
			},
			onItemAdd : function (value, data) {
				this.clearCache();
				var option = this.options[value];
				if( value === option.label ){
					jQuery('input#location-address').focus();
					return;
				}
				jQuery("input#location-name" ).val(option.value);
				jQuery('input#location-address').val(option.address);
				jQuery('input#location-town').val(option.town);
				jQuery('input#location-state').val(option.state);
				jQuery('input#location-region').val(option.region);
				jQuery('input#location-postcode').val(option.postcode);
				jQuery('input#location-latitude').val(option.latitude);
				jQuery('input#location-longitude').val(option.longitude);
				if( typeof(option.country) === 'undefined' || option.country === '' ){
					jQuery('select#location-country option:selected').removeAttr('selected');
				}else{
					jQuery('select#location-country option[value="'+option.country+'"]').attr('selected', 'selected');
				}
				jQuery("input#location-id" ).val(option.id).trigger('change');
				jQuery('div.em-location-data input, div.em-location-data select').prop('readonly', true).css('opacity', '0.5');
				jQuery('#em-location-reset').show();
				jQuery('#em-location-search-tip').hide();
				// selectize stuff
				this.disable();
				this.$control.blur();
				jQuery('div.em-location-data [class^="em-selectize"]').each( function(){
					if( 'selectize' in this ) {
						this.selectize.disable();
					}
				})
				// trigger hook
				jQuery(document).triggerHandler('em_locations_autocomplete_selected', [event, option]);
			}
		});
		jQuery('#em-location-reset a').on('click', function(){
			jQuery('div.em-location-data input, div.em-location-data select').each( function(){
				this.style.removeProperty('opacity')
				this.readOnly = false;
				if( this.type == 'text' ) this.value = '';
			});
			jQuery('div.em-location-data option:selected').removeAttr('selected');
			jQuery('input#location-id').val('');
			jQuery('#em-location-reset').hide();
			jQuery('#em-location-search-tip').show();
			jQuery('#em-map').hide();
			jQuery('#em-map-404').show();
			if(typeof(marker) !== 'undefined'){
				marker.setPosition(new google.maps.LatLng(0, 0));
				infoWindow.close();
				marker.setDraggable(true);
			}
			// clear selectize autocompleter values, re-enable any selectize ddms
			let $selectize = $("div.em-location-data input#location-name")[0].selectize;
			$selectize.enable();
			$selectize.clear(true);
			$selectize.clearOptions();
			jQuery('div.em-location-data select.em-selectize').each( function(){
				if( 'selectize' in this ){
					this.selectize.enable();
					this.selectize.clear(true);
				}
			});
			// return true
			return false;
		});
		if( jQuery('input#location-id').val() != '0' && jQuery('input#location-id').val() != '' ){
			jQuery('div.em-location-data input, div.em-location-data select').each( function(){
				this.style.setProperty('opacity','0.5', 'important')
				this.readOnly = true;
			});
			jQuery('#em-location-reset').show();
			jQuery('#em-location-search-tip').hide();
			jQuery('div.em-location-data select.em-selectize, div.em-location-data input.em-selectize-autocomplete').each( function(){
				if( 'selectize' in this ) this.selectize.disable();
			});
		}
	}

	// Add click handler for recurrence conversion links
	document.querySelectorAll( '.em-convert-recurrence-link' ).forEach( link => {
		link.addEventListener( 'click', function ( e ) {
			if ( !confirm( EM.convert_recurring_warning ) ) {
				e.preventDefault();
				return false;
			}
			let nonce = this.getAttribute( 'data-nonce' );
			if ( nonce ) {
				this.href = this.href.replace( 'nonce=x', 'nonce=' + nonce );
			}
		} );
	} );

	// trigger selectize loader
	em_setup_ui_elements(document);

	/* Done! */
	$(document).triggerHandler('em_javascript_loaded');
});

/**
 * Sets up external UI libraries and adds them to elements within the supplied container. This can be a jQuery or DOM element, subfunctions will either handle accordingly or this function will ensure it's the right one to pass on..
 * @param jQuery|DOMElement container
 */
function em_setup_ui_elements ( $container ) {
	let container = ( $container instanceof jQuery ) ? $container[0] : $container;
	// Selectize
	em_setup_selectize( $container );
	// Tippy
	em_setup_tippy( $container );
	// Moment JS
	em_setup_moment_times( $container );
	// Date & Time Pickers
	if( container.querySelector('.em-datepicker') ){
		em_setup_datepicker( container );
	}
	if( container.querySelector(".em-time-input") ){
		em_setup_timepicker( container );
	}
	// Phone numbers
	em_setup_phone_inputs( container );
	// let other things hook in
	document.dispatchEvent( new CustomEvent( 'em_setup_ui_elements', { detail: { container : container } } ) );
}

/**
 * Unsetup containers with UI elements, primarily useful if intending on duplicating an element which would require re-setup.
 * @param $container
 */
function em_unsetup_ui_elements( $container ) {
	let container = $container instanceof jQuery ? $container[0] : $container;
	em_unsetup_selectize( container );
	em_unsetup_tippy( container );
	em_unsetup_datepicker( container );
	em_unsetup_timepicker( container );
	em_unsetup_phone_inputs( container );
	// let other things hook in
	document.dispatchEvent( new CustomEvent( 'em_unsetup_ui_elements', { detail: { container : container } } ) );
}

/* Local JS Timezone related placeholders */
/* Moment JS Timzeone PH */
function em_setup_moment_times( container_element ) {
	container = jQuery(container_element);
	if( window.moment ){
		var replace_specials = function( day, string ){
			// replace things not supported by moment
			string = string.replace(/##T/g, Intl.DateTimeFormat().resolvedOptions().timeZone);
			string = string.replace(/#T/g, "GMT"+day.format('Z'));
			string = string.replace(/###t/g, day.utcOffset()*-60);
			string = string.replace(/##t/g, day.isDST());
			string = string.replace(/#t/g, day.daysInMonth());
			return string;
		};
		container.find('.em-date-momentjs').each( function(){
			// Start Date
			var el = jQuery(this);
			var day_start = moment.unix(el.data('date-start'));
			var date_start_string = replace_specials(day_start, day_start.format(el.data('date-format')));
			if( el.data('date-start') !== el.data('date-end') ){
				// End Date
				var day_end = moment.unix(el.data('date-end'));
				var day_end_string = replace_specials(day_start, day_end.format(el.data('date-format')));
				// Output
				var date_string = date_start_string + el.data('date-separator') + day_end_string;
			}else{
				var date_string = date_start_string;
			}
			el.text(date_string);
		});
		var get_date_string = function(ts, format){
			let date = new Date(ts * 1000);
			let minutes = date.getMinutes();
			if( format == 24 ){
				let hours = date.getHours();
				hours = hours < 10 ? '0' + hours : hours;
				minutes = minutes < 10 ? '0' + minutes : minutes;
				return hours + ':' + minutes;
			}else{
				let hours = date.getHours() % 12;
				let ampm = hours >= 12 ? 'PM' : 'AM';
				if( hours === 0 ) hours = 12; // the hour '0' should be '12'
				minutes = minutes < 10 ? '0'+minutes : minutes;
				return hours + ':' + minutes + ' ' + ampm;
			}
		}
		container.find('.em-time-localjs').each( function(){
			var el = jQuery(this);
			var strTime = get_date_string( el.data('time'), el.data('time-format') );
			if( el.data('time-end') ){
				var separator = el.data('time-separator') ? el.data('time-separator') : ' - ';
				strTime = strTime + separator + get_date_string( el.data('time-end'), el.data('time-format') );
			}
			el.text(strTime);
		});
	}
};

function em_load_jquery_css( wrapper = false ){
	if( EM.ui_css && jQuery('link#jquery-ui-em-css').length == 0 ){
		var script = document.createElement("link");
		script.id = 'jquery-ui-em-css';
		script.rel = "stylesheet";
		script.href = EM.ui_css;
		document.body.appendChild(script);
		if( wrapper ){
			em_setup_jquery_ui_wrapper();
		}
	}
}

function em_setup_jquery_ui_wrapper(){
	if( jQuery('#em-jquery-ui').length === 0 ){
		jQuery('body').append('<div id="em-jquery-ui" class="em">');
	}
}

/* Useful function for adding the em_ajax flag to a url, regardless of querystring format */
var em_ajaxify = function(url){
	if ( url.search('em_ajax=0') != -1){
		url = url.replace('em_ajax=0','em_ajax=1');
	}else if( url.search(/\?/) != -1 ){
		url = url + "&em_ajax=1";
	}else{
		url = url + "?em_ajax=1";
	}
	return url;
};

// load externals after DOM load, supplied by EM.assets, only if selector matches
var em_setup_scripts = function( $container = false ) {
	let container = $container || document;
	if( EM && 'assets' in EM ) {
		let baseURL = EM.url + '/includes/external/';
		for ( const [selector, assets] of Object.entries(EM.assets) ) {
			// load scripts if one element exists for selector
			if ( container.querySelector(selector) ) {
				if ('css' in assets) {
					// Iterate through assets.css object and add stylesheet to head
					for (const [id, value] of Object.entries(assets.css)) {
						// Check if the stylesheet with the given ID already exists
						if (!document.getElementById( id + '-css' )) {
							// Create a new link element for the stylesheet
							const link = document.createElement('link');
							link.id = id + '-css';
							link.rel = 'stylesheet';
							link.href = value.match(/^http/) ? value : baseURL + value;

							// Append the stylesheet to the document head
							document.head.appendChild(link);
						}
					}
				}
				if ('js' in assets) {
					// add a tracking of all assets to load, and execute loaded hooks after all assets are loaded and in order of dependence
					let loaded = {};
					let loadedListener = function( id ) {
						loaded[id] = false;
						if ( Object.entries( loaded ).length === Object.entries( assets.js ).length ) {
							// all items for this asset loaded, so we go through all the entries and fire their events
							for ( id of Object.keys( loaded ) ) {
								loadAsset( id )
							}
						}
					};
					let loadAsset = function( id ) {
						if ( !loaded[id] ) {
							let asset = assets.js[id];
							if ( typeof asset === 'object' && 'event' in asset ) {
								if ( asset?.requires) {
									loadAsset( asset.requires );
								}
								document.dispatchEvent( new CustomEvent( asset.event, {
									detail: {
										container: container,
									}
								} ) );
							}
							loaded[id] = true;
						}
					};
					// Iterate through assets.js object and add script to head
					for ( const [ id, value ] of Object.entries(assets.js)) {
						// Check if the script with the given ID already exists
						if ( !document.getElementById( id + '-js' ) ) {
							// Create a new script element for the JavaScript file
							const script = document.createElement('script');
							script.id = id + '-js';
							script.async = true;
							if ( typeof value === 'object' ) {
								// add locale data
								if ( 'locale' in value && value.locale ) {
									script.dataset.locale = value.locale;
								}
								script.src = value.url.match(/^http/g) ? value.url : baseURL + value.url;
							} else {
								script.src = value.match(/^http/g) ? value : baseURL + value;
							}
							// listen for loads so we execute the real onload hooks once all files are loaded (or errorred out)
							script.onload = () => loadedListener(id);
							script.onerror = () => loadedListener(id);
							// Append the script to the document head
							document.head.appendChild(script);
						}
					}
				}
			}
		}
	}
}
document.addEventListener('DOMContentLoaded', () => em_setup_scripts( document ));