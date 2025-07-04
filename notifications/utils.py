import json
import requests
from django.conf import settings
from .models import Notification

# Try to import Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    FIREBASE_ADMIN_AVAILABLE = True
except ImportError:
    FIREBASE_ADMIN_AVAILABLE = False
    print("Firebase Admin SDK not installed. Install with: pip install firebase-admin")

def send_notification(user, message, title="Notification", data=None, send_push=True):
    """
    Send both in-app and push notifications
    
    Args:
        user: User instance
        message: Notification message
        title: Notification title (default: "Notification")
        data: Additional data payload (optional)
        send_push: Whether to send push notification (default: True)
    """
    # Create in-app notification (existing functionality)
    notification = Notification.objects.create(user=user, message=message)
    
    # Send push notification if enabled and user has FCM token
    if send_push and user.fcm_token:
        send_push_notification(
            fcm_token=user.fcm_token,
            title=title,
            message=message,
            data=data
        )
    
    return notification

def initialize_firebase():
    """
    Initialize Firebase Admin SDK
    """
    if not FIREBASE_ADMIN_AVAILABLE:
        return False
        
    if not firebase_admin._apps:
        try:
            # Initialize Firebase Admin SDK
            if hasattr(settings, 'FIREBASE_SERVICE_ACCOUNT_KEY_PATH'):
                cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH)
            else:
                # Use default credentials (if running on Google Cloud)
                cred = credentials.ApplicationDefault()
            
            firebase_admin.initialize_app(cred)
            return True
        except Exception as e:
            print(f"Error initializing Firebase: {e}")
            return False
    return True

def send_push_notification(fcm_token, title, message, data=None):
    """
    Send push notification using Firebase Admin SDK (recommended)
    Falls back to HTTP v1 API if Admin SDK not available
    """
    
    # Try Firebase Admin SDK first (recommended approach)
    if FIREBASE_ADMIN_AVAILABLE and initialize_firebase():
        try:
            # Create message
            notification = messaging.Notification(
                title=title,
                body=message
            )
            
            # Android specific config
            android_config = messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default'
                )
            )
            
            # iOS specific config  
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        badge=1
                    )
                )
            )
            
            # Create message
            msg = messaging.Message(
                notification=notification,
                token=fcm_token,
                data=data or {},
                android=android_config,
                apns=apns_config
            )
            
            # Send message
            response = messaging.send(msg)
            print(f"Push notification sent successfully (Admin SDK): {response}")
            return True
            
        except Exception as e:
            print(f"Error sending push notification (Admin SDK): {e}")
            # Fall back to HTTP v1 API
            return send_push_notification_http_v1(fcm_token, title, message, data)
    
    # Fallback to HTTP v1 API
    return send_push_notification_http_v1(fcm_token, title, message, data)

def get_access_token():
    """
    Get OAuth2 access token for Firebase FCM v1 API
    """
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        
        # Load service account credentials
        credentials = service_account.Credentials.from_service_account_file(
            settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH,
            scopes=['https://www.googleapis.com/auth/firebase.messaging']
        )
        
        # Get access token
        auth_req = Request()
        credentials.refresh(auth_req)
        return credentials.token
        
    except Exception as e:
        print(f"Error getting access token: {e}")
        return None

def send_push_notification_http_v1(fcm_token, title, message, data=None):
    """
    Send push notification using HTTP v1 API (fallback method)
    """
    
    # Check if we have the required settings for HTTP v1
    if not (hasattr(settings, 'FIREBASE_SERVICE_ACCOUNT_KEY_PATH') and 
            hasattr(settings, 'FIREBASE_PROJECT_ID')):
        print("Firebase HTTP v1 API requires FIREBASE_SERVICE_ACCOUNT_KEY_PATH and FIREBASE_PROJECT_ID settings")
        return False
    
    access_token = get_access_token()
    
    if not access_token:
        print("Could not get access token for Firebase HTTP v1 API")
        return False
    
    url = f"https://fcm.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/messages:send"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "message": {
            "token": fcm_token,
            "notification": {
                "title": title,
                "body": message
            },
            "android": {
                "priority": "high",
                "notification": {
                    "sound": "default"
                }
            },
            "apns": {
                "payload": {
                    "aps": {
                        "sound": "default",
                        "badge": 1
                    }
                }
            }
        }
    }
    
    if data:
        payload["message"]["data"] = data
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        result = response.json()
        print(f"Push notification sent successfully (HTTP v1): {result}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"Error sending push notification (HTTP v1): {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return False

def send_bulk_push_notification(fcm_tokens, title, message, data=None):
    """
    Send push notification to multiple users
    
    Args:
        fcm_tokens: List of FCM registration tokens
        title: Notification title
        message: Notification message
        data: Additional data payload (optional)
    """
    
    url = "https://fcm.googleapis.com/fcm/send"
    
    headers = {
        "Authorization": f"key={settings.FIREBASE_SERVER_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "registration_ids": fcm_tokens,
        "notification": {
            "title": title,
            "body": message,
            "sound": "default",
            "badge": 1
        },
        "priority": "high"
    }
    
    if data:
        payload["data"] = data
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        result = response.json()
        print(f"Bulk notification result: {result}")
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"Error sending bulk push notification: {e}")
        return None

def send_topic_notification(topic, title, message, data=None):
    """
    Send push notification to a topic
    
    Args:
        topic: Firebase topic name
        title: Notification title
        message: Notification message
        data: Additional data payload (optional)
    """
    
    url = "https://fcm.googleapis.com/fcm/send"
    
    headers = {
        "Authorization": f"key={settings.FIREBASE_SERVER_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "to": f"/topics/{topic}",
        "notification": {
            "title": title,
            "body": message,
            "sound": "default",
            "badge": 1
        },
        "priority": "high"
    }
    
    if data:
        payload["data"] = data
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        result = response.json()
        print(f"Topic notification result: {result}")
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"Error sending topic notification: {e}")
        return None