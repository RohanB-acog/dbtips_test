"""
Module for regenerating cache data using the build_dossier run_endpoints function.
"""

import asyncio
import sys
import os
from sqlalchemy import select, update
from .utils import (
    setup_logging,
    check_environment_variables,
    BASE_DIR
)

# Import database models and functions
sys.path.append(BASE_DIR)
from build_dossier import SessionLocal, DiseasesDossierStatus, run_endpoints, get_db


async def regenerate_cache():
    """Regenerate cache for all diseases by running endpoints."""
    logger = setup_logging("regenerate_cache")
    logger.info("Starting cache regeneration...")
    
    # Check environment variables
    missing_vars = check_environment_variables()
    if missing_vars:
        logger.error(f"Missing environment variables: {missing_vars}")
        return False
    
    disease_ids = []
    try:
        async with SessionLocal() as db:
            logger.info("Database connection established successfully.")
            result = await db.execute(select(DiseasesDossierStatus))
            disease_records = result.scalars().all()
            disease_ids = [record.id for record in disease_records]
            
            if not disease_ids:
                logger.error("No diseases found in database.")
                return False
            
            logger.info(f"Found {len(disease_ids)} diseases to regenerate cache for: {disease_ids}")
            
            # Update status to submitted for all diseases
            for disease_id in disease_ids:
                update_stmt = (
                    update(DiseasesDossierStatus)
                    .where(DiseasesDossierStatus.id == disease_id)
                    .values(status="submitted")
                )
                await db.execute(update_stmt)
            await db.commit()
            logger.info("Updated disease statuses to 'submitted'.")
            
            # Run endpoints for all diseases
            logger.info("Running endpoints for all diseases...")
            # Use get_db from build_dossier to ensure the correct database session is used
            status = await run_endpoints(disease_ids)
            
            # Update status after regeneration
            final_status = status if status else "error"
            for disease_id in disease_ids:
                update_stmt = (
                    update(DiseasesDossierStatus)
                    .where(DiseasesDossierStatus.id == disease_id)
                    .values(status=final_status)
                )
                await db.execute(update_stmt)
            await db.commit()
            
            logger.info(f"Cache regeneration completed with status: {final_status}")
            return final_status == "processed"
            
    except Exception as e:
        logger.error(f"Error regenerating cache: {str(e)}")
        
        # Set status to error if regeneration fails
        try:
            async with SessionLocal() as db:
                for disease_id in disease_ids:
                    update_stmt = (
                        update(DiseasesDossierStatus)
                        .where(DiseasesDossierStatus.id == disease_id)
                        .values(status="error")
                    )
                    await db.execute(update_stmt)
                await db.commit()
                logger.info("Set disease statuses to 'error' after failure.")
        except Exception as restore_error:
            logger.error(f"Error restoring disease statuses: {str(restore_error)}")
        
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