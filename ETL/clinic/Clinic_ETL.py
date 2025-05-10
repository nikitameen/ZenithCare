import pyodbc
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from tqdm import tqdm
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fetch_sql_data():
    """Fetch data from SQL Server using Windows Authentication"""
    try:
        conn_str = (
            r"Driver={SQL Server};"
            r"Server=Meenketan;"
            r"Database=Zenithcare;"
            r"Trusted_Connection=yes;"
        )
        
        logger.info("Connecting to SQL Server...")
        with pyodbc.connect(conn_str) as conn:
            query = """
            SELECT clinicid, city, county, countydimid, state, lat, lang, zipcode, clinicname 
            FROM dbo.ClinicZipCountyFact
            """
            df = pd.read_sql(query, conn)
            logger.info(f"Successfully fetched {len(df)} records from SQL Server")
            return df
            
    except Exception as e:
        logger.error(f"SQL Server connection failed: {e}")
        raise

def initialize_firebase():
    """Initialize Firebase with hsphere configuration"""
    try:
        # Load credentials from the serviceAccountKey.json file
        cred = credentials.Certificate("serviceAccountKey.json")
        
        # Initialize app with hsphere configuration
        firebase_admin.initialize_app(cred, {
            'projectId': 'hsphere',  # Project ID from the service account
            'databaseAuthVariableOverride': {
                'uid': 'python-migration-script'
            }
        })
        
        # Get Firestore client with explicit database reference
        db = firestore.client()
        
        # Verify connection
        test_ref = db.collection('_connection_test').document('temp')
        test_ref.set({'timestamp': datetime.utcnow()})
        test_ref.delete()
        
        logger.info("Successfully connected to Firestore (hsphere project)")
        return db
        
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        logger.info("\nTROUBLESHOOTING TIPS:")
        logger.info("1. Verify serviceAccountKey.json has Firestore admin privileges")
        logger.info("2. Check Firebase project ID matches your credentials")
        logger.info("3. Ensure the service account has access to Firestore")
        raise

def migrate_to_firestore(db, dataframe, batch_size=500):
    """Migrate data to Firestore with enhanced validation"""
    try:
        total_records = len(dataframe)
        success_count = 0
        batch = db.batch()
        collection_ref = db.collection("clinics")
        
        logger.info(f"Starting migration of {total_records} records to Firestore...")
        
        # Data validation and transformation
        def clean_data(row):
            return {
                'clinicid': str(row['clinicid']),
                'city': str(row['city']) if pd.notna(row['city']) else None,
                'county': str(row['county']) if pd.notna(row['county']) else None,
                'countydimid': int(row['countydimid']) if pd.notna(row['countydimid']) else None,
                'state': str(row['state']) if pd.notna(row['state']) else None,
                'lat': float(row['lat']) if pd.notna(row['lat']) else None,
                'lang': float(row['lang']) if pd.notna(row['lang']) else None,
                'zipcode': str(int(row['zipcode'])) if pd.notna(row['zipcode']) else None,
                'clinicname': str(row['clinicname']) if pd.notna(row['clinicname']) else None,
                'migration_timestamp': firestore.SERVER_TIMESTAMP
            }
        
        # Migration with progress tracking
        with tqdm(total=total_records, desc="Migrating to Firestore") as pbar:
            for _, row in dataframe.iterrows():
                try:
                    data = clean_data(row)
                    doc_ref = collection_ref.document(data['clinicid'])
                    batch.set(doc_ref, data)
                    success_count += 1
                    
                    if success_count % batch_size == 0:
                        batch.commit()
                        batch = db.batch()
                        pbar.update(batch_size)
                        
                except Exception as e:
                    logger.warning(f"Skipped record {row['clinicid']}: {str(e)}")
                    pbar.update(1)
                    continue
        
        # Final commit
        if success_count % batch_size != 0:
            batch.commit()
            pbar.update(success_count % batch_size)
            
        logger.info(f"Migration complete. Success: {success_count}, Failed: {total_records - success_count}")
        return success_count
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

def main():
    try:
        logger.info("🚀 Starting Clinic Data Migration to Firestore 🚀")
        
        # Step 1: Fetch SQL Data
        df = fetch_sql_data()
        
        # Step 2: Initialize Firestore with hsphere config
        db = initialize_firebase()
        
        # Step 3: Execute Migration
        result = migrate_to_firestore(db, df)
        
        logger.info(f"✅ Successfully migrated {result} records to Firestore DB")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Critical failure: {e}")
        return 1

if __name__ == "__main__":
    exit(main())