"""
Module for restoring cache data from backup.
"""

import os
import asyncio
import shutil
import glob
from pathlib import Path
from .utils import (
    setup_logging,
    BACKUP_DIR,
    DISEASE_CACHE_DIR,
    LOGS_DIR
)
from .clear_cache import clear_and_create_empty_files


async def get_latest_backup():
    """Get the path to the latest backup directory."""
    logger = setup_logging("restore")
    
    if not os.path.exists(BACKUP_DIR):
        logger.error(f"Backup directory {BACKUP_DIR} not found.")
        return None
    
    # List all backup directories
    backup_dirs = glob.glob(os.path.join(BACKUP_DIR, "*"))
    backup_dirs = [d for d in backup_dirs if os.path.isdir(d)]
    
    if not backup_dirs:
        logger.error("No backup directories found.")
        return None
    
    # Sort by modification time (newest first)
    backup_dirs.sort(key=os.path.getmtime, reverse=True)
    latest_backup = backup_dirs[0]
    
    logger.info(f"Found latest backup: {latest_backup}")
    return latest_backup


async def restore_from_backup(timestamp=None):
    """Restore cache data from specified backup or latest if not specified."""
    logger = setup_logging("restore")
    logger.info(f"Starting restore {'from specified backup' if timestamp else 'from latest backup'}...")
    
    # Determine backup directory
    if timestamp:
        backup_dir = os.path.join(BACKUP_DIR, timestamp)
        if not os.path.exists(backup_dir):
            logger.error(f"Specified backup directory {backup_dir} not found.")
            return False
    else:
        backup_dir = await get_latest_backup()
        if not backup_dir:
            return False
    
    logger.info(f"Restoring from backup: {backup_dir}")
    
    try:
        # Clear existing cache and create empty files
        await clear_and_create_empty_files()
        
        # Copy disease JSON files from backup
        disease_backup_dir = os.path.join(backup_dir, "disease")
        if os.path.exists(disease_backup_dir):
            logger.info("Copying disease JSON files from backup...")
            json_files = glob.glob(os.path.join(disease_backup_dir, "*.json"))
            
            if not json_files:
                logger.warning("No JSON files found in backup.")
            else:
                for json_file in json_files:
                    filename = os.path.basename(json_file)
                    destination = os.path.join(DISEASE_CACHE_DIR, filename)
                    shutil.copy2(json_file, destination)
                    logger.info(f"Restored file: {filename}")
        else:
            logger.warning(f"Disease backup directory {disease_backup_dir} not found.")
        
        # Restore logs if they exist
        logs_backup_dir = os.path.join(backup_dir, "logs")
        if os.path.exists(logs_backup_dir):
            logger.info("Restoring logs...")
            os.makedirs(LOGS_DIR, exist_ok=True)
            
            log_files = glob.glob(os.path.join(logs_backup_dir, "*"))
            for log_file in log_files:
                if os.path.isfile(log_file):
                    filename = os.path.basename(log_file)
                    destination = os.path.join(LOGS_DIR, filename)
                    shutil.copy2(log_file, destination)
                    logger.info(f"Restored log: {filename}")
        
        logger.info("Restore completed successfully.")
        return True
        
    except Exception as e:
        logger.error(f"Error during restore process: {str(e)}")
        return False


async def main():
    """Main entry point for restore module."""
    import sys
    
    # Check if timestamp argument is provided
    timestamp = None
    if len(sys.argv) > 1:
        timestamp = sys.argv[1]
    
    result = await restore_from_backup(timestamp)
    if result:
        print("Restore completed successfully.")
    else:
        print("Restore failed. Check logs for details.")


if __name__ == "__main__":
    asyncio.run(main())