# Animacharacter Platform

Animacharacter Platform è un framework per il controllo remoto di sistemi hardware composti da molti elementi controllabili.

L'obiettivo del progetto è fornire un'architettura standard per separare il software che genera i comandi dal software che interagisce con l'hardware reale.

Il caso d'uso principale è la robotica animatronica, dove una piattaforma può essere composta da decine di motori, LED, sensori e microcontrollori diversi. Tuttavia il framework può essere utilizzato in qualsiasi sistema in cui un singolo processo debba coordinare molti dispositivi distribuiti.

## Il problema

In una piattaforma reale, i vari dispositivi sono spesso collegati a hardware differenti e utilizzano protocolli differenti.

Ad esempio:

```text
Client
 ├─> Arduino (Seriale)
 ├─> Driver motori (SPI)
 ├─> Controller LED
 └─> ...
```

Con l'aumentare della complessità, il codice applicativo finisce per contenere dettagli specifici dell'hardware, rendendo difficile estendere o modificare il sistema.

## L'idea

Animacharacter Platform introduce un livello intermedio tra il software applicativo e l'hardware.

Il software applicativo descrive semplicemente lo stato desiderato della piattaforma; il framework si occupa di trasportare i comandi, instradarli e convertirli nelle operazioni necessarie per ciascun dispositivo.

```text
Applicazione
      ↓
Animacharacter Platform
      ↓
Hardware
```

Questo permette di modificare o sostituire l'hardware senza dover cambiare il software che lo controlla.

## Architettura

Il sistema è composto da due parti principali.

### Client

Il client è una libreria Python utilizzata dalle applicazioni.

Espone una rappresentazione gerarchica della piattaforma hardware e permette di modificarne lo stato tramite una API ad alto livello.

Esempio:

```python
robot.head.left_eye.pan.value = 10
robot.body.rotation.value = 30
```

L'applicazione non deve conoscere come questi valori verranno trasmessi o quali dispositivi fisici li eseguiranno.

### Engine

L'Engine è il processo che riceve i comandi dal client e li distribuisce ai componenti responsabili del controllo dell'hardware.

```text
Client
   ↓
Engine
   ↓
Hardware
```

L'Engine può essere eseguito su un mini computer a bordo della piattaforma, ad esempio un Raspberry Pi.

## Estensibilità

L'integrazione con l'hardware è realizzata tramite plugin Python caricati dinamicamente.

Ogni plugin definisce:

* quali elementi della piattaforma controlla;
* come comunicare con l'hardware associato;
* eventuali logiche di controllo o coordinazione.

Questo consente di integrare dispositivi differenti senza modificare il nucleo del framework.

## Tipi di comunicazione

Il framework distingue due categorie di dati.

### Comandi di controllo

Rappresentano lo stato o il movimento desiderato della piattaforma e vengono trasmessi in forma compatta e a bassa latenza.

### Dati di configurazione

Rappresentano parametri, impostazioni e informazioni strutturate che cambiano raramente e non richiedono trasmissione realtime.

La distinzione tra questi due flussi permette di trattare in modo diverso dati con requisiti temporali differenti.

## Obiettivi del progetto

* Fornire un modello uniforme per il controllo di sistemi hardware complessi.
* Separare la logica applicativa dai dettagli dell'hardware.
* Consentire l'integrazione di dispositivi eterogenei tramite plugin.
* Supportare piattaforme con molti elementi controllabili.
* Permettere la cooperazione tra sottosistemi mantenendo un'architettura modulare.

Per una descrizione dettagliata dell'architettura interna e dei componenti del framework, consultare la documentazione del progetto.
