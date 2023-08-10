Nimble Programming Hackathon

## Requirements

- Ubuntu 22.04+
- Python 3.10+
- numpy
- openCV
- aiortc

## Instructions

1. Extract the compressed file. The structure should look like this:

├─ client <br>
│   ├── client.py <br>
│   ├── test_client.py <br>
├─ server <br>
│   ├── server.py <br>
│   ├── test_server.py <br
├─ requirements.txt <br>
├─ requirements.test.txt <br>
├─ Dockerfile.client <br>
├─ Dockerfile.server <br>
├─ docker-compose.yml <br>
├─ server-deployment.yaml <br>
├─ client-deployment.yaml <br>
├─ ballaction.mov <br>
├─ README.md <br>

2. Navigate to the project directory and install the required dependencies.

```
pip install -r requirements.txt
```

It is a better practice to install OpenCV from source to run GUI applications. Link [here](https://docs.opencv.org/3.4/d2/de6/tutorial_py_setup_in_ubuntu.html)

3. To run the application, start the server using `cd server; python3 server.py`. This will start the server on localhost and default port 8080. Next start the client -> `cd client; python3 client.py`. The client will attempt to connect to the server using TCP connection and will start receiving the images of a bouncing ball across the screen.

4. To run the unit tests, there are additional dependencies that need to be installed using `pip install -r requirements.tests.txt`. The tests can be then be run on command line using `pytest -vv` from the root directory.

## Deployment

1. Docker - Build the images for client and server using
```
docker build -t myserver:latest -f Dockerfile.server .
docker build -t myclient:latest -f Dockerfile.client .
```
Once the Docker image is built, run it in a container using the following commands:
```
docker run --name myserver-container --network host myserver:latest
docker run --name myclient-container --network host myclient:latest
```

2. Kubernetes - Make sure you have a Kubernetes cluster set up and the kubectl command-line tool installed and configured to access your cluster. Deploy the Kubernetes resources by running the following commands:
```
minikube start
kubectl apply -f server-deployment.yaml
kubectl apply -f client-deployment.yaml
```
Verify that the resources have been created successfully by running the following command:
```
kubectl get deployments
```
