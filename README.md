# Test task
## Framework: FastAPI

1. First, clone the repository:
```bash
git clone https://github.com/Dark16V/test-task.git
```
2. Navigate to the project directory.
```bash
cd ./test-task
```
3. Create a Docker Compose image
```bash
docker-compose build  
```
4. Run it
```bash
docker-compose up -d
```
5. Go to http://localhost:8000/ and log in with the test users:

full\_name='Dark', password=123456

or admin:

full\_name='admin', password=123456

6. You can view your profile (as a user), and as an admin, you can create, delete, and update users, as well as view their profiles. 

To test the webhook, go to [http://localhost:8000/docs#/default/payment\_webhook\_webhook\_payment\_post](http://localhost:8000/docs#/default/payment_webhook_webhook_payment_post) or open 
[http://localhost:8000/docs](http://localhost:8000/docs), scroll to the very end of the endpoints list, select the payment webhook, then send test data and check that the route works:

{

  "transaction_id": "5eae174f-7cd0-472c-bd36-35660f00132b",

  
  "account_id": 1,

  
  "user_id": 1,

  
  "amount": 100.0,

  
  "signature": "13d6d987bb6a41ac42804867afe96054c48bc4da84b7d05bf3e59f0585b4dbd7"
  
}

7. To stop docker, enter `docker-compose down` in the terminal:
```bash
docker-compose down
```



