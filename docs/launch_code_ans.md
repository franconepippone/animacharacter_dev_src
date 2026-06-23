Ecco la base del codice per i file di launch, strutturata secondo l'architettura **v2**. Ho applicato un approccio da "campo": niente fronzoli, focus sulla robustezza e sull'uso dei segnali nativi del sistema operativo tramite il launch system di ROS 2.

### 1. Helper Function: Notifica Eventi
Per evitare di ripetere codice, definiamo una funzione che genera l'azione di pubblicazione "one-shot" su `/system_events`.

```python
from launch.actions import ExecuteProcess

def notify_event(node_name, event_type, is_critical=False):
    # Formato: node_name, event_type (START/EXIT), exit_code (per ora 0), is_critical
    msg = f"{{node_name: '{node_name}', event_type: '{event_type}', exit_code: 0, is_critical: {str(is_critical).lower()}}}"
    return ExecuteProcess(
        cmd=['ros2', 'topic', 'pub', '--once', '/system_events', 'my_msgs/msg/SystemEvent', msg],
        shell=True
    )
```

### 2. `main.launch.py` (Il Direttore d'Orchestra)
Questo file è il punto di ingresso e contiene il "paracadute" per il Supervisor.

```python
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch_ros.actions import Node
from launch.launch_description_sources import PythonLaunchDescriptionSource
import os
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_path = get_package_share_directory('animacharacter_engine')
    
    # 1. Supervisor: Il nodo che decide lo stato
    supervisor_node = Node(
        package='animacharacter_engine',
        executable='supervisor_node',
        name='supervisor'
    )

    # 2. Watchdog Supervisor: Se il supervisor crasha, segnala e ferma tutto
    supervisor_die_handler = RegisterEventHandler(
        OnProcessExit(
            target_action=supervisor_node,
            on_exit=[
                # Pubblicazione diretta di emergenza
                ExecuteProcess(cmd=['ros2', 'topic', 'pub', '--once', '/system_status', 'std_msgs/msg/Int32', 'data: 99']),
                EmitEvent(event=Shutdown(reason='Supervisor Fatal Crash'))
            ]
        )
    )

    # 3. Inclusioni Gerarchiche
    core_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_path, 'launch', 'core.launch.py'))
    )
    
    monitor_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_path, 'launch', 'monitor.launch.py'))
    )

    return LaunchDescription([
        supervisor_node,
        supervisor_die_handler,
        core_launch,
        monitor_launch
    ])
```

### 3. `core.launch.py` (Sottosistema Critico)
Qui gestiamo i processi che, se falliscono, devono terminare l'intera sessione.

```python
from launch_ros.actions import Node
from launch.actions import RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit, OnProcessStart
from launch.events import Shutdown

def generate_launch_description():
    hw_manager = Node(
        package='animacharacter_engine',
        executable='hardware_manager_node',
        name='hardware_manager'
    )

    # Gestione crash CORE: Notifica e Shutdown Globale
    hw_die_handler = RegisterEventHandler(
        OnProcessExit(
            target_action=hw_manager,
            on_exit=[
                notify_event('hardware_manager', 'EXIT', is_critical=True),
                EmitEvent(event=Shutdown(reason='Core Hardware Failure'))
            ]
        )
    )

    # Notifica avvio al Supervisor
    hw_start_handler = RegisterEventHandler(
        OnProcessStart(
            target_action=hw_manager,
            on_start=[notify_event('hardware_manager', 'START', is_critical=True)]
        )
    )

    return LaunchDescription([
        hw_manager,
        hw_start_handler,
        hw_die_handler,
        # Include session_manager.launch.py qui...
    ])
```

### 4. `monitor.launch.py` (Sottosistema con Respawn)
Processi meno critici che possono essere riavviati dal launch system.

```python
from launch_ros.actions import Node

def generate_launch_description():
    # WebUI con respawn automatico
    web_ui = Node(
        package='animacharacter_monitor',
        executable='web_ui_node',
        respawn=True,
        respawn_delay=2.0
    )

    # Status Panel: Driver del pannello LED locale
    status_panel = Node(
        package='animacharacter_monitor',
        executable='status_panel_node',
        respawn=True
    )

    return LaunchDescription([
        web_ui,
        status_panel,
        # Aggiungi RegisterEventHandler per OnProcessExit se vuoi 
        # loggare i respawn sul Supervisor via /system_events
    ])
```

### Analisi Tecnica e Consigli per l'implementazione:

*   **Il paracadute (Fail-safe):** In `main.launch.py`, l'azione `OnProcessExit` sul Supervisor garantisce che se il "cervello" muore, lo Status Panel riceva il codice di errore 99 prima che il sistema si spenga. 
*   **Separazione Netta:** Nota che `core.launch.py` emette un evento di `Shutdown` globale in caso di crash. Questo è coerente con la tua specifica "crash del core arrestano l'intero sistema".
*   **Topic vs Heartbeat:** Il Supervisor ascolterà `/system_events`. Se un nodo del monitor crasha, il Supervisor vedrà l'evento `EXIT` ma non ordinerà lo shutdown, permettendo al launch system di fare il `respawn=True` in autonomia.
*   **Sezione Grigia - Discovery DDS:** Ricorda che `ros2 topic pub --once` deve avviare un nodo interno, fare il discovery e pubblicare. Questo può richiedere tempo (~0.5s). Se il sistema è estremamente instabile, il Supervisor potrebbe ricevere il messaggio con ritardo. Tuttavia, per uno status panel locale, questa è la soluzione più semplice ed efficace.

Questa struttura è pronta per essere integrata nel tuo pacchetto ROS 2. Assicurati di aggiornare il file `setup.py` (per Python) o `CMakeLists.txt` (per C++) per installare correttamente questi file nella cartella `share`.