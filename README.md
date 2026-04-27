## **Challenge1 : Idempotency-Gateway**
Idempotency, in simple terms, means that repeating the same action multiple times still produces the same result as doing it once, and I applied this idea to solve the real problem of double charging in payment systems, which often happens when a request times out and gets retried. To fix this, I built an Idempotency Gateway using FastAPI in Python that ensures every payment request is treated as a single unique transaction by using an Idempotency-Key as a fingerprint for each request. When a request comes in, the system checks the key: if it’s new, it processes and stores the result; if it’s repeated with the same data, it simply returns the stored response instead of reprocessing; and if the same key is used with different data, it rejects it to prevent errors or misuse. I also added hashing of key fields like amount and currency to better identify identical transactions, plus locking and threading to safely handle simultaneous duplicate requests so only one is processed while others wait for the same result. Finally, I included a TTL mechanism that automatically clears old keys after 24 hours to keep the system efficient, making the whole gateway act as a reliable
### control layer that guarantees each payment is executed exactly once, even under retries or heavy traffic
<img alt="figure1" height="600" src="https://github.com/user-attachments/assets/14b5a672-1f34-4ccd-babd-979e786e3e53" width="800"/>
### **User Story 1  First Transaction (Happy Path)**
The first thing I built is the normal payment flow, where everything works as expected. When a request comes in to */process-payment*, the system first checks if the *Idempotency-Key* is included in the headers. If it’s missing, the request is just rejected immediately because nothing can continue without it.

If the key is there, I treat it as a new transaction. I take the payment details (amount and currency) and also create a hash of the request body so I can later compare requests safely. Then I store this request in memory with a status of “processing,” meaning the system has officially started working on it.

After that, I simulate real payment processing by adding a small 2-second delay. Once that finishes, I return a response like “Charged 100 GHS” and store that response in memory. This is basically the first clean flow  one request goes in, gets processed, and the result is saved for future use if needed.

<img alt="figure2" height="600" src="https://github.com/user-attachments/assets/3d471a0f-d43b-4af5-8ae2-1d946aa5db68" width="800"/>
### **User Story 2  Duplicate Attempt (Idempotency Logic)**
The second part is what makes the system actually useful in real life. This is where retries happen. If a client doesn’t get a response (maybe due to network issues), it can send the same request again using the same *Idempotency-Key*.

When that happens, the system first checks if it has already seen that key before. If it finds it, and the request data is exactly the same (checked using the hash), then I don’t process anything again. I just return the same response I already stored earlier.

So there is no delay, no re-running of payment, nothing happens twice. I also return a header called *X-Cache-Hit: true* so the client can clearly see that this response was reused and not newly processed. This is basically what makes the system safe against duplicate charges.

<img alt="figure3" height="600" src="https://github.com/user-attachments/assets/1e1a120f-c2bb-43bb-bf61-3a58347a71aa" width="800"/>
### **User Story 3  Same Key with Different Data (Safety Check)**
This part is more about protection and correctness. If someone tries to reuse the same *Idempotency-Key* but changes the payment details, that becomes a problem.

So what I do is compare the new request with the original one using the hash I stored earlier. If the data is different, I immediately reject the request with an error (422). The idea is simple: one key should always represent one exact payment, nothing else.

This helps prevent mistakes and also protects the system from someone trying to reuse a key for a different transaction. It keeps the data clean and consistent.

<img alt="figure4" height="600" src="https://github.com/user-attachments/assets/61b387c8-25bc-43bf-82a8-5cf23990f137" width="800"/>
### **Bonus User Story  In-Flight Check (Race Condition Handling)**
This was one of the trickier parts I had to handle. The issue is when two identical requests arrive at almost the same time. For example, Request A comes in and starts processing, but before it finishes (during the 2-second delay), Request B arrives with the same key.

Instead of letting both run or rejecting the second one, I made the second request wait. When the first request starts processing, I mark it as “processing” and create a signal using a threading event.

So when Request B comes in, it sees that the same key is already being processed, and instead of doing anything new, it just waits. Once Request A finishes, it triggers the signal, and Request B simply returns the same result. This way, even if requests hit the system at the exact same time, only one payment is actually processed.

<img alt="figure5" height="600" src="https://github.com/user-attachments/assets/13e4d336-9dd3-4750-b6be-d07053ce0d7a" width="800"/>
### **Developer’s Choice  TTL Cleanup (System Health Feature)**
The extra thing I added is a simple cleanup system using TTL (Time-To-Live). Basically, I didn’t want the system to keep old idempotency keys forever because that would slowly fill up memory and make things messy.

So I set it so that every key expires after 24 hours. Whenever a new request comes in, the system also checks and removes old entries automatically.This keeps the system light and clean over time, and also makes sure old transactions don’t interfere with new ones.

<img alt="figure6" height="600" src="https://github.com/user-attachments/assets/be1724be-09ce-4d3c-8f36-bfc89fa563ec" width="800"/>

**INSTALL DEPENDENCES AND RUN THE PROJECT**

1. **Setup & Installation**
* Clone repository:
* Ensure you have both `main.py` and `requirements.txt` in the same directory
* pip install -r requirements.txt
2. **Run the project**
* uvicorn main:app --reload
3. **Access the application**
* API endpoint: <http://localhost:8000>
* Interactive documentation: <http://localhost:8000/docs>  (FastAPI Swagger UI)
## **API Reference**
### **POST /process-payment**
This endpoint is used to process a payment request.\
To ensure that duplicate requests don’t result in multiple charges, you must include an idempotency key in the request header.

**Required Header:**

Idempotency-Key: <any string unique>
## **How the API Responds**
Below are the different scenarios you might encounter when using this endpoint:
### **1. First Request**
* **Status:** 201 Created
* **Response:**

{

"status": "success",

"message": "Charged 1000.0 GHS"

}

When a request is sent for the first time with a new idempotency key, the payment is processed successfully. <img alt="201" height="1079" src="https://github.com/user-attachments/assets/9320d77c-8ff7-4e18-80fc-e1db4bd5653b" width="1919"/>
### **2. Duplicate Request (Same Key + Same Body)**
* **Status:** 201 Created
* **Response:**

{

"status": "success",

"message": "Charged 1000.0 GHS"

}

If the same request is sent again with the same idempotency key and identical data, the system does not process it again. Instead, it returns the original response.

<img alt="201" height="1079" src="https://github.com/user-attachments/assets/509c35bb-b08e-40d6-8bc7-be7cf0fbb364" width="1919"/>
### **3. In-Flight Duplicate Request**
* **Status:** 201 Created
* **Response:** Same as above (after a short wait)

If a duplicate request arrives while the first one is still being processed, the system waits for the original request to finish and then returns the same result.
### **4. Same Key, Different Request Body**
* **Status:** 422 Unprocessable Entity
* **Response:**

{

"detail": "This key was already used with a different request body."

}

An idempotency key can only be used with one specific request. If you reuse it with different data, the request is rejected.

<img alt="morethan\_one" height="1079" src="https://github.com/user-attachments/assets/633565b8-0301-4d51-91fb-523a5ef1ee79" width="1919"/>
### **5. Missing Idempotency Key**
* **Status:** 400 Bad Request
* **Response:**

{

"detail": "Idempotency-Key header is required."

}

If the idempotency key is not provided, the request will not be processed.

<img alt="400" height="1079" src="https://github.com/user-attachments/assets/7959a5e3-8a9b-4c28-b24b-10dfb3f364ee" width="1919"/>
### **6. Invalid Currency**
* **Status:** 422 Unprocessable Entity
* **Response:**

{

"detail": [

{

     "type": "value\_error",

     "loc": \["body", "currency"\],

     "msg": "Currency must be one of: GHS, RWF",

     "input": "USD"
}

]

}

The API only accepts specific currencies. Any unsupported currency will result in a validation error.

<img alt="422\_invalid\_currency" height="1079" src="https://github.com/user-attachments/assets/9f4809c8-7bdd-48ca-8487-2b84e3a74695" width="1919"/>
### **7. Invalid Amount (≤ 0)**
* **Status:** 422 Unprocessable Entity
* **Response:**

{

"detail": [

{

     "type": "greater\_than",

     "loc": \["body", "amount"\],

     "msg": "Input should be greater than 0",

     "input": 0
}

]

}

The payment amount must be greater than zero. Zero or negative values are rejected. <img alt="422" height="1079" src="https://github.com/user-attachments/assets/c3ecbcd6-d9fc-4e0e-b8c8-a0f16a4e0656" width="1919"/>









# **Challenge2 : Pulse-Check Device Heartbeat Monitor**
A lightweight REST API that monitors remote devices by tracking heartbeat signals. If a device stops sending signals within its defined timeout window, the system automatically flags it as down.
## Tech Stack
- Python 3
- Flask 3.0
- APScheduler 3.10
## Getting Started
~~~ bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py
~~~

The server starts on `http://localhost:5000` by default.
## API Endpoints

|Method|Endpoint|Description|
| :-: | :-: | :-: |
|`GET`|`/health`|Check if the server is running|
|`POST`|`/monitors`|Register a new device monitor|
|`POST`|`/monitors/{id}/heartbeat`|Send a heartbeat for a device|
|`POST`|`/monitors/{id}/pause`|Pause monitoring for a device|
|`DELETE`|`/monitors/{id}`|Remove a monitor|
|`GET`|`/monitors`|List all monitors|
|`GET`|`/monitors/{id}`|Get a specific monitor|
|`GET`|`/monitors/{id}/heartbeat-history`|View heartbeat history for a device|

To run all this it's better to have **postman** to keep it easer

GET /health : <img alt="200\_ok" height="1075" src="https://github.com/user-attachments/assets/d23cf9fd-ae5e-4204-95f2-84c9e020e695" width="1917"/>

REGISTER and GET : <img alt="registered" height="1079" src="https://github.com/user-attachments/assets/181e0052-9839-4979-8ad5-45cbbf218197" width="1919"/>

GET with ID specified : <img alt="GET-idspecified" height="1049" src="https://github.com/user-attachments/assets/e28b7135-a46a-4e0e-890a-8ffb2748072d" width="964"/>

DELETE : <img alt="delete" height="1030" src="https://github.com/user-attachments/assets/702abad3-6af3-4443-9a74-fc183f85efcf" width="727"/>
### Register a monitor
~~~ json
POST /monitors
{
  "id": "device-123",
  "timeout": 30,
  "alert_email": "email@example.com"
}
~~~

-----
## How It Works
### User Story 1: Registering a Monitor
Devices are registered via `POST /monitors` with a device ID, timeout (in seconds), and an alert email. The system validates the input, stores the monitor, and immediately starts a background timer. If no heartbeat arrives before the timer runs out, the device gets marked as down.

<img alt="f1" height="600" src="https://github.com/user-attachments/assets/3fda6169-ba26-459b-8b77-bfefcc7820ce" width="800"/>

-----
### User Story 2: Heartbeat (Timer Reset)
Devices send a heartbeat via `POST /monitors/{id}/heartbeat`. Each heartbeat resets the timer back to the full timeout and logs the timestamp. The response confirms the reset and shows how many seconds remain until the next expected heartbeat.

<img alt="f2" height="600" src="https://github.com/user-attachments/assets/959d19b5-faa7-41b1-b817-cf889185b0eb" width="800"/>

-----
### User Story 3: Alert on Failure
If the timer expires without receiving a heartbeat, the device status changes to `"down"` and an alert is logged:
~~~ json
{ "ALERT": "Device device-123 is down!", "time": 1234567890.0 }
~~~

In a real deployment, this would connect to an email service or external monitoring dashboard.

<img alt="f3" height="600" src="https://github.com/user-attachments/assets/a8606100-5aa0-43ac-8bd2-9dc5618f458b" width="800"/>

-----
### Bonus: Pause / Snooze
`POST /monitors/{id}/pause` puts a device in maintenance mode — the timer stops and no alerts fire. When a heartbeat comes in after a pause, the device automatically resumes active monitoring and the timer restarts.

<img alt="f4" height="600" src="https://github.com/user-attachments/assets/a8606100-5aa0-43ac-8bd2-9dc5618f458b" width="800"/>

-----
### Extra Feature: Heartbeat History
Every heartbeat timestamp is stored per device, capped at the 50 most recent entries. This makes it easier to see how often a device has been communicating and spot any gaps in activity.

<img alt="f5" height="600" src="https://github.com/user-attachments/assets/cb0a4d91-44c2-4944-90f4-5928f29ee6ea" width="800"/>
