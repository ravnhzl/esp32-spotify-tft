# ESP32 Spotify TFT Display

A DIY Spotify Now Playing display built using an ESP32 DevKit and a 2.8 inch ILI9341 SPI TFT display.

## Overview

This project connects Spotify on a PC or any devices to an ESP32 over USB serial. The ESP32 receives playback information and renders a custom Spotify interface on the ILI9341 TFT.

```text
Spotify
   ↓
Spotify Web API
   ↓
Python
   ↓
USB Serial
   ↓
ESP32
   ↓
ILI9341 SPI TFT
```

## Pictures

<p align="center">
  <img src="images/ESP Showcase (2).jpg" width="300">
  <img src="images/ESP32 Devkit V1.jpg" width="300">
</p>

## Features

- Song title, artist, and album
- Album artwork
- Synchronized lyrics
- Playback progress
- ~~Real-Time volume display~~ does not work right now, I'll probably add it soon
- Play / pause control
- Previous track
- Next track
- Scrolling long song titles
- USB serial communication
- Custom TFT interface

## Hardware

* ESP32 DevKit V1
* 2.8 inch ILI9341 SPI TFT
* 3 tactile buttons
* Breadboard and some jumper wires

## TFT Wiring

| ILI9341    |   ESP32 |
| ---------- | ------: |
| VCC        |    3.3V |
| GND        |     GND |
| CS         |  GPIO 5 |
| RESET      |  GPIO 4 |
| DC         |  GPIO 2 |
| MOSI / SDI | GPIO 23 |
| SCK        | GPIO 18 |
| MISO / SDO | GPIO 19 |
| LED / BL   |    3.3V |

## Buttons

| Function     | GPIO |
| ------------ | ---: |
| Previous     |   25 |
| Play / Pause |   26 |
| Next         |   27 |

The buttons use the ESP32's internal pull up resistors and connect to GND when pressed.

## Software

### ESP32

- Arduino IDE
- Adafruit GFX Library
- Adafruit ILI9341 Library

### Python

- Python 3
- Requests
- PySerial
- Pillow

The Python program communicates with Spotify and sends playback information and album artwork to the ESP32 through USB serial.

## Lyrics

Synchronized lyrics are retrieved from LRCLIB and converted into the current lyric line based on the Spotify playback position.

## Personalization

Want to put your own Instagram username on the display?

Open the Arduino `.ino` file and look for:

```cpp
const char* INSTAGRAM_USERNAME = "@YOURUSERNAME";
```

Replace `@YOURUSERNAME` with your own Instagram username:

Upload the code to your ESP32 and your username will appear next to the Instagram icon on the TFT.

## Project Status

Right now it's only a working prototype.

The display supports Spotify playback information, album artwork, synchronized lyrics, playback controls, and progress tracking.

## Future Improvements

- Unicode font support for Chinese, Korean, Japanese, and Cyrillic lyrics
- Improved button responsiveness during artwork updates
- More polished UI animations
- Standalone Wi-Fi version without requiring a PC
