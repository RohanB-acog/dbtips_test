#build_dossier.py
from db.database import get_db # , engine, Base, SessionLocal
from db.models import DiseasesDossierStatus 
from db.database import Base

from api_models import DiseasesRequest, DiseaseRequest
from api import get_evidence_literature_semaphore, get_mouse_studies, \
                get_network_biology_semaphore, get_top_10_literature, \
                get_diseases_profiles, get_indication_pipeline_semaphore, \
                get_kol, get_key_influencers, get_rna_sequence_semaphore, \
                get_disease_ontology
                
import logging
import time
import asyncio
import json
import os
from graphrag_service import get_redis
from fastapi import HTTPException
from sqlalchemy.sql import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import update
import os, sys
import tzlocal
from datetime import datetime, timezone



logging.basicConfig(
    filename="cached_data_json/logs/build_dossier.log",  # Log file location
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

task_started = False
WAIT_TIME = 200

POSTGRES_USER: str = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB: str = os.getenv("POSTGRES_DB")
POSTGRES_HOST: str = os.getenv("POSTGRES_HOST")

if any(var is None for var in [POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST]):
    logging.info("Connection parameters not configured properly")
    sys.exit()

# Define the PostgreSQL database URL using environment variables
SQLALCHEMY_DATABASE_URL: str = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}"

engine = create_async_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession
)

# Cache directory
DISEASE_CACHE_DIR = "cached_data_json/disease"


async def create_models():
    # This will create the tables for all models defined with Base
    # Base.metadata.create_all(bind=engine)
    async with engine.begin() as conn:  # `engine.begin()` ensures the connection is properly initialized
        await conn.run_sync(Base.metadata.create_all)


async def check_empty_json_files(disease_ids):
    """
    Check if JSON files for given disease IDs are empty or nearly empty.
    Returns a list of diseases that need regeneration.
    """
    needs_regeneration = []
    
    for disease_id in disease_ids:
        # Format the filename with underscores instead of spaces
        filename = f"{disease_id.replace(' ', '_')}.json"
        file_path = os.path.join(DISEASE_CACHE_DIR, filename)
        
        # Check if file exists but is empty or nearly empty
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    # Check if the JSON is empty or has minimal content
                    if not data or (isinstance(data, dict) and len(data) <= 2):
                        needs_regeneration.append(disease_id)
                        logging.info(f"File exists but is empty/minimal for disease: {disease_id}")
            except json.JSONDecodeError:
                # Empty or invalid JSON
                needs_regeneration.append(disease_id)
                logging.info(f"Invalid JSON for disease: {disease_id}")
            except Exception as e:
                logging.error(f"Error checking JSON file for {disease_id}: {str(e)}")
                needs_regeneration.append(disease_id)
        else:
            # File doesn't exist
            needs_regeneration.append(disease_id)
            logging.info(f"No cache file exists for disease: {disease_id}")
            
    return needs_regeneration


async def build_dossier():
    print("dossier started")
    global task_started
    if task_started:
        return  # Prevent multiple instances from starting
    task_started = True

    # db = get_db()
    while True:

        async with SessionLocal() as db:
            print("connection created")
            # processing_records = await db.execute(select(DiseasesDossierStatus).filter(DiseasesDossierStatus.status == "processing")).all()
            result = await db.execute(
                select(DiseasesDossierStatus).where(DiseasesDossierStatus.status == "processing")
            )
            processing_records = result.scalars().all()

            processing_records = [record.id for record in processing_records if record]
            logging.info(f"Processing jobs: {processing_records}")
            try:
                if not processing_records:
                    pending_jobs = []
                    result = await db.execute(
                        select(DiseasesDossierStatus).where(
                            DiseasesDossierStatus.status.in_(["error", "submitted"])
                        )
                    )
                    disease_records = result.scalars().all()
                    if disease_records:
                        for disease in disease_records:
                            pending_jobs.append(disease.id)

                    # Also check for diseases with 'processed' status but empty JSON files
                    result = await db.execute(
                        select(DiseasesDossierStatus).where(
                            DiseasesDossierStatus.status == "processed"
                        )
                    )
                    processed_records = result.scalars().all()
                    processed_diseases = [record.id for record in processed_records if record]
                    
                    # Check if any 'processed' diseases have empty JSON files
                    if processed_diseases:
                        needs_regeneration = await check_empty_json_files(processed_diseases)
                        if needs_regeneration:
                            pending_jobs.extend(needs_regeneration)
                            logging.info(f"Adding {len(needs_regeneration)} 'processed' diseases with empty files to pending jobs")

                    print("pending jobs: ", pending_jobs)
                    for disease in pending_jobs:
                        disease_arr = []
                        disease_arr.append(disease)
                        print("processing jobs: ",disease_arr)
                        local_time = datetime.now(tzlocal.get_localzone())

                        #change the status of current building disease to processing and processing_time
                        update_stmt = (
                            update(DiseasesDossierStatus)
                            .where(DiseasesDossierStatus.id == disease)
                            .values(status="processing", submission_time=local_time)
                        )
                        await db.execute(update_stmt) 
                        await db.commit()
                        print("status updated to processing: ", disease_arr)
                        
                        # run all endpoints for the disease
                        build_status = await run_endpoints(disease_arr, force_regenerate=True)
                        
                        # update the status and processed_time according to the build status
                        if build_status != 'error':
                            local_time = datetime.now(tzlocal.get_localzone())

                            update_stmt = (
                                update(DiseasesDossierStatus)
                                .where(DiseasesDossierStatus.id == disease)
                                .values(status=build_status, processed_time=local_time)
                            )
                        else:
                            update_stmt = (
                                update(DiseasesDossierStatus)
                                .where(DiseasesDossierStatus.id == disease)
                                .values(status=build_status)
                            )

                        await db.execute(update_stmt)
                        await db.commit()
                        logging.info(f"updated status: {disease}")

                await asyncio.sleep(WAIT_TIME)
            except Exception as e:
                logging.error(f"Error in build_dossier: {e}")

            finally:
                await db.close()
                print("connection closed")


def check_file_for_disease(disease_id, force_regenerate=False):
    """
    Check if a disease JSON file exists and has valid content.
    Returns True if file should be skipped (valid content exists), False if processing is needed.
    """
    if force_regenerate:
        logging.info(f"Force regeneration enabled for {disease_id}, will process regardless of cache status")
        return False
    
    # Format the filename with underscores instead of spaces
    filename = f"{disease_id.replace(' ', '_')}.json"
    file_path = os.path.join(DISEASE_CACHE_DIR, filename)
    
    if not os.path.exists(file_path):
        logging.info(f"No cache file found for {disease_id}, will process")
        return False
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            # Check if there's meaningful content
            if not data or (isinstance(data, dict) and len(data) <= 2):
                logging.info(f"Cache file for {disease_id} is empty or has minimal content, will process")
                return False
            logging.info(f"Valid cache exists for {disease_id}, using cached content")
            return True
    except json.JSONDecodeError:
        logging.info(f"Invalid JSON in cache file for {disease_id}, will process")
        return False
    except Exception as e:
        logging.error(f"Error checking cache file for {disease_id}: {str(e)}")
        return False


async def run_endpoints(unique_diseases, force_regenerate=False):
    
    try:
        db = next(get_db())
        # async with SessionLocal() as db:
        redis = get_redis()
        print("connection created in end points")

        # Define endpoint categories
        diseases_only_endpoints = [
            get_evidence_literature_semaphore, 
            get_mouse_studies, 
            get_network_biology_semaphore, 
            get_top_10_literature, 
            get_diseases_profiles, 
            get_indication_pipeline_semaphore, 
            get_kol, 
            get_key_influencers, 
            get_rna_sequence_semaphore
        ]

        disease_only_endpoints = [
            get_disease_ontology
        ]

        # Check if all diseases have valid cache content
        all_cached = all(check_file_for_disease(disease, force_regenerate) for disease in unique_diseases)
        
        if not all_cached or force_regenerate:
            # Call diseases-only endpoints
            for endpoint in diseases_only_endpoints:
                try:
                    request_data = DiseasesRequest(diseases=unique_diseases)
                    logging.info(f"Calling {endpoint.__name__} with all diseases: {unique_diseases}")
                    if endpoint.__name__ in ['get_network_biology_semaphore', 'get_indication_pipeline_semaphore']:
                        response = await endpoint(request_data, db=db)
                    elif endpoint.__name__ in ["get_top_10_literature", 'get_key_influencers']:
                        response = await endpoint(request_data)
                    else:
                        response = await endpoint(request_data, redis=redis, db=db)
                    logging.info("Response received")
                    
                except Exception as e:
                    if isinstance(e, HTTPException) and e.status_code == 404 and 'EFO ID not found' in e.detail:
                        continue 
                    logging.error(f"Error calling {endpoint.__name__} for {unique_diseases}: {e}")
                    return 'error'
                await asyncio.sleep(5)

            # Call disease-only endpoints
            for disease in unique_diseases:
                for endpoint in disease_only_endpoints:
                    try:
                        request_data = DiseaseRequest(disease=disease)
                        logging.info(f"Calling {endpoint.__name__} for disease: {disease}")
                        response = await endpoint(request_data, redis=redis, db=db)
                    except Exception as e:
                        logging.error(f"Error calling {endpoint.__name__} for disease {disease}: {e}")
                        return 'error'
            await asyncio.sleep(5)
        else:
            logging.info(f"All diseases {unique_diseases} have valid cache content, skipping API calls")
        
        return 'processed'

    finally:
        db.close()
        print("connection closed in endpoints")


async def main():
    """Main entry point to initialize database and start dossier processing."""
    await create_models()
    await build_dossier()


if __name__ == "__main__":
    # time.sleep(100)
    asyncio.run(main())