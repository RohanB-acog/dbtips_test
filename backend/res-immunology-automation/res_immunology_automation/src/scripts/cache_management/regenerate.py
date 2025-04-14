"""
Module for regenerating cache data using the build_dossier run_endpoints function.
"""

import asyncio
import sys
import os
from sqlalchemy import select, update
from datetime import datetime
from .utils import (
    setup_logging,
    check_environment_variables,
    BASE_DIR
)

# Import database models and functions
sys.path.append(BASE_DIR)
from build_dossier import SessionLocal, DiseasesDossierStatus, run_endpoints, get_db
from graphrag_service import get_redis


async def verify_redis_connection():
    """Verify Redis connection is working."""
    logger = setup_logging("verify_redis")
    
    try:
        redis = get_redis()
        # Perform a simple ping operation to verify connection
        ping_result = redis.ping()
        if ping_result:
            logger.info("Redis connection verified successfully")
            return True
        else:
            logger.error("Redis connection check failed")
            return False
    except Exception as e:
        logger.error(f"Error verifying Redis connection: {str(e)}")
        return False


async def regenerate_single_disease(disease_id):
    """Regenerate cache data for a single disease."""
    logger = setup_logging("regenerate_single")
    logger.info(f"Starting regeneration for disease: {disease_id}")
    
    try:
        # Update status to regeneration
        async with SessionLocal() as db:
            update_stmt = (
                update(DiseasesDossierStatus)
                .where(DiseasesDossierStatus.id == disease_id)
                .values(status="regeneration")
            )
            await db.execute(update_stmt)
            await db.commit()
            logger.info(f"Updated disease {disease_id} status to 'regeneration'")
        
        # Run endpoints for this single disease
        single_disease_list = [disease_id]
        status = await run_endpoints(single_disease_list)
        
        # Update status after regeneration
        async with SessionLocal() as db:
            current_time = datetime.utcnow()
            if status and status != "error":
                final_status = "processed"
                update_stmt = (
                    update(DiseasesDossierStatus)
                    .where(DiseasesDossierStatus.id == disease_id)
                    .values(status=final_status, processed_time=current_time)
                )
                await db.execute(update_stmt)
                await db.commit()
                logger.info(f"Disease {disease_id} regeneration completed successfully. Status set to 'processed'")
                return True
            else:
                update_stmt = (
                    update(DiseasesDossierStatus)
                    .where(DiseasesDossierStatus.id == disease_id)
                    .values(status="error")
                )
                await db.execute(update_stmt)
                await db.commit()
                logger.error(f"Disease {disease_id} regeneration failed. Status set to 'error'")
                return False
            
    except Exception as e:
        logger.error(f"Error regenerating disease {disease_id}: {str(e)}")
        
        # Set status to error if regeneration fails
        try:
            async with SessionLocal() as db:
                update_stmt = (
                    update(DiseasesDossierStatus)
                    .where(DiseasesDossierStatus.id == disease_id)
                    .values(status="error")
                )
                await db.execute(update_stmt)
                await db.commit()
                logger.info(f"Set disease {disease_id} status to 'error' after failure")
        except Exception as restore_error:
            logger.error(f"Error restoring disease status: {str(restore_error)}")
        
        return False


async def regenerate_cache():
    """Regenerate cache sequentially for diseases with 'processed' status."""
    logger = setup_logging("regenerate_cache")
    logger.info("Starting sequential cache regeneration...")
    
    # Check environment variables
    missing_vars = check_environment_variables()
    if missing_vars:
        logger.error(f"Missing environment variables: {missing_vars}")
        return False
    
    # Verify Redis connection
    redis_check = await verify_redis_connection()
    if not redis_check:
        logger.error("Redis connection verification failed. Cannot proceed with regeneration.")
        return False
    
    try:
        # Get all diseases with 'processed' status
        async with SessionLocal() as db:
            logger.info("Database connection established successfully.")
            
            # Only select diseases with 'processed' status
            result = await db.execute(
                select(DiseasesDossierStatus).where(DiseasesDossierStatus.status == "processed")
            )
            disease_records = result.scalars().all()
            disease_ids = [record.id for record in disease_records]
            
        if not disease_ids:
            logger.error("No diseases with 'processed' status found in database.")
            return False
        
        logger.info(f"Found {len(disease_ids)} diseases with 'processed' status to regenerate cache for: {disease_ids}")
        logger.info(f"Will process diseases sequentially in this order: {disease_ids}")
        
        # Process diseases one at a time
        overall_success = True
        for disease_id in disease_ids:
            logger.info(f"Processing disease {disease_id}...")
            success = await regenerate_single_disease(disease_id)
            if not success:
                logger.warning(f"Failed to regenerate disease {disease_id}")
                overall_success = False
            # Small delay between processing diseases to avoid overloading system
            await asyncio.sleep(2)
        
        if overall_success:
            logger.info("All diseases processed successfully.")
        else:
            logger.warning("Some diseases failed to regenerate. Check logs for details.")
            
        return overall_success
            
    except Exception as e:
        logger.error(f"Error during sequential regeneration: {str(e)}")
        return False


async def verify_regenerated_files():
    """Verify that regenerated JSON files exist and are not empty."""
    from .utils import DISEASE_CACHE_DIR
    
    logger = setup_logging("verify_regeneration")
    
    if not os.path.exists(DISEASE_CACHE_DIR):
        logger.error(f"Disease cache directory {DISEASE_CACHE_DIR} not found.")
        return False
    
    json_files = [f for f in os.listdir(DISEASE_CACHE_DIR) if f.endswith('.json')]
    if not json_files:
        logger.warning("No JSON files found after regeneration.")
        return False
    
    empty_files = []
    for json_file in json_files:
        file_path = os.path.join(DISEASE_CACHE_DIR, json_file)
        if os.path.getsize(file_path) == 0:
            empty_files.append(json_file)
            logger.warning(f"JSON file {json_file} is empty after regeneration.")
    
    if empty_files:
        logger.warning(f"Found {len(empty_files)} empty JSON files after regeneration.")
        return False
    
    logger.info(f"Successfully verified {len(json_files)} regenerated JSON files.")
    return True


async def main():
    """Main entry point for regenerate module."""
    result = await regenerate_cache()
    if result:
        verification = await verify_regenerated_files()
        if verification:
            print("Cache regeneration and verification completed successfully.")
        else:
            print("Cache regeneration completed, but verification detected issues. Check logs for details.")
    else:
        print("Cache regeneration failed. Check logs for details.")


if __name__ == "__main__":
    asyncio.run(main())