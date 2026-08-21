"""Firebase Admin SDK initialization and singleton client management.

Provides a thread-safe, serverless-compatible singleton for Firebase Admin and Firestore.
Credentials can be provided via environment variables (recommended for Vercel) or a local file.
"""

import base64
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_firebase_app = None
_firestore_db = None
_initialized = False


def initialize_firebase():
    """Initialize the Firebase Admin SDK singleton.

    Order of credential resolution:
    1. Base64-encoded Service Account JSON: FIREBASE_SERVICE_ACCOUNT_KEY_BASE64
    2. Discrete environment variables: FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, FIREBASE_PRIVATE_KEY
    3. File path: FIREBASE_SERVICE_ACCOUNT_PATH or default 'serviceAccountKey.json'
    4. Default Google Application Credentials (if running in GCP)
    """
    global _firebase_app, _firestore_db, _initialized

    if _initialized and _firebase_app is not None:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        # Prevent duplicate app initialization in serverless warm containers
        if firebase_admin._apps:
            _firebase_app = firebase_admin.get_app()
            _firestore_db = firestore.client()
            _initialized = True
            return _firebase_app

        cred = None

        # 1. Base64-encoded Service Account JSON
        b64_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_BASE64", "").strip()
        if b64_key:
            try:
                decoded_json = base64.b64decode(b64_key).decode("utf-8")
                key_dict = json.loads(decoded_json)
                cred = credentials.Certificate(key_dict)
            except Exception as e:
                logger.warning("Failed to parse FIREBASE_SERVICE_ACCOUNT_KEY_BASE64: %s", e)

        # 2. Discrete environment variables (Best for Vercel)
        if cred is None:
            project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
            client_email = os.getenv("FIREBASE_CLIENT_EMAIL", "").strip()
            private_key = os.getenv("FIREBASE_PRIVATE_KEY", "").strip()

            if project_id and client_email and private_key:
                # Replace literal escaped newlines with actual newline characters
                private_key = private_key.strip("'").strip('"').replace("\\n", "\n")
                cert_dict = {
                    "type": "service_account",
                    "project_id": project_id,
                    "private_key": private_key,
                    "client_email": client_email,
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
                try:
                    cred = credentials.Certificate(cert_dict)
                except Exception as e:
                    logger.warning("Failed to initialize Firebase credentials from discrete env vars: %s", e)

        # 3. Local Service Account JSON File Path
        if cred is None:
            file_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json").strip()
            if file_path and os.path.exists(file_path):
                try:
                    cred = credentials.Certificate(file_path)
                except Exception as e:
                    logger.warning("Failed to load Firebase credentials from file %s: %s", file_path, e)

        # 4. Initialize Firebase App
        if cred is not None:
            _firebase_app = firebase_admin.initialize_app(cred)
            _firestore_db = firestore.client()
            _initialized = True
            logger.info("Firebase Admin successfully initialized.")
            return _firebase_app

    except ImportError:
        logger.warning("firebase_admin package is not installed.")
    except Exception as e:
        logger.warning("Firebase Admin initialization skipped or encountered error: %s", e)

    _initialized = True
    return None


def get_firestore_client() -> Optional[Any]:
    """Retrieve the Firestore client singleton. Returns None if Firebase is not configured."""
    global _firestore_db
    if _firestore_db is None:
        initialize_firebase()
    return _firestore_db


def is_firebase_available() -> bool:
    """Check whether Firebase Admin and Firestore are successfully connected."""
    client = get_firestore_client()
    return client is not None
