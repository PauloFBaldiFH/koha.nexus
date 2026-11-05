/**
 * em/event-when — tabbed event details canvas block (When + Bookings).
 *
 * Renders the EM "When"/"Recurrences" and "Bookings/Registration" classic-metabox HTML
 * directly in the Gutenberg editor canvas as a tabbed panel, pinned below the title.
 * The classic metaboxes are hidden via CSS (they stay in the DOM so Gutenberg's
 * meta-box-loader POST can still serialize them). Before each save, the validation
 * guard calls syncAllCanvasToMetabox() to mirror canvas-block inputs into the hidden
 * metaboxes. After each save, window.emReloadWhenBlock() re-fetches the server HTML
 * so nonces and record IDs stay fresh — the same URL that reloadEMMetaBoxes() uses.
 *
 * The block keeps its historical name (em/event-when) for backwards compatibility with
 * posts saved since 7.3.4 that already contain the serialized block comment.
 */
import { registerBlockType } from '@wordpress/blocks';
import { useEffect, useRef } from '@wordpress/element';
import metadata from './block.json';

const BLOCK_CLASS = 'em-event-when-block';

// Module-level so the active tab survives loadContent() rebuilds (post-save refresh).
let activeTab = 'when';

// Minimal escaper for values interpolated into markup strings. Tab ids/labels come
// from the server-side registry, but we escape defensively all the same.
function esc( s ) {
	return String( s == null ? '' : s )
		.replace( /&/g, '&amp;' )
		.replace( /</g, '&lt;' )
		.replace( />/g, '&gt;' )
		.replace( /"/g, '&quot;' );
}

// Scoped styles injected with the block HTML so they travel into the editor-canvas
// iframe document without needing a separate editorStyle asset in the build.
const TAB_CSS = `
.${ BLOCK_CLASS } {
	max-width: 920px;
	margin: 16px auto;
	padding: 20px 24px;
	border: 1px solid #e0e0e0;
	border-radius: 8px;
	background: #fff;
	box-sizing: border-box;
}
.${ BLOCK_CLASS } .em-canvas-tabs {
	display: flex;
	gap: 4px;
	margin: 0 0 16px;
	border-bottom: 1px solid #ddd;
}
.${ BLOCK_CLASS } .em-canvas-tab {
	appearance: none;
	background: none;
	border: none;
	border-bottom: 3px solid transparent;
	cursor: pointer;
	font-size: 14px;
	font-weight: 500;
	padding: 8px 14px;
	margin-bottom: -1px;
	color: inherit;
	opacity: 0.7;
}
.${ BLOCK_CLASS } .em-canvas-tab:hover {
	opacity: 1;
}
.${ BLOCK_CLASS } .em-canvas-tab.is-active {
	border-bottom-color: var( --wp-admin-theme-color, #3858e9 );
	font-weight: 600;
	opacity: 1;
}
.${ BLOCK_CLASS } .em-canvas-tab-panel[hidden] {
	display: none;
}
`;

function setActiveTab( container, tab ) {
	const panels = container.querySelectorAll( '.em-canvas-tab-panel' );
	const buttons = container.querySelectorAll( '.em-canvas-tab' );
	// Fall back to the first available panel if the requested tab isn't rendered
	// (e.g. bookings disabled on this site, or tab removed by a reload).
	if ( ! container.querySelector( `.em-canvas-tab-panel[data-em-tab="${ tab }"]` ) ) {
		tab = panels[ 0 ]?.getAttribute( 'data-em-tab' ) || 'when';
	}
	activeTab = tab;
	panels.forEach( ( p ) => {
		p.hidden = p.getAttribute( 'data-em-tab' ) !== tab;
	} );
	buttons.forEach( ( b ) => {
		b.classList.toggle( 'is-active', b.getAttribute( 'data-em-tab-target' ) === tab );
	} );
}

function EventWhenEdit() {
	const containerRef = useRef( null );

	function loadContent() {
		const container = containerRef.current;
		if ( ! container ) return;

		// Canvas layout only. In the tabs/metaboxes layouts the real metaboxes are
		// presented in the parent document, so this block — which may still be
		// serialized into older posts' content — renders nothing.
		if ( ( window.EM_EDITOR_TABS?.layout || 'canvas' ) !== 'canvas' ) {
			container.innerHTML = '';
			container.style.display = 'none';
			return;
		}

		const url = window._wpMetaBoxUrl;
		if ( ! url ) return;

		fetch( url, { credentials: 'same-origin' } )
			.then( ( r ) => r.text() )
			.then( ( html ) => {
				const doc = new DOMParser().parseFromString( html, 'text/html' );

				// Build the canvas tabs from the registry (window.EM_EDITOR_TABS): only tabs/boxes
				// with canvas_support render in the iframe; the rest (e.g. Where, whose map needs
				// the parent document) stay as normal metaboxes. Keep only metaboxes whose HTML is
				// present in the fetched document (a box can be absent when its feature is off).
				const canvasTabs = ( window.EM_EDITOR_TABS?.tabs || [] )
					.filter( ( t ) => t.canvas_support )
					.map( ( t ) => ( {
						id: t.id,
						label: t.label,
						boxes: ( t.metaboxes || [] )
							.filter( ( mb ) => mb.canvas_support )
							.map( ( mb ) => ( {
								id: mb.id,
								className: ( mb.class || '' ).trim(),
								inside: doc.getElementById( mb.id )?.querySelector( '.inside' ),
							} ) )
							.filter( ( mb ) => mb.inside ),
					} ) )
					.filter( ( t ) => t.boxes.length );

				if ( typeof window.em_unsetup_ui_elements === 'function' ) {
					try { window.em_unsetup_ui_elements( container ); } catch ( _ ) {}
				}

				container.innerHTML = '';
				container.insertAdjacentHTML( 'beforeend', `<style>${ TAB_CSS }</style>` );

				// Tab bar only when there is more than one tab to show.
				if ( canvasTabs.length > 1 ) {
					const tabsHtml = canvasTabs.map( ( t ) =>
						'<button type="button" class="em-canvas-tab" role="tab" data-em-tab-target="' + esc( t.id ) + '">' + esc( t.label ) + '</button>'
					).join( '' );
					container.insertAdjacentHTML( 'beforeend', '<div class="em-canvas-tabs" role="tablist">' + tabsHtml + '</div>' );
				}

				// Each metabox keeps a data-em-metabox wrapper so the validation guard can
				// route synced fields back to the right hidden metabox; its registry class
				// (e.g. the Recurrences box's visibility hooks) rides along on that wrapper.
				const panels = canvasTabs.map( ( t, idx ) => {
					const boxesHtml = t.boxes.map( ( box ) => {
						const clsAttr = box.className ? ' class="' + esc( box.className ) + '"' : '';
						return '<div' + clsAttr + ' data-em-metabox="' + esc( box.id ) + '">' + box.inside.innerHTML + '</div>';
					} ).join( '' );
					return '<div class="em-canvas-tab-panel" data-em-tab="' + esc( t.id ) + '"' + ( idx > 0 ? ' hidden' : '' ) + '>' + boxesHtml + '</div>';
				} ).join( '' );

				// Mount the panels inside the same ancestors EM's admin CSS/JS expect: a
				// .wp-admin / .wp-core-ui scope (so the .wp-admin form rules, WP core's
				// admin form/button styles, and the :has() booking toggle all apply) and a
				// <form> (so form.em-is-recurring and closest('form') resolve). The block
				// root already carries .em for the event-editor stylesheet.
				container.insertAdjacentHTML( 'beforeend',
					'<div class="wp-admin wp-core-ui em-event-editor">' +
						'<form class="em-canvas-form" novalidate>' + panels + '</form>' +
					'</div>'
				);

				// A stray submit (Enter in a text field) must never navigate the iframe.
				container.querySelector( 'form.em-canvas-form' )?.addEventListener( 'submit', ( e ) => e.preventDefault() );

				// Wire tab switching before widget setup so a failed setup doesn't
				// leave the tabs dead.
				container.querySelectorAll( '.em-canvas-tab' ).forEach( ( btn ) => {
					btn.addEventListener( 'click', () => {
						setActiveTab( container, btn.getAttribute( 'data-em-tab-target' ) );
					} );
				} );
				setActiveTab( container, activeTab );

				// Run EM's setup in the container's OWN window. In the Gutenberg canvas
				// that window is the iframe's, where EM's runtime (jQuery, flatpickr,
				// timepicker, em_setup_*) is also loaded — so widgets bind to the iframe
				// document and behave natively (e.g. the datepicker closes on outside
				// click). Falls back to the parent window if the iframe copy is absent.
				const emWin = container.ownerDocument.defaultView || window;
				const inIframe = ( window.EM_EDITOR_TABS?.layout || 'canvas' ) === 'canvas' && emWin !== window;
				const emSetup = ( inIframe && typeof emWin.em_setup_ui_elements === 'function' )
					? emWin.em_setup_ui_elements
					: window.em_setup_ui_elements;
				if ( typeof emSetup === 'function' ) {
					try { emSetup( container ); } catch ( _ ) {}
				}

				// In iframe-native mode, wire the recurrence + ticket editors in the iframe.
				// EM's own lazy-loader (em_setup_scripts) loads event-editor.js into the
				// iframe — keyed on the .em-event-editor wrapper — and fires
				// em_event_editor_ready on the iframe's document when it loads. It dedups by
				// script id, so it can't double-load (the SyntaxError we'd otherwise hit).
				// On a re-mount the script is already present, so we fire ready ourselves for
				// the freshly-injected content.
				if ( inIframe ) {
					if ( typeof emWin.emRecurrenceFormRoot === 'function' ) {
						try { emWin.document.dispatchEvent( new emWin.CustomEvent( 'em_event_editor_ready' ) ); } catch ( _ ) {}
					} else if ( typeof emWin.em_setup_scripts === 'function' ) {
						try { emWin.em_setup_scripts( container ); } catch ( _ ) {}
					}
				}

				// Initialise any location maps in the freshly-injected content. The map JS
				// (em_maps_*) lives in events-manager.js (loaded in the iframe) but only
				// auto-scans on initial load / search events — never on our async injection —
				// so kick it for this container. First use loads the Google API + scans the
				// whole iframe document; afterwards we re-init each map node directly.
				const mapWin = inIframe ? emWin : window;
				if ( container.querySelector( '.em-location-map, .em-locations-map' ) ) {
					try {
						if ( mapWin.em_maps_loaded && typeof mapWin.em_maps_load_location === 'function' ) {
							container.querySelectorAll( '.em-location-map' ).forEach( ( el ) => mapWin.em_maps_load_location( el ) );
							container.querySelectorAll( '.em-locations-map' ).forEach( ( el ) => mapWin.em_maps_load_locations && mapWin.em_maps_load_locations( el ) );
						} else if ( typeof mapWin.em_maps_load === 'function' ) {
							mapWin.em_maps_load();
						}
					} catch ( _ ) {}
				}
			} )
			.catch( ( e ) => {
				// eslint-disable-next-line no-console
				console.error( '[EM] event-when block: fetch failed', e );
			} );
	}

	useEffect( () => {
		loadContent();

		// Expose refresh hook — called by reloadEMMetaBoxes() in the validation
		// guard after each save so nonces and record IDs stay current.
		window.emReloadWhenBlock = loadContent;

		return () => {
			window.emReloadWhenBlock = null;
			const container = containerRef.current;
			if ( container && typeof window.em_unsetup_ui_elements === 'function' ) {
				try { window.em_unsetup_ui_elements( container ); } catch ( _ ) {}
			}
		};
	}, [] );

	return (
		<div className={ `${ BLOCK_CLASS } em` } ref={ containerRef } />
	);
}

registerBlockType( metadata.name, {
	edit: EventWhenEdit,
	save: () => null,
} );
