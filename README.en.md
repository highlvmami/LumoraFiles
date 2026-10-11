<div align="center">

# LumoraFiles

**A desktop app that moves files between your phone and computer over the same Wi-Fi, and turns the phone into a remote control for the computer.**

[Türkçe](README.md) · English

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Flask-3-000000?logo=flask&logoColor=white" alt="Flask 3">
  <img src="https://img.shields.io/badge/Tkinter-GUI-FFD43B?logo=python&logoColor=black" alt="Tkinter">
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black" alt="JavaScript">
  <img src="https://img.shields.io/badge/pynput-mss-6366F1" alt="pynput, mss">
  <img src="https://img.shields.io/badge/Windows-0078D4?logo=windows&logoColor=white" alt="Windows">
</p>

</div>

A small window opens on your computer and shows a QR code, an address and a PIN. Scan the QR with your phone and a page opens in its browser: no app to install, no internet needed. From there you send files, download files from the computer, control its volume and slides, use its mouse and keyboard, and watch its screen. The server is Python + Flask, the window is Tkinter, and the phone page is plain HTML/CSS/JS with no framework.

> Everything stays on your local network and nothing goes to the internet. Because the phone can control the computer, do not share the PIN and do not expose port 8000 to the internet.

## Features

### File transfer
- **Phone to computer:** pick several files and each one gets a progress bar. Large files stream to disk without filling memory.
- **Computer to phone:** drag and drop a file onto the window (or use "Dosya seç…") and it appears in the phone page's download list.
- A file with an existing name is never overwritten (`photo_1.jpg`); path tricks such as `../` in file names are stripped.

### Phone remote
- **Media and volume:** play/pause, next/previous, volume up/down, mute.
- **Presentations:** next, previous, start (F5), blank screen, end.
- **Mouse and keyboard:** one finger moves the mouse, tap is a left click, a two-finger tap is a right click, a two-finger drag scrolls. Type text (including Turkish characters) and press keys such as Enter, arrows and Esc.
- **Computer commands:** lock, sleep, shut down, restart. Shut down and restart ask for confirmation on the phone, wait 30 seconds and can be cancelled.
- **Programs:** launch programs from the list in `komutlar.json` (default: Calculator, Notepad, File Explorer).
- **Screen view:** watch the computer screen live on the phone; tapping the picture clicks that spot on the computer.

### Security
- **PIN:** a random 6-digit PIN is generated on every start. A device without the PIN cannot reach any page or file.
- **QR sign-in:** the QR code contains the PIN, so the phone that scans it signs in without typing.
- **Attempt limit:** after 5 wrong attempts a device is locked out for 1 minute.
- **New PIN:** one click generates a new PIN and signs every connected phone out.
- **Remote control switch:** one checkbox in the window turns off the remote and screen view while file transfer keeps working.
- The phone can only send the **index number** of a program in `komutlar.json`, never the command itself.

## How to use it

1. Double-click `LumoraFiles.bat`. On the first run it installs what it needs.
2. The window shows the QR code and the PIN.
3. Connect the phone to the **same Wi-Fi** as the computer and scan the QR. The page opens and you are signed in.
4. Pick **Dosya** (files), **Kumanda** (remote) or **Ekran** (screen) from the tabs.

## How it works

- **The server lives inside the window.** `masaustu.py` starts the Flask server on a background thread and leaves the main thread to the Tkinter window. The server never touches the window directly; it drops the names of received files into a `queue.Queue`, and the window checks the queue every half second to update its list.
- **Local IP.** A UDP socket "connects" to an outside address without sending anything; whichever network card the operating system picks, its address is the computer's local IP. The server listens on `0.0.0.0`, otherwise the phone could not reach it.
- **Progress bar.** Each file goes in its own `XMLHttpRequest`, because `fetch` does not report upload progress and `upload.onprogress` does.
- **Keys and mouse.** `pynput` generates real input events; media keys, presentation keys and Unicode text all take the same path. On the touchpad, movements are sent in batches every 30 ms instead of on every touch event.
- **Screen view.** `mss` grabs the main screen and Pillow shrinks it to a JPEG. The phone asks for the next frame as soon as one arrives, so the speed adapts to the network. A frame is downloaded into memory first and then swapped in, so the picture does not flicker. A tap is sent as a **fraction** of the screen, so it works at any resolution.
- **PIN and session.** The right PIN earns a random session key stored as a cookie. Every request (files, remote, screen) checks it. The PIN comparison runs in constant time.

## Tech stack

| Part | Technology |
|---|---|
| Server | Python 3.10+, Flask |
| Desktop window | Tkinter, `tkinterdnd2` (drag and drop) |
| Phone page | HTML, CSS, JavaScript (no framework) |
| Keys and mouse | `pynput` |
| Screen capture | `mss`, Pillow |
| QR code | `qrcode` |

## Project layout

| Path | What |
|---|---|
| `main.py` | Flask server: file transfer, PIN sign-in, local IP lookup |
| `uzak.py` | Remote control: media, presentations, mouse, keyboard, commands, screenshot |
| `masaustu.py` | Tkinter window (QR, PIN, file lists, permission checkbox) |
| `templates/index.html` | Phone page (Dosya / Kumanda / Ekran tabs) |
| `templates/giris.html` | PIN sign-in page |
| `komutlar.json` | Programs the phone can launch (created on first run) |
| `LumoraFiles.bat` | Double-click launcher for Windows, also does the setup |
| `alinanlar/` | Files received from the phone |
| `paylasilan/` | Files prepared for the phone |

## Running locally

Requirements: Python 3.10+ from [python.org](https://www.python.org/downloads/) (tick **"Add python.exe to PATH"** when installing). Tkinter comes with the python.org installer.

**Windows:** double-click `LumoraFiles.bat`.

**By hand:**

```bash
python -m venv venv
venv\Scripts\activate          # macOS / Linux: source venv/bin/activate
pip install -r requirements.txt
python masaustu.py             # with the window
python main.py                 # server only, prints the QR code in the terminal
```

## Configuration

| Setting | Meaning |
|---|---|
| `PORT` (`main.py`) | Server port, default 8000 |
| `DENEME_SINIRI`, `KILIT_SURESI` (`main.py`) | How many wrong PINs and how many seconds of lockout (5 tries, 60 s) |
| `komutlar.json` | Program list as `[{"ad": "Calculator", "komut": "calc"}]` |
| `LUMORA_KURU=1` (environment variable) | Records key presses and commands instead of running them; for tests |

## Troubleshooting

- The phone and computer must be on the **same Wi-Fi**. Guest networks usually isolate devices from each other.
- Windows asks for a firewall permission on first run: allow it for **Private networks**.
- If the QR does not scan, type the address shown in the window (`http://192.168…:8000`) on the phone and enter the PIN.
- The PIN changes on every start; after restarting the app, scan the QR again.
- System commands (lock, sleep, shut down) currently work only on Windows. File transfer works on other systems too.
