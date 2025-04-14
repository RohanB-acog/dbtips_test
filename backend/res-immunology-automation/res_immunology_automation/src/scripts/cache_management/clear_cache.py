"""
Module for clearing cache and creating empty JSON files.
"""

import os
import asyncio
import json
import sys
from sqlalchemy import select, update
from .utils import (
    setup_logging,
    DISEASE_CACHE_DIR,
    BASE_DIR
)

# Import database models
sys.path.append(BASE_DIR)
from build_dossier import SessionLocal
from db.models import DiseasesDossierStatus
from graphrag_service import get_redis


async def create_empty_disease_files():
    """Create empty JSON files for all diseases in the database while preserving their status."""
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
            
            # Note: We're not changing any database statuses in this function
            # This preserves the existing statuses (like "processed")
            
            return True
            
    except Exception as e:
        logger.error(f"Error creating empty files: {str(e)}")
        return False


async def clear_redis_cache():
    """Clear all data from Redis cache."""
    logger = setup_logging("clear_redis")
    
    try:
        # Get Redis connection
        redis = get_redis()
        logger.info("Connected to Redis successfully")
        
        # Flush all data from Redis - using non-async call
        redis.flushall()
        logger.info("Successfully cleared all data from Redis cache")
        return True
        
    except Exception as e:
        logger.error(f"Error clearing Redis cache: {str(e)}")
        return False


async def clear_and_create_empty_files():
    """Clear cache directory, Redis cache, and create empty JSON files for all diseases while preserving statuses."""
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
        
        # Clear Redis cache
        logger.info("Clearing Redis cache...")
        redis_result = await clear_redis_cache()
        if not redis_result:
            logger.error("Failed to clear Redis cache.")
            return False
        
        # Create empty files for all diseases in database while preserving statuses
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