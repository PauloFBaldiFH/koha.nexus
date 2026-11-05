import { __ } from '@wordpress/i18n';
import { useBlockProps, InspectorControls } from '@wordpress/block-editor';
import {
	PanelBody,
	TextControl,
	ToggleControl,
	SelectControl,
} from '@wordpress/components';
import ServerSideRender from '@wordpress/server-side-render';

const SIZE_OPTIONS = [
	{ label: __( 'Responsive', 'events-manager' ), value: 'auto' },
	{ label: __( 'Large', 'events-manager' ), value: 'large' },
	{ label: __( 'Medium', 'events-manager' ), value: 'medium' },
	{ label: __( 'Small', 'events-manager' ), value: 'small' },
];

const STYLE_OPTIONS = [
	{ label: __( 'Default (site setting)', 'events-manager' ), value: '' },
	{ label: __( 'Pills', 'events-manager' ), value: 'pill' },
	{ label: __( 'Single dot', 'events-manager' ), value: 'dot' },
	{ label: __( 'Multiple dots', 'events-manager' ), value: 'dots' },
	{ label: __( 'Rings', 'events-manager' ), value: 'ring' },
];

// Archetypes are localised by blocks/_bootstrap.php (window.EMBlocks) so the
// block inspector can offer the same archetype choice the widget does. Empty
// on sites without custom archetypes — in which case we hide the control,
// mirroring the widget's `if ( Archetypes::$types )` guard.
const ARCHETYPES =
	( typeof window !== 'undefined' &&
		window.EMBlocks &&
		window.EMBlocks.archetypes ) ||
	[];

export default function Edit( { attributes, setAttributes } ) {
	const {
		title,
		long_events,
		category,
		scope,
		calendar_size,
		calendar_event_style,
		limit,
		event_archetype,
	} = attributes;

	return (
		<>
			<InspectorControls>
				<PanelBody title={ __( 'Calendar settings', 'events-manager' ) }>
					<TextControl
						label={ __( 'Title', 'events-manager' ) }
						value={ title }
						onChange={ ( v ) => setAttributes( { title: v } ) }
					/>
					<ToggleControl
						label={ __( 'Show long events', 'events-manager' ) }
						checked={ !! long_events }
						onChange={ ( v ) =>
							setAttributes( { long_events: !! v } )
						}
					/>
					<ToggleControl
						label={ __( 'Future events only', 'events-manager' ) }
						checked={ scope === 'future' }
						onChange={ ( v ) =>
							setAttributes( { scope: v ? 'future' : 'all' } )
						}
					/>
					<TextControl
						label={ __( 'Category IDs', 'events-manager' ) }
						help={ __( '1,2,3 or 2 (0 = all)', 'events-manager' ) }
						value={ category }
						onChange={ ( v ) => setAttributes( { category: v } ) }
					/>
					{ ARCHETYPES.length > 0 && (
						<SelectControl
							label={ __( 'Archetype', 'events-manager' ) }
							value={ event_archetype }
							options={ [
								{
									label: __( 'Default', 'events-manager' ),
									value: '',
								},
								...ARCHETYPES,
							] }
							onChange={ ( v ) =>
								setAttributes( { event_archetype: v } )
							}
						/>
					) }
					<SelectControl
						label={ __( 'Calendar size', 'events-manager' ) }
						value={ calendar_size }
						options={ SIZE_OPTIONS }
						onChange={ ( v ) =>
							setAttributes( { calendar_size: v } )
						}
					/>
					<SelectControl
						label={ __( 'Event style', 'events-manager' ) }
						value={ calendar_event_style }
						options={ STYLE_OPTIONS }
						onChange={ ( v ) =>
							setAttributes( { calendar_event_style: v } )
						}
					/>
					<TextControl
						type="number"
						min="0"
						label={ __( 'Events per day', 'events-manager' ) }
						help={ __(
							'Max events shown per calendar day (0 = no limit; blank = site default).',
							'events-manager'
						) }
						value={ limit }
						onChange={ ( v ) => setAttributes( { limit: v } ) }
					/>
				</PanelBody>
			</InspectorControls>
			<div { ...useBlockProps() }>
				<ServerSideRender
					block="events-manager/calendar"
					attributes={ attributes }
				/>
			</div>
		</>
	);
}
