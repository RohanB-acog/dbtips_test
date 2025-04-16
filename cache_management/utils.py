"""
Utility functions for cache management operations.
"""

import os
import logging
import sys
from datetime import datetime
import glob
from pathlib import Path
from sqlalchemy import select
import asyncio
import tzlocal 
# Base directories
BASE_DIR = "/app/res-immunology-automation/res_immunology_automation/src/scripts"
CACHE_DIR = os.path.join(BASE_DIR, "cached_data_json")
DISEASE_CACHE_DIR = os.path.join(CACHE_DIR, "disease")
BACKUP_DIR = os.path.join(BASE_DIR, "backedup_cache_data")
LOGS_DIR = os.path.join(CACHE_DIR, "logs")

# Will be set dynamically based on database submission time
BACKUP_TIMESTAMP_DIR = None


def setup_logging(log_name):
    """Set up logging configuration for modules."""
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.INFO)
    
    # Create logs directory if it doesn't exist
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # File handler
    log_file = os.path.join(LOGS_DIR, f"{log_name}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


async def get_database_timestamp():
    """Get timestamp from database for backup directory naming."""
    logger = setup_logging("db_timestamp")
    
    try:
        # Import here to avoid circular imports
        sys.path.append(BASE_DIR)
        from build_dossier import SessionLocal
        from db.models import DiseasesDossierStatus
        
        async with SessionLocal() as db:
            # Get the earliest submission time from processed diseases
            result = await db.execute(
                select(DiseasesDossierStatus.submission_time)
                .where(DiseasesDossierStatus.status == "processed")
                .order_by(DiseasesDossierStatus.submission_time.asc())
                .limit(1)
            )
            
            submission_time = result.scalar_one_or_none()
            
            if submission_time:
                timestamp = submission_time.strftime("%Y%m%d_%H%M%S")
                logger.info(f"Using database timestamp for backup: {timestamp}")
                return timestamp
            else:
                # Fallback to current time if no submission time found
                timestamp = datetime.now(tzlocal.get_localzone()).strftime("%Y%m%d_%H%M%S")
                logger.warning(f"No submission time found in database, using current time: {timestamp}")
                return timestamp
                # datetime.now(tzlocal.get_localzone())

    except Exception as e:
        logger.error(f"Error getting database timestamp: {str(e)}")
        # Fallback to current time
        timestamp = datetime.now(tzlocal.get_localzone()).strftime("%Y%m%d_%H%M%S")
        logger.warning(f"Using current time as fallback: {timestamp}")
        return timestamp


async def create_directories():
    """Create necessary directories for cache management using database timestamp."""
    global BACKUP_TIMESTAMP_DIR
    
    # Get timestamp from database
    timestamp = await get_database_timestamp()
    BACKUP_TIMESTAMP_DIR = os.path.join(BACKUP_DIR, timestamp)
    
    os.makedirs(os.path.join(BACKUP_TIMESTAMP_DIR, "disease"), exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    return BACKUP_TIMESTAMP_DIR


def cleanup_old_backups(keep_count=1):
    """Clean up old backup directories, keeping only the newest ones."""
    logger = setup_logging("cleanup")
    
    # List all backup directories
    backup_dirs = glob.glob(os.path.join(BACKUP_DIR, "*"))
    backup_dirs = [d for d in backup_dirs if os.path.isdir(d)]
    
    # Sort by modification time (newest first)
    backup_dirs.sort(key=os.path.getmtime, reverse=True)
    
    # Keep the newest 'keep_count' backups, remove the rest
    if len(backup_dirs) > keep_count:
        for old_dir in backup_dirs[keep_count:]:
            logger.info(f"Removing old backup directory: {old_dir}")
            try:
                # Use shutil for recursive directory removal
                import shutil
                shutil.rmtree(old_dir)
            except Exception as e:
                logger.error(f"Failed to remove directory {old_dir}: {str(e)}")


def get_all_disease_ids():
    """Get all disease IDs from JSON files in cache directory."""
    if not os.path.exists(DISEASE_CACHE_DIR):
        return []
    
    json_files = glob.glob(os.path.join(DISEASE_CACHE_DIR, "*.json"))
    return [Path(file).stem for file in json_files]


def check_environment_variables():
    """Check if required environment variables are set."""
    required_vars = ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_HOST"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    return missing_vars


if __name__ == "__main__":
    logger = setup_logging("utils")
    logger.info("Testing utilities module")
    
    try:
        backup_dir = asyncio.run(create_directories())
        logger.info(f"Created directories: {backup_dir}")
        
        disease_ids = get_all_disease_ids()
        logger.info(f"Found disease IDs: {disease_ids}")
        
        missing_vars = check_environment_variables()
        if missing_vars:
            logger.warning(f"Missing environment variables: {missing_vars}")
        else:
            logger.info("All required environment variables are set")
            
        cleanup_old_backups()
        logger.info("Cleanup completed")
        
    except Exception as e:
        logger.error(f"Error in utils: {str(e)}")