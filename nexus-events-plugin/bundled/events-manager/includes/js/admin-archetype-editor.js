// DOMContentLoaded - already loaded via EM loader

// Access the variables from EM.archetypesEditor
const i18n = EM.archetypesEditor?.i18n || {};
const repeatingEnabled = EM.archetypesEditor?.repeating_enabled || false;
const postTypes = (EM.archetypesEditor?.post_types || []).map(pt => String(pt).toLowerCase());
const archetypes = document.getElementById( 'archetypes-list' );
let container = document.getElementById( 'event-archetypes-container' );

// Enable base-event-form-extras inputs/textareas (used when a new archetype is added dynamically)
function enableBaseExtras() {
	const extras = container.querySelector('.base-event-form-extras');
	if (!extras) return;
	extras.querySelectorAll('input, textarea, select').forEach(el => {
		if (el.disabled) el.disabled = false;
	});
}

// If there are no archetypes, (re)check and disable all base extras checkboxes
function maybeResetBaseExtras() {
	const extras = container.querySelector('.base-event-form-extras');
	if (!extras) return;
	const items = archetypes.querySelectorAll('.archetype-item');
	if (items.length === 0) {
		extras.querySelectorAll('input[type="checkbox"]').forEach(el => {
			el.checked = true;
			el.disabled = true;
		});
	}
}

// Handle edit pencil for base event CPT fields
container.addEventListener('click', function(e) {
	if (e.target.matches('.edit-base-cpt')) {
		const input = e.target.previousElementSibling.previousElementSibling;
		const hiddenNonce = e.target.previousElementSibling;

		if (input.disabled) {
			// Show warning message
			if (confirm(i18n.warning_cpt_change)) {
				// Enable the input and set the name attribute
				input.disabled = false;
				input.name = input.getAttribute('data-name');

				// Set the name for the hidden nonce input
				hiddenNonce.name = hiddenNonce.getAttribute('data-name');

				// Focus the input
				input.focus();
			}
		}
	}
});

// Prevent form submission when hitting enter on inputs
container.addEventListener( 'keypress', function ( e ) {
	if ( (e.target.matches( '.archetype-item input[type="text"]' ) ||
			e.target.matches( '.base-event-form input[type="text"]' )) &&
		e.key === 'Enter' ) {
		e.preventDefault();
	}
} );

// Add new archetype
container.querySelector( '#add-new-archetype' )?.addEventListener( 'click', function () {
	// Get the template content and add it to the archetypes list
	const template = container.querySelector( '#archetype-template' ).content.cloneNode(true);
	const frag = template;
	archetypes.appendChild(frag);
	// Ensure new item is marked and in edit mode
	const newItem = archetypes.lastElementChild;
	if (newItem && newItem.classList.contains('archetype-item')) {
		newItem.dataset.key = 'new';
		newItem.querySelectorAll( '.archetype-display' ).forEach( el => { el.style.display = 'none' } );
		newItem.querySelectorAll('.archetype-edit').forEach( el => { el.style.display = 'table-row-group' } );
	}
	// Enable base extras now that we have at least one archetype
	enableBaseExtras();
} );

// Edit archetype
container.addEventListener( 'click', function ( e ) {
	if ( e.target.matches( '.edit-archetype' ) ) {
		const item = e.target.closest( '.archetype-item' );
		item.querySelectorAll( '.archetype-display' ).forEach( el => { el.style.display = 'none' } );
		item.querySelectorAll( '.archetype-edit' ).forEach( el => { el.style.display = 'table-row-group' } );
	}
} );

// Cancel edit
container.addEventListener( 'click', function ( e ) {
	if ( e.target.matches( '.cancel-edit' ) ) {
		const item = e.target.closest( '.archetype-item' );
		// If this is a newly created archetype, remove it entirely
		if ( item && item.dataset.key === 'new' ) {
			item.remove();
			// If no archetypes remain, reset base extras
			maybeResetBaseExtras();
			updateArchetypesInput();
			return;
		}
		item.querySelectorAll( '.archetype-edit' ).forEach( el => { el.style.display = 'none' } );
		item.querySelectorAll( '.archetype-display' ).forEach( el => { el.style.display = 'table-row-group' } );
	}
} );

// Edit CPT name (with warning)
container.addEventListener( 'click', function ( e ) {
	if ( e.target.matches( '.edit-cpt' ) ) {
		const input = e.target.previousElementSibling;

		if ( input.disabled ) {
			if ( confirm( i18n.warning_cpt_change ) ) {
				input.disabled = false;
				input.focus();
			}
		}
	}
} );

// Save archetype
container.addEventListener( 'click', function ( e ) {
	if ( e.target.matches( '.save-archetype' ) ) {
		const item = e.target.closest( '.archetype-item' );
		const isValid = validateArchetype( item );

		if ( !isValid ) {
			return;
		}

		// Update the display view with the new values
		updateArchetypeDisplay( item );

		// Hide edit form, show display view
		item.querySelectorAll( '.archetype-edit' ).forEach( el => { el.style.display = 'none' } );
		item.querySelectorAll( '.archetype-display' ).forEach( el => { el.style.display = 'table-row-group' } );

		// Update the hidden input
		updateArchetypesInput();
	}
} );

// Delete archetype (confirmation only for existing, not-new items)
container.addEventListener( 'click', function ( e ) {
	if ( e.target.matches( '.delete-archetype' ) ) {
		const item = e.target.closest( '.archetype-item' );
		const isNew = item && item.dataset.key === 'new';
		if ( item ) {
			if ( !isNew ) {
				if ( confirm( i18n.confirm_delete ) ) {
					// add a hidden input to delete CPT, it's processed when saving
					let nonceEl = document.createElement('input');
					nonceEl.setAttribute('type', 'hidden');
					nonceEl.setAttribute('value', item.dataset.cpt );
					nonceEl.setAttribute('data-delete-nonce', item.dataset.deleteNonce );
					archetypes.parentElement.append(nonceEl);
					// remove item and refresh values
					item.remove();
					updateArchetypesInput();
					// If no archetypes remain, reset base extras
					maybeResetBaseExtras();
				}
			} else {
				// New items are deleted without confirmation
				item.remove();
				updateArchetypesInput();
				// If no archetypes remain, reset base extras
				maybeResetBaseExtras();
			}
		}
	}
} );

// Listen for changes to the archetype-label inputs and update the h4 title accordingly
archetypes.addEventListener('input', function(e) {
	if (e.target && e.target.classList.contains('archetype-label')) {
		const item = e.target.closest('.archetype-item');
		if (item) {
			const h4 = item.querySelector('h4');
			if (h4) {
				// Get the input value
				const labelValue = e.target.value;

				// Preserve any special label (like Main) that might be in a span
				const span = h4.querySelector('span');
				if ( span ) {
					// If there's a span (for Main archetype), set the text before the span
					h4.textContent = '';
					h4.appendChild( document.createTextNode(labelValue + " ") );
					h4.appendChild( span );
				} else {
					// For regular archetypes, just update the text
					h4.textContent = labelValue;
				}
			}
		}
	}
});

// Validate archetype data
function validateArchetype( item ) {
	let valid = true;
	let filled = true;
	const label = item.querySelector( '.archetype-label' ).value.trim();
	const labelSingle = item.querySelector( '.archetype-label-single' ).value.trim();
	const slug = item.querySelector( '.archetype-slug' ).value.trim();
	const cpt = item.querySelector( '.archetype-cpt' ).value.trim();
	const cpts = item.querySelector( '.archetype-cpts' ).value.trim();
	const icon = item.querySelector( '.archetype-icon' ).value.trim();

	// Reset previous error styling
	item.querySelectorAll( 'input' ).forEach( input => {
		input.style.borderColor = '';
	} );

	// Check required fields
	if ( !label ) {
		item.querySelector( '.archetype-label' ).style.borderColor = 'red';
		filled = false;
	}

	if ( !labelSingle ) {
		item.querySelector( '.archetype-label-single' ).style.borderColor = 'red';
		filled = false;
	}

	if ( !slug ) {
		item.querySelector( '.archetype-slug' ).style.borderColor = 'red';
		filled = false;
	}

	if ( !cpt ) {
		item.querySelector( '.archetype-cpt' ).style.borderColor = 'red';
		filled = false;
	}

	if ( !cpts ) {
		item.querySelector( '.archetype-cpts' ).style.borderColor = 'red';
		filled = false;
	}

	// Validate slug format (lowercase, no spaces, allow slashes and hyphens)
	if ( slug && !/^[a-z0-9\/-]+$/.test( slug ) ) {
		alert( i18n.error_slug_format );
		item.querySelector( '.archetype-slug' ).style.borderColor = 'red';
		valid = false;
	}

	// Validate CPT format (lowercase, no spaces, etc.)
	let cptInput = item.querySelector( '.archetype-cpt' );
	if ( !cptInput.disabled && cpt && !/^[a-z0-9_-]+$/.test( cpt ) ) {
		alert( i18n.error_cpt_format );
		cptInput.style.borderColor = 'red';
		valid = false;
	}

	let cptsInput = item.querySelector( '.archetype-cpts' );
	if ( !cptsInput.disabled && cpts && !/^[a-z0-9_-]+$/.test( cpts ) ) {
		alert( i18n.error_cpts_format );
		cptsInput.style.borderColor = 'red';
		valid = false;
	}

	// Check CPT does not conflict with existing WP post types
	if ( !cptInput.disabled && cpt && postTypes.includes(cpt.toLowerCase()) ) {
		alert( i18n.error_cpt_exists );
		item.querySelector( '.archetype-cpt' ).style.borderColor = 'red';
		valid = false;
	}

	// Validate icon format (lowercase, no spaces, allow slashes and hyphens, or URL)
	let isValidUrl = function (str) {
		try {
			new URL(str);
			return true;
		} catch (e) {
			return false;
		}
	}
	if ( icon && !( /^dashicons\-[a-z0-9\/-]+$/.test( icon ) || isValidUrl(icon) ) ) {
		alert( i18n.error_icon_format );
		item.querySelector( '.archetype-icon' ).style.borderColor = 'red';
		valid = false;
	}

	if ( !filled ) {
		alert( i18n.error_required_fields );
	}

	return valid && filled;
}

// Update the display view generically based on data-name and preview classes
function updateArchetypeDisplay( item ) {
	const yes = i18n.yes || 'Yes';
	const no = i18n.no || 'No';
	const inputs = item.querySelectorAll('[data-name]');

	// Update the title (from label)
	const labelInput = item.querySelector('[data-name="label"]');
	if (labelInput) {
		const h4 = item.querySelector('h4');
		if (h4 && h4.firstChild) {
			h4.firstChild.nodeValue = (labelInput.value || '') + ' ';
		}
	}

	inputs.forEach(el => {
		const displayClass = Array.from(el.classList).find(c => c.indexOf('archetype-display-') === 0);
		if (!displayClass) return;
		const cell = item.querySelector('.' + displayClass);
		if (!cell) return;
		if (el.type === 'checkbox') {
			cell.textContent = el.checked ? yes : no;
		} else {
			cell.textContent = el.value === '' && cell.getAttribute('placeholder') ? cell.getAttribute('placeholder') : el.value;
		}
	});
}

// Update the hidden input with all archetype data
function updateArchetypesInput() {
	const archetypesData = {};

	// Process each archetype item
	archetypes.querySelectorAll('.archetype-item').forEach(item => {
		if (item.dataset.delete) return; // Skip items marked for deletion

		// get values for this archetype
		const fields = item.querySelectorAll('[data-name]');
		if (!fields.length) return;
		// Create a temporary form and clone the entire archetype item into it
		const form = document.createElement('form');
		const clone = item.cloneNode(true);
		form.appendChild(clone);
		// In the clone, copy data-name to name so FormData picks them up
		form.querySelectorAll('[data-name]').forEach(el => {
			const dn = el.getAttribute('data-name');
			if (dn) el.setAttribute('name', dn);
		});
		// Build FormData from the temporary form (only named inputs are included)
		const fd = new FormData(form);
		const query = new URLSearchParams(fd).toString();
		// Convert FormData to query string, then parse using qs for nested/array support
		const obj = Qs.parse(query);

		// Include CPT/CPTS nonces if unlocked (use original item for disabled and data-nonce)
		const cptInput = item.querySelector('.archetype-cpt');
		if (cptInput && cptInput.disabled === false && cptInput.dataset.nonce) {
			obj.cpt_nonce = cptInput.dataset.nonce;
		}
		const cptsInput = item.querySelector('.archetype-cpts');
		if (cptsInput && cptsInput.disabled === false && cptsInput.dataset.nonce) {
			obj.cpts_nonce = cptsInput.dataset.nonce;
		}

		// Determine key: original CPT or current CPT value
		const key = item.dataset.cpt || obj.cpt;
		if ( key ) {
			archetypesData[key] = Object.assign({}, archetypesData[key] || {}, obj);
		}
	});

	// find all CPTs to delete
	const cptsToDelete = {};
	const deleteNonceInputs = archetypes.parentElement.querySelectorAll('input[type="hidden"][data-delete-nonce]');
	if (deleteNonceInputs && deleteNonceInputs.length > 0) {
		deleteNonceInputs.forEach(item => {
			cptsToDelete[item.value] = item.dataset.deleteNonce;
		});
	}

	// Create the final data object and store in hidden input
	const data = { custom: archetypesData, delete: cptsToDelete };
	document.getElementById('event-archetypes-input').value = JSON.stringify(data);
	console.log('Saved archetypes: %o', data);
}

// Check and handle archetypes UI visibility based on mode select
function toggleArchetypesUI() {
	const modeSelect = document.querySelector( 'select[name="dbem_ms_archetypes_mode"]' );
	const archetypesUI = document.querySelector( '.archetypes-ui-container' );
	if ( modeSelect && archetypesUI ) {
		archetypesUI.classList.toggle('hidden', modeSelect.value === 'custom');
	}
}
toggleArchetypesUI();
document.querySelector( 'select[name="dbem_ms_archetypes_mode"]' )?.addEventListener( 'change', toggleArchetypesUI );

// Normalize accented characters to base characters
function normalizeAccents(str) {
	const accentMap = {
		'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'ā': 'a', 'ã': 'a', 'å': 'a', 'ą': 'a', 'ă': 'a', 'ǎ': 'a', 'ȧ': 'a', 'ạ': 'a',
		'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e', 'ē': 'e', 'ę': 'e', 'ě': 'e', 'ė': 'e', 'ẹ': 'e',
		'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i', 'ī': 'i', 'į': 'i', 'ǐ': 'i', 'ị': 'i',
		'ó': 'o', 'ò': 'o', 'ö': 'o', 'ô': 'o', 'ō': 'o', 'õ': 'o', 'ø': 'o', 'ő': 'o', 'ǒ': 'o', 'ọ': 'o',
		'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u', 'ū': 'u', 'ů': 'u', 'ű': 'u', 'ǔ': 'u', 'ụ': 'u',
		'ý': 'y', 'ỳ': 'y', 'ÿ': 'y', 'ŷ': 'y', 'ȳ': 'y', 'ỵ': 'y',
		'ñ': 'n', 'ń': 'n', 'ň': 'n', 'ņ': 'n', 'ṅ': 'n', 'ṇ': 'n',
		'ç': 'c', 'ć': 'c', 'č': 'c', 'ċ': 'c', 'ĉ': 'c', 'ḉ': 'c',
		'ş': 's', 'š': 's', 'ś': 's', 'ș': 's', 'ṡ': 's', 'ṣ': 's',
		'ğ': 'g', 'ǧ': 'g', 'ģ': 'g', 'ġ': 'g', 'ḡ': 'g',
		'ř': 'r', 'ŕ': 'r', 'ṙ': 'r', 'ṛ': 'r',
		'ł': 'l', 'ľ': 'l', 'ļ': 'l', 'ḷ': 'l', 'ḹ': 'l',
		'ž': 'z', 'ź': 'z', 'ż': 'z', 'ẓ': 'z', 'ẕ': 'z',
		'đ': 'd', 'ď': 'd', 'ḍ': 'd', 'ḑ': 'd',
		'ţ': 't', 'ť': 't', 'ț': 't', 'ṭ': 't', 'ṫ': 't',
		'ķ': 'k', 'ḳ': 'k', 'ḵ': 'k',
		'ḥ': 'h', 'ḩ': 'h', 'ḫ': 'h',
		'ḅ': 'b', 'ḇ': 'b',
		'ṗ': 'p', 'ṕ': 'p',
		'ṃ': 'm', 'ṁ': 'm',
		'ẇ': 'w', 'ẁ': 'w', 'ẃ': 'w', 'ẅ': 'w',
		'ẋ': 'x', 'ẍ': 'x',
		'ḟ': 'f',
		'ṽ': 'v', 'ṿ': 'v',
	};

	return str.toLowerCase().replace(/[^\x00-\x7F]/g, function(char) {
		return accentMap[char] || char;
	});
}

// Auto-populate CPT field from singular label
function autoPopulateSingularCPT(labelValue, cptInput) {
	if (!labelValue.trim() || !cptInput || cptInput.disabled || cptInput.getAttribute('data-edited') ) {
		return;
	}

	// Normalize accents, convert to lowercase, replace spaces with hyphens, remove non-alphanumeric chars except hyphens and underscores
	let cptValue = normalizeAccents(labelValue)
		.toLowerCase()
		.replace(/\s+/g, '-')
		.replace(/[^a-z0-9_-]/g, '')
		.substring(0, 20); // Limit to 20 chars

	cptInput.value = cptValue;
}

// Auto-populate CPTs field from plural label
function autoPopulatePluralCPT(labelValue, cptsInput) {
	if (!labelValue.trim() || !cptsInput || cptsInput.disabled || cptsInput.getAttribute('data-edited')) {
		return;
	}

	// Normalize accents, convert to lowercase, replace spaces with hyphens, remove non-alphanumeric chars except hyphens and underscores
	let cptsValue = normalizeAccents(labelValue)
		.toLowerCase()
		.replace(/\s+/g, '-')
		.replace(/[^a-z0-9_-]/g, '')
		.substring(0, 20); // Limit to 20 chars

	cptsInput.value = cptsValue;
}

// Mark CPT fields as edited when they are directly changed by the user
container.addEventListener('change', function(e) {
	if (e.target.classList.contains('archetype-cpt') || e.target.classList.contains('archetype-cpts')) {
		// Mark as manually edited to prevent future auto-population
		e.target.setAttribute('data-edited', 'true');
	}
});

// Reset data-edited attribute and attempt auto-population when CPT field is cleared and loses focus
container.addEventListener('blur', function(e) {
	if ( e.target.classList.contains('archetype-cpt') || e.target.classList.contains('archetype-cpts') ) {
		// Custom archetypes: if the field is empty, reset the edited flag and try to auto-populate
		if ( !e.target.value.trim() ) {
			e.target.removeAttribute('data-edited');

			// Find the corresponding label field and attempt auto-population
			const item = e.target.closest('.archetype-item');
			if ( item ) {
				if ( e.target.classList.contains('archetype-cpt') ) {
					// For singular CPT field, use singular label
					const singularLabelInput = item.querySelector('.archetype-label-single');
					if (singularLabelInput && singularLabelInput.value.trim()) {
						autoPopulateSingularCPT(singularLabelInput.value, e.target);
					}
				} else if ( e.target.classList.contains('archetype-cpts') ) {
					// For plural CPT field, use plural label
					const pluralLabelInput = item.querySelector('.archetype-label');
					if (pluralLabelInput && pluralLabelInput.value.trim()) {
						autoPopulatePluralCPT(pluralLabelInput.value, e.target);
					}
				}
			}
		}
	}

	// Base Event CPT fields
	if ( (e.target.id === 'em_cp_events_cpt' || e.target.id === 'em_cp_events_cpts') && !e.target.value.trim() ) {
		if ( e.target.id === 'em_cp_events_cpt' ) {
			const labelSingle = container.querySelector('#dbem_cp_events_label_single');
			if (labelSingle && labelSingle.value.trim()) {
				autoPopulateSingularCPT(labelSingle.value, e.target);
			}
		} else {
			const labelPlural = container.querySelector('#dbem_cp_events_label');
			if (labelPlural && labelPlural.value.trim()) {
				autoPopulatePluralCPT(labelPlural.value, e.target);
			}
		}
	}

	// Base Location CPT fields
	if ( (e.target.id === 'dbem_cp_locations_cpt' || e.target.id === 'dbem_cp_locations_cpts') && !e.target.value.trim() ) {
		if ( e.target.id === 'dbem_cp_locations_cpt' ) {
			const labelSingleLoc = container.querySelector('#dbem_cp_locations_label_single');
			if (labelSingleLoc && labelSingleLoc.value.trim()) {
				autoPopulateSingularCPT(labelSingleLoc.value, e.target);
			}
		} else {
			const labelPluralLoc = container.querySelector('#dbem_cp_locations_label');
			if (labelPluralLoc && labelPluralLoc.value.trim()) {
				autoPopulatePluralCPT(labelPluralLoc.value, e.target);
			}
		}
	}
}, true);

// Use delegated event listener for all inputs
container.addEventListener('input', function(e) {
	// Handle auto-population from archetype labels (only for custom archetypes)
	if (e.target.classList.contains('archetype-label') || e.target.classList.contains('archetype-label-single')) {
		const item = e.target.closest('.archetype-item');
		if (item) {
			const cptInput = item.querySelector('.archetype-cpt');
			const cptsInput = item.querySelector('.archetype-cpts');

			if (e.target.classList.contains('archetype-label-single')) {
				// Singular label populates CPT field
				autoPopulateSingularCPT(e.target.value, cptInput);
			} else if (e.target.classList.contains('archetype-label')) {
				// Plural label populates CPTs field
				autoPopulatePluralCPT(e.target.value, cptsInput);
			}
		}
	}
});

// Prevent invalid characters from being typed in CPT fields
container.addEventListener('keypress', function(e) {
	if (e.target.id === 'em_cp_events_cpt' ||
		e.target.id === 'em_cp_events_cpts' ||
		e.target.classList.contains('archetype-cpt') ||
		e.target.classList.contains('archetype-cpts')) {

		const char = String.fromCharCode(e.which);
		const allowedPattern = /[a-z0-9_-]/;

		// Allow control keys (backspace, delete, etc.)
		if (e.which < 32 || e.ctrlKey || e.metaKey) {
			return;
		}

		// Block characters that don't match pattern or if already at max length
		if (!allowedPattern.test(char) || e.target.value.length >= 20) {
			e.preventDefault();
		}
	}

	// Prevent invalid characters in slug fields while typing
	if (e.target.classList.contains('archetype-slug') || e.target.id === 'dbem_cp_events_slug' || e.target.id === 'dbem_cp_locations_slug') {
		const char = String.fromCharCode(e.which);
		const allowedSlugPattern = /[a-z0-9\/-]/;
		// Allow control keys
		if (e.which < 32 || e.ctrlKey || e.metaKey) {
			return;
		}
		// Convert uppercase to lowercase by blocking and inserting lowercase equivalent is complex in keypress; instead block uppercase and rely on input handler to lowercase existing value
		if (!allowedSlugPattern.test(char.toLowerCase())) {
			e.preventDefault();
		}
	}
});