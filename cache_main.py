#!/usr/bin/env python3
"""
Cache Management Script

This script manages cache operations for disease data, including:
- Backing up cache and populating database
- Clearing cache and creating empty files
- Regenerating cache data
- Restoring from backup

Usage:
    python cache_main.py [OPTIONS]

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
import traceback

# Add the script directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

# Import cache management modules
from cache_management.backup import backup_and_populate_db
from cache_management.clear_cache import clear_and_create_empty_files
from cache_management.regenerate import regenerate_cache
from cache_management.restore import restore_from_backup
from cache_management.utils import setup_logging, create_directories


# Import build_dossier modules directly to ensure they're available
try:
    from build_dossier import get_db, run_endpoints, SessionLocal, DiseasesDossierStatus
except ImportError:
    pass  # Will be handled in the modules that need these imports


class CacheManagementError(Exception):
    """Custom exception for cache management operations."""
    pass


async def print_usage():
    """Display usage instructions."""
    print(__doc__)


async def perform_full_cycle():
    """Perform a full cache management cycle: backup, clear, regenerate."""
    logger = setup_logging("full_cycle")
    logger.info("Starting full cache management cycle...")
    
    try:
        # Step 1: Backup
        logger.info("Step 1: Backing up cache and populating database...")
        backup_result = await backup_and_populate_db()
        if not backup_result:
            raise CacheManagementError("Backup step failed")
        
        # Step 2: Clear and create empty files
        logger.info("Step 2: Clearing cache and creating empty files...")
        clear_result = await clear_and_create_empty_files()
        if not clear_result:
            raise CacheManagementError("Clear step failed")
        
        # Step 3: Regenerate
        logger.info("Step 3: Regenerating cache data...")
        regenerate_result = await regenerate_cache()
        if not regenerate_result:
            raise CacheManagementError("Regeneration step failed")
        
        logger.info("Full cache management cycle completed successfully.")
        return True
        
    except CacheManagementError as e:
        logger.error(f"{str(e)}. Aborting full cycle.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in full cycle: {str(e)}")
        logger.error(traceback.format_exc())
        return False


async def execute_operation(operation_name, operation_func, *args):
    """Execute a cache management operation with proper error handling."""
    logger = setup_logging("execute_operation")
    
    try:
        logger.info(f"Starting {operation_name}...")
        result = await operation_func(*args)
        
        if result:
            logger.info(f"{operation_name} completed successfully.")
            print(f"{operation_name} completed successfully.")
        else:
            logger.error(f"{operation_name} failed.")
            print(f"{operation_name} failed. Check logs for details.")
            
        return result
        
    except Exception as e:
        logger.error(f"Exception during {operation_name}: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"{operation_name} failed with exception: {str(e)}. Check logs for details.")
        return False


async def main():
    """Main entry point for the cache management script."""
    try:
        # Create directories
        await create_directories()
        
        # Parse command line arguments
        if len(sys.argv) < 2 or sys.argv[1] == "--help":
            await print_usage()
            return
        
        option = sys.argv[1]
        
        if option == "--backup":
            await execute_operation("Backup", backup_and_populate_db)
                
        elif option == "--clear":
            await execute_operation("Cache clearing", clear_and_create_empty_files)
                
        elif option == "--regenerate":
            await execute_operation("Cache regeneration", regenerate_cache)
                
        elif option == "--restore":
            timestamp = sys.argv[2] if len(sys.argv) > 2 else None
            await execute_operation("Restore", restore_from_backup, timestamp)
                
        elif option == "--full":
            await execute_operation("Full cycle", perform_full_cycle)
                
        else:
            print(f"Error: Invalid option '{option}'.")
            await print_usage()
                
    except Exception as e:
        logger = setup_logging("main_exception")
        logger.error(f"Unhandled exception in main: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())