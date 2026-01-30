from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError
import uvicorn
import logging

# main.py
from fastapi import FastAPI
from .ros_node import spin_threaded, get_node, SessionCreationHttpResponse

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

class AuthRequest(BaseModel):
    apikey: str


@app.post("/auth")
def auth(req: AuthRequest):
    # make this more robust, use hashes?
    if req.apikey != CLIENT_KEY:
        return SessionCreationHttpResponse(success=False, msg="Wrong API key")

    logger.info("Got valid auth request, attempting session creation")
    sess_resp: SessionCreationHttpResponse = get_node().make_session_creation_request()
    
    logger.info(f"Session response from node is: {sess_resp}")

    if sess_resp.success:
        logging.info("Session created successfully, sending session data to client: %s", sess_resp)
    else:
        logger.warning("Request to create a new session failed: %s", sess_resp)

    # send response to client
    return sess_resp



def main():
    t = spin_threaded() # this launches the ros node in another thread
    uvicorn.run(
        "fastapi_authenticator.auth_server:app",       # module:variable
        host="0.0.0.0",
        port=8000,
        reload=False      # reload=True breaks single-process ROS nodes
    )