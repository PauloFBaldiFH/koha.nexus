import { __ } from '@wordpress/i18n';
import { useBlockProps, InspectorControls } from '@wordpress/block-editor';
import {
	PanelBody,
	TextControl,
	SelectControl,
	TextareaControl,
	__experimentalNumberControl as NumberControl,
} from '@wordpress/components';
import ServerSideRender from '@wordpress/server-side-render';

const ORDER_OPTIONS = [
	{ label: __( 'Ascending', 'events-manager' ), value: 'ASC' },
	{ label: __( 'Descending', 'events-manager' ), value: 'DESC' },
];

const ORDERBY_OPTIONS = [
	{
		label: __(
			'Event start date/time, location name',
			'events-manager'
		),
		value: 'event_start_date,event_start_time,location_name',
	},
	{
		label: __( 'Location name', 'events-manager' ),
		value: 'location_name',
	},
];

const SCOPE_OPTIONS = [
	{ label: __( 'Future', 'events-manager' ), value: 'future' },
	{ label: __( 'Past', 'events-manager' ), value: 'past' },
	{ label: __( 'All', 'events-manager' ), value: 'all' },
];

export default function Edit( { attributes, setAttributes } ) {
	const {
		title,
		scope,
		order,
		orderby,
		limit,
		no_locations_text,
		format_header,
		format,
		format_footer,
	} = attributes;

	return (
		<>
			<InspectorControls>
				<PanelBody
					title={ __( 'Locations list settings', 'events-manager' ) }
				>
					<TextControl
						label={ __( 'Title', 'events-manager' ) }
						value={ title }
						onChange={ ( v ) => setAttributes( { title: v } ) }
					/>
					<NumberControl
						label={ __( 'Number of locations', 'events-manager' ) }
						min={ 1 }
						value={ limit }
						onChange={ ( v ) =>
							setAttributes( { limit: parseInt( v, 10 ) || 5 } )
						}
					/>
					<SelectControl
						label={ __( 'Scope', 'events-manager' ) }
						value={ scope }
						options={ SCOPE_OPTIONS }
						onChange={ ( v ) => setAttributes( { scope: v } ) }
					/>
					<SelectControl
						label={ __( 'Order by', 'events-manager' ) }
						value={ orderby }
						options={ ORDERBY_OPTIONS }
						onChange={ ( v ) => setAttributes( { orderby: v } ) }
					/>
					<SelectControl
						label={ __( 'Order', 'events-manager' ) }
						value={ order }
						options={ ORDER_OPTIONS }
						onChange={ ( v ) => setAttributes( { order: v } ) }
					/>
					<TextControl
						label={ __( 'No locations message', 'events-manager' ) }
						value={ no_locations_text }
						onChange={ ( v ) =>
							setAttributes( { no_locations_text: v } )
						}
					/>
				</PanelBody>
				<PanelBody
					title={ __( 'Output format (advanced)', 'events-manager' ) }
					initialOpen={ false }
				>
					<TextareaControl
						label={ __( 'List header format', 'events-manager' ) }
						value={ format_header }
						onChange={ ( v ) =>
							setAttributes( { format_header: v } )
						}
					/>
					<TextareaControl
						label={ __( 'List item format', 'events-manager' ) }
						help={ __(
							'Leave blank to use the default format from Settings.',
							'events-manager'
						) }
						value={ format }
						onChange={ ( v ) => setAttributes( { format: v } ) }
					/>
					<TextareaControl
						label={ __( 'List footer format', 'events-manager' ) }
						value={ format_footer }
						onChange={ ( v ) =>
							setAttributes( { format_footer: v } )
						}
					/>
				</PanelBody>
			</InspectorControls>
			<div { ...useBlockProps() }>
				<ServerSideRender
					block="events-manager/locations"
					attributes={ attributes }
				/>
			</div>
		</>
	);
}
