"""
Module for regenerating cache data using the build_dossier run_endpoints function.
"""

import asyncio
import sys
import os
from sqlalchemy import select, update
from datetime import datetime, timedelta
from .utils import (
    setup_logging,
    check_environment_variables,
    BASE_DIR,
    DISEASE_CACHE_DIR
)
import tzlocal

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


async def update_status_to_processing(disease_id):
    """Update disease status from 'regeneration' to 'processing'."""
    logger = setup_logging("update_status")
    
    try:
        async with SessionLocal() as db:
            logger.info(f"Updating status for disease {disease_id} from 'regeneration' to 'processing'")
            update_stmt = (
                update(DiseasesDossierStatus)
                .where(DiseasesDossierStatus.id == disease_id)
                .values(status="processing")
            )
            await db.execute(update_stmt)
            await db.commit()
            logger.info(f"Successfully updated disease {disease_id} status to 'processing'")
            return True
    except Exception as e:
        logger.error(f"Error updating disease {disease_id} status to 'processing': {str(e)}")
        return False


async def verify_json_file_content(disease_id):
    """Verify the JSON file is not empty after regeneration."""
    logger = setup_logging("verify_json")
    
    file_path = os.path.join(DISEASE_CACHE_DIR, f"{disease_id}.json")
    if not os.path.exists(file_path):
        logger.error(f"JSON file for disease {disease_id} does not exist after regeneration.")
        return False
    
    if os.path.getsize(file_path) == 0:
        logger.error(f"JSON file for disease {disease_id} is empty after regeneration.")
        return False
    
    # Check if the file contains valid JSON and is not just '{}'
    try:
        import json
        with open(file_path, 'r') as f:
            content = json.load(f)
            if not content:
                logger.error(f"JSON file for disease {disease_id} contains empty object.")
                return False
    except json.JSONDecodeError:
        logger.error(f"JSON file for disease {disease_id} contains invalid JSON.")
        return False
    except Exception as e:
        logger.error(f"Error checking JSON content for disease {disease_id}: {str(e)}")
        return False
    
    logger.info(f"Successfully verified JSON content for disease {disease_id}.")
    return True


async def regenerate_single_disease(disease_id):
    """Regenerate cache data for a single disease."""
    logger = setup_logging("regenerate_single")
    logger.info(f"Starting regeneration for disease: {disease_id}")
    
    try:
        # First update status from "regeneration" to "processing"
        status_update = await update_status_to_processing(disease_id)
        if not status_update:
            logger.warning(f"Failed to update status to 'processing' for disease {disease_id}, but continuing with regeneration")
        
        # Run endpoints for this single disease
        single_disease_list = [disease_id]
        status = await run_endpoints(single_disease_list)
        
        # Verify that the generated JSON file is not empty
        json_valid = await verify_json_file_content(disease_id)
        
        # Update status after regeneration
        async with SessionLocal() as db:
            current_time = datetime.now(tzlocal.get_localzone())
            if status and status != "error" and json_valid:
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
                if not json_valid:
                    logger.error(f"Disease {disease_id} regeneration produced empty or invalid JSON. Status set to 'error'")
                else:
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
    """Regenerate cache sequentially for diseases with 'regeneration' status."""
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
        # Get all diseases with 'regeneration' status
        async with SessionLocal() as db:
            logger.info("Database connection established successfully.")
            
            # Select diseases with 'regeneration' status
            result = await db.execute(
                select(DiseasesDossierStatus).where(DiseasesDossierStatus.status == "regeneration")
            )
            disease_records = result.scalars().all()
            disease_ids = [record.id for record in disease_records]
            
        if not disease_ids:
            logger.error("No diseases with 'regeneration' status found in database.")
            return False
        
        logger.info(f"Found {len(disease_ids)} diseases with 'regeneration' status to regenerate cache for: {disease_ids}")
        logger.info(f"Will process diseases sequentially in this order: {disease_ids}")
        
        # Process diseases one at a time
        overall_success = True
        failed_diseases = []
        
        for disease_id in disease_ids:
            logger.info(f"Processing disease {disease_id}...")
            success = await regenerate_single_disease(disease_id)
            if not success:
                logger.warning(f"Failed to regenerate disease: {disease_id}")
                failed_diseases.append(disease_id)
                overall_success = False
                    
            # Small delay between processing diseases to avoid overloading system
            await asyncio.sleep(2)
        
        if overall_success:
            logger.info("All diseases processed successfully.")
        else:
            logger.warning(f"The following diseases failed to regenerate: {', '.join(failed_diseases)}")
            
        return overall_success
            
    except Exception as e:
        logger.error(f"Error during sequential regeneration: {str(e)}")
        return False


async def verify_regenerated_files():
    """Verify that regenerated JSON files exist and are not empty."""
    logger = setup_logging("verify_regeneration")
    
    if not os.path.exists(DISEASE_CACHE_DIR):
        logger.error(f"Disease cache directory {DISEASE_CACHE_DIR} not found.")
        return False
    
    try:
        async with SessionLocal() as db:
            # Select diseases with 'processed' status after regeneration
            result = await db.execute(
                select(DiseasesDossierStatus).where(DiseasesDossierStatus.status == "processed")
            )
            disease_records = result.scalars().all()
            processed_disease_ids = [record.id for record in disease_records]
            
            # Select diseases with 'error' status after regeneration
            result = await db.execute(
                select(DiseasesDossierStatus).where(DiseasesDossierStatus.status == "error")
            )
            error_disease_ids = [record.id for record in disease_records]
            
        logger.info(f"Found {len(processed_disease_ids)} successfully processed diseases")
        logger.info(f"Found {len(error_disease_ids)} diseases with errors")
        
        for disease_id in processed_disease_ids:
            file_path = os.path.join(DISEASE_CACHE_DIR, f"{disease_id}.json")
            if not os.path.exists(file_path):
                logger.warning(f"Disease {disease_id} marked as processed but JSON file not found")
                return False
            if os.path.getsize(file_path) == 0:
                logger.warning(f"Disease {disease_id} marked as processed but JSON file is empty")
                return False
                
        logger.info("Successfully verified regenerated JSON files.")
        return True
            
    except Exception as e:
        logger.error(f"Error verifying regenerated files: {str(e)}")
        return False


async def main():
    """Main entry point for regenerate module."""
    try:
        result = await regenerate_cache()
        if result:
            verification = await verify_regenerated_files()
            if verification:
                print("Cache regeneration and verification completed successfully.")
            else:
                print("Cache regeneration completed, but verification detected issues. Check logs for details.")
        else:
            print("Cache regeneration failed. Check logs for details.")
    except Exception as e:
        logger = setup_logging("main_exception")
        logger.error(f"Unhandled exception in main: {str(e)}")
        print(f"Cache regeneration failed with exception: {str(e)}. Check logs for details.")


if __name__ == "__main__":
    asyncio.run(main())