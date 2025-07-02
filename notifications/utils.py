import json
import requests
from django.conf import settings
from .models import Notification

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
    if send_push and hasattr(user, 'fcm_token') and user.fcm_token:
        send_push_notification(
            fcm_token=user.fcm_token,
            title=title,
            message=message,
            data=data
        )
    
    return notification

def send_push_notification(fcm_token, title, message, data=None):
    """
    Send push notification using Firebase Cloud Messaging
    
    Args:
        fcm_token: User's FCM registration token
        title: Notification title
        message: Notification message
        data: Additional data payload (optional)
    """
    
    # Firebase FCM endpoint
    url = "https://fcm.googleapis.com/fcm/send"
    
    # Headers
    headers = {
        "Authorization": f"key={settings.FIREBASE_SERVER_KEY}",
        "Content-Type": "application/json"
    }
    
    # Notification payload
    payload = {
        "to": fcm_token,
        "notification": {
            "title": title,
            "body": message,
            "sound": "default",
            "badge": 1
        },
        "priority": "high"
    }
    
    # Add data payload if provided
    if data:
        payload["data"] = data
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        result = response.json()
        if result.get('success') == 1:
            print(f"Push notification sent successfully to {fcm_token[:10]}...")
            return True
        else:
            print(f"Failed to send push notification: {result}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Error sending push notification: {e}")
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