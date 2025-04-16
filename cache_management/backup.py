"""
Module for backing up disease cache data.
"""

import os
import asyncio
import tzlocal 
import shutil
import sys
from datetime import datetime, timedelta
import json
from sqlalchemy import select
from pathlib import Path
from .utils import (
    setup_logging, 
    create_directories, 
    cleanup_old_backups,
    DISEASE_CACHE_DIR, 
    BACKUP_TIMESTAMP_DIR,
    LOGS_DIR,
    BASE_DIR
)

# Import database models
sys.path.append(BASE_DIR)
from build_dossier import SessionLocal
from db.models import DiseasesDossierStatus


async def backup_processed_diseases():
    """Backup disease cache files with 'processed' status."""
    logger = setup_logging("backup")
    logger.info("Starting backup of processed diseases...")
    
    # Create backup directories with database timestamp
    backup_dir = await create_directories()
    logger.info(f"Created backup directory: {backup_dir}")
    
    if not os.path.exists(DISEASE_CACHE_DIR):
        logger.error(f"Disease cache directory {DISEASE_CACHE_DIR} not found.")
        return False
    
    try:
        # Get all diseases with 'processed' status
        async with SessionLocal() as db:
            result = await db.execute(
                select(DiseasesDossierStatus).where(DiseasesDossierStatus.status == "processed")
            )
            disease_records = result.scalars().all()
            processed_disease_ids = [record.id for record in disease_records]
            
        if not processed_disease_ids:
            logger.error("No diseases with 'processed' status found in database.")
            return False
            
        logger.info(f"Found {len(processed_disease_ids)} diseases with 'processed' status to backup: {processed_disease_ids}")
        
        # Verify that JSON files exist for these diseases
        json_files_to_backup = []
        for disease_id in processed_disease_ids:
            json_file = f"{disease_id}.json"
            file_path = os.path.join(DISEASE_CACHE_DIR, json_file)
            if os.path.exists(file_path):
                json_files_to_backup.append(json_file)
            else:
                logger.warning(f"Disease {disease_id} has 'processed' status but no JSON file found.")
        
        if not json_files_to_backup:
            logger.error("No JSON files found to backup.")
            return False
            
        logger.info(f"Backing up {len(json_files_to_backup)} JSON files...")
        
        # Copy JSON files to backup directory
        for json_file in json_files_to_backup:
            source = os.path.join(DISEASE_CACHE_DIR, json_file)
            destination = os.path.join(backup_dir, "disease", json_file)
            shutil.copy2(source, destination)
            logger.info(f"Backed up {json_file}")
            
        return True
        
    except Exception as e:
        logger.error(f"Error during backup process: {str(e)}")
        return False


async def backup_and_populate_db():
    """Backup cache files and populate database with disease data."""
    logger = setup_logging("backup")
    logger.info("Starting backup process...")
    
    # Create backup directories with database timestamp
    backup_dir = await create_directories()
    logger.info(f"Created backup directory: {backup_dir}")
    
    if not os.path.exists(DISEASE_CACHE_DIR):
        logger.error(f"Disease cache directory {DISEASE_CACHE_DIR} not found.")
        return False
    
    # Check for JSON files
    json_files = [f for f in os.listdir(DISEASE_CACHE_DIR) if f.endswith('.json')]
    if not json_files:
        logger.error("No JSON files found to backup.")
        logger.error("Please ensure cache files are generated before running this script.")
        return False
    
    try:
        # Copy disease JSON files to backup
        logger.info("Copying disease JSON files to backup directory...")
        for json_file in json_files:
            source = os.path.join(DISEASE_CACHE_DIR, json_file)
            destination = os.path.join(backup_dir, "disease", json_file)
            shutil.copy2(source, destination)
        
        # Backup logs if they exist
        if os.path.exists(LOGS_DIR):
            logger.info("Backing up logs...")
            logs_backup_dir = os.path.join(backup_dir, "logs")
            os.makedirs(logs_backup_dir, exist_ok=True)
            
            log_files = [f for f in os.listdir(LOGS_DIR) if os.path.isfile(os.path.join(LOGS_DIR, f))]
            for log_file in log_files:
                source = os.path.join(LOGS_DIR, log_file)
                destination = os.path.join(logs_backup_dir, log_file)
                shutil.copy2(source, destination)
        
        # Clean up old backups
        cleanup_old_backups()
        
        logger.info(f"Backup completed. Stored in: {backup_dir}")
        return True
        
    except Exception as e:
        logger.error(f"Error during backup process: {str(e)}")
        return False


async def main():
    """Main entry point for backup module."""
    result = await backup_and_populate_db()
    if result:
        print("Backup completed successfully.")
    else:
        print("Backup failed. Check logs for details.")


if __name__ == "__main__":
    asyncio.run(main())