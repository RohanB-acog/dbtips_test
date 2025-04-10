#!/usr/bin/env python3
"""
Cache Management Script

This script manages cache operations for disease data, including:
- Backing up cache and populating database
- Clearing cache and creating empty files
- Regenerating cache data
- Restoring from backup

Usage:
    python cache_management.py [OPTIONS]

Options:
    --backup           Backup cache and populate database
    --clear            Clear cache and create empty files
    --regenerate       Regenerate the cache data
    --restore [TIMESTAMP]  Restore from backup (uses latest if not specified)
    --full             Perform full cycle: backup, clear, regenerate
    --help             Display this help message
"""

import asyncio
import sys
import os

# Add the script directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

# Import cache management modules
from cache_management import (
    backup_and_populate_db,
    clear_and_create_empty_files,
    regenerate_cache,
    restore_from_backup,
    setup_logging,
    create_directories
)

# Import build_dossier modules directly to ensure they're available
try:
    from build_dossier import get_db, run_endpoints, SessionLocal, DiseasesDossierStatus
except ImportError:
    pass  # Will be handled in the modules that need these imports


async def print_usage():
    """Display usage instructions."""
    print(__doc__)


async def perform_full_cycle():
    """Perform a full cache management cycle: backup, clear, regenerate."""
    logger = setup_logging("full_cycle")
    logger.info("Starting full cache management cycle...")
    
    # Step 1: Backup
    logger.info("Step 1: Backing up cache and populating database...")
    backup_result = await backup_and_populate_db()
    if not backup_result:
        logger.error("Backup step failed. Aborting full cycle.")
        return False
    
    # Step 2: Clear and create empty files
    logger.info("Step 2: Clearing cache and creating empty files...")
    clear_result = await clear_and_create_empty_files()
    if not clear_result:
        logger.error("Clear step failed. Aborting full cycle.")
        return False
    
    # Step 3: Regenerate
    logger.info("Step 3: Regenerating cache data...")
    regenerate_result = await regenerate_cache()
    if not regenerate_result:
        logger.error("Regeneration step failed.")
        return False
    
    logger.info("Full cache management cycle completed successfully.")
    return True


async def main():
    """Main entry point for the cache management script."""
    # Create directories
    create_directories()
    
    # Parse command line arguments
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        await print_usage()
        return
    
    option = sys.argv[1]
    
    try:
        if option == "--backup":
            result = await backup_and_populate_db()
            print("Backup " + ("completed successfully." if result else "failed."))
            
        elif option == "--clear":
            result = await clear_and_create_empty_files()
            print("Cache clearing " + ("completed successfully." if result else "failed."))
            
        elif option == "--regenerate":
            result = await regenerate_cache()
            print("Cache regeneration " + ("completed successfully." if result else "failed."))
            
        elif option == "--restore":
            timestamp = sys.argv[2] if len(sys.argv) > 2 else None
            result = await restore_from_backup(timestamp)
            print("Restore " + ("completed successfully." if result else "failed."))
            
        elif option == "--full":
            result = await perform_full_cycle()
            print("Full cycle " + ("completed successfully." if result else "failed."))
            
        else:
            print(f"Error: Invalid option '{option}'.")
            await print_usage()
            
    except Exception as e:
        print(f"Error: {str(e)}")
        logger = setup_logging("error")
        logger.error(f"Unhandled exception: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())