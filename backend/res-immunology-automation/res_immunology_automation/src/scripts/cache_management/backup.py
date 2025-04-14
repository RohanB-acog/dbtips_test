"""
Module for backing up disease cache data and populating the database.
"""

import os
import asyncio
import shutil
import sys
from datetime import datetime
import json
from sqlalchemy import delete
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
from db.models import Disease, DiseasesDossierStatus


async def populate_database_from_cache():
    """Populate database with diseases from cached JSON files, setting status to 'processed'."""
    logger = setup_logging("populate_db")
    
    if not os.path.exists(DISEASE_CACHE_DIR):
        logger.error(f"Cache directory {DISEASE_CACHE_DIR} does not exist.")
        return False
    
    disease_files = [f for f in os.listdir(DISEASE_CACHE_DIR) if f.endswith('.json')]
    disease_ids = [os.path.splitext(f)[0] for f in disease_files]
    
    if not disease_ids:
        logger.error("No disease JSON files found in cache directory.")
        return False
    
    try:
        async with SessionLocal() as db:
            logger.info("Clearing existing database entries...")
            await db.execute(delete(Disease))
            await db.execute(delete(DiseasesDossierStatus))
            await db.commit()
            
            logger.info(f"Populating database with {len(disease_ids)} diseases: {disease_ids}")
            for disease_id in disease_ids:
                file_path = os.path.join(DISEASE_CACHE_DIR, f"{disease_id}.json")
                disease = Disease(id=disease_id, file_path=file_path)
                db.add(disease)
                # Set status to 'processed' 
                status = DiseasesDossierStatus(
                    id=disease_id,
                    status="processed",  # 'processed'
                    submission_time=datetime.utcnow(),
                    processed_time=datetime.utcnow()  # Add processed_time as we're setting status to processed
                )
                db.add(status)
            await db.commit()
            logger.info("Database population completed successfully with 'processed' status.")
            return True
            
    except Exception as e:
        logger.error(f"Error populating database: {str(e)}")
        return False


async def backup_and_populate_db():
    """Backup cache files and populate database with disease data."""
    logger = setup_logging("backup")
    logger.info("Starting backup and database population...")
    
    # Create backup directories
    backup_dir = create_directories()
    logger.info(f"Created backup directory: {backup_dir}")
    
    if not os.path.exists(DISEASE_CACHE_DIR):
        logger.error(f"Disease cache directory {DISEASE_CACHE_DIR} not found.")
        return False
    
    # Check for JSON files
    json_files = [f for f in os.listdir(DISEASE_CACHE_DIR) if f.endswith('.json')]
    if not json_files:
        logger.error("No JSON files found to backup or populate database.")
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
        
        # Populate database from cache, setting status to 'processed'
        db_result = await populate_database_from_cache()
        if not db_result:
            logger.error("Failed to populate database from cache.")
            return False
        
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
        print("Backup and database population completed successfully.")
    else:
        print("Backup and database population failed. Check logs for details.")


if __name__ == "__main__":
    asyncio.run(main())