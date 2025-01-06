# gopro-renamer
Renames and organizes GoPro media files by grouping sequential chapters into folders. When GoPro splits long recordings into multiple files, it uses confusing names like GH010123.MP4, GH020123.MP4, etc. This script organizes these related files together alphanumerically for easier management.

## Optional
For fancy progress bars, you can install tqdm.

tqdm
```
pip install tqdm
```
## Usage
```
Example:

python gopro-renamer.py --path /path_to_gopro_files/

---

usage: gopro-renamer.py [-h] [--path PATH] [--recursive] [--dry-run] [--undo] [--copy] [--backup]

Rename and organize GoPro video files and their associated files.

options:
  -h, --help   show this help message and exit
  --path PATH  Base path to organize (default: current directory)
  --recursive  Process subdirectories recursively
  --dry-run    Show what would be done without actually moving files
  --undo       Undo the last organization
  --copy       Copy files instead of renaming them
  --backup     Create backups when copying files (only works with --copy)
```
