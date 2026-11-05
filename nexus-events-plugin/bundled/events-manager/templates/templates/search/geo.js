jQuery(document).on('em_maps_loaded', function() {
	jQuery('input.em-search-geo').each(function () {
		var input = /** @type {HTMLInputElement} */ jQuery(this);
		var wrapper = input.closest('div.em-search-geo');
		var autocomplete = new google.maps.places.Autocomplete(input[0]);
		var geo_coords = wrapper.find("input.em-search-geo-coords");

		var geo_field_status = function (status) {
			wrapper.data('status', status);
			var em_search = wrapper.closest('.em-search-legacy');
			// backcompat
			if( em_search.length > 0 ){
				// old templates - soon to be deprecated
				if( status == 'on' ){
					wrapper.css('background-image', wrapper.css('background-image').replace('search-geo.png', 'search-geo-on.png').replace('search-geo-off.png', 'search-geo-on.png'));
					em_search.find('select.em-search-country option:first-child').prop('selected','selected').trigger('change');
					em_search.find('.em-search-location').slideUp();
					em_search.find('.em-search-geo-units').slideDown();
				}else{
					if( status == 'off' ){
						wrapper.css('background-image', wrapper.css('background-image').replace('search-geo.png', 'search-geo-off.png').replace('search-geo-on.png', 'search-geo-off.png'));
					}else{
						wrapper.css('background-image', wrapper.css('background-image').replace('search-geo-off.png', 'search-geo.png').replace('search-geo-on.png', 'search-geo.png'));
					}
					let current_value = geo_coords.val();
					geo_coords.val('');
					if( current_value !== geo_coords.val() ){
						geo_coords.trigger('change');
					}
					em_search.find('.em-search-location').slideDown();
					em_search.find('.em-search-geo-units').slideUp();
				}
			}else{
				// new templates
				em_search = wrapper.closest('.em-search, .em-search-advanced');
				if( status === 'on' ){
					input.addClass('on').removeClass('off');
					em_search.find('select.em-search-country option:first-child').prop('selected','selected').trigger('change');
					em_search.find('.em-search-location').slideUp();
					em_search.find('.em-search-geo-units').slideDown();
				}else{
					if( status === 'off' ){
						input.addClass('off').removeClass('on');
					}else{
						input.removeClass('off').removeClass('on');
					}
					let current_value = geo_coords.val();
					geo_coords.val('');
					if( current_value !== geo_coords.val() ){
						geo_coords.trigger('change');
					}
					em_search.find('.em-search-location').slideDown();
					em_search.find('.em-search-geo-units').slideUp();
				}
			}
		};

		var ac_listener = function (place) {
			var place = autocomplete.getPlace();
			if (!place || !place.geometry) { //place not found
				if (input.val() == '' || input.val() == EM.geo_placeholder) {
					geo_field_status(false);
				} else {
					if (wrapper.data('last-search') == input.val()) {
						geo_field_status('on');
						let current_value = geo_coords.val();
						geo_coords.val(wrapper.data('last-coords'));
						if( current_value !== geo_coords.val() ){
							geo_coords.trigger('change');
						}
						return;
					}
					//do a nearest match suggestion as last resort
					if (input.val().length >= 2) {
						geo_field_status(false);
						autocompleteService = new google.maps.places.AutocompleteService();
						autocompleteService.getPlacePredictions({
							'input': input.val(),
							'offset': input.val().length
						}, function listentoresult(list, status) {
							if (list != null && list.length != 0) {
								placesService = new google.maps.places.PlacesService(document.getElementById('em-search-geo-attr'));
								placesService.getDetails({'reference': list[0].reference}, function detailsresult(detailsResult, placesServiceStatus) {
									//we have a match, ask the user
									wrapper.data('last-search', detailsResult.formatted_address);
									wrapper.data('last-coords', detailsResult.geometry.location.lat() + ',' + detailsResult.geometry.location.lng());
									if (input.val() == detailsResult.formatted_address || confirm(EM.geo_alert_guess.replace('%s', '"' + detailsResult.formatted_address + '"'))) {
										geo_field_status('on');
										let current_value = geo_coords.val();
										geo_coords.val(detailsResult.geometry.location.lat() + ',' + detailsResult.geometry.location.lng());
										if( current_value !== geo_coords.val() ){
											geo_coords.trigger('change');
										}
										input.val(detailsResult.formatted_address);
									} else {
										input.data('last-key', false);
										geo_field_status('off');
									}
								});
							} else {
								geo_field_status('off');
							}
						});
					} else {
						geo_field_status('off');
					}
				}
				wrapper.data('last-search', input.val());
				wrapper.data('last-coords', geo_coords.val());
				return;
			}
			geo_field_status('on');
			let current_value = geo_coords.val();
			geo_coords.val(place.geometry.location.lat() + ',' + place.geometry.location.lng());
			if( current_value !== geo_coords.val() ){
				geo_coords.trigger('change');
			}
			wrapper.data('last-search', input.val());
			wrapper.data('last-coords', geo_coords.val());
		};
		google.maps.event.addListener(autocomplete, 'place_changed', ac_listener);

		if (geo_coords.val() != '') {
			geo_field_status('on');
			wrapper.data('last-search', input.val());
			wrapper.data('last-coords', geo_coords.val());
		}
		input.on('keydown', function (e) {
			//if enter is pressed once during 'near' input, don't do anything so Google can select location, otherwise let behavior (form submittal) proceed
			if (e.which == 13) {
				if (this.getAttribute('data-last-key') != 13 || wrapper.data('status') != 'on') {
					e.preventDefault();
				}
			} else if( e.which == 8 && this.classList.contains('on') ){
				// clear a valid search and start again
				this.value = '';
				geo_field_status(false);
			}
			this.setAttribute('data-last-key', e.which);
		}).on('keypress', function(e){
			if( e.which !== 13 && this.classList.contains('on') ){
				// clear a valid search and start again
				this.value = '';
			}
		}).on('input', function(e){
			if (this.value == '') {
				geo_field_status(false);
			} else if (wrapper.data('last-search') != this.value) {
				geo_field_status('off');
			}
		}).on('click', function(){
			const end = this.value.length;
			this.setSelectionRange(end, end);
			this.focus();
		});
	});
});