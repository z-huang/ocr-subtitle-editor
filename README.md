# OCR Subtitle Editor

An efficient GUI tool for extracting subtitles from videos using OCR and editing subtitles with keyboard shortcuts.

This tool, combined with our post-processing pipeline, has been used to build a comprehensive dataset for Taiwanese kua-á-hì.

![Screenshot](https://github.com/z-huang/ocr-subtitle-editor/blob/main/screenshot.png)

## Getting Started

- Python 3.11
- `pip install -r requirements.txt`

## Features

- Extract subtitles from video frames using EasyOCR
- Efficient subtitle editor tool to manually correct the subtitles

## Keyboard Shortcuts

- Arrow Up/Down: Move selection up or down the list
- Shift + Arrow Up/Down: select multiple subtitle lines
- `n`: Move selection up
- `N`: Move selection down
- `e`: Edit selected subtitle
- `Esc`: Exit edit mode
- `m`: Merge selected subtitle lines
- `d`: Delete selected subtitle lines
- `,`: Replace subtitle spacing with Chinese comma (，)
- `h`: Reorder subtitle segments separated by spaces
- `r`: Reload subtitle file
