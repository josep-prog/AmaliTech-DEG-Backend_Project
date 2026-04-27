## **Challenge1 : Idempotency-Gateway**

### Idempotency, in simple terms, means that repeating the same action multiple times still produces the same result as doing it once, and I applied this idea to solve the real problem of double charging in payment systems, which often happens when a request times out and gets retried. To fix this, I built an Idempotency Gateway using FastAPI in Python that ensures every payment request is treated as a single unique transaction by using an Idempotency-Key as a fingerprint for each request. When a request comes in, the system checks the key: if it’s new, it processes and stores the result; if it’s repeated with the same data, it simply returns the stored response instead of reprocessing; and if the same key is used with different data, it rejects it to prevent errors or misuse. I also added hashing of key fields like amount and currency to better identify identical transactions, plus locking and threading to safely handle simultaneous duplicate requests so only one is processed while others wait for the same result. Finally, I included a TTL mechanism that automatically clears old keys after 24 hours to keep the system efficient, making the whole gateway act as a reliable control layer that guarantees each payment is executed exactly once, even under retries or heavy traffic

### **User Story 1  First Transaction (Happy Path)**

The first thing I built is the normal payment flow, where everything works as expected. When a request comes in to */process-payment*, the system first checks if the *Idempotency-Key* is included in the headers. If it’s missing, the request is just rejected immediately because nothing can continue without it.

If the key is there, I treat it as a new transaction. I take the payment details (amount and currency) and also create a hash of the request body so I can later compare requests safely. Then I store this request in memory with a status of “processing,” meaning the system has officially started working on it.

After that, I simulate real payment processing by adding a small 2-second delay. Once that finishes, I return a response like “Charged 100 GHS” and store that response in memory. This is basically the first clean flow  one request goes in, gets processed, and the result is saved for future use if needed.

### **User Story 2  Duplicate Attempt (Idempotency Logic)**

The second part is what makes the system actually useful in real life. This is where retries happen. If a client doesn’t get a response (maybe due to network issues), it can send the same request again using the same *Idempotency-Key*.

When that happens, the system first checks if it has already seen that key before. If it finds it, and the request data is exactly the same (checked using the hash), then I don’t process anything again. I just return the same response I already stored earlier.

So there is no delay, no re-running of payment, nothing happens twice. I also return a header called *X-Cache-Hit: true* so the client can clearly see that this response was reused and not newly processed. This is basically what makes the system safe against duplicate charges.

### **User Story 3  Same Key with Different Data (Safety Check)**

This part is more about protection and correctness. If someone tries to reuse the same *Idempotency-Key* but changes the payment details, that becomes a problem.

So what I do is compare the new request with the original one using the hash I stored earlier. If the data is different, I immediately reject the request with an error (422). The idea is simple: one key should always represent one exact payment, nothing else.

This helps prevent mistakes and also protects the system from someone trying to reuse a key for a different transaction. It keeps the data clean and consistent.

### **Bonus User Story  In-Flight Check (Race Condition Handling)**

This was one of the trickier parts I had to handle. The issue is when two identical requests arrive at almost the same time. For example, Request A comes in and starts processing, but before it finishes (during the 2-second delay), Request B arrives with the same key.

Instead of letting both run or rejecting the second one, I made the second request wait. When the first request starts processing, I mark it as “processing” and create a signal using a threading event.

So when Request B comes in, it sees that the same key is already being processed, and instead of doing anything new, it just waits. Once Request A finishes, it triggers the signal, and Request B simply returns the same result.

This way, even if requests hit the system at the exact same time, only one payment is actually processed.

### **Developer’s Choice  TTL Cleanup (System Health Feature)**

The extra thing I added is a simple cleanup system using TTL (Time-To-Live). Basically, I didn’t want the system to keep old idempotency keys forever because that would slowly fill up memory and make things messy.

So I set it so that every key expires after 24 hours. Whenever a new request comes in, the system also checks and removes old entries automatically.This keeps the system light and clean over time, and also makes sure old transactions don’t interfere with new ones.

**INSTALL DEPENDENCES AND RUN THE PROJECT**

1. **Setup & Installation**  
* Clone repository:    
* Ensure you have both \`main.py\` and \`requirements.txt\` in the same directory  
* pip install \-r requirements.txt  
    
2. **Run the project**  
* uvicorn main:app \--reload

3. **Access the application**  
* API endpoint: [http://localhost:8000](http://localhost:8000)   
* Interactive documentation: [http://localhost:8000/docs](http://localhost:8000/docs) (FastAPI Swagger UI)  
* Alternative documentation: [http://localhost:8000/redoc](http://localhost:8000/redoc) 

**API Reference**

**POST /process-payment**

**Required header**: Idempotency-Key: \<any unique string\>

| Scenario | Status | Body | Extra header |
| :---- | :---- | :---- | :---- |
| First request | **201**  | {"status":"success","message":"Charged 100.0 GHS"} |  |
| Duplicate (same key \+ same body) | **201** | {"status":"success","message":"Charged 100.0 GHS"} | X-Cache-Hit: true |
| In-flight duplicate | **201** | same as above (after wait) | X-Cache-Hit: true |
| Same key, different body | **422** | {"detail":"Idempotency key already used for a different request body."} |  |
| Missing key | **400** | {"detail":"Idempotency-Key header is required."} |  |
| Invalid currency | **422** | Validation error details |  |
| Amount \<= 0 | **422** | Validation error details |  |

