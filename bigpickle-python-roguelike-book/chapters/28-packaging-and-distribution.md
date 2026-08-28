# Chapter 28: Packaging and Distribution

You have a complete roguelike. Now share it with the world. This chapter covers creating standalone executables, platform-specific builds, CI/CD pipelines, and distribution platforms.

## Why Package?

Most players won't install Python and run `pip install`. They want a double-click executable. Packaging creates a standalone application that includes:
- The Python interpreter
- All dependencies (tcod, numpy, etc.)
- Game data files (fonts, sounds, data)

## PyInstaller

PyInstaller bundles Python applications into standalone executables:

```bash
pip install pyinstaller
```

### Basic Build

```bash
pyinstaller --onefile --windowed --name "DungeonCrawler" main.py
```

Options:
- `--onefile`: Single executable (slower startup, easier distribution)
- `--onedir`: Directory with all files (faster startup)
- `--windowed`: No console window (for GUI games)
- `--name`: Executable name

### Including Data Files

```bash
pyinstaller --onefile --windowed \
  --add-data "data/fonts/*:data/fonts" \
  --add-data "data/sounds/*:data/sounds" \
  --add-data "data/entities/*:data/entities" \
  --name "DungeonCrawler" \
  main.py
```

### Handling Data Paths in Code

```python
import sys
from pathlib import Path

def get_data_path(relative_path: str) -> Path:
    """Get path to data file, works for both dev and packaged."""
    if getattr(sys, '_MEIPASS', None):
        # Running as PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Running in development
        base_path = Path(__file__).parent
    
    return base_path / relative_path

# Usage
FONT_PATH = get_data_path("data/fonts/dejavu10x10.ttf")
```

### PyInstaller Spec File

Create `dungeoncrawler.spec` for reproducible builds:

```python
# dungeoncrawler.spec
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('data/fonts/*', 'data/fonts'),
        ('data/sounds/*', 'data/sounds'),
        ('data/entities/*', 'data/entities'),
    ],
    hiddenimports=['tcod', 'numpy', 'tcod.ecs'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='DungeonCrawler',
    debug=False,
    strip=False,
    upx=True,
    console=False,
)
```

## Platform-Specific Builds

### Windows
```bash
pyinstaller dungeoncrawler.spec
# Output: dist/DungeonCrawler.exe
```

### macOS
```bash
pyinstaller --windowed --name "DungeonCrawler" --icon icon.icns main.py
# Creates .app bundle
```

### Linux
```bash
pyinstaller --onefile --name "dungeoncrawler" main.py
# Creates standalone binary
```

## Using cx_Freeze

Alternative to PyInstaller:

```python
# setup.py
from cx_Freeze import setup, Executable

setup(
    name="DungeonCrawler",
    version="1.0.0",
    description="A roguelike dungeon crawler",
    options={
        "build_exe": {
            "packages": ["tcod", "numpy", "tcod.ecs"],
            "include_files": [
                ("data/", "data/"),
            ],
        }
    },
    executables=[Executable("main.py", base="Win32GUI")],
)
```

```bash
python setup.py build
```

## CI/CD with GitHub Actions

Automate builds for all platforms:

```yaml
# .github/workflows/build.yml
name: Build

on:
  push:
    tags: ['v*']

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [windows-latest, macos-latest, ubuntu-latest]
    
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install pyinstaller
        pip install -r requirements.txt
    
    - name: Build
      run: pyinstaller --onefile --windowed --name DungeonCrawler main.py
    
    - name: Upload artifact
      uses: actions/upload-artifact@v4
      with:
        name: DungeonCrawler-${{ matrix.os }}
        path: dist/
```

## Distribution Platforms

### itch.io
- Free hosting for indie games
- Supports Windows, macOS, Linux uploads
- Browser-based play option (with WebAssembly)

### GitHub Releases
- Attach executables to releases
- Free for open-source projects
- Version tagging with `git tag v1.0.0`

### Steam (Advanced)
- Requires Steamworks SDK integration
- Steam achievements, cloud saves
- More complex setup

## Creating an itch.io Page

```
Title: Dungeon Crawler
Description: A roguelike built with Python and tcod
Upload:
  - DungeonCrawler.exe (Windows)
  - DungeonCrawler.app.zip (macOS)
  - dungeoncrawler (Linux)
Price: Free / Pay What You Want
```

## Exercises

- Create a build script that builds for all platforms
- Add a version number that auto-increments
- Create an in-game update checker
- Add crash reporting that uploads logs
- Create a website with screenshots and downloads
