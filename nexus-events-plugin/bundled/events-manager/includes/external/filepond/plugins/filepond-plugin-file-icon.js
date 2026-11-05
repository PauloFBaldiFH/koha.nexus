/*!
 * FilePondPluginFileIcon 1.0.0
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
		global.FilePondPluginFileIcon = factory();
	}
})(this, function() {
	'use strict';

	const getFileExtension = (filename) => {
		return filename.split('.').pop().toLowerCase();
	};

	const isImage = (fileType) => /^image/.test(fileType);

	const createFileIcon = (root, el, file, item) => {
		const extension = getFileExtension(file.name);
		const fileIcon = document.createElement('span');
		fileIcon.classList.add('filepond--file-icon', `file-icon-type-${extension}`);

		const iconSize = root.query('GET_FILE_ICON_SIZE') || 40;
		fileIcon.style.width = `${iconSize}px`;
		fileIcon.style.height = `${iconSize}px`;

		el.prepend(fileIcon);
		el.classList.add('has-icon');

		// move filesize into admin container for a good look
		let filesize = el.querySelector('.filepond--file-info-sub');
		if ( filesize ) {
			el.querySelector('.filepond--file-info-main-container').appendChild( filesize );
		}

		const previewHeight = iconSize + 20;
		root.dispatch('DID_UPDATE_PANEL_HEIGHT', {
			id: item.id,
			height: previewHeight
		});
		// allow others to hook into this
		root.dispatch('DID_FILE_ICON_RENDERED', {
			id: item.id,
			file,
			iconElement: fileIcon,
		});
	};

	return function({ addFilter, utils }) {
		addFilter('CREATE_VIEW', (viewAPI) => {
			const { is, view, query } = viewAPI;

			if (!is('file')) return;

			const didLoadItem = ({ root, props }) => {
				const item = query('GET_ITEM', props.id);
				if (!item) return;

				const file = item.file;
				const isImageFile = isImage(file.type);

				// Safely retrieve options (fallback to defaults if not ready)
				const allowFileIcon = root.query('GET_ALLOW_FILE_ICON') ?? true;
				const fileIconIncludeImages = root.query('GET_FILE_ICON_INCLUDE_IMAGES') ?? false;

				if (!allowFileIcon) return;

				// Skip images if option is disabled for images
				if (!fileIconIncludeImages && isImageFile) return;

				createFileIcon(root, root.element.querySelector('.filepond--file-info'), file, item);
			};

			const rescaleItem = (root, props) => {
				if (!root.ref.fileIcon) return;

				const item = root.query('GET_ITEM', { id: props.id });
				if (!item) return;

				const panelAspectRatio = root.query('GET_PANEL_ASPECT_RATIO');
				const itemPanelAspectRatio = root.query('GET_ITEM_PANEL_ASPECT_RATIO');
				const fixedHeight = root.query('GET_IMAGE_PREVIEW_HEIGHT');
				if (panelAspectRatio || itemPanelAspectRatio || fixedHeight) return;

				const iconSize = root.query('GET_FILE_ICON_SIZE') || 40;
				const itemWidth = root.rect.element.width;
				const previewHeight = Math.max(iconSize + 20, itemWidth * (3 / 4));

				root.dispatch('DID_UPDATE_PANEL_HEIGHT', {
					id: item.id,
					height: previewHeight
				});
			};

			view.registerWriter(utils.createRoute({
				DID_LOAD_ITEM: didLoadItem,
				DID_FINISH_CALCULATE_PREVIEWSIZE: ({ root, props }) => {
					if (root.ref.fileIcon) {
						rescaleItem(root, props);
					}
				}
			}));
		});

		return {
			options: {
				allowFileIcon: [true, utils.Type.BOOLEAN],
				fileIconIncludeImages: [false, utils.Type.BOOLEAN],
				fileIconSize: [40, utils.Type.INT],
			},
		};
	};
});