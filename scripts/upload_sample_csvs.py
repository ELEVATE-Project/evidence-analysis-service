#!/usr/bin/env python3
"""
Upload Sample CSV Files to Cloud Storage
Uploads project sample CSV files to cloud storage with consistent paths.
"""
import sys
import asyncio
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import SessionLocal
from services.storage_service import StorageService
from models.csv_source_type import CsvSourceType
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SampleCsvUploader:
    """Uploads sample CSV files to cloud storage and updates database."""
    
    def __init__(self):
        self.storage_service = StorageService()
        self.db = SessionLocal()
        self.base_path = Path(__file__).parent.parent / "public" / "sample-csv"
        
    async def upload_file(self, local_file_path: Path, cloud_path: str) -> str:
        """Upload a file to cloud storage."""
        if not local_file_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_file_path}")
        
        logger.info(f"Uploading {local_file_path.name} -> {cloud_path}")
        
        # Read file content
        with open(local_file_path, 'rb') as f:
            file_content = f.read()
        
        # Upload to cloud storage
        result = await self.storage_service.upload_file(
            file_content=file_content,
            file_path=cloud_path,
            content_type='text/csv'
        )
        
        logger.info(f"✓ Uploaded successfully: {cloud_path}")
        return cloud_path
    
    async def upload_project_samples(self) -> dict:
        """Upload project sample CSV files."""
        projects_folder = self.base_path / "projects"
        
        if not projects_folder.exists():
            raise FileNotFoundError(f"Projects folder not found: {projects_folder}")
        
        uploads = {}
        
        # Upload input sample
        input_file = projects_folder / "sample_input.csv"
        input_cloud_path = "projects/sample_input.csv"
        uploads['input'] = await self.upload_file(input_file, input_cloud_path)
        
        # Upload criteria sample
        criteria_file = projects_folder / "sample_criteria.csv"
        criteria_cloud_path = "projects/sample_criteria.csv"
        uploads['criteria'] = await self.upload_file(criteria_file, criteria_cloud_path)
        
        return uploads
    
    def update_database(self, uploads: dict) -> None:
        """Update database with uploaded file paths."""
        logger.info("Updating database with cloud paths...")
        
        try:
            # Update project_report type
            result = self.db.execute(
                text("""
                    UPDATE csv_source_types 
                    SET 
                        sample_input_file_url = :input_url,
                        sample_criteria_file_url = :criteria_url
                    WHERE 
                        type_key = 'project_report' 
                        AND tenant_code = 'default' 
                        AND organization_code = 'default_code'
                """),
                {
                    'input_url': uploads['input'],
                    'criteria_url': uploads['criteria']
                }
            )
            
            self.db.commit()
            logger.info(f"✓ Updated database: {result.rowcount} row(s) affected")
            
            # Verify update
            verification = self.db.execute(
                text("""
                    SELECT id, type_key, sample_input_file_url, sample_criteria_file_url
                    FROM csv_source_types
                    WHERE type_key = 'project_report'
                """)
            ).fetchone()
            
            if verification:
                logger.info(f"\nVerification:")
                logger.info(f"  ID: {verification[0]}, Type: {verification[1]}")
                logger.info(f"  Input URL: {verification[2]}")
                logger.info(f"  Criteria URL: {verification[3]}")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Database update failed: {e}")
            raise
    
    async def verify_access(self, uploads: dict) -> None:
        """Verify uploaded files are accessible via signed URLs."""
        logger.info("\nVerifying file access via signed URLs...")
        
        for file_type, cloud_path in uploads.items():
            try:
                signed_url = await self.storage_service.generate_download_url(
                    file_path=cloud_path,
                    expiration=60,
                    response_filename=f"sample_{file_type}.csv"
                )
                logger.info(f"✓ {file_type.capitalize()}: Accessible (URL expires in {signed_url['expires_in_seconds']}s)")
            except Exception as e:
                logger.error(f"✗ {file_type.capitalize()}: Access failed - {e}")
                raise
    
    async def run(self) -> None:
        """Run the complete upload process."""
        try:
            logger.info("=" * 60)
            logger.info("Sample CSV Upload Script")
            logger.info("=" * 60)
            logger.info(f"Storage Provider: {self.storage_service.storage_provider}")
            logger.info(f"Bucket: {self.storage_service.bucket_name}")
            logger.info("")
            
            # Upload files
            uploads = await self.upload_project_samples()
            
            # Update database
            self.update_database(uploads)
            
            # Verify access
            await self.verify_access(uploads)
            
            logger.info("\n" + "=" * 60)
            logger.info("✓ Sample CSV upload completed successfully!")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"\n✗ Upload failed: {e}")
            raise
        finally:
            self.db.close()


def main():
    """Main entry point."""
    try:
        uploader = SampleCsvUploader()
        asyncio.run(uploader.run())
        return 0
    except Exception as e:
        logger.exception("Upload script failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
