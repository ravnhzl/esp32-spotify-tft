#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>

// TFT
#define TFT_CS   5
#define TFT_RST  4
#define TFT_DC   2
#define TFT_MOSI 23
#define TFT_SCLK 18
#define TFT_MISO 19

// Buttons
#define BTN_PREV 25
#define BTN_PLAY 26
#define BTN_NEXT 27

Adafruit_ILI9341 tft(TFT_CS, TFT_DC, TFT_RST);

// Personalization
const char* INSTAGRAM_USERNAME = "@YOURUSERNAME";

// Song title area
#define TITLE_X 125
#define TITLE_Y 35
#define TITLE_W 180
#define TITLE_H 25

GFXcanvas16 titleCanvas(TITLE_W, TITLE_H);

// Lyrics area
#define LYRIC_X 125
#define LYRIC_Y 105
#define LYRIC_W 180
#define LYRIC_H 45

GFXcanvas16 lyricCanvas(LYRIC_W, LYRIC_H);

// Spotify data
String song = "";
String artist = "";
String album = "";
String lyric = "";

long progressMs = 0;
long durationMs = 0;
int volumePercent = 0;
bool playing = false;

// Artwork
bool receivingArtwork = false;
size_t artworkBytes = 0;

// Title scrolling
bool titleNeedsScroll = false;
int titleScrollX = 0;
int titleMaxScroll = 0;
int scrollDirection = -1;

unsigned long titleStart = 0;
unsigned long lastScroll = 0;

const unsigned long TITLE_PAUSE = 2000;
const int TITLE_SPEED = 1;

// Button states
bool prevLast = HIGH;
bool playLast = HIGH;
bool nextLast = HIGH;

// Progress
unsigned long lastProgress = 0;


void setup() {
  Serial.begin(115200);

  pinMode(BTN_PREV, INPUT_PULLUP);
  pinMode(BTN_PLAY, INPUT_PULLUP);
  pinMode(BTN_NEXT, INPUT_PULLUP);

  SPI.begin(TFT_SCLK, TFT_MISO, TFT_MOSI, TFT_CS);

  tft.begin();
  tft.setRotation(1);
  tft.setTextWrap(false);
  tft.fillScreen(ILI9341_BLACK);

  titleCanvas.setTextWrap(false);
  lyricCanvas.setTextWrap(false);

  drawUI();
}


void loop() {
  handleButtons();
  handleSerial();
  updateTitle();
  updateProgress();
}


void drawUI() {
  tft.fillScreen(ILI9341_BLACK);

  // Header
  tft.setTextColor(ILI9341_WHITE);
  tft.setTextSize(2);
  tft.setCursor(12, 10);
  tft.print("SPOTIFY");

  drawInstagram();

  tft.setTextColor(ILI9341_DARKGREY);
  tft.setTextSize(1);
  tft.setCursor(250, 14);
  tft.print("USB");

  // Artwork placeholder
  tft.fillRect(12, 35, 100, 100, 0x4208);

  drawTitle();
  drawArtist();
  drawAlbum();
  drawLyric();
  drawPlay();
  drawProgress();
  drawVolume();
  drawControls();
}


void drawInstagram() {
  int x = 105;
  int y = 10;
  int size = 14;

  tft.drawRoundRect(x, y, size, size, 4, ILI9341_WHITE);
  tft.drawCircle(x + 7, y + 7, 3, ILI9341_WHITE);
  tft.fillCircle(x + 11, y + 3, 1, ILI9341_WHITE);

  tft.setTextColor(ILI9341_LIGHTGREY);
  tft.setTextSize(1);
  tft.setCursor(123, 13);
  tft.print(INSTAGRAM_USERNAME);
}


void handleSerial() {
  // Artwork is sent as raw RGB565 data
  if (receivingArtwork) {
    while (Serial.available() && artworkBytes < 20000) {
      uint8_t hi = Serial.read();

      while (!Serial.available())
        delayMicroseconds(50);

      uint8_t lo = Serial.read();

      uint16_t color = ((uint16_t)hi << 8) | lo;

      size_t pixel = artworkBytes / 2;
      int x = pixel % 100;
      int y = pixel / 100;

      tft.drawPixel(12 + x, 35 + y, color);
      artworkBytes += 2;
    }

    if (artworkBytes >= 20000)
      receivingArtwork = false;

    return;
  }

  if (!Serial.available())
    return;

  String msg = Serial.readStringUntil('\n');
  msg.trim();

  if (msg == "ARTSTART") {
    receivingArtwork = true;
    artworkBytes = 0;
    return;
  }

  if (msg == "ARTEND") {
    receivingArtwork = false;
    return;
  }

  if (msg.startsWith("SONG|")) {
    parseSong(msg);
    return;
  }

  if (msg.startsWith("LYRIC|")) {
    parseLyric(msg);
    return;
  }
}


void parseSong(String msg) {
  String p[8];
  int part = 0;
  int start = 0;

  for (int i = 0; i < msg.length() && part < 7; i++) {
    if (msg[i] == '|') {
      p[part++] = msg.substring(start, i);
      start = i + 1;
    }
  }

  p[part] = msg.substring(start);

  String newSong = p[1];

  artist = p[2];
  album = p[3];

  progressMs = p[4].toInt();
  durationMs = p[5].toInt();
  playing = p[6].toInt();

  volumePercent = constrain(p[7].toInt(), 0, 100);

  // Reset scrolling when a new song starts
  if (newSong != song) {
    song = newSong;

    int textWidth = song.length() * 12;

    titleNeedsScroll = textWidth > TITLE_W;
    titleMaxScroll = max(0, textWidth - TITLE_W);

    titleScrollX = 0;
    scrollDirection = -1;

    titleStart = millis();
    lastScroll = millis();
  } else {
    song = newSong;
  }

  lastProgress = millis();

  drawTitle();
  drawArtist();
  drawAlbum();
  drawPlay();
  drawProgress();
  drawVolume();
  drawControls();
}


void parseLyric(String msg) {
  lyric = msg.substring(6);
  lyric.trim();

  drawLyric();
}


void drawLyric() {
  lyricCanvas.fillScreen(ILI9341_BLACK);

  if (lyric.length() == 0) {
    tft.drawRGBBitmap(
      LYRIC_X,
      LYRIC_Y,
      lyricCanvas.getBuffer(),
      LYRIC_W,
      LYRIC_H
    );
    return;
  }

  lyricCanvas.setTextColor(ILI9341_WHITE);
  lyricCanvas.setTextSize(1);
  lyricCanvas.setTextWrap(false);

  const int MAX_CHARS = 29;

  String line1 = "";
  String line2 = "";
  String line3 = "";

  int lineNumber = 0;
  int start = 0;

  while (start < lyric.length()) {
    int space = lyric.indexOf(' ', start);
    String word;

    if (space == -1) {
      word = lyric.substring(start);
      start = lyric.length();
    } else {
      word = lyric.substring(start, space);
      start = space + 1;
    }

    String testLine;

    if (lineNumber == 0) {
      testLine = line1.length() == 0 ? word : line1 + " " + word;

      if (testLine.length() <= MAX_CHARS) {
        line1 = testLine;
      } else {
        lineNumber = 1;
        line2 = word;
      }
    }
    else if (lineNumber == 1) {
      testLine = line2.length() == 0 ? word : line2 + " " + word;

      if (testLine.length() <= MAX_CHARS) {
        line2 = testLine;
      } else {
        lineNumber = 2;
        line3 = word;
      }
    }
    else {
      testLine = line3.length() == 0 ? word : line3 + " " + word;

      if (testLine.length() <= MAX_CHARS)
        line3 = testLine;
    }
  }

  lyricCanvas.setCursor(0, 1);
  lyricCanvas.print(line1);

  if (line2.length() > 0) {
    lyricCanvas.setCursor(0, 13);
    lyricCanvas.print(line2);
  }

  if (line3.length() > 0) {
    lyricCanvas.setCursor(0, 25);
    lyricCanvas.print(line3);
  }

  tft.drawRGBBitmap(
    LYRIC_X,
    LYRIC_Y,
    lyricCanvas.getBuffer(),
    LYRIC_W,
    LYRIC_H
  );
}


void drawTitle() {
  titleCanvas.fillScreen(ILI9341_BLACK);

  titleCanvas.setTextColor(ILI9341_WHITE);
  titleCanvas.setTextSize(2);
  titleCanvas.setTextWrap(false);
  titleCanvas.setCursor(titleScrollX, 3);
  titleCanvas.print(song);

  tft.drawRGBBitmap(
    TITLE_X,
    TITLE_Y,
    titleCanvas.getBuffer(),
    TITLE_W,
    TITLE_H
  );
}


void updateTitle() {
  if (!titleNeedsScroll)
    return;

  unsigned long now = millis();

  if (now - titleStart < TITLE_PAUSE)
    return;

  if (now - lastScroll >= 50) {
    lastScroll = now;
    titleScrollX += scrollDirection * TITLE_SPEED;

    if (titleScrollX <= -titleMaxScroll) {
      titleScrollX = -titleMaxScroll;
      scrollDirection = 1;
      titleStart = now;
    }

    if (titleScrollX >= 0) {
      titleScrollX = 0;
      scrollDirection = -1;
      titleStart = now;
    }

    drawTitle();
  }
}


void drawArtist() {
  tft.fillRect(125, 68, 180, 18, ILI9341_BLACK);

  tft.setTextColor(ILI9341_LIGHTGREY);
  tft.setTextSize(1);
  tft.setTextWrap(false);

  String s = artist;

  if (s.length() > 29)
    s = s.substring(0, 29);

  tft.setCursor(125, 72);
  tft.print(s);
}


void drawAlbum() {
  tft.fillRect(125, 87, 180, 18, ILI9341_BLACK);

  tft.setTextColor(ILI9341_LIGHTGREY);
  tft.setTextSize(1);
  tft.setTextWrap(false);

  String s = album;

  if (s.length() > 29)
    s = s.substring(0, 29);

  tft.setCursor(125, 91);
  tft.print(s);
}


void drawPlay() {
  tft.fillRect(135, 112, 50, 30, ILI9341_BLACK);
  drawLyric();
}


void drawProgress() {
  tft.fillRect(0, 153, 320, 25, ILI9341_BLACK);

  tft.fillRoundRect(12, 158, 296, 6, 3, 0x4208);

  if (durationMs > 0) {
    int width = (long)296 * progressMs / durationMs;
    width = constrain(width, 0, 296);

    if (width > 0) {
      tft.fillRoundRect(
        12,
        158,
        width,
        6,
        3,
        ILI9341_WHITE
      );
    }
  }

  tft.setTextSize(1);
  tft.setTextColor(ILI9341_LIGHTGREY);

  tft.setCursor(12, 170);
  tft.print(formatTime(progressMs));

  String total = formatTime(durationMs);

  tft.setCursor(308 - total.length() * 6, 170);
  tft.print(total);
}


String formatTime(long ms) {
  long sec = max(0L, ms) / 1000;

  int min = sec / 60;
  int s = sec % 60;

  char buf[10];
  sprintf(buf, "%d:%02d", min, s);

  return String(buf);
}


void updateProgress() {
  if (!playing)
    return;

  unsigned long now = millis();

  if (now - lastProgress >= 1000) {
    lastProgress = now;
    progressMs += 1000;

    if (progressMs > durationMs)
      progressMs = durationMs;

    drawProgress();
  }
}


void drawVolume() {
  tft.fillRect(0, 190, 320, 20, ILI9341_BLACK);

  tft.setTextSize(1);
  tft.setTextColor(ILI9341_WHITE);
  tft.setCursor(12, 198);
  tft.print("VOL");

  tft.fillRoundRect(
    45,
    198,
    220,
    8,
    4,
    0x4208
  );

  int width = 220L * volumePercent / 100;

  if (width > 0) {
    tft.fillRoundRect(
      45,
      198,
      width,
      8,
      4,
      ILI9341_WHITE
    );
  }

  tft.setTextColor(ILI9341_LIGHTGREY);
  tft.setCursor(273, 198);

  tft.print(volumePercent);
  tft.print("%");
}


void drawControls() {
  tft.fillRect(0, 215, 320, 25, ILI9341_BLACK);

  tft.setTextColor(ILI9341_WHITE);
  tft.setTextSize(2);

  tft.setCursor(55, 220);
  tft.print("|<");

  tft.setCursor(150, 220);

  if (playing)
    tft.print("||");
  else
    tft.print(">");

  tft.setCursor(245, 220);
  tft.print(">|");
}


void handleButtons() {
  bool prev = digitalRead(BTN_PREV);
  bool play = digitalRead(BTN_PLAY);
  bool next = digitalRead(BTN_NEXT);

  if (prevLast == HIGH && prev == LOW)
    Serial.println("PREVIOUS");

  if (playLast == HIGH && play == LOW)
    Serial.println("PLAY");

  if (nextLast == HIGH && next == LOW)
    Serial.println("NEXT");

  prevLast = prev;
  playLast = play;
  nextLast = next;
}
