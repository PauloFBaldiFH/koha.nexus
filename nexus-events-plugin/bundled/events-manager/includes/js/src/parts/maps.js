/*
 * MAP FUNCTIONS
 */
var em_maps_loaded = false;
var maps = {};
var maps_markers = {};
var maps_infoWindows = {};
var content
//loads maps script if not already loaded and executes EM maps script
function em_maps_load(){
	if( !em_maps_loaded ){
		if ( jQuery('script#google-maps').length == 0 && ( typeof google !== 'object' || typeof google.maps !== 'object' ) ){
			let script = document.createElement("script");
			script.type = "text/javascript";
			script.id = "google-maps";
			script.async = true;
			let proto = (EM.is_ssl) ? 'https:' : 'http:';
			if( typeof EM.google_maps_api !== 'undefined' ){
				script.src = proto + '//maps.google.com/maps/api/js?loading=async&v=quarterly&libraries=places&callback=em_maps&key='+EM.google_maps_api;
			}else{
				script.src = proto + '//maps.google.com/maps/api/js?loading=async&v=quarterly&libraries=places&callback=em_maps';
			}
			document.body.appendChild(script);
		}else if( typeof google === 'object' && typeof google.maps === 'object' && !em_maps_loaded ){
			em_maps();
		}else if( jQuery('script#google-maps').length > 0 ){
			jQuery(window).load(function(){ if( !em_maps_loaded ) em_maps(); }); //google isn't loaded so wait for page to load resources
		}
	}
}
jQuery(document).on('em_view_loaded_map', function( e, view, form ){
	if( !em_maps_loaded ){
		em_maps_load();
	}else{
		let map = view.find('div.em-locations-map');
		em_maps_load_locations( map[0] );
	}
});
/*
 * Custom JSON map styling vs Advanced Markers. Google forbids the legacy `styles` property when a `mapId` is present, and Advanced Markers require a `mapId` — the two are mutually exclusive. So when the site has custom JSON styling configured we build a raster map with NO mapId (so the styles apply) and fall back to the legacy google.maps.Marker that a raster map can host; otherwise we keep the mapId + Advanced Markers path.
 */
function em_map_get_styles( map_id ){
	if( typeof EM.google_map_id_styles == 'object' && typeof EM.google_map_id_styles[map_id] !== 'undefined' ){
		return EM.google_map_id_styles[map_id];
	}
	if( typeof EM.google_maps_styles !== 'undefined' ){
		return EM.google_maps_styles;
	}
	return null;
}
function em_map_create( el, map_options, map_id ){
	let styles = em_map_get_styles( map_id );
	if( styles ){
		map_options = jQuery.extend({}, map_options, { styles: styles });
		delete map_options.mapId; // styles are ignored (and warned about) while a mapId is present
	}
	let map = new google.maps.Map( el, map_options );
	map.em_styled = !!styles;
	return map;
}
function em_map_create_marker( AdvancedMarkerElement, map, marker_options, map_id ){
	let marker;
	if( map.em_styled ){
		// a styled raster map cannot host Advanced Markers, so use the legacy marker
		marker = new google.maps.Marker({
			position: marker_options.position,
			map: map,
			title: marker_options.title,
			draggable: !!marker_options.gmpDraggable,
		});
		marker.em_advanced = false;
	}else{
		marker = new AdvancedMarkerElement( marker_options );
		marker.em_advanced = true;
	}
	marker.em_map_id = map_id;
	return marker;
}
function em_marker_position( marker ){
	return ( typeof marker.getPosition === 'function' ) ? marker.getPosition() : marker.position;
}
//re-usable function to load global location maps
async function em_maps_load_locations( element ){
	const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
	let el = element;
	let map_id = el.getAttribute('id').replace('em-locations-map-','');
	let em_data;
	if ( document.getElementById('em-locations-map-coords-'+map_id) ) {
		em_data = JSON.parse( document.getElementById('em-locations-map-coords-'+map_id).text );
	} else {
		let coords_data = el.parentElement.querySelector('.em-locations-map-coords');
		if ( coords_data ) {
			em_data = JSON.parse( coords_data.text );
		} else {
			em_data = {};
		}
	}
	jQuery.getJSON(document.URL, em_data , function( data ) {
		if( data.length > 0 ){
			//define default options and allow option for extension via event triggers
			let map_options = {
				mapTypeId: google.maps.MapTypeId.ROADMAP,
				mapId: 'em-locations-map-' + map_id
			};
			jQuery(document).triggerHandler('em_maps_locations_map_options', map_options);
			let marker_options = {};
			jQuery(document).triggerHandler('em_maps_location_marker_options', marker_options);

			maps[map_id] = em_map_create(el, map_options, map_id);
			maps_markers[map_id] = [];

			let bounds = new google.maps.LatLngBounds();

			jQuery.map( data, function( location, i ){
				if( !(location.location_latitude == 0 && location.location_longitude == 0) ){
					let latitude = parseFloat( location.location_latitude );
					let longitude = parseFloat( location.location_longitude );
					let location_position = new google.maps.LatLng( latitude, longitude );
					//extend the default marker options
					jQuery.extend(marker_options, {
						position: location_position,
						map: maps[map_id]
					})
					let marker = em_map_create_marker(AdvancedMarkerElement, maps[map_id], marker_options, map_id);
					maps_markers[map_id] = marker;
					em_map_InfoWindow ( location.location_name, location.location_balloon, marker );
					//extend bounds
					bounds.extend(new google.maps.LatLng(latitude,longitude))
				}
			});
			// Zoom in to the bounds
			maps[map_id].fitBounds(bounds);

			//Call a hook if exists
			if( jQuery ) {
				jQuery(document).triggerHandler('em_maps_locations_hook', [maps[map_id], data, map_id, maps_markers[map_id]]);
			}
			document.dispatchEvent( new CustomEvent('em_maps_locations_hook', {
				detail: {
					map : maps[map_id],
					data : data,
					id : map_id,
					markers : maps_markers[map_id],
					el : el,
				},
				cancellable : true,
			}));
		} else {
			el.firstElementChild.innerHTML = 'No locations found';
			if( jQuery ) {
				jQuery(document).triggerHandler('em_maps_locations_hook_not_found', [ jQuery(el) ]);
			}
			document.dispatchEvent( new CustomEvent('em_maps_locations_hook_not_found', {
				detail: {
					id : map_id,
					el : el
				},
				cancellable : true,
			}));
		}
	});
}
async function em_maps_load_location(el){
	el = jQuery(el);
	const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
	let mapId = el.attr('id');
	let map_id = mapId.replace('em-location-map-','');
	let map_title = el.attr('title');
	let em_LatLng = new google.maps.LatLng( jQuery('#em-location-map-coords-'+map_id+' .lat').text(), jQuery('#em-location-map-coords-'+map_id+' .lng').text());
	//extend map and markers via event triggers
	let map_options = {
		zoom: 14,
		center: em_LatLng,
		mapTypeId: google.maps.MapTypeId.ROADMAP,
		mapTypeControl: false,
		gestureHandling: 'cooperative',
		mapId: mapId,
	};
	jQuery(document).triggerHandler('em_maps_location_map_options', map_options);
	maps[map_id] = em_map_create( document.getElementById('em-location-map-'+map_id), map_options, map_id);
	let marker_options = {
		position: em_LatLng,
		map: maps[map_id],
		title: map_title,
	};
	jQuery(document).triggerHandler('em_maps_location_marker_options', marker_options);
	let marker = em_map_create_marker(AdvancedMarkerElement, maps[map_id], marker_options, map_id);
	maps_markers[map_id] = marker;
	let content = jQuery('#em-location-map-info-'+map_id + ' .em-map-balloon-content').get(0);
	em_map_InfoWindow( map_title, content, marker, true );

	//JS Hook for handling map after instantiation
	//Example hook, which you can add elsewhere in your theme's JS - jQuery(document).on('em_maps_location_hook', function(){ alert('hi');} );
	jQuery(document).triggerHandler('em_maps_location_hook', [maps[map_id], infoWindow, maps_markers[map_id], map_id]);
	//map resize listener
	jQuery(window).on('resize', function(e) {
		google.maps.event.trigger(maps[map_id], "resize");
		maps[map_id].setCenter(em_marker_position(maps_markers[map_id]));
		maps[map_id].panBy(40,-70);
	});
}
jQuery(document).on('em_search_ajax', function(e, vars, wrapper){
	if( em_maps_loaded ){
		wrapper.find('div.em-location-map').each( function(index, el){ em_maps_load_location(el); } );
		wrapper.find('div.em-locations-map').each( function(index, el){ em_maps_load_locations(el); });
	}
});
//Load single maps (each map is treated as a seperate map).
async function em_maps() {
	/**
	 * InfoWindow object - Location info bubble on map, showing the current map
	 */
	let infoWindow;
	//Find all the maps on this page and load them
	jQuery('div.em-location-map').each( function(index, el){ em_maps_load_location(el); } );
	jQuery('div.em-locations-map').each( function(index, el){ em_maps_load_locations(el); } );

	//Location stuff - only needed if inputs for location exist
	if( jQuery('select#location-select-id, input#location-address').length > 0 ){
		const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
		let map
		let marker;

		// refresh map with current location info
		let refresh_map_location = function(){
			let location_latitude = jQuery('#location-latitude').val();
			let location_longitude = jQuery('#location-longitude').val();
			let hasCoords = location_latitude != 0 || location_longitude != 0;
			if( hasCoords ){
				let position = new google.maps.LatLng(location_latitude, location_longitude); //the location coords
				marker.position = position;
				let mapTitle = (jQuery('input#location-name').length > 0) ? jQuery('input#location-name').val():jQuery('input#title').val();
				mapTitle = em_esc_attr(mapTitle);
				marker.title = mapTitle ;
				marker.gmpDraggable = true;
				jQuery('#em-map').show();
				jQuery('#em-map-404').hide();
				google.maps.event.trigger(map, 'resize');
				map.setCenter(position);
				map.panBy(40,-55);
				infoWindow?.close();
				infoWindow = em_map_InfoWindow( mapTitle, em_esc_attr(jQuery('#location-address').val()) + '<br>' + em_esc_attr(jQuery('#location-town').val()), marker, true );
				jQuery(document).triggerHandler('em_maps_location_hook', [map, infoWindow, marker, 0]);
			} else {
				jQuery('#em-map').hide();
				jQuery('#em-map-404').show();
			}
		};

		// Add listeners for changes to address or location ID

		// get or refresh the map by location id
		let get_map_by_id = function(id){
			if(jQuery('#em-map').length > 0){
				jQuery('#em-map-404 .em-loading-maps').show();
				jQuery.getJSON(document.URL,{ em_ajax_action:'get_location', id:id }, function(data){
					let hasCoords = data.location_latitude != 0 && data.location_longitude != 0;
					if( hasCoords ){
						loc_latlng = new google.maps.LatLng(data.location_latitude, data.location_longitude);
						marker.position = loc_latlng;
						marker.title = data.location_name;
						marker.gmpDraggable = false;
						jQuery('#em-map').show();
						jQuery('#em-map-404').hide();
						jQuery('#em-map-404 .em-loading-maps').hide();
						map.setCenter(loc_latlng);
						map.panBy(40,-55);
						infoWindow?.close();
						infoWindow = em_map_InfoWindow( data.location_name, data.location_balloon, marker, true );
						google.maps.event.trigger(map, 'resize');
						jQuery(document).triggerHandler('em_maps_location_hook', [map, infoWindow, marker, 0]);
					}else{
						jQuery('#em-map').hide();
						jQuery('#em-map-404').show();
						jQuery('#em-map-404 .em-loading-maps').hide();
					}
				});
			}
		};
		jQuery('#location-select-id, input#location-id').on('change', function() { get_map_by_id( jQuery(this).val() ); } );

		// detect changes to address fields and build a coordinate from geocoding
		jQuery('#location-name, #location-town, #location-address, #location-state, #location-postcode, #location-country').on('change', function(){
			//build address
			if( jQuery(this).prop('readonly') === true ) return;
			let addresses = [ jQuery('#location-address').val(), jQuery('#location-town').val(), jQuery('#location-state').val(), jQuery('#location-postcode').val() ];
			let address = '';
			jQuery.each( addresses, function(i, val){
				if( val != '' ){
					address = ( address == '' ) ? address+val:address+', '+val;
				}
			});
			if( address == '' ){ //in case only name is entered, no address
				jQuery('#em-map').hide();
				jQuery('#em-map-404').show();
				return false;
			}
			//do country last, as it's using the text version
			if( jQuery('#location-country option:selected').val() != 0 ){
				address = ( address == '' ) ? address+jQuery('#location-country option:selected').text():address+', '+jQuery('#location-country option:selected').text();
			}
			//add working indcator whilst we search
			jQuery('#em-map-404 .em-loading-maps').show();
			//search!
			if( address != '' && jQuery('#em-map').length > 0 ){
				let geocoder = new google.maps.Geocoder();
				geocoder.geocode( { 'address': address }, function(results, status) {
					if (status == google.maps.GeocoderStatus.OK) {
						jQuery('#location-latitude').val(results[0].geometry.location.lat());
						jQuery('#location-longitude').val(results[0].geometry.location.lng());
					}
					refresh_map_location();
				});
			}
		});
		
		// Check if we are on a location editing page, and if address was previously entered, if so we check location coords
		let location_latitude = jQuery('#location-latitude').val();
		let location_longitude = jQuery('#location-longitude').val();
		let hasCoords = location_latitude != 0 || location_longitude != 0;
		if ( !hasCoords  ) {
			// check if there's any address items that were added previously
			if ( document.getElementById('location-address')?.value != '' && (document.getElementById('location-address')?.value != '' || document.getElementById('location-town')?.value != '' || document.getElementById('location-state')?.value != '' || document.getElementById('location-postcode')?.value != '' ) ) {
				// trigger a change so we reload the address and coords
				jQuery('#location-address').trigger('change');
				if ( 'google_maps_resave_location' in EM ) {
					alert(EM.google_maps_resave_location);
				}
			}
		}

		// Load map initially
		if(jQuery('#em-map').length > 0){
			let em_LatLng = new google.maps.LatLng(0, 0);
			let map_options = {
				zoom: 14,
				center: em_LatLng,
				mapTypeId: google.maps.MapTypeId.ROADMAP,
				mapTypeControl: false,
				gestureHandling: 'cooperative',
				mapId: 'em-map',
			};
			// the location editor keeps Advanced Markers (mapId) for the draggable coordinate picker; custom front-end JSON styling is intentionally not applied here (it can't coexist with a mapId, and a dark style hinders coordinate picking)
			map = new google.maps.Map( document.getElementById('em-map'), map_options);
			marker = new AdvancedMarkerElement({
				position: em_LatLng,
				map: map,
				gmpDraggable: true,
			});
			google.maps.event.addListener(marker, 'dragend', function() {
				let position = marker.position;
				jQuery('#location-latitude').val(position.lat);
				jQuery('#location-longitude').val(position.lng);
				map.setCenter(position);
				map.panBy(40,-55);
			});
			if( jQuery('#location-select-id').length > 0 ){
				jQuery('#location-select-id').trigger('change');
			}else{
				refresh_map_location();
			}
			jQuery(document).triggerHandler('em_map_loaded', [map, infoWindow, marker]);
		}
		//map resize listener
		jQuery(window).on('resize', function(e) {
			google.maps.event.trigger(map, "resize");
			map.setCenter(marker.position);
			map.panBy(40,-55);
		});
	}
	em_maps_loaded = true; //maps have been loaded
	jQuery(document).triggerHandler('em_maps_loaded');
}

function em_map_InfoWindow( title, content, marker, open = false ) {
	let title_content = document.createElement("div");
	let map_id = ('em_map_id' in marker) ? marker.em_map_id : marker.map.mapId.replace(/em-location-maps?-/,'');
	title_content.className = "em-map-balloon-title";
	title_content.innerHTML = title;
	if ( typeof content === 'string' ) {
		let wrapper = document.createElement("div");
		wrapper.innerHTML = content;
		content = wrapper;
	}
	// wrap content in div with class if not already done
	content.classList.add('em-map-balloon-content');
	let infoWindow = new google.maps.InfoWindow( {
		content: content,
		headerContent: title_content,
	} );
	infoWindow.addListener('domready', function() {
		marker.map.panBy(40,-70);
	});
	if ( !( map_id in maps_infoWindows ) ) {
		maps_infoWindows[ map_id ] = [];
	}
	maps_infoWindows[ map_id ].push( infoWindow );
	let open_options = {
		shouldFocus: false,
		anchor: marker,
		map: marker.map,
	};
	let click_event = ( ('em_advanced' in marker) ? marker.em_advanced : !(marker instanceof google.maps.Marker) ) ? 'gmp-click' : 'click';
	marker.addListener(click_event, () => {
		maps_infoWindows[ map_id ]?.forEach( ( infoWindow ) => infoWindow.close() );
		infoWindow.open( open_options );
	});
	if ( open ) {
		maps_infoWindows[ map_id ]?.forEach( ( infoWindow ) => infoWindow.close() );
		infoWindow.open( open_options );
	}
	return infoWindow;
}

/**
 * @deprecated use em_map_infowindow instead
 * @param marker
 * @param message
 * @param map
 */
function em_map_infobox(marker, message, map) {
	let iw = new google.maps.InfoWindow({ content: message });
	google.maps.event.addListener(marker, 'click', function() {
		if( infoWindow ) infoWindow.close();
		infoWindow = iw;
		iw.open(map,marker);
	});
}

function em_esc_attr( str ){
	if( typeof str !== 'string' ) return '';
	return str.replace(/</gi,'&lt;').replace(/>/gi,'&gt;');
}