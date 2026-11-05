/*!
 * FilePondPluginImageThumbnail 1.0.0
 * Author: Pixelite SL
 * Licensed under MIT, https://opensource.org/licenses/MIT/
 * Please visit https://pqina.nl/filepond/ for details.
 */
(function(global, factory) {
	if (typeof exports === 'object' && typeof module !== 'undefined') {
		module.exports = factory();
	} else if (typeof define === 'function' && define.amd) {
		define(factory);
	} else {
		global.FilePondPluginImageThumbnail = factory();
	}
})(this, function() {
	'use strict';

	const isImage = (item) => item.fileType && /^image/.test(item.fileType);

	const createThumbnail = (root, el, file, item ) => {
		const thumbnail = document.createElement('img');
		thumbnail.classList.add('filepond--image-thumbnail', 'filepond--image-preview'); // critical to trigger preview overlay, we don't expect ppl to use this and the preview plugin
		thumbnail.src = URL.createObjectURL(file);
		let imageThumbnailHeight = root.query('GET_IMAGE_THUMBNAIL_HEIGHT');
		thumbnail.style.width = root.query('GET_IMAGE_THUMBNAIL_WIDTH') + "px";
		thumbnail.style.height = imageThumbnailHeight + "px";
		thumbnail.style.objectFit = 'cover';
		thumbnail.style.marginLeft = '10px';
		// add thumbnail and class
		el.prepend(thumbnail);
		el.classList.add('has-thumbnail');
		// move filesize into admin container for a good look
		let filesize = el.querySelector('.filepond--file-info-sub');
		if ( filesize ) {
			el.querySelector('.filepond--file-info-main-container').appendChild( filesize );
		}
		// Request update to panel height with added margin
		const previewHeight = imageThumbnailHeight + 20; // 20px extra margin
		root.dispatch('DID_UPDATE_PANEL_HEIGHT', {
			id: item.id,
			height: previewHeight
		});
		// Dispatch a custom event to simulate image preview container creation
		root.dispatch('DID_IMAGE_PREVIEW_CONTAINER_CREATE', {
			id: item.id
		});
	};

	return function({ addFilter, utils }) {
		addFilter('CREATE_VIEW', (viewAPI) => {
			const { is, view, query } = viewAPI;

			if (!is('file')) return;

			const didLoadItem = ({ root, props }) => {
				const item = query('GET_ITEM', props.id);
				if (!item || !isImage(item)) return;
				createThumbnail(root, root.element.querySelector('.filepond--file-info'), item.file, item);
			};

			const rescaleItem = (root, props) => {
				if (!root.ref.imageThumbnail) return;
				const item = root.query('GET_ITEM', { id: props.id });
				if (!item) return;

				const panelAspectRatio = root.query('GET_PANEL_ASPECT_RATIO');
				const itemPanelAspectRatio = root.query('GET_ITEM_PANEL_ASPECT_RATIO');
				const fixedHeight = root.query('GET_IMAGE_PREVIEW_HEIGHT');
				if (panelAspectRatio || itemPanelAspectRatio || fixedHeight) return;

				const imageThumbnailHeight = root.query('GET_IMAGE_THUMBNAIL_HEIGHT');
				const itemWidth = root.rect.element.width;
				const previewHeight = Math.max(imageThumbnailHeight + 20, itemWidth * (3 / 4));

				root.dispatch('DID_UPDATE_PANEL_HEIGHT', {
					id: item.id,
					height: previewHeight
				});
			};

			view.registerWriter(utils.createRoute({
				DID_LOAD_ITEM: didLoadItem,
				DID_FINISH_CALCULATE_PREVIEWSIZE: ({ root, props }) => {
					if (root.ref.imageThumbnail) {
						rescaleItem(root, props);
					}
				}
			}));
		});

		return {
			options: {
				allowImageThumbnail: [true, utils.Type.BOOLEAN],
				imageThumbnailWidth: [50, utils.Type.INT],
				imageThumbnailHeight: [50, utils.Type.INT]
			},
		};
	};
});