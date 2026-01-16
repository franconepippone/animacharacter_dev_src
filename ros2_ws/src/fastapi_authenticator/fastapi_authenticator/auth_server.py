from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError
import uvicorn
import logging
import requests

# main.py
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from .ros_node import spin_threaded, get_node


### LOGGING CONFIGURATION

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # minimum level to handle

# Create a console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)  # minimum level to emit

# Optional: formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)

# Add the handler to your logger
logger.addHandler(ch)



# FASTAPI APP 

app = FastAPI()

SECRET_KEY = "server-secret"
CLIENT_KEY = "supersecret-client-key"


# MODELS

class SessionCreationResponse(BaseModel):
    outcome: bool
    nng_address: str = ""
    udp_address: str = ""
    token: str = ""

class AuthRequest(BaseModel):
    key: str


@app.post("/auth")
def auth(req: AuthRequest):
    # make this more robus, use hashes?
    if req.key != CLIENT_KEY:
        raise HTTPException(401, "Invalid key")

    logger.info("Got valid auth request, attempting session creation")
    sess_resp = get_node().make_session_creation_request()
    logger.info(f"Session response from node is: {sess_resp}")

    http_response = SessionCreationResponse(
        outcome=sess_resp.success,
        nng_address=sess_resp.nng_address,
        udp_address=sess_resp.udp_address,
        token=sess_resp.token
    )

    if sess_resp.success:
        logging.info("Session created successfully, sending session data to client")
    else:
        logger.warning("Request to create a new session failed")

    # send response to client
    return http_response



def main():
    t = spin_threaded() # this launches the ros node in another thread
    uvicorn.run(
        "fastapi_authenticator.auth_server:app",       # module:variable
        host="0.0.0.0",
        port=8000,
        reload=False      # reload=True breaks single-process ROS nodes
    )