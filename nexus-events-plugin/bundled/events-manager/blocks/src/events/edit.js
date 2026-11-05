import { __ } from '@wordpress/i18n';
import { useBlockProps, InspectorControls } from '@wordpress/block-editor';
import {
	PanelBody,
	TextControl,
	ToggleControl,
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
			'start date, start time, event name',
			'events-manager'
		),
		value: 'event_start_date,event_start_time,event_name',
	},
	{
		label: __(
			'name, start date, start time',
			'events-manager'
		),
		value: 'event_name,event_start_date,event_start_time',
	},
	{
		label: __( 'name, end date, end time', 'events-manager' ),
		value: 'event_name,event_end_date,event_end_time',
	},
	{
		label: __(
			'end date, end time, event name',
			'events-manager'
		),
		value: 'event_end_date,event_end_time,event_name',
	},
];

const SCOPE_OPTIONS = [
	{ label: __( 'Future', 'events-manager' ), value: 'future' },
	{ label: __( 'Past', 'events-manager' ), value: 'past' },
	{ label: __( 'All', 'events-manager' ), value: 'all' },
	{ label: __( 'Today', 'events-manager' ), value: 'today' },
	{ label: __( 'This week', 'events-manager' ), value: 'this-week' },
	{ label: __( 'This month', 'events-manager' ), value: 'month' },
];

export default function Edit( { attributes, setAttributes } ) {
	const {
		title,
		scope,
		order,
		orderby,
		limit,
		category,
		all_events,
		all_events_text,
		no_events_text,
		format_header,
		format,
		format_footer,
	} = attributes;

	return (
		<>
			<InspectorControls>
				<PanelBody title={ __( 'Events list settings', 'events-manager' ) }>
					<TextControl
						label={ __( 'Title', 'events-manager' ) }
						value={ title }
						onChange={ ( v ) => setAttributes( { title: v } ) }
					/>
					<NumberControl
						label={ __( 'Number of events', 'events-manager' ) }
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
						label={ __( 'Category IDs', 'events-manager' ) }
						help={ __(
							'1,2,3 or 2 (0 = all)',
							'events-manager'
						) }
						value={ category }
						onChange={ ( v ) => setAttributes( { category: v } ) }
					/>
					<ToggleControl
						label={ __(
							'Show "all events" link at bottom',
							'events-manager'
						) }
						checked={ !! all_events }
						onChange={ ( v ) =>
							setAttributes( { all_events: !! v } )
						}
					/>
					{ all_events && (
						<TextControl
							label={ __(
								'"All events" link text',
								'events-manager'
							) }
							value={ all_events_text }
							onChange={ ( v ) =>
								setAttributes( { all_events_text: v } )
							}
						/>
					) }
					<TextControl
						label={ __( 'No events message', 'events-manager' ) }
						value={ no_events_text }
						onChange={ ( v ) =>
							setAttributes( { no_events_text: v } )
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
					block="events-manager/events"
					attributes={ attributes }
				/>
			</div>
		</>
	);
}
