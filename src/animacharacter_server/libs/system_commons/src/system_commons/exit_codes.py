"""
Container module for all exit codes of processes. Each number is unique among all the processes of the system.  
A descriptive message of the cause can be acquired calling 'get_cause(exit_code)'.
"""

HWMNG_NO_CONFIG_FILES_SPECIFIED = 19
HWMNG_CONFIG_LOAD_FAILED = 20
HWMNG_NO_CONFIG_SPECIFIED = 21
HWMNG_UNKNOWN_CONFIG_SPECIFIED = 22
HWMNG_INVALID_CONFIG_FORMAT = 22

HWMNG_DATABUS_FIN_ERROR = 30
HWMNG_FAILED_TO_LOAD_CONTROLLERS = 31

# yet to implement
HWMNG_CONTROLLER_FATAL = 40 # when a controller raises a fatal error


# maps exit codes to human-readable descriptions
EXIT_CAUSES = {
    HWMNG_NO_CONFIG_FILES_SPECIFIED: "no hardware configuration files were specified",
    HWMNG_CONFIG_LOAD_FAILED: "the hardware configuration could not be loaded",
    HWMNG_NO_CONFIG_SPECIFIED: "no hardware configuration was selected",
    HWMNG_UNKNOWN_CONFIG_SPECIFIED: "the selected hardware configuration is unknown or invalid",
    HWMNG_DATABUS_FIN_ERROR: "the hardware manager databus failed during shutdown",
    HWMNG_FAILED_TO_LOAD_CONTROLLERS: "one or more hardware controllers failed to load",
    HWMNG_CONTROLLER_FATAL: "a hardware controller reported a fatal error",
}

def get_cause(exit_code: int) -> str:
    """Returns a human-readable description of the exit code."""
    return EXIT_CAUSES.get(exit_code, "unknown_exit_code")