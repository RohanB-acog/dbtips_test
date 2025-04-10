"""
Module for clearing cache and creating empty JSON files.
"""

import os
import asyncio
import json
import sys
from sqlalchemy import select
from .utils import (
    setup_logging,
    DISEASE_CACHE_DIR,
    BASE_DIR
)

# Import database models
sys.path.append(BASE_DIR)
from build_dossier import SessionLocal, DiseasesDossierStatus


async def create_empty_disease_files():
    """Create empty JSON files for all diseases in the database."""
    logger = setup_logging("create_empty_files")
    
    # Ensure cache directory exists
    os.makedirs(DISEASE_CACHE_DIR, exist_ok=True)
    
    try:
        async with SessionLocal() as db:
            result = await db.execute(select(DiseasesDossierStatus))
            disease_records = result.scalars().all()
            disease_ids = [record.id for record in disease_records]
            
            if not disease_ids:
                logger.error("No diseases found in database to create empty files for.")
                return False
            
            logger.info(f"Creating empty JSON files for {len(disease_ids)} diseases: {disease_ids}")
            for disease_id in disease_ids:
                file_path = os.path.join(DISEASE_CACHE_DIR, f"{disease_id}.json")
                with open(file_path, 'w') as f:
                    json.dump({}, f)
                logger.info(f"Created empty file: {file_path}")
            
            return True
            
    except Exception as e:
        logger.error(f"Error creating empty files: {str(e)}")
        return False


async def clear_and_create_empty_files():
    """Clear cache directory and create empty JSON files for all diseases."""
    logger = setup_logging("clear_cache")
    logger.info("Starting cache clearing and empty file creation...")
    
    if not os.path.exists(DISEASE_CACHE_DIR):
        logger.error(f"Disease cache directory {DISEASE_CACHE_DIR} not found.")
        os.makedirs(DISEASE_CACHE_DIR, exist_ok=True)
        logger.info(f"Created disease cache directory: {DISEASE_CACHE_DIR}")
    
    try:
        # Remove all JSON files from cache directory
        logger.info("Removing all JSON files from disease cache directory...")
        files_removed = 0
        for filename in os.listdir(DISEASE_CACHE_DIR):
            if filename.endswith('.json'):
                file_path = os.path.join(DISEASE_CACHE_DIR, filename)
                os.remove(file_path)
                files_removed += 1
        
        logger.info(f"Removed {files_removed} JSON files from cache directory.")
        
        # Create empty files for all diseases in database
        result = await create_empty_disease_files()
        if not result:
            logger.error("Failed to create empty disease files.")
            return False
        
        logger.info("Cache clearing and empty file creation completed successfully.")
        return True
        
    except Exception as e:
        logger.error(f"Error during cache clearing: {str(e)}")
        return False


async def main():
    """Main entry point for clear_cache module."""
    result = await clear_and_create_empty_files()
    if result:
        print("Cache clearing and empty file creation completed successfully.")
    else:
        print("Cache clearing and empty file creation failed. Check logs for details.")


if __name__ == "__main__":
    asyncio.run(main())