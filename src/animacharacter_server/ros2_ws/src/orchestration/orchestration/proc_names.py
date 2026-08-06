
# those are the unique string ids that identify processes in a /process_event message
# they are contained here since they are shared between launch files and supervisor_node.py

# domains for names
DOMAIN_CORE = 'core'
DOMAIN_MONITOR = 'monitor'

HARDWARE_MANAGER = f'{DOMAIN_CORE}:hardware_manager'
SESSION_MANAGER = f'{DOMAIN_CORE}:session_manager'
SESSION_CONNECTION_SERVER = f'{DOMAIN_CORE}:session_connection_server'


def get_domain_from_proc_name(name: str) -> str | None:
    words = name.split(':')
    if len(words) == 2:
        return words[0]
    

### NOTE: right now we are *experimentally* encoding the process "domain" inside its name. This way nodes (mainly, the supervisor node) receiving /process_events can 
# have logic that reacts to entire domains without checking for every single process name. Ideally, we should add a "domain" fields to the SystemEvents interface,
# but this can work fine if it remains this simple.