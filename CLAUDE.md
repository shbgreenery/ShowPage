# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a collection of automated game solving tools for Android mobile games. The tools work by:
1. Taking screenshots via ADB (Android Debug Bridge)
2. Analyzing the game state using image processing (PIL/Pillow)
3. Executing tap/swipe commands to automatically solve puzzles

## Architecture

### Core Components

**ADB Proxy Server** (`adb_proxy.py`)
- HTTP server (port 8085) that bridges web UI to ADB commands
- Endpoints: `/health`, `/devices`, `/screenshot`, `/tap`, `/swipe`
- Uses `ThreadingHTTPServer` for concurrent request handling
- Constants organized into `Config`, `Status`, `HttpCode`, `ADBCommand` classes

**Game Solvers**
- `puzzle_solver.py` - Automated puzzle solver using color detection (RGB matching)
- `puzzle_solver.html` - Web UI for puzzle solving
- `nonogram.html` - Nonogram (logic puzzle) solver with ADB integration
- `minesweeper.html` - Minesweeper solver

**Main Entry Point**
- `index.html` - Dashboard linking to all game tools

## Running the Tools

### Activate Virtual Environment (Required)
```bash
source venv/bin/activate
```
Dependencies: Pillow 12.1.0, requests 2.32.5, tqdm

### Start ADB Proxy Server
```bash
python adb_proxy.py
```
Default port: 8085. Ensure Android device is connected with USB debugging enabled.

### Run Puzzle Solver (Python CLI)
```bash
python puzzle_solver.py
```
Enter number of rounds to solve, or leave empty for infinite loop.

### Game Solver Web UIs
Open any HTML file directly in a browser (requires adb_proxy.py running):
- `index.html` - Main dashboard
- `puzzle_solver.html` - Puzzle solver
- `nonogram.html` - Nonogram solver
- `minesweeper.html` - Minesweeper solver

## Key Implementation Details

### Color Detection (Puzzle Solver)
- Uses PIL to get pixel colors from screenshots
- Target color: RGB(36, 138, 114) with ±10 tolerance
- Parallel color filtering using `ThreadPoolExecutor(max_workers=4)`
- Thread-safe pixel access via `image.load()`

### Point Generation (Puzzle)
- 19 rows, staggered layout (hexagonal pattern)
- Fixed coordinate calculation: y = 580 + row * 54
- This logic is duplicated between `puzzle_solver.html` (JS) and `puzzle_solver.py` (Python)

### ADB Command Patterns
- **Screenshot**: `adb exec-out screencap -p` (returns PNG bytes)
- **Tap**: `adb shell input tap {x} {y}`
- **Swipe**: Multi-command shell script with `input motionevent DOWN/MOVE/UP`
- Batch taps: Combine multiple tap commands into one shell script (N+1 pattern fix)

## Code Quality Notes

### Constants Used
- Proxy URL/port is hardcoded in multiple files (8085) - not yet centralized
- Swipe midpoint coordinates: `(100, 1500)` in adb_proxy.py, `(100, 1650)` in puzzle_solver.py
- The Python code uses proper constants, JavaScript code generally does not

### Duplicated Code
- Point generation logic exists in both JS and Python
- Similar color matching logic in both languages
- Batch tap logic duplicated between HTML files

### Known Issues (Not Yet Addressed)
- nonogram.html has event listener cleanup issues
- localStorage grows unbounded (no size limits)
- Various hardcoded colors/coordinates in JavaScript files
