# Animacharacter Platform

**Animacharacter Platform** è un framework per il controllo remoto di sistemi hardware composti da molti assi di movimento o di stato, con particolare attenzione ad animatronics, robot modulari e piattaforme distribuite.
Il suo obiettivo è separare in modo netto:

* l’interfaccia remota usata dal client;
* la logica di instradamento dei comandi;
* l’integrazione con hardware eterogeneo;
* la possibilità di introdurre logiche di controllo custom, anche in retroazione.

Il sistema è progettato per essere:

* **estensibile**, tramite plugin;
* **modulare**, tramite una separazione netta tra client, engine e controller hardware;
* **portabile**, tramite distribuzione dell’Engine in container Docker;
* **adatto a sistemi distribuiti**, non solo ad animatronics ma anche a qualunque piattaforma con più attuatori, sensori o sottosistemi coordinati.

---

# Visione generale

Il progetto risolve un problema tipico dei sistemi hardware complessi: un client remoto deve poter inviare comandi a una piattaforma composta da molti attuatori, spesso gestiti da microcontrollori, driver o schede diverse, ciascuno con protocolli e vincoli propri.

Senza un livello intermedio, il software tende rapidamente a trasformarsi in una rete di adattatori specifici, conversioni di protocollo e logiche ad hoc.
Animacharacter Platform introduce invece un’architettura uniforme che standardizza:

1. **l’invio dei comandi** dal client;
2. **il trasporto** verso l’Engine;
3. **l’instradamento** verso i controller corretti;
4. **l’esecuzione finale** sull’hardware.

In questo modo il client lavora su un modello astratto e coerente, mentre l’implementazione concreta dell’hardware resta nascosta nei controller.

---

# Scopo del framework

Lo scopo del framework è fornire un livello intermedio tra il client e l’hardware che permetta di:

* controllare in modo uniforme assi eterogenei;
* mappare un comando logico su dispositivi fisici diversi;
* supportare sistemi con molti gradi di libertà;
* combinare controllo diretto, controllo mediato e controllo in retroazione;
* gestire sia comandi realtime sia configurazioni strutturate;
* mantenere il sistema estendibile senza modificare il nucleo dell’Engine.

In questa architettura, un “asse” non coincide necessariamente con un motore.
Un asse può rappresentare:

* una posizione lineare;
* un angolo;
* una rotazione;
* un LED;
* un valore di intensità;
* una velocità;
* una combinazione di più attuatori fisici;
* un parametro logico di controllo.

---

# Componenti principali

## 1. Animacharacter Client

Animacharacter Client è una libreria Python installabile e importabile in qualunque script Python.

Funzioni principali:

* costruire comandi verso la piattaforma;
* esporre un’API gerarchica e leggibile;
* nascondere al programmatore i dettagli dei motionframe e degli ID interni degli assi;
* generare motionframe a partire da una struttura logica ad albero;
* inviare sia comandi realtime sia pacchetti di configurazione.

Il client rappresenta la piattaforma hardware in modo astratto, simile a un filesystem o a un oggetto gerarchico navigabile tramite notazione dot.

---

## 2. Animacharacter Engine

Animacharacter Engine è il lato server del sistema.
È basato su **ROS2** ed è distribuito come immagine Docker, così da poter essere eseguito su hardware compatibile come:

* Raspberry Pi;
* Orange Pi;
* altri mini computer o schede con supporto Docker.

L’Engine fornisce:

* gestione delle sessioni;
* ricezione dei pacchetti dal client;
* instradamento verso i componenti interni;
* gestione dei controller hardware;
* supporto al databus interno;
* supporto ai pacchetti di configurazione.

L’Engine è il punto centrale di controllo che media tra client remoto e hardware fisico.

---

## 3. SessionManager

Il **SessionManager** gestisce la sessione con il client e il traffico di rete.

Responsabilità:

* autenticare il client;
* gestire la connessione;
* ricevere i pacchetti in ingresso;
* distinguere tra traffico di controllo e traffico di configurazione;
* inoltrare i dati ai componenti interni competenti.

Il SessionManager non espone la propria logica all’utente finale.

---

## 4. HardwareManager

L’**HardwareManager** è il componente che coordina i controller hardware.

Responsabilità:

* mantenere il pool dei controller disponibili;
* associare ogni controller a uno o più identificatori di asse;
* inoltrare i motion command ai controller corretti;
* distribuire i pacchetti config ai controller interessati;
* orchestrare il flusso interno tra controller e databus.

L’HardwareManager è il punto di smistamento tra il traffico ricevuto dall’Engine e i controller plugin.

---

## 5. HardwareController

Un **HardwareController** è una classe Python caricata dinamicamente dall’Engine come plugin.

Responsabilità:

* definire quali assi o quali percorsi di configurazione gestisce;
* ricevere i comandi pertinenti;
* tradurre i comandi in operazioni concrete sull’hardware;
* implementare eventuali logiche di compensazione o controllo locale;
* pubblicare o leggere dati sul databus condiviso.

Un controller può essere:

* un driver diretto verso un dispositivo fisico;
* un adattatore verso un microcontrollore esterno;
* un modulo di controllo logico che non parla direttamente con l’hardware;
* un componente di retroazione che legge dati da altri controller.

---

## 6. Databus

Il **databus** è un canale interno condiviso usato dai controller per scambiare dati.

Caratteristiche:

* accessibile in lettura e scrittura dai controller;
* utile per condividere stati osservati dall’hardware;
* utile per pubblicare setpoint intermedi;
* utile per implementare compensazioni tra sottosistemi;
* utile per costruire logiche di controllo distribuite.

Il databus consente interazione tra controller indipendenti senza accoppiarli direttamente.

---

# Modello di controllo

## Definizione di asse

Un asse è un’unità logica controllabile identificata da un ID univoco.

Nel sistema, un asse può rappresentare:

* un singolo attuatore;
* un canale di output;
* una variabile continua;
* un valore composito rappresentato in forma astratta;
* una combinazione di hardware controllata come singola entità logica.

Ogni asse è identificato da un **uint8**.

Questo implica una cardinalità massima teorica di 256 ID distinti per spazio di indirizzamento.
La scelta privilegia semplicità, compattezza e rapidità di processamento.

---

## Motion command

Un **motion command** è la coppia:

**(axis_id : setpoint)**

dove:

* `axis_id` è un identificatore uint8;
* `setpoint` è il valore desiderato per quell’asse;
* `setpoint` è rappresentato come `float`.

La scelta del tipo `float` permette di uniformare la gestione dei comandi e semplificare l’architettura interna.
Anche assi booleani o interi possono essere codificati in forma float e riconvertiti dal controller se necessario.

---

## Motionframe

Un **motionframe** è un pacchetto che contiene uno o più motion command.

Serve per trasmettere in modo compatto una configurazione di movimento o stato verso l’Engine.

### Struttura wire

```text
[ uint8 | float32 || uint8 | float32 || uint8 | float32 || ... ]
```

Ogni coppia rappresenta un motion command indipendente.

### Ruolo del motionframe

Il motionframe è il formato usato per:

* aggiornamenti rapidi;
* streaming di setpoint;
* controllo temporale frequente;
* invio di più assi in un unico pacchetto.

---

# Comunicazione Client <-> Engine

La comunicazione avviene tramite due socket distinti:

* **TCP** per trasmissioni affidabili e per traffico a bassa frequenza;
* **UDP** per lo streaming dei motionframe.

Questa separazione distingue chiaramente:

* dati critici per la continuità del controllo;
* dati meno sensibili alla latenza;
* aggiornamenti frequenti;
* configurazioni strutturate.

---

## TCP

Il canale TCP è usato per:

* autenticazione e session management;
* invio di messaggi affidabili;
* configurazioni;
* dati non realtime;
* comunicazioni che richiedono conferma di ricezione.

---

## UDP

Il canale UDP è usato per:

* streaming dei motionframe;
* aggiornamenti rapidi;
* pacchetti di movimento con bassa latenza.

UDP è adatto perché privilegia rapidità e continuità del flusso rispetto alla ritrasmissione affidabile.

---

# Percorso di un motionframe

Il flusso di un motionframe è il seguente:

```text
Client
→ UDP
→ SessionManager
→ HardwareManager
→ HardwareController
→ Hardware
```

### Fasi

1. Il client costruisce il motionframe.
2. Il motionframe viene inviato via UDP.
3. Il SessionManager riceve il pacchetto.
4. Il pacchetto viene inoltrato all’HardwareManager.
5. L’HardwareManager seleziona i controller interessati in base agli axis_id presenti.
6. Ogni HardwareController riceve i comandi rilevanti.
7. Il controller li traduce in azioni concrete sull’hardware.

---

# Architettura dei controller

## Assegnazione degli axis_id

Ogni HardwareController dichiara quali axis_id gestisce.
L’HardwareManager usa questa informazione per distribuire correttamente i motion command.

Questo permette di:

* dividere il carico tra più controller;
* associare controller diversi a hardware diversi;
* mantenere il sistema scalabile;
* isolare i dettagli implementativi del singolo sottosistema.

---

## Controller diretti

Un controller diretto si occupa di tradurre il comando in un’azione immediata sull’hardware.

Esempi:

* un controller che pilota un LED tramite GPIO;
* un controller che invia un comando seriale ad Arduino;
* un controller che parla con un driver su SPI.

---

## Controller di controllo logico

Non tutti i controller devono comandare direttamente hardware.

Alcuni controller possono:

* calcolare setpoint derivati;
* leggere dati dal databus;
* applicare leggi di compensazione;
* produrre segnali intermedi per altri controller.

In questo caso il controller agisce come un modulo di controllo e non come un driver hardware.

---

## Closed-loop e soft closed-loop

Il sistema supporta anche architetture in retroazione.

### Closed-loop

Un controller può leggere un valore osservato dall’hardware o da un altro controller, confrontarlo con il target e correggere il comando in uscita.

### Soft closed-loop

Quando la retroazione è gestita a frequenze moderate, il sistema realizza una forma di soft closed-loop.
Questo approccio è utile quando la logica di controllo è implementata in Python e non richiede hard realtime.

### Esempio concettuale

Un controller per la testa di un robot può leggere la rotazione del corpo dal databus e compensare automaticamente l’offset introdotto dal corpo stesso.

---

# Uso del databus tra controller

Il databus consente cooperazione tra controller che gestiscono parti diverse dello stesso sistema.

Esempio concettuale:

* il controller del corpo pubblica la rotazione effettiva;
* il controller della testa legge questo valore;
* il controller della testa sottrae tale offset dal proprio comando;
* il risultato è un comportamento coordinato.

Questo modello è utile quando più sottosistemi sono meccanicamente o logicamente dipendenti.

---

# Pacchetti di configurazione

Oltre ai motionframe, il sistema supporta **config packet**.

Un config packet è un pacchetto usato per trasferire dati strutturati a bassa criticità temporale, come:

* configurazioni degli attuatori;
* parametri di tuning;
* accelerazioni;
* profili di velocità;
* rampe;
* modalità operative;
* metadati aggiuntivi.

Il config packet non sostituisce il motionframe: lo completa.

---

## Config packet e JSON tree

Un config packet è una stringa JSON organizzata gerarchicamente.

L’Engine interpreta il JSON come un albero di topic.
Ogni topic corrisponde al percorso gerarchico delle chiavi nel JSON.

### Esempio di struttura

```json
{
  "head": {
    "eyes": {
      "left_eye_offset": 3.0,
      "right_eye_offset": 1.0
    }
  },
  "body": {
    "body_lean_accel": 100,
    "do_body_tilt": false
  }
}
```

Nel modello gerarchico:

* `head/eyes` identifica il sottoalbero relativo agli occhi della testa;
* `body` identifica il sottoalbero relativo al corpo.

---

## Routing dei config packet

Quando un config packet arriva all’Engine:

1. viene ricevuto dal SessionManager;
2. viene inoltrato all’HardwareManager;
3. l’HardwareManager confronta il JSON tree con le subscription attive;
4. ogni controller iscritto a un percorso specifico riceve il sottooggetto corrispondente.

Esempi di subscription:

* `head/eyes`
* `left_arm/motorA`
* `leds/left_eye`

Il callback del controller viene chiamato con il sottooggetto JSON associato al topic.

---

# Differenza tra motionframe e config packet

| Tipo          | Scopo                               | Frequenza | Struttura         |
| ------------- | ----------------------------------- | --------- | ----------------- |
| motionframe   | controllo rapido di assi e setpoint | alta      | binaria, compatta |
| config packet | configurazione e metadata           | bassa     | JSON gerarchico   |

Questa separazione evita di usare lo stesso meccanismo per problemi diversi.

---

# Lato client: Animadummy

Lato client, la piattaforma hardware viene rappresentata come una struttura gerarchica di oggetti chiamata **Animadummy**.

Animadummy modella la piattaforma come un albero formato da:

* **ActuatorGroups**: nodi interni, simili a directory;
* **Actuators**: foglie, corrispondenti agli elementi controllabili.

L’accesso avviene tramite notazione dot.

### Esempi

```python
head.left_eye.tilt.value = 3
body.rotation.value = 1.2
body.lean.value = 1
head.right_eye.led.r.value = 2
```

Questa interfaccia consente di:

* assegnare valori agli attuatori in modo intuitivo;
* costruire una configurazione completa dell’albero;
* generare il motionframe corrispondente;
* inviare solo aggiornamenti parziali quando necessario.

---

## Generazione del motionframe dal client

Sul nodo radice dell’albero è disponibile il metodo:

```python
.generate_motionframe()
```

Questo metodo:

1. legge lo stato corrente dell’Animadummy;
2. converte gli aggiornamenti nei relativi motion command;
3. costruisce il motionframe;
4. restituisce il pacchetto pronto per l’invio all’Engine.

È possibile generare motionframe anche da nodi non radice, per ottenere aggiornamenti parziali di sottogruppi dell’albero.

---

## Virtual JSON tree lato client

Ogni Animadummy mantiene anche un albero JSON virtuale interno, completamente configurabile.

Questo albero viene usato per:

* memorizzare parametri di configurazione;
* accumulare aggiornamenti strutturati;
* generare config packet;
* mantenere separati i dati di configurazione dai dati di movimento.

Sono disponibili helper method specifici per impostazioni di configurazione, ad esempio:

```python
body.rotation.set_acceleration(2.3)
```

---

# Sicurezza

Animacharacter Platform include un livello di sicurezza applicativo pensato per ambienti di rete non affidabili.

## Autenticazione tramite PSK

Per connettersi al server, il client deve possedere una **PSK** preconfigurata.
Senza chiave valida:

* la connessione non viene accettata;
* la sessione non può proseguire.

## Integrità dei pacchetti

I pacchetti sono protetti da meccanismi di integrità a livello applicativo sia per TCP sia per UDP.

Questo riduce il rischio di:

* alterazione dei messaggi;
* spoofing;
* replay non autorizzato.

La sicurezza non va intesa come garanzia assoluta in senso matematico, ma come strato aggiuntivo di protezione applicativa.

---

# Portabilità e distribuzione

L’Engine è distribuito come immagine Docker, così da poter essere eseguito facilmente su hardware compatibile.

Vantaggi:

* deployment semplice;
* isolamento dell’ambiente;
* portabilità tra macchine diverse;
* maggiore ripetibilità dell’installazione;
* facilità di integrazione in sistemi embedded o mini-PC.

---

# Casi d’uso

Il sistema non è limitato agli animatronics.

Può essere usato per:

* robot umanoidi;
* robot mobili con sottosistemi multipli;
* sistemi di luci coordinate;
* installazioni distribuite con molti attuatori;
* piattaforme ibride hardware/software con controllo centralizzato;
* qualunque sistema in cui un singolo master invia comandi a una piattaforma composta da più assi.

---

# Esempio concettuale di sistema animatronico

Un robot umanoide su ruote può avere:

* LED degli occhi;
* rotazione del corpo;
* movimento della testa;
* giunti delle braccia;
* altri elementi espressivi o funzionali.

In questo caso:

* il client lavora su una rappresentazione logica uniforme;
* l’Engine smista i comandi;
* ciascun controller traduce il comando nel linguaggio dell’hardware locale;
* il sistema rimane scalabile anche con hardware eterogeneo.

---

# Sintesi architetturale

```text
CLIENT
  ↓
Animacharacter Client
  ↓ UDP/TCP
SessionManager
  ↓
HardwareManager
  ↓
HardwareController plugin
  ↓
Hardware fisico
```

Per il controllo distribuito interno:

```text
HardwareController ↔ databus ↔ HardwareController
```

Per le configurazioni:

```text
Client → config packet JSON → Engine → controller subscribed to topic
```

---

# Principio di progetto

Il principio centrale del sistema è questo:

* il client deve poter esprimere intenzioni di controllo in modo semplice e gerarchico;
* l’Engine deve gestire il trasporto, il routing e l’instradamento;
* i controller devono isolare l’implementazione hardware;
* il databus deve permettere cooperazione e retroazione tra sottosistemi;
* il modello complessivo deve restare estendibile senza modificare il nucleo del framework.

In altre parole, Animacharacter Platform fornisce un’astrazione completa e configurabile per il controllo standardizzato di piattaforme hardware con molti gradi di libertà.
