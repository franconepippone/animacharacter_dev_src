Ecco la sintesi dell'architettura finalizzata. Siamo passati da un sistema puramente "notification-driven" (eventi volatili) a un sistema "state-driven" con memoria, dove il Supervisor agisce come l'unica sorgente di verità per lo stato del robot.
1. Interfaccia SystemAlerts (High-Level API)
Ogni nodo (Core o Plugin) interagisce con il sistema di diagnostica tramite un'astrazione a "flag" che nasconde il trasporto ROS 2.
raise_alert(level, code, subcode, brief, TTL, ...): Alza o rinfresca una flag di errore. Chiamate multiple con lo stesso code non duplicano l'allerta ma aggiornano il timestamp/TTL (meccanismo Keep-Alive).
clear_alert(code): Rimuove esplicitamente una flag precedentemente alzata.
get_active_alerts(): Restituisce l'istantanea del registro attivo.
2. Struttura Dati dell'Alert
Abbiamo rimosso il campo domain per semplicità, adottando un Flat Global Namespace basato su range numerici (es. 0-99 Core, 100-999 HWMNG, etc. [Turn 38]).
Campo
Tipo
Descrizione
source
string
Nome del nodo/istanza che ha generato l'allerta (es. head_ctrl).
level
int
INFO, WARN, ERR, FATAL.
code
int
Major Code. Identificativo univoco globale per la logica del Supervisor.
subcode
string
Minor Code. Identificativo user-defined (es. "C2") per il tecnico umano.
brief
string
Descrizione breve per LCD 16x2.
TTL
int
Time-To-Live in ms. Se > 0, l'alert sparisce se non rinfrescato (auto-clear).
3. FSM di Sistema e Messaggio Status
Il Supervisor gestisce la macchina a stati globale e pubblica su /system_status (QoS: Transient Local) la fotografia del sistema [Turn 30, 32].
Stati della FSM:
BOOTING: Inizializzazione nodi e attesa segnali READY.
STANDBY: Sistema pronto, motori disarmati. Può essere Nominal o Degraded.
ACTIVE: Sessione operativa in corso. Può essere Nominal o Degraded.
FAULT: Stato di emergenza. Arresto hardware e blocco comandi.
SHUTTING_DOWN: Chiusura coordinata dei processi.
Struttura dati SystemStatus:
state_id: (string) Lo stato corrente della FSM.
is_degraded: (bool) Flag che indica la presenza di WARN o ERR non bloccanti.
fault_ref: (Alert Object) Se lo stato è FAULT, contiene l'alert che ha scatenato il blocco (identità del "killer").
4. Logica del Supervisor
Il Supervisor è un gestore di registro. Mantiene una mappa in memoria degli alert attivi { (source, code) : AlertData }.
Aggregazione: Quando riceve un alert, lo inserisce nel registro. Se è un LEVEL_INFO, lo tratta come "one-shot" (non lo registra, lo notifica e basta [Turn 39]).
Arbitraggio: Se entra un ERR da un componente del Core o un FATAL da chiunque, la FSM transita istantaneamente in FAULT.
Garanzia di Stato: Il Supervisor ricalcola is_degraded a ogni modifica del registro. Se il registro si svuota, il sistema torna Nominal.
5. Esempi di Flusso di Propagazione
A. User-defined (Non-fatale: es. USB scollegata)
Plugin Driver: Rileva il distacco e chiama raise_alert(WARN, code=104, subcode="C2", TTL=5s).
HWMNG: (Se il driver crasha) L'HWMNG cattura l'eccezione e ri-emette l'alert per procura [Turn 33].
Supervisor: Inserisce nel registro. Vede LEVEL_WARN -> Imposta is_degraded = True.
Status Panel: Mostra STB (D) e alterna sulla seconda riga 104-C2: USB LOST.
Risoluzione: Il driver viene ricollegato, il TTL scade o viene inviato un clear_alert. Il Supervisor pulisce il registro e torna Nominal.
B. Fatal User-defined (Errore critico rilevato dal nodo)
Nodo: Rileva surriscaldamento critico, chiama raise_alert(FATAL, code=500, ...).
Supervisor: Riceve FATAL. Porta la FSM in FAULT e popola fault_ref con l'alert 500.
Launch System: (Opzionale) Se il nodo si chiude dopo l'alert, il launch rileva l'uscita, ma il Supervisor ha già il colpevole nel registro.
C. Crash di Processo (Segfault o Kill improvviso)
OS/Kernel: Uccide il processo D1.
Launch System: Rileva l'uscita tramite OnProcessExit e pubblica l'evento con exit_code=139 [Turn 36, 40].
Supervisor: Riceve la notifica di uscita. Poiché D1 non ha inviato un alert FATAL prima di morire, il Supervisor fabbrica un alert sintetico: source="D1", level=FATAL, code=SYS_CRASH, subcode="139" [Turn 40].
Status: Il sistema entra in FAULT e il display mostra ERR 101-139 D1 (dove 101 è il Major Code del crash di processo).
Questa architettura garantisce che l'operatore sappia sempre chi ha causato il problema, anche se il colpevole è morto prima di poter parlare [120, Turn 36, 40].