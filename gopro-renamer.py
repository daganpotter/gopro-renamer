import os
import shutil
import sys
import logging
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import json

# Try to import tqdm, but provide a fallback if not available
try:
    from tqdm import tqdm
    HAVE_TQDM = True
except ImportError:
    HAVE_TQDM = False
    
    # Simple progress indicator fallback
    class SimpleProg:
        def __init__(self, total, desc):
            self.total = total
            self.desc = desc
            self.n = 0
            self.last_print = 0
            print(f"{desc}: 0/{total}", end='', flush=True)
            
        def update(self, n=1):
            self.n += n
            # Only update display every 1% to avoid console spam
            if self.n - self.last_print >= max(1, self.total // 100):
                print(f"\r{self.desc}: {self.n}/{self.total}", end='', flush=True)
                self.last_print = self.n
                
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            print(f"\r{self.desc}: {self.n}/{self.total} - Done!", flush=True)
            
    tqdm = SimpleProg

class GoProFileRenamer:
    GOPRO_PATTERNS = [
        r'^G[HX]\d{2}\d{4}\.(?:MP4|THM|LRV)$',
        r'^GOPR\d{4}\.(?:MP4|THM|LRV)$',
        r'^\d{8}_\d{6}_\d{3}\.(?:MP4|THM|LRV)$'
    ]

    def __init__(self, base_path, recursive=False, dry_run=False, copy_mode=False, create_backup=False):
        self.base_path = Path(base_path)
        self.recursive = recursive
        self.dry_run = dry_run
        self.copy_mode = copy_mode
        self.create_backup = create_backup and copy_mode  # Only create backup if in copy mode
        self.backup_path = None
        self.moved_files = defaultdict(list)
        self.setup_logging()

    def setup_logging(self):
        """Configure logging with both file and console output"""
        log_file = self.base_path / f'gopro_renamer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def check_disk_space(self, required_space):
        """Check if there's enough disk space available"""
        if self.copy_mode:
            total, used, free = shutil.disk_usage(self.base_path)
            return free > required_space
        return True

    def get_total_size(self, files):
        """Calculate total size of files to be copied"""
        return sum(f.stat().st_size for f in files if f.exists())

    def is_gopro_file(self, filename):
        """Check if file matches any GoPro naming pattern"""
        return any(re.match(pattern, filename, re.IGNORECASE) for pattern in self.GOPRO_PATTERNS)

    def get_file_number(self, filename):
        """Extract file number from GoPro filename"""
        if match := re.search(r'(?:GH|GX)\d{2}(\d{4})', filename):
            return match.group(1)
        elif match := re.search(r'GOPR(\d{4})', filename):
            return match.group(1)
        elif match := re.search(r'\d{8}_\d{6}_(\d{3})', filename):
            return match.group(1)
        return None

    def find_gopro_files(self):
        """Find all GoPro files in directory"""
        files_dict = defaultdict(lambda: defaultdict(list))
        
        def process_directory(directory):
            try:
                for item in directory.iterdir():
                    if item.is_file() and self.is_gopro_file(item.name):
                        file_number = self.get_file_number(item.name)
                        if file_number:
                            files_dict[directory][file_number].append(item)
                    elif item.is_dir() and self.recursive and item != self.backup_path:
                        process_directory(item)
            except PermissionError as e:
                self.logger.warning(f"Permission denied accessing {directory}: {e}")
            except Exception as e:
                self.logger.error(f"Error processing directory {directory}: {e}")

        process_directory(self.base_path)
        return files_dict

    def organize_files(self):
        """Main function to organize GoPro files"""
        try:
            self.logger.info(f"Starting GoPro file {'copy' if self.copy_mode else 'rename'} operation...")
            
            # Find all files first
            files_by_dir = self.find_gopro_files()
            if not files_by_dir:
                self.logger.info("No GoPro files found to process.")
                return

            # Calculate total files to process for progress bar
            total_operations = sum(
                len(files) for directory in files_by_dir.values()
                for file_group in directory.values()
                for files in [file_group]
                if len([f for f in files if f.suffix.upper() == '.MP4']) > 1
            )

            if total_operations == 0:
                self.logger.info("No files need reorganization.")
                return

            # Create backup directory if needed
            if self.create_backup:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.backup_path = self.base_path / f'gopro_renamer_backup_{timestamp}'
                if not self.dry_run:
                    self.backup_path.mkdir(exist_ok=True)

            self.logger.info(f"Found {total_operations} files to process")
            
            # Process files with progress indicator
            progress_cls = tqdm if HAVE_TQDM else SimpleProg
            with progress_cls(total=total_operations, desc="Processing files") as pbar:
                for directory, files_dict in files_by_dir.items():
                    for file_number, files in files_dict.items():
                        mp4_files = [f for f in files if f.suffix.upper() == '.MP4']
                        
                        if len(mp4_files) > 1:
                            folder_name = f"Video_{file_number}"
                            folder_path = directory / folder_name

                            if not self.dry_run:
                                folder_path.mkdir(exist_ok=True)

                            # Check disk space if copying
                            if self.copy_mode:
                                required_space = self.get_total_size(files)
                                if not self.check_disk_space(required_space):
                                    raise OSError(f"Not enough disk space to copy files (needed: {required_space // 1024 ** 2}MB)")

                            for file in files:
                                try:
                                    new_path = folder_path / file.name
                                    if not self.dry_run:
                                        if self.copy_mode:
                                            shutil.copy2(str(file), str(new_path))
                                        else:
                                            os.rename(str(file), str(new_path))
                                        
                                        self.moved_files[str(directory)].append({
                                            'original': str(file),
                                            'new': str(new_path),
                                            'operation': 'copy' if self.copy_mode else 'rename'
                                        })
                                    
                                    self.logger.info(f"{'Would' if self.dry_run else ''} "
                                                   f"{'copy' if self.copy_mode else 'rename'} "
                                                   f"'{file}' to '{new_path}'")
                                except Exception as e:
                                    self.logger.error(f"Error processing file {file}: {e}")
                                    raise
                                
                                pbar.update(1)

            # Save movement record
            if not self.dry_run and self.moved_files:
                self._save_movement_record()

            self.logger.info("Organization complete!")
            if self.dry_run:
                self.logger.info("This was a dry run - no files were actually modified.")

        except Exception as e:
            self.logger.error(f"Error during organization: {str(e)}", exc_info=True)
            raise

    def _save_movement_record(self):
        """Save record of all file movements"""
        record_file = self.base_path / 'gopro_renamer_movements.json'
        with open(record_file, 'w') as f:
            json.dump(self.moved_files, f, indent=2)

    def undo_organization(self):
        """Undo the last organization based on movement record"""
        movement_record = self.base_path / 'file_movements.json'
        if not movement_record.exists():
            self.logger.info("No organization to undo.")
            return

        try:
            with open(movement_record) as f:
                moved_files = json.load(f)

            total_operations = sum(len(movements) for movements in moved_files.values())
            progress_cls = tqdm if HAVE_TQDM else SimpleProg
            with progress_cls(total=total_operations, desc="Undoing changes") as pbar:
                for directory, movements in moved_files.items():
                    for movement in movements:
                        original_path = Path(movement['original'])
                        new_path = Path(movement['new'])
                        operation = movement.get('operation', 'rename')

                        if new_path.exists():
                            if not self.dry_run:
                                original_path.parent.mkdir(parents=True, exist_ok=True)
                                if operation == 'copy':
                                    new_path.unlink()
                                    self.logger.info(f"Removed copy at '{new_path}'")
                                else:
                                    os.rename(str(new_path), str(original_path))
                                    self.logger.info(f"Renamed '{new_path}' back to '{original_path}'")
                            else:
                                self.logger.info(
                                    f"Would {'remove' if operation == 'copy' else 'rename'} "
                                    f"'{new_path}' {'back to' if operation != 'copy' else 'from'} "
                                    f"'{original_path}'"
                                )
                        pbar.update(1)

            # Clean up empty folders and movement record
            if not self.dry_run:
                self._cleanup_empty_folders()
                movement_record.unlink()

            self.logger.info("Undo complete!")
            if self.dry_run:
                self.logger.info("This was a dry run - no files were actually modified.")

        except Exception as e:
            self.logger.error(f"Error during undo: {str(e)}", exc_info=True)
            raise

    def _cleanup_empty_folders(self):
        """Remove empty folders after undo"""
        for root, dirs, files in os.walk(self.base_path, topdown=False):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                try:
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        self.logger.info(f"Removed empty folder: {dir_path}")
                except Exception as e:
                    self.logger.warning(f"Could not remove folder {dir_path}: {str(e)}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Rename and organize GoPro video files and their associated files.')
    parser.add_argument('--path', type=str, default=os.getcwd(),
                      help='Base path to organize (default: current directory)')
    parser.add_argument('--recursive', action='store_true',
                      help='Process subdirectories recursively')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would be done without actually moving files')
    parser.add_argument('--undo', action='store_true',
                      help='Undo the last organization')
    parser.add_argument('--copy', action='store_true',
                      help='Copy files instead of renaming them')
    parser.add_argument('--backup', action='store_true',
                      help='Create backups when copying files (only works with --copy)')

    args = parser.parse_args()
    
    renamer = GoProFileRenamer(
        args.path, 
        args.recursive, 
        args.dry_run, 
        args.copy,
        args.backup
    )
    
    if args.undo:
        renamer.undo_organization()
    else:
        renamer.organize_files()

if __name__ == "__main__":
    main()