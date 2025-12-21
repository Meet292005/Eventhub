import requests
from django.conf import settings
import requests

def send_test_sms(phone_number, message):
    url = "https://www.fast2sms.com/dev/bulkV2"

    payload = {
        'sender_id': 'FSTSMS',
        'message': message,
        'language': 'english',
        'route': 'q',  # 'q' is promotional (no DLT needed)
        'numbers': phone_number,
    }

    headers = {
        'authorization': settings.FAST2SMS_API_KEY,
        'Content-Type': "application/x-www-form-urlencoded",
        'Cache-Control': "no-cache"
    }
    response = requests.post(url, data=payload, headers=headers)
    print("Fast2SMS raw response:", response.text)  #

    print(f"Sending SMS to {phone_number}: {message}")

    response = requests.post(url, data=payload, headers=headers)
    return response.json() # ✅ correct
