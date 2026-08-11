# Sistema di alert

Il sistema di alert è il metodo in cui i nodi del sistema segnalano globalmente eventi di sistema di livello INFO, ERROR, WARNING e FATAL.
Il sistema di alert (oltre alle pubblicazioni automatiche su /process_events) è il pilota principale della FSM di stato. In altre parole,
le transizioni di stato vengono innescate principalmente proprio da alert di sistema.

## Cosa è un alert?

Un Alert può essere pensato come una 'flag' (spia) di sistema, con associati dei dati (e metadati), che può essere accesa (raise) e spenta (clear).
Un alert è composto da:
- **LEVEL** (INFO / WARNING / ERROR /FATAL):    livello di allerta
- **SOURCE** (str):     sorgente (entita causa) dell'alert. NB: l'entità che *solleva* l'alert e l'entità sorgente possono essere diverse!
- **CODE** (int):   codice (ID) di allarme, predefinito a priori. Identifica univocamente ogni tipo di alert.
- **TTL** (secs) [OPZIONALE]:   tempo di durata dell'alert. Un alert con ttl viene spento (*clear*) in automatico allo scadere del suo ttl. Un alert senza ttl 
rimane acceso fino a un *clear*.
- **SUBCODE** (int) [OPZIONALE]:     Se l'alert è innescato da un sotto-sistema (in genere user-defined, i.e. instanza di un hw-controller), il codice user-defined è incapsulato qui.
- **BRIEF** (str):  Descrizione breve (mostrata su display LCD 16x2)
- **DESCRIPTION** (str):    Descrizione accurata.

> NOTA: un alert INFO è un caso speciale di alert in cui il TTL è forzato a 0 (*one-shot*). Non ha senso parlare di *raise* e *clear* di un info. Esempio: eventi di connettività (session manager) come *connecting..* *disconnecting..* sono alert INFO. Eventi di *READYNESS*, sono alert di info (one-shot); es.: Nodo A è operativo -> raise un alert INFO.

## Come si usa il sistema?

Ogni nodo è provvisto di un oggetto condiviso* chiamato SystemAlerts. SystemAlerts espone la seguente interfaccia ad ogni nodo:

```python
.raise_alert(level: int, src: str, code: int, ttl: secs(float), subcode: int = -1, brief: str = '', desc: str = '')
.clear_alert(code: int)
.get_active_alerts()

# si può assegnare un callback per ogni nuovo evento
on_alert_change(action: RAISE/CLEAR, alert: Alert)   #<--- muove la FSM del supervisor

``` 

> *l'oggetto appare condiviso, ma internamente scambia messaggi tramite topic ros su /system_alarms. Il Server può essere hostato dal nodo supervisor, o da un altro nodo.

## Integrazione con launch

Il launch già provvede a monitorare lo stato a livello OS dei processi. Al giungere di eventi di processo come EXIT / CRASH, tramite la lettura del loro exit code, 
il supervisor sa cosa è storto: il supervisor solleva un Alert generico dove segnala l'avvenimento (in genere con TTL). Ad esempio, se crasha un processo secondario (i.e. WebUI), il supervisor riceve il crash e può decidere di sollevare un Alarm (con predefinito codice di errore), con TTL o - ancora meglio - fino a quando non riceve un process START o un READY.

Tuttavia, quando un processo *core* decide di fare un *"suicidio volontario"*, come previsto da *launch_architecture*, il sistema deve spegnersi completametne. Di norma, prima di un EXIT, il processo dovrebbe sempre cercare di sollevare un Alert, 
che, oltre a includere il codice di errore (stesso dell'uscita del processo), include anche tutti i metadati allegati.   

A questo punto il supervisor può decidere cosa fare:
- ha ricevuto sia Alert FATAL che /process_events crash: non solleva nessun altro alert, ma aggiorna la FSM e il /system_status
- ha ricevuto solo un /process_events crash: fabbrica un Alert FATAL generico, con lo specifico codice di errore. Aggiorna FSM e /system_status

> CASO EXTRA: supervisor riceve Alert FATAL ma non crash? C'è un problema, un Alert FATAL deve preannunciare sempre un *crash*. Il supervisor potrebbe
aspettare un ulteriore finestra di tempo, oppure, precauzionalmente, fare uno shutdown generale comunque.

## Visualizzazione su uno Status-Panel

Il nodo status panel è provvisto di un oggetto SystemAlerts, dunque monitora direttamente gli alert.
Può leggere metadati, codice di errore, livello, src, brief... Il compito è quello di mostrare piu fedelmente possibile 
gli alert (livello >= WRN). Una possibile formattazione su LCD potrebbe essere:

```
[LEVEL] [CODE]-[SUBCODE] [SRC]
[BRIEF]
```

Esempi:
```
FTL 4 HWMNG
Invalid config
```

```
WRN 22 SSMNG
1 Missed earthbeat
```

```
ERR 6-C2 HEAD
Overcurrent
```
^^^ 
codice univoco di sistema: 6 (errore generico di driver nell'hardware manager) 
C2: codice user-defined; specifico per il driver
src: HEAD (nome del driver, fonte del danno) IMPORTANTE!! codici user-defined dei driver potrebbero sovrapporsi
brief: Overcurrent (breve descrizione)


## Descrizione di flussi di propagazione di alert

### Generici alert di sistema

Qualsiasi componente del sistema che deve comunicare un alert seplicemente fa raise_alert con il codice specifico dell'allerta.

### Alert dei HW-Controller (user-defined)

Un hardare controller può sollevare delle eccezioni: Warning / Error / Fatal.

- Warning: hwmng solleva:
```
alert(
          level= WARNING, 
            src= NOME_CONTROLLER, 
           code= CODICE_DI_WRN_PER_CONTROLLER_GENERICO,
            ttl= FISSO o USER_DEFINED,
        subcode= CODICE_ECCEZIONE_DA_CONTROLLER,
          brief= DA_ECCEZIONE_CONTROLLER,
    description= DETTAGLIATA, MIX fra hwmng + controller
)
```
Anche in caso di spam, l'alert è acceso una sola volta e rimane acceso fino a quando l'ultimo ttl non scade. ANZI: il meccanismo funziona proprio così: il controller riemette periodicamente il warning fino a quando persiste il problema; il warning è rimosso automaticamente dal TTL.

- Error: hwmng solleva eccezione simile a prima^^^, il controller viene resettato. Al prossimo tentativo di *init* (fatto da reconciler), se il
controller continua a fallire, viene settato un altro alarm con code= CONTROLLER_INIT_FAILED e subcode relativo all'ecezione tirata in init. Questo alarm si spegne
solo quando l'init ha successo.

- Fatal: questo caso rientra in quanto dscritto in [Integrazione con launch](#integrazione-con-launch); viene pubblicato un alert Fatal che wrappa l'eccezione del controller; dopodichè HWMNG si suicida volontariamente. Supervisor mette insieme i pezzi e capisce cosa è successo.



## NOTA sui codici di errore

In generale **Codice di Alert** e **Codice di uscita dei processi** non andrebbero mischiati, in quanto appartengono a domini diversi. Tuttavia, fa comodo utilizzare lo stesso codice per per exit che seguono alert fatali, in modo che gli usufruitori di /process_events e SystemAlerts, non debbano continuamente rimappare i codici fra due domini diversi; es:
```python
# invece di..
if convert_to_alert_domain(exit_code) == alert.code: ... #sono lo stesso evento

# basta...
if exit_code == alert.code:
```

Si può sempre modificare questa cosa in futuro.
