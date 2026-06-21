# Animacharacter Platform: un framework flessibile per controllo remoto di animatronics e sistemi simili

Questo progetto nasce dalla necessità di controllare, da un client remoto, una piattaforma hardware con un alto numero di gradi di libertà o assi di movimento in modo rapido (supporto per streaming) e indipendente, e potenzialmente anche coordinato secondo leggi interne e customizzabili. Una piattaforma hardware animatronica possiede spesso decine di assi (motori, led, ...), che in genere sono controllati in gruppi da microcontrollori diversi e di vario tipo, potenzialmente sotto diversi standard o regole protocollari. Ciò significa che un collegamento diretto fra client -> attutatore sarebbe estremamente specifico e consisterebbe in una pila di tencologie e protocolli specifici solo per quello specifico attuatore. Ad esempio, supponiamo abbiamo un robot umanoide su ruote su cui si volgiono controllare due "assi": colore dei led degli occhi, e rotazione del corpo. Se si dovesse approcciare la programmazione di questo in modo non strutturato, si potrebbe magari riuscire a standardizzare il primo tratto di connessione CLIENT -> SERVER-entrypoint, ma l'instradamento del comando dal server all'attuatore/asse desiderato sarebbe un casino. Questo perché, il led degli occhi è controllato magari da un arduino connesso tramite seriale che parla il protocollo X, mentre il corpo è controllato da magari da un driver tramite SPI che usa un protocollo Y. Per decine e decine di attuatori, il codice si trasformerebbe in un conglomerato di if e addattatori fra un protocollo all'altro, rendendo il tutto un casino. 

Il nucleo di questo software è proprio questo: risolvere il problema dell'instradamento end-to-end di un comando di movimento di un asse, gestendo tutta l'infrastruttura "boilerplate" e lasciando all'utente un sistema facilmente estensibile tramite un sistema di plugin che permette di controllare in modo semplice (diretto, CLIENT->ACTUATOR) o piu complesso (CLIENT->CONTROLLER->ACTUATOR--closed-loop-->CONTROLLER) ammettendo anche sistemi di "soft" closed loop (closed loop a basse frequenze, 100Hz, 200Hz al massimo per hardware performanti, perche il codice è scritto in python che non è la cosa migliore)  

E' da notare che l'alta estensibilità e personalizzabilità di questo software lo rende adatto non solo al controllo di un "animatronic" o singolo robot, ma anche al controllo coordinato di sistemi altamente distribuiti (hardware e software); ad esempio, un insieme di luci di natale che decorano una casa e che richiedono un controllo sincronizzato. Insomma tutto ciò che vuole una relazione del tipo:
MASTER_SINGOLO -> comandi -> PIATTAFORMA CON DECINE DI ASSI REAGISCE

Inoltre nel contesto della robotica animatronica, un asse può essere un motore, ma può come abbiamo visto anche rappresentare un LED o magari un moto combinato di motori (ad esempio per giunti 2dof differenziali, asse A: motori girano nello stesso senso, asse B: motori girano in senso opposto).

Questo software non fa solo questo, ma cura anche il lato sicurezza. Un client per connettersi a un server deve possedere una PSK (chiave di sicurezza, o password pre impostata); la comunicazione non può avvenire e non può continuare per un client senza chiave, i pacchetti sono protetti da integrità a alivello applicativo sia per TCP che per UDP, il che rende impossibile lo spoofing o il replay. Questo garantisce uno strato aggiuntivo di sicurezza qualora il sistema dovesse operare in reti non sicure.

### Divisone generale

Il client (animacharacter client) è una libreria python, può essere installata e importata in qualsiasi script python e espone un API (personalizzabile) per controllare ogni asse della piattaforma hardware

Il "server", o in modo piu proprio Animacharacter Engine, è un sistema basato su ros2, rilasciato sotto forma di un immagine docker eseguibile facilmente su raspberry pi, orange pi o su qualiasi scheda che supporti docker. Questo rende l'Engine altamente portatile e plug-and-play, tuttavia a bordo dell'animatronic è richiesto un mini computer che possa girarlo. 

## Come programmo il mio animatronic?

Il sistema di plugin è il cuore che permette la massima estensibilità per qualsiasi use-case.
Prima occorre però parlare del protocollo con cui parlano CLIENT -> ENGINE.

### comunicazione Client <-> Engine

la comunicazione avviene attraverso 2 socket:
- uno TCP (trasmissioni a bassa latenza, alto contenuto)
- uno UDP (streaming di pacchetti di movimento)

Il socket UDP è quello utilizzato per la trasmissione dei comandi di movimento. In particolare, introduciamo il concetto di **motionframe**: un motionframe è il formato di pacchetto che viaggia su rete fra il client e il server. Consiste in un contenitore di comandi, o **motion command**. Ogni motion command non è altro che una coppia key:value (asse:setpoint). la key (id) è un ID (uint8) che rappresenta in modo univoco in tutta la piattaforma un determinato asse controllabile. value (setpoint) è il valore di movimento che si desidera assegnare a quell'asse. In base alla natura dell'asse, questo potrebbe essere una posizione lineare (m), un angolo (deg), un intensità luminosa (rgb), una velocità angolare (rpm) e tanti altri ancora. Il value è un **float**. Questo è un buon compromesso, in quanto la maggior parte delle assi sono continue, e qualora si dovessero avere assi booleane o intere è facile codificare il valore in un float (round(float) -> int, float > 0 -> bool), a discapito di qualche byte di memoria in più. A seguito di varie valutazioni, si è deciso di fissare il formato a float e di non rendere modificabile il tipo di dato; questo semplifica notevolmente l'architettura interna e comunnque non c'è perdita di flessibilità; come già detto, l'unico lato negativo è l'utilizzo maggiore di memoria e di dati trasmessi, ma nella maggior parte dei casi, non sarà mai un problema per l'hardware di oggi. 

#### Struttura motionframe su wire:

[ uint8 | float32 || uint8 | float32 || uint8 | float32 || ...] # (axis:setpoint, axis:setpoint, axis:setpoint, ...)

### Il percorso di un motionframe
Un motionframe è costruito dal client e inviato al server tramite UDP. La componente dell'engine che gestisce le sessioni con l'utente e il traffico è chiamata **SessionManager**, il suo funzionamento non è esposto all'utente. Il SessionManager riceve i pacchetti e li inoltra (tramite topic ros) al componente che si occupa dello smistamento e del controllo dell'hardware: **HardwareManager**.

Un hardware manager è l'unita responsabile di gesitre un pool di HardwareController; ogni hardware controller è implementato dall'utente (plugin) e si occupa di gestire una sottoporzione del sistema. Ogni controller si "iscrive" a un set di axis_id; durante il loop di controllo, se il client a inviato un motionframe che contiene motion command relativi a quell'asse, il controller viene notificato e può implementare la propria logica custom per eseguire quei comandi. 

Per un led connesso direttamente al raspberry pi un controller può semplicemente usare un API per i GPIO per accenderlo, o magari un controller può gestire un intero ramo di assi che sono controllate da un arduino, e inoltrare (esempio, con seriale) il comando ricevuto da CLIENT a arduino. 

### Hardware COntrollers plugins
Questo è il cuore dell'architettura dell'animacharacter Engine. I controller sono classi scritte in python, che vengono caricate dinamicamente tipo plugin dall'engine al suo avvio. I controller definiscono esattamente quali axis_id sono in uso e come inoltrare i rispettivi comandi alla piattaforma hardware. Quersto lascia un enorme flessibilità all'utente per il controllo di qualsiasi tipo di hardware. Essi sono la colla che unisce Client -> Engine -> *HW Controller* -> Hardware, completando il percorso. 

Un hardware controller è molto di più tuttavia; ogni controller gira parallalamente a una frequenza di loop determinata. TUtti i controller hanno a disposizione un databus condiviso, su cui ogniuno può scrivere/leggere. QUesto abilita al closed-loop inter-controller; esempio: 
Il mio robot ha una testa animatronica e un corpo animatronico; entrambi sono gestiti da controller diversi, perche sono connessi rispettivamente a un ardujno Uno e a un arduino nano. Poiche la testa è attaccata al corpo, la rotazione della testa orizoontale effettiva è rotazionetesta+rotazione corpo. Supponiamo di voler disaccoppiare queste assi: di fatto, è necessario rimuovere al controlo della testa la rotazionecorpo, in modo da compensare per l'offset introdotto da questultima. Tramite il databus, il controler per corpo può pubblicare in continuazione la sua rotazione (letta da hardware), e il controller per la testa può leggere in continuazione questo dato all'interno del suo control loop, sottraendolo al comando e quindi creando di fatto una compensazione a "ciclo-chiuso" (non esattamente, ma il concetto è lo stesso).

Inoltre, si potrebbero avere controller che non controllano nessun hardware, e fungono solo da veri e propri algoritmi di controllo per altri controller (che invece fungono da driver hardware). Ad esempio: controller A e controller B sono "driver" (interfacciano l'hardware); invece che iscriversi a axis_id, leggono dei valori di controllo sul databus.
COntroller C invece ascolta gli axis_id, esegue la legge di controllo e poi pubblica i valori di setpoint sul databus, che A e B leggono. Possono essereci anche ulteriori loop interni di informazioni fra A/B e C sempre tramite databus. 


                                                       +---> controller A ---> databus
remote CLIENT --> controller C (control law) --- databus ----> controller B 
        databus ----^

### Solo stremaing di motionframe?
Avere un canale di comunicazione dedicato allo streaming di motionframe è sicuramente necessario, ma da solo diventa limitante, in quando messaggi con meno criticità temporali e potenzialmente strutture più complesse o personalizzate diventano impossibili da invaire. Ad esempio, c'è una differenza fra un informazione di "setpoint" (trasmissione rapida, dimensione piccola) e una informazione di configurazione (settaggi di multiple variabili come accelerazione, profili di velocità, rampe, modalità e altri metadati; bassa criticità temporale). Per qeusta ragione, il sistema permette l'invio di pacchetti "config". Un pacchetto config è inviato qualora sia richiesta la trasmissione di un informazione più complessa in modo strutturato, come, apputno, per configurazione degli attutatori (ma non solo). 

#### Config e JSON tree
Un pacchetto config non è altro che una stringa JSON, che in modo gerarchico si preoccupa di tramsettere tutto il necessario all'engine. In particolare, il json è trattato come una gerarchia di "topic". Banamlemnte, un topic non è altro che una concatenazione di "key" dei campi json, che in modo univoco identificano un elemento di json all'interno della stringa.

Ad esempio, il file json:
{
    "head" : {
        "eyes": {
            left_eye_offset: 3.0,
            right_eye_offset: 1.0
        }
    },
    "body" : {
        body_lean_accell: 100,
        do_body_tilt: false
    }
}

Il percorso "head/eyes" si riferisce all'oggeto che si ottiene traversando il file con le chiavi "head" e poi "eyes", in questo caso:
{
left_eye_offset: 3.0,
right_eye_offset: 1.0
}

è il risultato. Allo stesso modo, "body/" da {
        body_lean_accell: 100,
        do_body_tilt: false
    }

E' evidente come in questo modo molteplici informazioni possano essere trasmesse in modo gerarchico e strutturato. QUando un "config packet" raggiunge l'Engine, esso viene inoltrato all'HardwareManager. COsi come per i motion_ids, ogni controller può "iscriversi" a un dato percorso nel json tree, come "head/eyes" oppure "left_arm/motorA", oppure "leds/left_eye". Qualora nel json tree del config packet esista questo discorso, l'oggetto contenuto viene inoltrato al rispettivo controller iscritto a quel percorso, e il callback assegnato viene chiamato con quell'oggetto come argomento. Questo permette ai controller di reagire in modo custom alla ricezioni di pacchetti config, che possono indicare sia configurazioni, sia magari eventi di on/off a che richiedono ulteriore metadata all'invio.



## Client side

A livello client, la libreria python rende il controllo di una piattaforma hardare estremamente semplice e intuitiva. L'intera piattaforma hardware è rappresentata da una struttura gerarchica di oggetti, simile a un file system, formata da AcutatorGroups (directories) e Actuators (foglie). Un oggetto del tipo si chiama Animadummy, (da anima= animatronic, e dummy=manichino posizionabile). Questo permette l'organizzazione gerarchica degli attuatori, che diventano accessibili attraverso notazione dot, es.: head.left_eye.tilt.value = 3, body.rotation.value = 1.2, body.lean.value = 1, head.right_eye.led.r.value = 2. l'untente può impostare i valori per "impostare" il manichino, dopodiche sull'ActuatorGroup radice può essere chiamati il metodo .generate_motionframe() per generae il motionframe corrispondente alla configurazione corrente. Il motionframe generato viene inviato all'engine dal Client. Questo significa che il funzoinamneto interno del motionframe e degli ID attuatore rimane nascosto all'utente e viene tutto gestito dagli animadummy. E inoltre possibile chiamare il meotodo .gen_motionframe su nodi non radice dell'albero, di attuatori, permettendo di fare update solo parziali di sottogruppi gerarchici di attuatori. Sempre dagli attuatori, si possono implementare degli helper method per settare configurazioni es.: body.rotation.set_acceleration(2.3). Questi metodi scrivono su un albero json virtuale interno all'animadummy e completamente configurabile, che può essere utilizzato per fare un "render" del json corrispondente a tutti gli aggiornamenti e creare un config packet. Il config packet può essere può spedito all'engine.

Questo crea astrazione completa e completamente configurabile sulla piattaforma robotica, fornendo all'utente un API chiara e pytonica per controllare una piattaforma hardare con numerosi gradi di libertà in modo standardizzato e seamless. 