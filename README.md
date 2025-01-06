# gopro-renamer
Rename GoPro media files so sequential files sort alphanumerically rather than using GoPro's terrible naming convention.


usage: gopro_renamer.py [-h] [--path PATH] [--recursive] [--dry-run] [--undo] [--copy] [--backup]

Rename and organize GoPro video files and their associated files.

options:
  -h, --help   show this help message and exit
  --path PATH  Base path to organize (default: current directory)
  --recursive  Process subdirectories recursively
  --dry-run    Show what would be done without actually moving files
  --undo       Undo the last organization
  --copy       Copy files instead of renaming them
  --backup     Create backups when copying files (only works with --copy)
