import os
import pytest
from app.ingestion.processor import run_universal_ingestion

def test_ingestion_runs_successfully():
    """
    Test that the ingestion pipeline runs on the DATA directory without throwing exceptions.
    Since the user confirmed we can write to Qdrant and wipe it after, we will run it on the 
    local 'DATA' directory.
    """
    # Assuming the DATA directory is in the root of the project
    data_dir = "DATA"
    
    if not os.path.exists(data_dir):
        pytest.skip(f"Data directory '{data_dir}' not found, skipping integration test.")
        
    try:
        # Run universal ingestion with wipe to test the collection recreation as well
        run_universal_ingestion(data_dir, wipe=True)
    except Exception as e:
        pytest.fail(f"Ingestion pipeline failed with exception: {e}")
