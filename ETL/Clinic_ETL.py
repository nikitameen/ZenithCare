import pyodbc
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from tqdm import tqdm  # For progress bar
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_sql_data():
    """Fetch data from SQL Server using Windows Authentication"""
    try:
        # Windows Authentication connection string
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
            logger.info(f"Successfully fetched {len(df)} records")
            return df
            
    except Exception as e:
        logger.error(f"SQL Server connection failed: {e}")
        raise

def initialize_firebase():
    """Initialize Firebase Firestore"""
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        raise

def migrate_to_firestore(db, dataframe, batch_size=400):
    """Migrate data to Firestore with batch processing"""
    try:
        total_records = len(dataframe)
        success_count = 0
        batch = db.batch()
        collection_ref = db.collection("clinics")
        
        logger.info(f"Starting migration of {total_records} records...")
        
        for idx, row in tqdm(dataframe.iterrows(), total=total_records):
            try:
                doc_ref = collection_ref.document(str(row["clinicid"]))
                batch.set(doc_ref, {
                    "city": row["city"] if pd.notna(row["city"]) else None,
                    "county": row["county"] if pd.notna(row["county"]) else None,
                    "countydimid": int(row["countydimid"]) if pd.notna(row["countydimid"]) else None,
                    "state": row["state"] if pd.notna(row["state"]) else None,
                    "lat": float(row["lat"]) if pd.notna(row["lat"]) else None,
                    "lang": float(row["lang"]) if pd.notna(row["lang"]) else None,
                    "zipcode": str(row["zipcode"]) if pd.notna(row["zipcode"]) else None,
                    "clinicname": row["clinicname"] if pd.notna(row["clinicname"]) else None
                })
                success_count += 1
                
                # Commit batch when reaching batch size
                if success_count % batch_size == 0:
                    batch.commit()
                    batch = db.batch()
                    
            except Exception as e:
                logger.warning(f"Error processing record {row['clinicid']}: {e}")
        
        # Commit any remaining documents
        if success_count % batch_size != 0:
            batch.commit()
            
        logger.info(f"Migration complete. Successfully migrated {success_count}/{total_records} records")
        return success_count
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

def main():
    try:
        # Step 1: Fetch data from SQL Server
        df = fetch_sql_data()
        
        # Step 2: Initialize Firebase
        db = initialize_firebase()
        
        # Step 3: Migrate data
        migrate_to_firestore(db, df)
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())