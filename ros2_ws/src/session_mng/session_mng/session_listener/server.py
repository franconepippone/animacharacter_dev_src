from http import client
from fastapi import FastAPI, Request
from pydantic import BaseModel, ValidationError
import uvicorn

# main.py
from fastapi import FastAPI, HTTPException
from .ros_node import spin_threaded, get_node, SessionCreationHttpResponse, get_logger, RequestArguments

# TODO: Security improvements
# - Move SECRET_KEY and CLIENT_KEY to environment variables (e.g., os.getenv)
# - Implement JWT-based authentication using python-jose for token generation/validation
# - Sanitize logs to avoid exposing sensitive data (e.g., session tokens, addresses)
#
# TODO: Architecture and robustness
# - Use context manager for ROS2 node lifecycle in ros_node.py for proper init/shutdown
# - Add FastAPI middleware for rate limiting, CORS, and request validation
# - Implement health endpoints (e.g., /health) to monitor ROS2 service availability
# - Introduce circuit breakers or retries for ROS2 service calls
#
# TODO: Testing and deployment
# - Add unit tests for FastAPI routes and ROS2 interactions using pytest and ROS2 tools
# - Consider containerization (e.g., Docker) with security scans
#

### LOGGING CONFIGURATION

logger = get_logger("session_listener_server")


# FASTAPI APP 

app = FastAPI()

SECRET_KEY = "server-secret"
CLIENT_KEY = "supersecret-client-key"


# MODELS

class AuthRequest(BaseModel):
    apikey: str
    udp_port: int


@app.post("/auth")
def auth(req: AuthRequest, rqst: Request):
    # make this more robust, use hashes?
    if req.apikey != CLIENT_KEY:
        raise HTTPException(401, "Authentication failed: wrong key")
    
    if rqst.client is None:
        raise HTTPException(400, "Could not get client address")
    
    creation_request_args = RequestArguments(
        rqst.client.host,
        req.udp_port
    )
    
    logger.info("Got auth request with valid API key, sending internal session creation request.")
    sess_resp: SessionCreationHttpResponse = get_node().make_session_creation_request(creation_request_args)
    
    logger.debug(f"Session response from node is: {sess_resp}")

    # log outcome
    if sess_resp.success:
        logger.info(f"Session created successfully, sending session data to remote client.")
        logger.debug(f"Session data: {sess_resp}")
    else:
        logger.warning(f"Request to create a new session failed, sending failure response to remote client - Reason: {sess_resp.msg}")
        logger.debug(f"Session failure response data: {sess_resp}")

    # send response to client
    return sess_resp



def main():
    t = spin_threaded() # this launches the ros node in another thread
    uvicorn.run(
        "session_mng.session_listener.server:app",       # module:variable
        host="0.0.0.0",
        port=8000,
        reload=False      # reload=True breaks single-process ROS nodes
    )